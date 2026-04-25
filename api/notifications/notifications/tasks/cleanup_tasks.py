# earning_backend/api/notifications/tasks/cleanup_tasks.py
"""
Cleanup tasks — delete old logs, expired notifications, stale queue entries,
and other housekeeping operations.

Schedule via Celery Beat:
    cleanup_expired_notifications    — daily at 03:00 UTC
    cleanup_old_delivery_logs        — daily at 03:30 UTC
    cleanup_stale_queue_entries      — daily at 04:00 UTC
    cleanup_old_push_delivery_logs   — weekly Sunday at 04:00 UTC
    cleanup_read_in_app_messages     — daily at 05:00 UTC
"""
import logging
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_expired_notifications',
)
def cleanup_expired_notifications():
    """
    Delete notifications that have passed their expiry time and are marked
    for auto-deletion. Preserves non-auto-delete records.
    """
    from api.notifications.models import Notification

    try:
        result = Notification.delete_expired()
        logger.info(f'cleanup_expired_notifications: deleted={result.get("deleted", 0)}')
        return result
    except Exception as exc:
        logger.error(f'cleanup_expired_notifications: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_old_notifications',
)
def cleanup_old_notifications(days: int = 90):
    """
    Delete notifications older than `days` days (default 90).
    Keeps unread notifications regardless of age.
    """
    from api.notifications._services_core import notification_service

    try:
        result = notification_service.cleanup_old_notifications(days=days)
        logger.info(f'cleanup_old_notifications (>{days}d): deleted={result.get("deleted", 0)}')
        return result
    except Exception as exc:
        logger.error(f'cleanup_old_notifications: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_old_delivery_logs',
)
def cleanup_old_delivery_logs(days: int = 30):
    """
    Delete PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog records older than
    `days` days (default 30). Keeps failed records an extra 14 days for debugging.
    """
    from api.notifications.models.channel import PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog

    cutoff = timezone.now() - timedelta(days=days)
    failed_cutoff = timezone.now() - timedelta(days=days + 14)

    total_deleted = 0

    for Model in (PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog):
        try:
            # Delete successful/delivered records past the main cutoff
            deleted_ok, _ = Model.objects.filter(
                created_at__lt=cutoff,
                status__in=('delivered', 'sent', 'opened', 'clicked'),
            ).delete()

            # Delete failed records past the extended cutoff
            deleted_fail, _ = Model.objects.filter(
                created_at__lt=failed_cutoff,
                status__in=('failed', 'bounced', 'invalid_token', 'invalid_number'),
            ).delete()

            count = deleted_ok + deleted_fail
            total_deleted += count
            logger.info(f'cleanup_old_delivery_logs {Model.__name__}: deleted={count}')
        except Exception as exc:
            logger.warning(f'cleanup_old_delivery_logs {Model.__name__}: {exc}')

    return {'success': True, 'total_deleted': total_deleted, 'days': days}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_stale_queue_entries',
)
def cleanup_stale_queue_entries(days: int = 7):
    """
    Delete NotificationQueue entries in terminal states (done/failed/cancelled)
    older than `days` days.
    """
    from api.notifications.models.schedule import NotificationQueue

    cutoff = timezone.now() - timedelta(days=days)
    try:
        deleted, _ = NotificationQueue.objects.filter(
            status__in=('done', 'cancelled'),
            updated_at__lt=cutoff,
        ).delete()

        # Also delete permanently failed entries (> 3 attempts)
        failed_deleted, _ = NotificationQueue.objects.filter(
            status='failed',
            attempts__gte=3,
            updated_at__lt=cutoff,
        ).delete()

        total = deleted + failed_deleted
        logger.info(f'cleanup_stale_queue_entries: deleted={total}')
        return {'success': True, 'deleted': total}
    except Exception as exc:
        logger.error(f'cleanup_stale_queue_entries: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_old_retry_records',
)
def cleanup_old_retry_records(days: int = 14):
    """
    Delete NotificationRetry records in terminal states older than `days` days.
    """
    from api.notifications.models.schedule import NotificationRetry

    cutoff = timezone.now() - timedelta(days=days)
    try:
        deleted, _ = NotificationRetry.objects.filter(
            status__in=('succeeded', 'abandoned'),
            updated_at__lt=cutoff,
        ).delete()
        logger.info(f'cleanup_old_retry_records: deleted={deleted}')
        return {'success': True, 'deleted': deleted}
    except Exception as exc:
        logger.error(f'cleanup_old_retry_records: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_read_in_app_messages',
)
def cleanup_read_in_app_messages(days: int = 30):
    """
    Delete InAppMessage records that have been read or dismissed and are
    older than `days` days. Keeps unread/unexpired messages.
    """
    from django.db.models import Q
    from api.notifications.models.channel import InAppMessage

    cutoff = timezone.now() - timedelta(days=days)
    try:
        deleted, _ = InAppMessage.objects.filter(
            created_at__lt=cutoff,
        ).filter(Q(is_read=True) | Q(is_dismissed=True)).delete()
        logger.info(f'cleanup_read_in_app_messages: deleted={deleted}')
        return {'success': True, 'deleted': deleted}
    except Exception as exc:
        logger.error(f'cleanup_read_in_app_messages: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_expired_in_app_messages',
)
def cleanup_expired_in_app_messages():
    """Delete InAppMessage records past their expires_at datetime."""
    from api.notifications.models.channel import InAppMessage

    try:
        deleted, _ = InAppMessage.objects.filter(
            expires_at__lt=timezone.now(),
        ).delete()
        logger.info(f'cleanup_expired_in_app_messages: deleted={deleted}')
        return {'success': True, 'deleted': deleted}
    except Exception as exc:
        logger.error(f'cleanup_expired_in_app_messages: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.cleanup_old_schedules',
)
def cleanup_old_schedules(days: int = 30):
    """
    Delete completed/cancelled/skipped NotificationSchedule records
    older than `days` days.
    """
    from api.notifications.models.schedule import NotificationSchedule

    cutoff = timezone.now() - timedelta(days=days)
    try:
        deleted, _ = NotificationSchedule.objects.filter(
            status__in=('sent', 'cancelled', 'skipped', 'failed'),
            updated_at__lt=cutoff,
        ).delete()
        logger.info(f'cleanup_old_schedules: deleted={deleted}')
        return {'success': True, 'deleted': deleted}
    except Exception as exc:
        logger.error(f'cleanup_old_schedules: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.run_all_cleanup',
)
def run_all_cleanup():
    """
    Master cleanup task — triggers all individual cleanup tasks.
    Schedule this via Celery Beat at 03:00 UTC daily.
    """
    tasks = [
        cleanup_expired_notifications.s(),
        cleanup_old_notifications.s(90),
        cleanup_old_delivery_logs.s(30),
        cleanup_stale_queue_entries.s(7),
        cleanup_old_retry_records.s(14),
        cleanup_expired_in_app_messages.s(),
        cleanup_read_in_app_messages.s(30),
        cleanup_old_schedules.s(30),
    ]
    from celery import group
    group(tasks).apply_async()
    logger.info(f'run_all_cleanup: triggered {len(tasks)} cleanup tasks')
    return {'queued': len(tasks)}
