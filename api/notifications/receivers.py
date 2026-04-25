# earning_backend/api/notifications/receivers.py
"""
Receivers — Django signal receivers for the notification system.

This file contains the actual receiver functions that respond to
Django signals. All receivers are connected in apps.py ready().

Separation from signals.py:
  - signals.py     : defines custom Signal objects
  - receivers.py   : implements the handler functions
  - apps.py        : connects receivers to signals via .connect()
"""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_notify(user, notification_type: str, title: str,
                 message: str, channel: str = 'in_app',
                 priority: str = 'medium', **kwargs):
    """
    Safe notification trigger — never raises, logs on error.
    Used by all receivers to avoid breaking the originating signal.
    """
    try:
        from api.notifications.services.NotificationService import notification_service
        notif = notification_service.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            channel=channel,
            priority=priority,
            **kwargs,
        )
        if notif:
            notification_service.send_notification(notif)
    except Exception as exc:
        logger.warning(f'_safe_notify type={notification_type}: {exc}')


# ---------------------------------------------------------------------------
# User lifecycle receivers
# ---------------------------------------------------------------------------

def on_user_post_save(sender, instance, created, **kwargs):
    """
    Trigger welcome notification when a new user registers.
    Connected in apps.py: post_save.connect(on_user_post_save, sender=User)
    """
    if not created:
        return
    try:
        _safe_notify(
            user=instance,
            notification_type='announcement',
            title='স্বাগতম! Welcome to Earning Site 🎉',
            message=(
                'আপনার account সফলভাবে তৈরি হয়েছে। '
                'এখনই task শুরু করুন এবং আয় করুন!'
            ),
            channel='in_app',
            priority='medium',
        )

        # Enroll in onboarding journey
        try:
            from api.notifications.services.JourneyService import journey_service
            journey_service.enroll_user(
                user=instance,
                journey_id='onboarding',
                context={'username': instance.username},
            )
        except Exception as exc:
            logger.debug(f'on_user_post_save journey enroll: {exc}')

    except Exception as exc:
        logger.warning(f'on_user_post_save: {exc}')


def on_user_level_up(sender, instance, **kwargs):
    """
    Triggered when user's level field increases.
    Emit level_up notification.
    """
    try:
        new_level = getattr(instance, 'level', None)
        if new_level and new_level > 1:
            _safe_notify(
                user=getattr(instance, 'user', instance),
                notification_type='level_up',
                title=f'🚀 Level Up! Level {new_level}',
                message=f'অভিনন্দন! আপনি Level {new_level} এ উন্নীত হয়েছেন। নতুন সুবিধা unlock!',
                channel='in_app',
                priority='high',
                metadata={'new_level': new_level},
            )
    except Exception as exc:
        logger.warning(f'on_user_level_up: {exc}')


# ---------------------------------------------------------------------------
# Notification lifecycle receivers
# ---------------------------------------------------------------------------

def on_notification_post_save(sender, instance, created, **kwargs):
    """
    After a Notification is created:
      1. Broadcast to WebSocket (Django Channels)
      2. Update unread count for the user
    """
    if not created:
        return
    try:
        from api.notifications.consumers import send_notification_to_user, send_count_update_to_user
        # Broadcast new notification to WebSocket
        send_notification_to_user(instance.user_id, {
            'id': instance.pk,
            'title': instance.title,
            'message': instance.message,
            'notification_type': instance.notification_type,
            'channel': instance.channel,
            'priority': instance.priority,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        })
        # Update badge count
        from api.notifications.models import Notification
        unread = Notification.objects.filter(
            user_id=instance.user_id,
            is_read=False,
            is_deleted=False,
        ).count()
        send_count_update_to_user(instance.user_id, unread)
    except Exception as exc:
        logger.debug(f'on_notification_post_save WS broadcast: {exc}')


def on_notification_read(sender, instance, **kwargs):
    """
    When a notification is marked read:
      - Update cache
      - Broadcast count update via WebSocket
    """
    try:
        from django.core.cache import cache
        cache_key = f'notif:count:{instance.user_id}'
        cache.delete(cache_key)

        from api.notifications.consumers import send_count_update_to_user
        from api.notifications.models import Notification
        unread = Notification.objects.filter(
            user_id=instance.user_id, is_read=False, is_deleted=False
        ).count()
        send_count_update_to_user(instance.user_id, unread)
    except Exception as exc:
        logger.debug(f'on_notification_read: {exc}')


# ---------------------------------------------------------------------------
# InAppMessage receivers
# ---------------------------------------------------------------------------

def on_in_app_message_post_save(sender, instance, created, **kwargs):
    """
    Broadcast new in-app message via WebSocket when created.
    """
    if not created:
        return
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer:
            msg_data = {
                'id': instance.pk,
                'title': instance.title,
                'body': instance.body,
                'message_type': instance.message_type,
                'display_priority': instance.display_priority,
                'cta_url': instance.cta_url or '',
                'created_at': instance.created_at.isoformat() if instance.created_at else None,
            }
            async_to_sync(channel_layer.group_send)(
                f'notifications_{instance.user_id}',
                {'type': 'new_in_app_message', 'message': msg_data},
            )
    except ImportError:
        pass
    except Exception as exc:
        logger.debug(f'on_in_app_message_post_save: {exc}')


# ---------------------------------------------------------------------------
# OptOutTracking receivers
# ---------------------------------------------------------------------------

def on_opt_out_post_save(sender, instance, **kwargs):
    """
    When user opts out of a channel — update their NotificationPreference.
    """
    try:
        from api.notifications.models import NotificationPreference
        pref, _ = NotificationPreference.objects.get_or_create(user=instance.user)

        channel = instance.channel
        channels = (
            ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
            if channel == 'all' else [channel]
        )
        update_fields = []
        for ch in channels:
            field = f'{ch}_enabled'
            if hasattr(pref, field):
                setattr(pref, field, not instance.is_active)
                update_fields.append(field)

        if update_fields:
            pref.save(update_fields=update_fields)
    except Exception as exc:
        logger.debug(f'on_opt_out_post_save: {exc}')


# ---------------------------------------------------------------------------
# NotificationFatigue receivers
# ---------------------------------------------------------------------------

def on_fatigue_post_save(sender, instance, **kwargs):
    """
    Log when a user becomes fatigued — alert admin if extremely fatigued.
    """
    if not instance.is_fatigued:
        return
    logger.info(
        f'Fatigue: user #{instance.user_id} '
        f'sent_today={instance.sent_today} '
        f'sent_week={instance.sent_this_week}'
    )
    # If extreme fatigue (10x daily limit), alert admin
    daily_limit = getattr(instance, 'daily_limit', 10) or 10
    if instance.sent_today >= daily_limit * 5:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            for admin in User.objects.filter(is_staff=True, is_active=True)[:3]:
                _safe_notify(
                    user=admin,
                    notification_type='system_alert',
                    title='⚠️ Extreme Notification Fatigue',
                    message=(
                        f'User #{instance.user_id} received {instance.sent_today} '
                        f'notifications today (limit: {daily_limit}). Review immediately.'
                    ),
                    channel='in_app',
                    priority='urgent',
                )
        except Exception as exc:
            logger.warning(f'on_fatigue_post_save admin alert: {exc}')


# ---------------------------------------------------------------------------
# DeviceToken receivers
# ---------------------------------------------------------------------------

def on_device_token_post_save(sender, instance, created, **kwargs):
    """
    Alert user when a new device is registered — potential security event.
    """
    if not created:
        return
    try:
        user = instance.user
        from api.notifications.models import DeviceToken
        existing_count = DeviceToken.objects.filter(user=user, is_active=True).count()

        if existing_count > 1:
            device_name = (
                getattr(instance, 'device_name', '') or
                getattr(instance, 'device_model', '') or
                'Unknown Device'
            )
            _safe_notify(
                user=user,
                notification_type='login_new_device',
                title='🔐 New Device Registered',
                message=(
                    f'"{device_name}" থেকে আপনার account এ login হয়েছে। '
                    f'এটি আপনি না হলে এখনই password পরিবর্তন করুন।'
                ),
                channel='in_app',
                priority='high',
            )
    except Exception as exc:
        logger.warning(f'on_device_token_post_save: {exc}')


# ---------------------------------------------------------------------------
# Campaign receivers
# ---------------------------------------------------------------------------

def on_campaign_completed(sender, instance, **kwargs):
    """
    When a campaign finishes, notify the creator.
    """
    try:
        creator = getattr(instance, 'created_by', None)
        if not creator:
            return
        _safe_notify(
            user=creator,
            notification_type='announcement',
            title=f'Campaign Completed: {instance.name}',
            message=(
                f'Campaign "{instance.name}" completed. '
                f'Sent: {instance.sent_count} / {instance.total_count}'
            ),
            channel='in_app',
            priority='medium',
            metadata={
                'campaign_id': str(instance.pk),
                'sent_count': instance.sent_count,
                'total_count': instance.total_count,
            },
        )
    except Exception as exc:
        logger.warning(f'on_campaign_completed: {exc}')


# ---------------------------------------------------------------------------
# Integration system receivers
# ---------------------------------------------------------------------------

def on_integration_event(sender, event_type: str, data: dict,
                         user_id: int = None, **kwargs):
    """
    Receiver for the custom integration_event signal.
    Routes events from the EventBus to notification creation.
    """
    try:
        from api.notifications.integration_system.event_bus import event_bus
        event_bus.publish(
            event_type=event_type,
            data=data,
            user_id=user_id,
            source_module=kwargs.get('source_module', 'signal'),
        )
    except Exception as exc:
        logger.warning(f'on_integration_event: {exc}')


def on_integration_error(sender, integration: str, error: str,
                         user_id: int = None, **kwargs):
    """
    Log integration errors to the audit trail.
    """
    try:
        from api.notifications.integration_system.integ_audit_logs import audit_logger
        audit_logger.log(
            action='error',
            module=integration,
            actor_id=user_id,
            success=False,
            error=error,
        )
    except Exception as exc:
        logger.debug(f'on_integration_error: {exc}')
