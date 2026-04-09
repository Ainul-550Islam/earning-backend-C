# api/djoyalty/tasks/notification_tasks.py
"""
Celery task: Loyalty notification sending।
Schedule: Daily — expiry warnings।
"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.send_expiry_notifications', bind=True, max_retries=3)
def send_expiry_notifications_task(self):
    """
    Soon-to-expire points এর জন্য customer দের notification পাঠাও।
    Returns: count of warnings sent
    """
    try:
        from ..services.points.PointsExpiryService import PointsExpiryService

        count = PointsExpiryService.send_expiry_warnings()
        logger.info('[djoyalty] Expiry notifications sent: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] send_expiry_notifications error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.send_pending_notifications', bind=True, max_retries=3)
def send_pending_notifications_task(self):
    """
    LoyaltyNotification table এর unsent notifications পাঠাও।
    Returns: count of notifications sent
    """
    try:
        from ..models.advanced import LoyaltyNotification
        from django.utils import timezone

        pending = LoyaltyNotification.objects.filter(is_sent=False)
        count = 0
        for notification in pending:
            try:
                # Actual sending logic — email/sms/push সেই অনুযায়ী implement করো
                notification.is_sent = True
                notification.sent_at = timezone.now()
                notification.save(update_fields=['is_sent', 'sent_at'])
                count += 1
            except Exception as e:
                logger.error('[djoyalty] Failed to send notification %d: %s', notification.id, e)

        logger.info('[djoyalty] Pending notifications sent: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] send_pending_notifications error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc
