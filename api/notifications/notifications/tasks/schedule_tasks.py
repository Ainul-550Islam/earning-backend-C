# earning_backend/api/notifications/tasks/schedule_tasks.py
"""
Scheduled notification dispatch tasks.
"""
import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_scheduled',
    name='notifications.send_scheduled_notifications',
)
def send_scheduled_notifications():
    """
    Periodic task (every minute): find all NotificationSchedule records
    that are due and trigger sends.
    """
    from api.notifications.models.schedule import NotificationSchedule
    from api.notifications._services_core import notification_service

    now = timezone.now()
    due_schedules = NotificationSchedule.objects.filter(
        status='pending',
        send_at__lte=now,
    ).select_related('notification')

    dispatched = 0
    failed = 0

    for schedule in due_schedules:
        try:
            schedule.status = 'processing'
            schedule.save(update_fields=['status', 'updated_at'])

            notification = schedule.notification
            success = notification_service.send_notification(notification)

            if success:
                schedule.mark_sent()
                dispatched += 1
            else:
                schedule.mark_failed(reason='send_notification returned False')
                failed += 1

        except Exception as exc:
            logger.error(f'send_scheduled_notifications: schedule #{schedule.pk} — {exc}')
            try:
                schedule.mark_failed(reason=str(exc))
            except Exception:
                pass
            failed += 1

    if dispatched or failed:
        logger.info(f'send_scheduled_notifications: dispatched={dispatched} failed={failed}')
    return {'dispatched': dispatched, 'failed': failed}


@shared_task(
    queue='notifications_scheduled',
    name='notifications.cancel_overdue_schedules',
)
def cancel_overdue_schedules(grace_hours: int = 24):
    """
    Mark NotificationSchedule records as 'skipped' if they are more than
    grace_hours past their send_at and still pending.
    """
    from api.notifications.models.schedule import NotificationSchedule
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=grace_hours)
    overdue = NotificationSchedule.objects.filter(
        status='pending',
        send_at__lt=cutoff,
    )

    count = overdue.count()
    overdue.update(status='skipped', updated_at=timezone.now())

    if count:
        logger.info(f'cancel_overdue_schedules: skipped {count} overdue schedule(s)')
    return {'skipped': count}


@shared_task(
    bind=True,
    queue='notifications_scheduled',
    name='notifications.schedule_notification',
)
def schedule_notification_task(self, notification_id: int, send_at_iso: str):
    """
    Create a NotificationSchedule record for a notification.
    send_at_iso: ISO 8601 datetime string.
    """
    from api.notifications.models import Notification
    from api.notifications.models.schedule import NotificationSchedule
    from datetime import datetime

    try:
        notification = Notification.objects.get(pk=notification_id)
        send_at = timezone.datetime.fromisoformat(send_at_iso)
        if timezone.is_naive(send_at):
            send_at = timezone.make_aware(send_at)

        schedule, created = NotificationSchedule.objects.get_or_create(
            notification=notification,
            defaults={
                'send_at': send_at,
                'status': 'pending',
            },
        )
        if not created:
            schedule.send_at = send_at
            schedule.status = 'pending'
            schedule.save(update_fields=['send_at', 'status', 'updated_at'])

        return {
            'success': True,
            'notification_id': notification_id,
            'schedule_id': schedule.pk,
            'send_at': send_at_iso,
        }
    except Exception as exc:
        logger.error(f'schedule_notification_task #{notification_id}: {exc}')
        return {'success': False, 'notification_id': notification_id, 'error': str(exc)}
