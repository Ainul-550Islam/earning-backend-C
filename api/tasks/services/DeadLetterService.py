"""
tasks/services/DeadLetterService.py
Manage the Dead Letter Queue — view, retry, and discard failed tasks.
"""
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class DeadLetterService:
    """
    Provides CRUD + reprocessing operations on TaskDeadLetterQueue entries.
    """

    def add_to_dlq(
        self,
        task_name: str,
        task_id: str,
        error: str,
        traceback: str = '',
        payload: dict = None,
        failure_reason: str = 'unknown',
        retry_count: int = 0,
        queue_name: str = '',
        worker_hostname: str = '',
        task_headers: dict = None,
    ) -> Dict[str, Any]:
        """
        Create a new DLQ entry for a permanently failed task.
        Called by RetryService after exhausting max_retries.
        """
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            entry = TaskDeadLetterQueue.objects.create(
                task_name=task_name,
                task_id=task_id,
                error=error[:5000],
                traceback=traceback,
                payload=payload or {},
                failure_reason=failure_reason,
                retry_count=retry_count,
                queue_name=queue_name,
                worker_hostname=worker_hostname,
                task_headers=task_headers or {},
                failed_at=timezone.now(),
                reprocess_status='pending',
            )
            logger.warning(f"[DLQ] Added: {task_name} id={task_id} reason={failure_reason}")
            return {'success': True, 'dlq_id': entry.pk}

        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.add_to_dlq: {e}")
            return {'success': False, 'error': str(e)}

    def list_pending(self, limit: int = 100) -> List[Dict]:
        """Return pending DLQ entries sorted by failed_at desc."""
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            return list(
                TaskDeadLetterQueue.objects.filter(
                    reprocess_status='pending'
                ).order_by('-failed_at')[:limit].values(
                    'id', 'task_name', 'task_id', 'error',
                    'failure_reason', 'retry_count', 'failed_at', 'queue_name',
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.list_pending: {e}")
            return []

    def list_all(
        self,
        status: str = None,
        task_name: str = None,
        limit: int = 200,
    ) -> List[Dict]:
        """Return DLQ entries with optional filters."""
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            qs = TaskDeadLetterQueue.objects.order_by('-failed_at')
            if status:
                qs = qs.filter(reprocess_status=status)
            if task_name:
                qs = qs.filter(task_name__icontains=task_name)

            return list(qs[:limit].values(
                'id', 'task_name', 'task_id', 'error', 'failure_reason',
                'retry_count', 'failed_at', 'queue_name', 'reprocess_status',
                'reprocessed_at', 'new_task_id',
            ))
        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.list_all: {e}")
            return []

    def retry_entry(self, dlq_id: int, notes: str = '') -> Dict[str, Any]:
        """
        Re-enqueue a DLQ entry by dispatching its original task again.
        Marks the entry as 'requeued' with the new Celery task ID.
        """
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue
            from celery import current_app

            entry = TaskDeadLetterQueue.objects.get(pk=dlq_id)

            if entry.reprocess_status not in ('pending',):
                return {
                    'success': False,
                    'error': f'Entry is already {entry.reprocess_status}',
                }

            # Re-dispatch
            payload  = entry.payload or {}
            args     = payload.get('args', [])
            kwargs   = payload.get('kwargs', {})

            result   = current_app.send_task(
                entry.task_name,
                args=args,
                kwargs=kwargs,
                queue=entry.queue_name or 'default',
            )

            entry.mark_requeued(new_task_id=result.id, notes=notes)
            logger.info(f"[DLQ] Requeued: {entry.task_name} new_id={result.id}")

            return {'success': True, 'dlq_id': dlq_id, 'new_task_id': result.id}

        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.retry_entry {dlq_id}: {e}")
            return {'success': False, 'error': str(e)}

    def retry_all_pending(self, task_name: str = None) -> Dict[str, Any]:
        """
        Retry all pending DLQ entries (optionally filtered by task_name).
        Returns counts of retried and failed re-dispatches.
        """
        retried = 0
        failed  = 0

        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            qs = TaskDeadLetterQueue.objects.filter(reprocess_status='pending')
            if task_name:
                qs = qs.filter(task_name=task_name)

            for entry in qs.iterator(chunk_size=50):
                result = self.retry_entry(entry.pk)
                if result.get('success'):
                    retried += 1
                else:
                    failed += 1

        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.retry_all_pending: {e}")

        return {'success': True, 'retried': retried, 'failed': failed}

    def discard_entry(self, dlq_id: int, notes: str = '') -> Dict[str, Any]:
        """Mark a DLQ entry as discarded (won't be retried)."""
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            entry = TaskDeadLetterQueue.objects.get(pk=dlq_id)
            entry.mark_discarded(notes=notes)
            logger.info(f"[DLQ] Discarded entry {dlq_id}")
            return {'success': True, 'dlq_id': dlq_id}

        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.discard_entry {dlq_id}: {e}")
            return {'success': False, 'error': str(e)}

    def discard_all(self, task_name: str = None) -> Dict[str, Any]:
        """Discard all pending DLQ entries (optionally filtered by task_name)."""
        discarded = 0
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            qs = TaskDeadLetterQueue.objects.filter(reprocess_status='pending')
            if task_name:
                qs = qs.filter(task_name=task_name)

            discarded = qs.update(
                reprocess_status='discarded',
                reprocessed_at=timezone.now(),
            )
        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.discard_all: {e}")

        return {'success': True, 'discarded': discarded}

    def get_stats(self) -> Dict[str, Any]:
        """Return DLQ aggregate statistics."""
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue
            from django.db.models import Count

            stats = TaskDeadLetterQueue.objects.aggregate(
                total=Count('id'),
                pending=Count('id', filter=__import__(
                    'django.db.models', fromlist=['Q']
                ).Q(reprocess_status='pending')),
                requeued=Count('id', filter=__import__(
                    'django.db.models', fromlist=['Q']
                ).Q(reprocess_status='requeued')),
                discarded=Count('id', filter=__import__(
                    'django.db.models', fromlist=['Q']
                ).Q(reprocess_status='discarded')),
            )

            top_failing = list(
                TaskDeadLetterQueue.objects
                .filter(reprocess_status='pending')
                .values('task_name')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )

            return {
                'total': stats['total'],
                'pending': stats['pending'],
                'requeued': stats['requeued'],
                'discarded': stats['discarded'],
                'top_failing_tasks': top_failing,
            }

        except Exception as e:
            logger.error(f"[ERROR] DeadLetterService.get_stats: {e}")
            return {}
