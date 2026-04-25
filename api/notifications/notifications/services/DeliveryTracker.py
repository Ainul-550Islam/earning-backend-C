# earning_backend/api/notifications/services/DeliveryTracker.py
"""
DeliveryTracker — tracks and updates delivery receipts across all channels.

Responsibilities:
  - Process inbound delivery webhooks (SendGrid, Twilio, APNs feedback)
  - Poll FCM / APNs for delivery confirmations
  - Update Notification status (is_delivered, is_read, etc.)
  - Update channel-level delivery logs (PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog)
  - Update CampaignResult counters
  - Feed data to NotificationInsight for daily analytics
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class DeliveryTracker:
    """
    Central service for tracking delivery receipts and updating all
    related models when a notification is delivered, opened, or clicked.
    """

    # ------------------------------------------------------------------
    # Generic notification status updaters
    # ------------------------------------------------------------------

    def mark_delivered(self, notification_id: int, provider: str = '', save: bool = True) -> Dict:
        """
        Mark a Notification as delivered.

        Args:
            notification_id: Notification PK.
            provider:        Provider string for logging.
            save:            Whether to persist the update.

        Returns:
            Dict with: success, notification_id, error.
        """
        try:
            from notifications.models import Notification

            notification = Notification.objects.get(pk=notification_id)
            notification.mark_as_delivered(save=save)

            logger.debug(
                f'DeliveryTracker: notification #{notification_id} marked delivered '
                f'via {provider or "unknown"}'
            )
            return {'success': True, 'notification_id': notification_id, 'error': ''}

        except Exception as exc:
            logger.error(f'DeliveryTracker.mark_delivered #{notification_id}: {exc}')
            return {'success': False, 'notification_id': notification_id, 'error': str(exc)}

    def mark_read(self, notification_id: int) -> Dict:
        """Mark a Notification as read."""
        try:
            from notifications.models import Notification
            notification = Notification.objects.get(pk=notification_id)
            notification.mark_as_read()
            return {'success': True, 'notification_id': notification_id, 'error': ''}
        except Exception as exc:
            logger.error(f'DeliveryTracker.mark_read #{notification_id}: {exc}')
            return {'success': False, 'notification_id': notification_id, 'error': str(exc)}

    def mark_clicked(self, notification_id: int) -> Dict:
        """Record a click on a notification."""
        try:
            from notifications.models import Notification
            notification = Notification.objects.get(pk=notification_id)
            notification.increment_click_count()
            return {'success': True, 'notification_id': notification_id, 'error': ''}
        except Exception as exc:
            logger.error(f'DeliveryTracker.mark_clicked #{notification_id}: {exc}')
            return {'success': False, 'notification_id': notification_id, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Webhook processors
    # ------------------------------------------------------------------

    def process_sendgrid_event(self, event: Dict) -> Dict:
        """
        Process a SendGrid inbound webhook event.
        Delegates to SendGridProvider.process_webhook_event and then
        updates the parent Notification status.
        """
        try:
            from .providers.SendGridProvider import sendgrid_provider
            result = sendgrid_provider.process_webhook_event(event)
            if result.get('processed'):
                # Update parent Notification if we can find it via message_id
                self._sync_notification_from_email_log(result.get('message_id', ''))
            return result
        except Exception as exc:
            logger.error(f'DeliveryTracker.process_sendgrid_event: {exc}')
            return {'processed': False, 'error': str(exc)}

    def process_twilio_sms_event(self, data: Dict) -> Dict:
        """
        Process a Twilio SMS status callback webhook.
        Delegates to TwilioProvider.process_status_webhook and syncs
        the parent Notification.
        """
        try:
            from .providers.TwilioProvider import twilio_provider
            result = twilio_provider.process_status_webhook(data)
            if result.get('processed'):
                self._sync_notification_from_sms_log(result.get('sid', ''))
            return result
        except Exception as exc:
            logger.error(f'DeliveryTracker.process_twilio_sms_event: {exc}')
            return {'processed': False, 'error': str(exc)}

    def process_push_delivery_receipt(
        self,
        notification_id: int,
        device_id: int,
        status: str,
        provider_message_id: str = '',
        error_code: str = '',
        error_message: str = '',
    ) -> Dict:
        """
        Process a push delivery receipt (e.g. from FCM delivery receipt API).

        Args:
            notification_id:    Notification PK.
            device_id:          PushDevice PK.
            status:             'delivered' | 'failed' | 'invalid_token'.
            provider_message_id: Provider's message ID.
            error_code:         Error code (for failed).
            error_message:      Error message text.
        """
        try:
            from notifications.models.channel import PushDeliveryLog

            log = PushDeliveryLog.objects.filter(
                notification_id=notification_id,
                device_id=device_id,
            ).order_by('-created_at').first()

            if log:
                if status == 'delivered':
                    log.mark_delivered(provider_message_id=provider_message_id)
                elif status in ('failed', 'invalid_token'):
                    log.mark_failed(error_code=error_code, error_message=error_message)
                    if status == 'invalid_token':
                        self._deactivate_push_device(device_id)

            if status == 'delivered':
                self.mark_delivered(notification_id, provider='push_receipt')

            return {'success': True, 'notification_id': notification_id, 'error': ''}

        except Exception as exc:
            logger.error(f'DeliveryTracker.process_push_delivery_receipt: {exc}')
            return {'success': False, 'notification_id': notification_id, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Bulk polling / reconciliation
    # ------------------------------------------------------------------

    def reconcile_undelivered(self, hours_back: int = 24) -> Dict:
        """
        Scan notifications sent in the last N hours that are still not marked
        as delivered, and attempt to reconcile their status.

        For email: checks EmailDeliveryLog for delivered/bounced events.
        For SMS: checks SMSDeliveryLog for delivered/failed events.
        For push: checks PushDeliveryLog.

        Returns:
            Dict with: reconciled_count, still_undelivered_count, errors.
        """
        from django.db.models import Q
        from notifications.models import Notification

        cutoff = timezone.now() - timedelta(hours=hours_back)
        reconciled = 0
        still_undelivered = 0
        errors = 0

        undelivered_qs = Notification.objects.filter(
            is_sent=True,
            is_delivered=False,
            created_at__gte=cutoff,
            is_deleted=False,
        )

        for notification in undelivered_qs.iterator(chunk_size=200):
            try:
                was_reconciled = self._reconcile_single(notification)
                if was_reconciled:
                    reconciled += 1
                else:
                    still_undelivered += 1
            except Exception as exc:
                logger.warning(f'DeliveryTracker.reconcile_undelivered #{notification.id}: {exc}')
                errors += 1

        return {
            'reconciled_count': reconciled,
            'still_undelivered_count': still_undelivered,
            'errors': errors,
        }

    # ------------------------------------------------------------------
    # Campaign result updates
    # ------------------------------------------------------------------

    def update_campaign_results(self, campaign_id: int) -> Dict:
        """
        Recalculate and save CampaignResult for a campaign based on the
        actual delivery logs.
        """
        try:
            from notifications.models.campaign import NotificationCampaign, CampaignResult
            from notifications.models import Notification
            from django.db.models import Count, Sum

            campaign = NotificationCampaign.objects.get(pk=campaign_id)

            # Aggregate stats from notifications linked to this campaign
            # (assuming notifications have campaign FK via metadata or a direct FK)
            notifications = Notification.objects.filter(
                campaign=campaign
            ) if hasattr(Notification, 'campaign') else Notification.objects.none()

            total = notifications.count()
            delivered = notifications.filter(is_delivered=True).count()
            failed = notifications.filter(status='failed').count()
            read = notifications.filter(is_read=True).count()
            clicked = notifications.aggregate(
                total_clicks=Sum('click_count')
            )['total_clicks'] or 0

            result, _ = CampaignResult.objects.get_or_create(campaign=campaign)
            result.sent = campaign.sent_count
            result.delivered = delivered
            result.failed = failed
            result.opened = read
            result.clicked = clicked
            result.recalculate_rates(save=False)
            result.save()

            return {
                'success': True,
                'campaign_id': campaign_id,
                'sent': result.sent,
                'delivered': result.delivered,
                'opened': result.opened,
                'clicked': result.clicked,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'DeliveryTracker.update_campaign_results campaign #{campaign_id}: {exc}')
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reconcile_single(self, notification) -> bool:
        """
        Try to reconcile delivery status for a single notification.
        Returns True if status was updated to delivered.
        """
        channel = getattr(notification, 'channel', '')

        if channel == 'email':
            from notifications.models.channel import EmailDeliveryLog
            log = EmailDeliveryLog.objects.filter(
                notification=notification,
                status__in=('delivered', 'opened', 'clicked'),
            ).first()
            if log:
                notification.mark_as_delivered()
                return True

        elif channel == 'sms':
            from notifications.models.channel import SMSDeliveryLog
            log = SMSDeliveryLog.objects.filter(
                notification=notification,
                status='delivered',
            ).first()
            if log:
                notification.mark_as_delivered()
                return True

        elif channel == 'push':
            from notifications.models.channel import PushDeliveryLog
            log = PushDeliveryLog.objects.filter(
                notification=notification,
                status='delivered',
            ).first()
            if log:
                notification.mark_as_delivered()
                return True

        return False

    def _sync_notification_from_email_log(self, message_id: str):
        """Update Notification.is_delivered based on EmailDeliveryLog status."""
        if not message_id:
            return
        try:
            from notifications.models.channel import EmailDeliveryLog
            log = EmailDeliveryLog.objects.filter(message_id=message_id).first()
            if log and log.status in ('delivered', 'opened', 'clicked'):
                log.notification.mark_as_delivered()
        except Exception as exc:
            logger.warning(f'DeliveryTracker._sync_notification_from_email_log: {exc}')

    def _sync_notification_from_sms_log(self, sid: str):
        """Update Notification.is_delivered based on SMSDeliveryLog status."""
        if not sid:
            return
        try:
            from notifications.models.channel import SMSDeliveryLog
            log = SMSDeliveryLog.objects.filter(provider_sid=sid).first()
            if log and log.status == 'delivered':
                log.notification.mark_as_delivered()
        except Exception as exc:
            logger.warning(f'DeliveryTracker._sync_notification_from_sms_log: {exc}')

    def _deactivate_push_device(self, device_id: int):
        """Deactivate a push device after an invalid token error."""
        try:
            from notifications.models.channel import PushDevice
            PushDevice.objects.filter(pk=device_id).update(
                is_active=False,
                updated_at=timezone.now(),
            )
        except Exception as exc:
            logger.warning(f'DeliveryTracker._deactivate_push_device #{device_id}: {exc}')


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
delivery_tracker = DeliveryTracker()
