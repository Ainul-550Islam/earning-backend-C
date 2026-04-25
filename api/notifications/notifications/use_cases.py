# earning_backend/api/notifications/use_cases.py
"""
Use Cases — Application use cases for the notification system.

Each use case encapsulates a single user-facing action:
  - SendNotification
  - MarkNotificationRead
  - BulkSendNotification
  - RegisterPushDevice
  - OptOutChannel
  - CreateCampaign
  - StartCampaign
  - EnrollUserInJourney
  - MarkAllNotificationsRead
  - DeleteNotification
  - UpdatePreferences
  - GenerateAnalyticsReport

Use cases call selectors (read) and repositories (write).
They never import from views.py or serializers.py.

Pattern inspired by: Django-Styleguide + Clean Architecture
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class UseCaseResult:
    success: bool
    data: Any = None
    error: str = ''
    error_code: str = ''

    @classmethod
    def ok(cls, data=None):
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, error_code: str = 'ERROR'):
        return cls(success=False, error=error, error_code=error_code)


# ---------------------------------------------------------------------------
# Send Notification
# ---------------------------------------------------------------------------

class SendNotificationUseCase:
    """
    Send a single notification to a user.

    Orchestrates:
    1. Validate input
    2. Check fatigue
    3. Check opt-out
    4. Create notification record
    5. Dispatch to channel provider
    6. Record metrics
    """

    def execute(
        self,
        user,
        title: str,
        message: str,
        notification_type: str = 'announcement',
        channel: str = 'in_app',
        priority: str = 'medium',
        action_url: str = '',
        metadata: Dict = None,
        scheduled_at=None,
        template_id: int = None,
        bypass_fatigue: bool = False,
        bypass_opt_out: bool = False,
    ) -> UseCaseResult:
        try:
            from api.notifications.validator import validate_notification_payload
            from api.notifications.services.NotificationService import notification_service
            from api.notifications.services.FatigueService import fatigue_service
            from api.notifications.services.OptOutService import opt_out_service
            from api.notifications.hooks import pipeline, StopPipeline
            from api.notifications.events import emit_notification_sent, emit_notification_failed

            # 1. Validate
            result = validate_notification_payload({
                'title': title, 'message': message,
                'channel': channel, 'priority': priority,
            })
            if not result.is_valid:
                return UseCaseResult.fail(str(result.errors), 'VALIDATION_ERROR')

            # 2. Check fatigue (bypass for critical/urgent)
            if not bypass_fatigue and priority not in ('critical', 'urgent'):
                if fatigue_service.is_fatigued(user, priority=priority):
                    return UseCaseResult.fail('User is notification-fatigued.', 'USER_FATIGUED')

            # 3. Check opt-out
            if not bypass_opt_out and priority not in ('critical',):
                if opt_out_service.is_opted_out(user, channel):
                    return UseCaseResult.fail(f'User opted out of {channel}.', 'USER_OPTED_OUT')

            # 4. Create notification
            notification = notification_service.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                channel=channel,
                priority=priority,
                action_url=action_url,
                metadata=metadata or {},
                template_id=template_id,
            )
            if not notification:
                return UseCaseResult.fail('Failed to create notification.', 'CREATE_FAILED')

            # 5. Schedule or send immediately
            if scheduled_at:
                from api.notifications.models.schedule import NotificationSchedule
                schedule = NotificationSchedule.objects.create(
                    notification=notification,
                    send_at=scheduled_at,
                    status='pending',
                )
                return UseCaseResult.ok({'notification_id': notification.pk, 'scheduled': True, 'schedule_id': schedule.pk})

            # 6. Run pre_send pipeline hooks
            notification, context = pipeline.run_safe('pre_send', notification, {})
            if context.get('pipeline_stopped'):
                return UseCaseResult.fail(context.get('stop_reason', 'Pipeline stopped'), 'PIPELINE_STOPPED')

            # 7. Dispatch
            send_result = notification_service.send_notification(notification)
            context['send_success'] = send_result
            pipeline.run_safe('post_send', notification, context)

            if send_result:
                fatigue_service.record_send(user)
                emit_notification_sent(notification, channel, {'success': True})

            return UseCaseResult.ok({
                'notification_id': notification.pk,
                'sent': send_result,
                'channel': channel,
            })

        except Exception as exc:
            logger.error(f'SendNotificationUseCase: {exc}')
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Mark Read
# ---------------------------------------------------------------------------

class MarkNotificationReadUseCase:
    """Mark one or all notifications as read for a user."""

    def execute(self, user, notification_id: int = None, mark_all: bool = False) -> UseCaseResult:
        try:
            from api.notifications.models import Notification
            from api.notifications.events import notification_read as notification_read_signal

            if mark_all:
                count = Notification.objects.filter(
                    user=user, is_read=False, is_deleted=False
                ).update(is_read=True, read_at=timezone.now(), updated_at=timezone.now())

                # Invalidate cache
                from api.notifications.helpers import invalidate_user_notification_cache
                invalidate_user_notification_cache(user.pk)

                return UseCaseResult.ok({'marked_count': count, 'all': True})

            if not notification_id:
                return UseCaseResult.fail('notification_id required.', 'MISSING_PARAM')

            notif = Notification.objects.filter(pk=notification_id, user=user, is_deleted=False).first()
            if not notif:
                return UseCaseResult.fail('Notification not found.', 'NOT_FOUND')

            if not notif.is_read:
                notif.is_read = True
                notif.read_at = timezone.now()
                notif.save(update_fields=['is_read', 'read_at', 'updated_at'])
                notification_read_signal.send(sender=notif.__class__, instance=notif, user=user)

            from api.notifications.helpers import invalidate_user_notification_cache
            invalidate_user_notification_cache(user.pk)

            return UseCaseResult.ok({'notification_id': notification_id, 'is_read': True})

        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Register Push Device
# ---------------------------------------------------------------------------

class RegisterPushDeviceUseCase:
    """Register or update a user's push notification device."""

    def execute(self, user, device_type: str, fcm_token: str = '',
                apns_token: str = '', web_push_subscription: dict = None,
                device_name: str = '', app_version: str = '') -> UseCaseResult:
        try:
            from api.notifications.validator import validate_device_registration
            from api.notifications.models import DeviceToken

            result = validate_device_registration({
                'device_type': device_type,
                'fcm_token': fcm_token,
                'apns_token': apns_token,
                'web_push_subscription': web_push_subscription,
            })
            if not result.is_valid:
                return UseCaseResult.fail(str(result.errors), 'VALIDATION_ERROR')

            # Deactivate duplicate tokens
            if fcm_token:
                DeviceToken.objects.filter(fcm_token=fcm_token).exclude(user=user).update(is_active=False)
            if apns_token:
                DeviceToken.objects.filter(apns_token=apns_token).exclude(user=user).update(is_active=False)

            # Get or create device
            device, created = DeviceToken.objects.get_or_create(
                user=user,
                device_type=device_type,
                defaults={
                    'fcm_token': fcm_token,
                    'apns_token': apns_token,
                    'web_push_subscription': web_push_subscription or {},
                    'device_name': device_name,
                    'app_version': app_version,
                    'is_active': True,
                    'push_enabled': True,
                    'last_active': timezone.now(),
                }
            )

            if not created:
                # Update existing device
                device.fcm_token = fcm_token or device.fcm_token
                device.apns_token = apns_token or device.apns_token
                device.web_push_subscription = web_push_subscription or device.web_push_subscription
                device.device_name = device_name or device.device_name
                device.app_version = app_version or device.app_version
                device.is_active = True
                device.last_active = timezone.now()
                device.save()

            return UseCaseResult.ok({'device_id': device.pk, 'created': created})

        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Opt Out
# ---------------------------------------------------------------------------

class OptOutChannelUseCase:
    """Opt a user out of a notification channel."""

    def execute(self, user, channel: str, reason: str = 'user_request',
                notes: str = '') -> UseCaseResult:
        try:
            from api.notifications.services.OptOutService import opt_out_service
            result = opt_out_service.opt_out(user, channel, reason=reason, notes=notes)
            if result.get('success'):
                from api.notifications.events import user_opted_out
                user_opted_out.send(sender=None, user=user, channel=channel, reason=reason)
            return UseCaseResult.ok(result) if result.get('success') else UseCaseResult.fail(result.get('error', ''))
        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Create Campaign
# ---------------------------------------------------------------------------

class CreateCampaignUseCase:
    """Create a new notification campaign."""

    def execute(self, created_by, name: str, template_id: int,
                segment_conditions: dict = None, send_at=None,
                description: str = '', context: dict = None) -> UseCaseResult:
        try:
            from api.notifications.validator import validate_campaign_payload
            from api.notifications.services.CampaignService import campaign_service

            result = validate_campaign_payload({'name': name, 'template_id': template_id, 'send_at': send_at})
            if not result.is_valid:
                return UseCaseResult.fail(str(result.errors), 'VALIDATION_ERROR')

            campaign = campaign_service.create_campaign(
                name=name,
                template_id=template_id,
                segment_conditions=segment_conditions or {},
                send_at=send_at,
                description=description,
                context=context or {},
                created_by=created_by,
            )

            if campaign and campaign.get('success'):
                return UseCaseResult.ok(campaign)
            return UseCaseResult.fail(campaign.get('error', 'Campaign creation failed'), 'CREATE_FAILED')

        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Bulk Send
# ---------------------------------------------------------------------------

class BulkSendNotificationUseCase:
    """Send a notification to multiple users (batch operation)."""

    def execute(self, user_ids: List[int], title: str, message: str,
                notification_type: str = 'announcement', channel: str = 'in_app',
                priority: str = 'medium', template_id: int = None,
                context: dict = None) -> UseCaseResult:
        try:
            from api.notifications.services.CampaignService import campaign_service
            from api.notifications.helpers import chunk_list

            if not user_ids:
                return UseCaseResult.fail('user_ids cannot be empty.', 'EMPTY_USERS')

            if len(user_ids) > 100_000:
                return UseCaseResult.fail('Maximum 100,000 users per bulk send.', 'TOO_MANY_USERS')

            # For small sends (<= 100), send inline
            if len(user_ids) <= 100:
                from django.contrib.auth import get_user_model
                from api.notifications.services.NotificationService import notification_service
                User = get_user_model()
                sent = 0
                failed = 0
                for user in User.objects.filter(pk__in=user_ids, is_active=True).iterator():
                    try:
                        notif = notification_service.create_notification(
                            user=user, title=title, message=message,
                            notification_type=notification_type,
                            channel=channel, priority=priority,
                        )
                        if notif and notification_service.send_notification(notif):
                            sent += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
                return UseCaseResult.ok({'sent': sent, 'failed': failed, 'total': len(user_ids)})

            # For large sends, use batch Celery task
            from api.notifications.tasks.batch_send_tasks import process_batch_task
            task = process_batch_task.delay(user_ids, title, message, notification_type, channel, priority, context or {})
            return UseCaseResult.ok({'task_id': task.id, 'total_users': len(user_ids), 'queued': True})

        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Enroll in Journey
# ---------------------------------------------------------------------------

class EnrollUserInJourneyUseCase:
    """Enroll a user in a multi-step notification journey."""

    def execute(self, user, journey_id: str, context: dict = None) -> UseCaseResult:
        try:
            from api.notifications.services.JourneyService import journey_service
            result = journey_service.enroll_user(user, journey_id, context)
            return UseCaseResult.ok(result) if result.get('success') else UseCaseResult.fail(result.get('error', ''), 'ENROLL_FAILED')
        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Update Preferences
# ---------------------------------------------------------------------------

class UpdatePreferencesUseCase:
    """Update a user's notification channel preferences."""

    def execute(self, user, preferences: dict) -> UseCaseResult:
        try:
            from api.notifications.models import NotificationPreference
            pref, _ = NotificationPreference.objects.get_or_create(user=user)
            allowed_fields = [
                'in_app_enabled', 'push_enabled', 'email_enabled',
                'sms_enabled', 'telegram_enabled', 'whatsapp_enabled',
                'browser_enabled', 'quiet_hours_enabled',
                'quiet_hours_start', 'quiet_hours_end',
                'notification_frequency', 'language',
            ]
            update_fields = []
            for field in allowed_fields:
                if field in preferences:
                    setattr(pref, field, preferences[field])
                    update_fields.append(field)

            if update_fields:
                update_fields.append('updated_at')
                pref.save(update_fields=update_fields)

            return UseCaseResult.ok({'updated_fields': update_fields})

        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')


# ---------------------------------------------------------------------------
# Delete Notification
# ---------------------------------------------------------------------------

class DeleteNotificationUseCase:
    """Soft-delete a notification."""

    def execute(self, user, notification_id: int, deleted_by=None) -> UseCaseResult:
        try:
            from api.notifications.models import Notification
            notif = Notification.objects.filter(pk=notification_id, user=user, is_deleted=False).first()
            if not notif:
                return UseCaseResult.fail('Notification not found.', 'NOT_FOUND')
            notif.is_deleted = True
            notif.deleted_at = timezone.now()
            notif.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

            from api.notifications.helpers import invalidate_user_notification_cache
            invalidate_user_notification_cache(user.pk)

            return UseCaseResult.ok({'notification_id': notification_id, 'deleted': True})
        except Exception as exc:
            return UseCaseResult.fail(str(exc), 'INTERNAL_ERROR')
