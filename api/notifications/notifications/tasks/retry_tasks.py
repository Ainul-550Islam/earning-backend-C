# earning_backend/api/notifications/tasks/retry_tasks.py
"""
Retry failed notification delivery attempts.
"""
import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


def _exponential_backoff_delay(attempt: int, base: int = 60, cap: int = 3600) -> int:
    """
    Calculate exponential backoff delay in seconds.
    attempt=1 → 60s, attempt=2 → 120s, attempt=3 → 240s ... cap at 3600s (1hr)
    Adds jitter to prevent thundering herd.
    """
    import random
    delay = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return int(delay + jitter)


@shared_task(
    bind=True,
    max_retries=1,
    queue='notifications_retry',
    name='notifications.retry_notification',
)
def retry_notification_task(self, notification_id: int):
    """
    Retry delivery for a single failed notification.
    Records the attempt in NotificationRetry model.
    """
    from api.notifications.models import Notification
    from api.notifications.models.schedule import NotificationRetry
    from api.notifications._services_core import notification_service

    try:
        notification = Notification.objects.get(pk=notification_id, is_deleted=False)

        # Get or create retry record
        attempt_number = NotificationRetry.objects.filter(
            notification=notification
        ).count() + 1

        retry = NotificationRetry.objects.create(
            notification=notification,
            attempt_number=attempt_number,
            max_attempts=3,
            status='processing',
            retry_at=timezone.now(),
        )

        # Attempt to send
        notification.prepare_for_retry()
        success = notification_service.send_notification(notification)

        if success:
            retry.mark_succeeded()
        else:
            retry.mark_failed(error='send_notification returned False')
            if attempt_number >= retry.max_attempts:
                retry.mark_abandoned()

        return {
            'success': success,
            'notification_id': notification_id,
            'attempt': attempt_number,
        }

    except Notification.DoesNotExist:
        logger.warning(f'retry_notification_task: notification #{notification_id} not found')
        return {'success': False, 'notification_id': notification_id, 'error': 'not found'}
    except Exception as exc:
        logger.error(f'retry_notification_task #{notification_id}: {exc}')
        return {'success': False, 'notification_id': notification_id, 'error': str(exc)}


@shared_task(
    queue='notifications_retry',
    name='notifications.process_all_retries',
)
def process_all_retries():
    """
    Periodic task: find all NotificationRetry records that are due and
    schedule retry_notification_task for each.
    """
    from api.notifications.models.schedule import NotificationRetry

    now = timezone.now()
    due_retries = NotificationRetry.objects.filter(
        status='scheduled',
        retry_at__lte=now,
    ).select_related('notification')

    queued = 0
    for retry in due_retries:
        if retry.has_exceeded_max():
            retry.mark_abandoned()
            continue
        try:
            retry.status = 'processing'
            retry.save(update_fields=['status', 'updated_at'])
            delay = _exponential_backoff_delay(retry.attempt_number)
            retry_notification_task.apply_async(
                args=[retry.notification_id],
                countdown=delay,
            )
            queued += 1
        except Exception as exc:
            logger.warning(f'process_all_retries: retry #{retry.pk} — {exc}')

    return {'queued': queued}


@shared_task(
    queue='notifications_retry',
    name='notifications.retry_failed_queue_entries',
)
def retry_failed_queue_entries():
    """Retry NotificationQueue entries that are in 'failed' status."""
    from api.notifications.models.schedule import NotificationQueue
    from datetime import timedelta

    # Only retry entries that failed in the last 24h
    cutoff = timezone.now() - timedelta(hours=24)
    failed_entries = NotificationQueue.objects.filter(
        status='failed',
        updated_at__gte=cutoff,
        attempts__lt=3,
    )

    requeued = 0
    for entry in failed_entries:
        try:
            entry.status = 'waiting'
            entry.scheduled_at = timezone.now()
            entry.save(update_fields=['status', 'scheduled_at', 'updated_at'])
            requeued += 1
        except Exception as exc:
            logger.warning(f'retry_failed_queue_entries #{entry.pk}: {exc}')

    return {'requeued': requeued}
