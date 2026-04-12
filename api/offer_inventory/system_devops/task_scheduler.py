# api/offer_inventory/system_devops/task_scheduler.py
"""
Task Scheduler Manager — Dynamic Celery task scheduling and management.
Schedule, cancel, monitor, and retry Celery tasks.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class TaskSchedulerManager:
    """Dynamic Celery task scheduling."""

    @staticmethod
    def schedule_offer_expiry(offer_id: str, expires_at) -> str:
        """Schedule automatic offer expiry at a specific time."""
        from api.offer_inventory.tasks import auto_expire_offers
        result = auto_expire_offers.apply_async(eta=expires_at)
        logger.info(f'Offer expiry scheduled: {offer_id} at {expires_at}')
        return result.id

    @staticmethod
    def schedule_bulk_notification(user_ids: list, title: str, body: str,
                                    delay_seconds: int = 0) -> str:
        """Schedule bulk notification with optional delay."""
        from api.offer_inventory.tasks import send_bulk_notification
        result = send_bulk_notification.apply_async(
            args=[user_ids, title, body],
            countdown=delay_seconds,
        )
        return result.id

    @staticmethod
    def schedule_postback(conversion_id: str, delay_seconds: int = 0) -> str:
        """Schedule a postback delivery."""
        from api.offer_inventory.tasks import deliver_postback
        result = deliver_postback.apply_async(
            args=[conversion_id, 0],
            countdown=delay_seconds,
        )
        return result.id

    @staticmethod
    def schedule_report_email(report_type: str, email: str,
                               days: int = 30, delay_hours: int = 0) -> str:
        """Schedule a report to be emailed."""
        from api.offer_inventory.tasks import send_email_batch
        result = send_email_batch.apply_async(
            args=[f'Report: {report_type}', 'emails/report.html', [], {}],
            countdown=delay_hours * 3600,
        )
        return result.id

    @staticmethod
    def get_pending_tasks(limit: int = 100) -> list:
        """Get list of pending Celery tasks from DB."""
        from api.offer_inventory.models import TaskQueue
        return list(
            TaskQueue.objects.filter(status='pending')
            .values('task_id', 'task_name', 'created_at', 'scheduled_for')
            .order_by('-created_at')[:limit]
        )

    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """Cancel a pending Celery task."""
        try:
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            from api.offer_inventory.models import TaskQueue
            TaskQueue.objects.filter(task_id=task_id).update(
                status='failure', error='Manually cancelled'
            )
            logger.info(f'Task cancelled: {task_id}')
            return True
        except Exception as e:
            logger.error(f'Task cancel error: {e}')
            return False

    @staticmethod
    def retry_failed_tasks(task_name: str = None, limit: int = 50) -> int:
        """Retry failed tasks."""
        from api.offer_inventory.models import TaskQueue
        qs = TaskQueue.objects.filter(status='failure')
        if task_name:
            qs = qs.filter(task_name=task_name)
        count = 0
        for task in qs[:limit]:
            try:
                from celery import current_app
                current_app.send_task(task.task_name, args=task.args or [])
                task.status = 'pending'
                task.save(update_fields=['status'])
                count += 1
            except Exception as e:
                logger.error(f'Task retry error {task.task_id}: {e}')
        return count

    @staticmethod
    def get_task_stats() -> dict:
        """Summary of task queue status."""
        from api.offer_inventory.models import TaskQueue
        from django.db.models import Count
        stats = dict(
            TaskQueue.objects.values_list('status')
            .annotate(count=Count('id'))
        )
        return {
            'pending'  : stats.get('pending', 0),
            'running'  : stats.get('running', 0),
            'success'  : stats.get('success', 0),
            'failure'  : stats.get('failure', 0),
        }
