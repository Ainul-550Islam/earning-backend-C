# api/djoyalty/tasks/notification_delivery_tasks.py
"""
Notification Delivery Celery Tasks।
Async notification sending, bulk dispatch, cleanup।

FIXED: send_expiry_warnings_task had name='djoyalty.send_expiry_warnings'
which DUPLICATED the same name in points_expiry_tasks.py। Celery
registers only one per name -- whichever loads last wins silently।
Renamed to 'djoyalty.send_expiry_warnings_delivery' to avoid conflict।
The canonical scheduled expiry warning task is in points_expiry_tasks.py।
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.send_notification', bind=True, max_retries=3)
def send_notification_task(self, customer_id: int, notification_type: str,
                            title: str, body: str, icon: str = '🔔',
                            action_url: str = '', metadata: dict = None,
                            priority: str = 'normal'):
    """Async notification sender -- called from Celery queue।"""
    try:
        from ..models.core import Customer
        from ..services.NotificationService import NotificationService

        customer = Customer.objects.get(id=customer_id, is_active=True)
        NotificationService.send(
            customer=customer,
            notification_type=notification_type,
            title=title,
            body=body,
            icon=icon,
            action_url=action_url,
            metadata=metadata or {},
            priority=priority,
        )
        return {'success': True, 'customer_id': customer_id}
    except Exception as exc:
        logger.error('send_notification_task #%d error: %s', customer_id, exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(name='djoyalty.send_bulk_notification')
def send_bulk_notification_task(customer_ids: list, notification_type: str,
                                 title: str, body: str, icon: str = '🔔',
                                 metadata: dict = None):
    """Send notification to many customers -- Celery batch।"""
    from ..models.core import Customer
    from ..services.NotificationService import NotificationService

    customers = Customer.objects.filter(id__in=customer_ids, is_active=True)
    sent = 0
    for customer in customers.iterator(chunk_size=50):
        try:
            NotificationService.send(
                customer=customer,
                notification_type=notification_type,
                title=title,
                body=body,
                icon=icon,
                metadata=metadata or {},
            )
            sent += 1
        except Exception as e:
            logger.debug('Bulk notif failed for %s: %s', customer.code, e)

    logger.info('send_bulk_notification_task: sent %d/%d', sent, len(customer_ids))
    return {'sent': sent, 'total': len(customer_ids)}


@shared_task(name='djoyalty.send_expiry_warnings_delivery')
def send_expiry_warnings_task(days_before: int = 7):
    """
    Send points expiry warnings via notification delivery queue।

    FIXED: was 'djoyalty.send_expiry_warnings' -- renamed to
    'djoyalty.send_expiry_warnings_delivery' to avoid duplicate
    registration with points_expiry_tasks.send_expiry_warnings_task।
    The celery_beat_config.py schedule points to the canonical task
    in points_expiry_tasks.py (name='djoyalty.send_expiry_warnings')।
    This task remains available for direct .delay() calls from
    notification queue workers।
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        from ..models.points import PointsExpiry
        from ..services.NotificationService import NotificationService

        cutoff = timezone.now() + timedelta(days=days_before)
        expiring = PointsExpiry.objects.filter(
            is_expired=False,
            expiry_date__lte=cutoff,
            expiry_date__gt=timezone.now(),
            points_remaining__gt=0,
        ).select_related('customer')

        sent = 0
        for exp in expiring.iterator(chunk_size=100):
            try:
                days_left = (exp.expiry_date.date() - timezone.now().date()).days
                NotificationService.notify_points_expiring(
                    exp.customer, exp.points_remaining, days_left
                )
                sent += 1
            except Exception as e:
                logger.debug('Expiry warning failed for %s: %s', exp.customer.code, e)

        logger.info(
            'send_expiry_warnings_delivery: sent %d warnings (%d days)', sent, days_before
        )
        return {'sent': sent}
    except Exception as exc:
        logger.error('send_expiry_warnings_delivery error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.cleanup_old_notifications')
def cleanup_old_notifications_task(days: int = 90):
    """Delete old read notifications to keep DB clean।"""
    try:
        from datetime import timedelta
        from django.utils import timezone
        from ..models.notifications import NotificationCenter

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = NotificationCenter.objects.filter(
            is_read=True,
            created_at__lt=cutoff,
        ).delete()

        logger.info(
            'cleanup_old_notifications_task: deleted %d old notifications', deleted
        )
        return {'deleted': deleted}
    except Exception as exc:
        logger.error('cleanup_old_notifications_task error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.process_queued_message')
def process_queued_message(message_data: dict):
    """
    Process a queued message from MessageQueueManager।
    Dispatches to appropriate handler based on event_type।
    """
    try:
        from ..integration_system.message_queue import Message
        from ..integration_system.event_bus import EventBus

        msg = Message.from_dict(message_data)
        customer = None
        if msg.customer_id:
            from ..models.core import Customer
            try:
                customer = Customer.objects.get(id=msg.customer_id)
            except Customer.DoesNotExist:
                pass

        EventBus.publish(
            msg.event_type,
            customer=customer,
            data=msg.payload,
        )
        return {'processed': True, 'message_id': msg.message_id}
    except Exception as exc:
        logger.error('process_queued_message error: %s', exc)
        return {'error': str(exc)}
