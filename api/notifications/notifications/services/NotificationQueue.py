# earning_backend/api/notifications/services/NotificationQueue.py
"""
NotificationQueueService — manages the in-database priority queue.

Works with the NotificationQueue model (models/schedule.py) and is
called by queue-related Celery tasks to enqueue, dequeue, and manage
pending notification sends.
"""

import logging
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationQueueService:

    DEFAULT_BATCH_SIZE = 100

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(
        self,
        notification,
        priority: int = 5,
        scheduled_at=None,
    ) -> Dict:
        """
        Add a notification to the priority queue.

        Args:
            notification: Notification model instance.
            priority:     1 (lowest) – 10 (highest). Default 5.
            scheduled_at: Earliest processing time (default: now).

        Returns:
            Dict with: success, queue_entry_id, error.
        """
        from api.notifications.models.schedule import NotificationQueue

        if not (1 <= priority <= 10):
            priority = max(1, min(10, priority))

        try:
            entry, created = NotificationQueue.objects.get_or_create(
                notification=notification,
                defaults={
                    'priority': priority,
                    'scheduled_at': scheduled_at or timezone.now(),
                    'status': 'waiting',
                },
            )
            if not created:
                # Already queued — update priority if higher
                if priority > entry.priority:
                    entry.priority = priority
                    entry.save(update_fields=['priority', 'updated_at'])

            return {
                'success': True,
                'queue_entry_id': entry.pk,
                'created': created,
                'error': '',
            }
        except Exception as exc:
            logger.error(f'NotificationQueueService.enqueue #{notification.id}: {exc}')
            return {'success': False, 'queue_entry_id': None, 'error': str(exc)}

    def enqueue_bulk(
        self,
        notifications: List,
        priority: int = 5,
        scheduled_at=None,
    ) -> Dict:
        """
        Enqueue a list of notifications efficiently using bulk_create.

        Returns:
            Dict with: success, enqueued_count, skipped_count, error.
        """
        from api.notifications.models.schedule import NotificationQueue

        existing_ids = set(
            NotificationQueue.objects.filter(
                notification__in=notifications
            ).values_list('notification_id', flat=True)
        )

        new_entries = []
        skipped = 0
        for notification in notifications:
            if notification.pk in existing_ids:
                skipped += 1
                continue
            new_entries.append(
                NotificationQueue(
                    notification=notification,
                    priority=priority,
                    scheduled_at=scheduled_at or timezone.now(),
                    status='waiting',
                )
            )

        try:
            if new_entries:
                NotificationQueue.objects.bulk_create(new_entries, ignore_conflicts=True)
            return {
                'success': True,
                'enqueued_count': len(new_entries),
                'skipped_count': skipped,
                'error': '',
            }
        except Exception as exc:
            logger.error(f'NotificationQueueService.enqueue_bulk: {exc}')
            return {'success': False, 'enqueued_count': 0, 'skipped_count': 0, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Dequeue (batch fetch for Celery worker)
    # ------------------------------------------------------------------

    def dequeue_batch(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        worker_id: str = '',
    ) -> List:
        """
        Atomically claim a batch of waiting queue entries for processing.

        Returns a list of NotificationQueue instances with status='processing'.
        Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent workers.
        """
        from api.notifications.models.schedule import NotificationQueue

        try:
            with transaction.atomic():
                entries = (
                    NotificationQueue.objects.select_for_update(skip_locked=True)
                    .filter(
                        status='waiting',
                        scheduled_at__lte=timezone.now(),
                    )
                    .order_by('-priority', 'scheduled_at')
                    [:batch_size]
                )

                pks = [e.pk for e in entries]
                if not pks:
                    return []

                NotificationQueue.objects.filter(pk__in=pks).update(
                    status='processing',
                    celery_task_id=worker_id,
                    updated_at=timezone.now(),
                )

                return list(
                    NotificationQueue.objects.filter(pk__in=pks)
                    .select_related('notification')
                )
        except Exception as exc:
            logger.error(f'NotificationQueueService.dequeue_batch: {exc}')
            return []

    # ------------------------------------------------------------------
    # Complete / fail
    # ------------------------------------------------------------------

    def mark_done(self, queue_entry_id: int) -> bool:
        """Mark a queue entry as done after successful processing."""
        from api.notifications.models.schedule import NotificationQueue
        try:
            NotificationQueue.objects.filter(pk=queue_entry_id).update(
                status='done', updated_at=timezone.now()
            )
            return True
        except Exception as exc:
            logger.error(f'NotificationQueueService.mark_done #{queue_entry_id}: {exc}')
            return False

    def mark_failed(self, queue_entry_id: int) -> bool:
        """Mark a queue entry as failed."""
        from api.notifications.models.schedule import NotificationQueue
        try:
            NotificationQueue.objects.filter(pk=queue_entry_id).update(
                status='failed', updated_at=timezone.now()
            )
            return True
        except Exception as exc:
            logger.error(f'NotificationQueueService.mark_failed #{queue_entry_id}: {exc}')
            return False

    def requeue(self, queue_entry_id: int, delay_seconds: int = 60) -> bool:
        """Return a failed entry to waiting status with a delay."""
        from api.notifications.models.schedule import NotificationQueue
        from datetime import timedelta
        try:
            entry = NotificationQueue.objects.get(pk=queue_entry_id)
            entry.status = 'waiting'
            entry.attempts += 1
            entry.last_attempt = timezone.now()
            entry.scheduled_at = timezone.now() + timedelta(seconds=delay_seconds)
            entry.save(update_fields=['status', 'attempts', 'last_attempt', 'scheduled_at', 'updated_at'])
            return True
        except Exception as exc:
            logger.error(f'NotificationQueueService.requeue #{queue_entry_id}: {exc}')
            return False

    # ------------------------------------------------------------------
    # Monitoring / stats
    # ------------------------------------------------------------------

    def get_queue_stats(self) -> Dict:
        """Return current queue depth and status breakdown."""
        from api.notifications.models.schedule import NotificationQueue
        from django.db.models import Count

        rows = (
            NotificationQueue.objects.values('status')
            .annotate(count=Count('id'))
        )
        stats = {row['status']: row['count'] for row in rows}
        stats['total'] = sum(stats.values())
        return stats

    def get_stuck_entries(self, processing_timeout_minutes: int = 10) -> List:
        """
        Return queue entries stuck in 'processing' status longer than timeout.
        Used by recover_stuck_tasks in Celery.
        """
        from api.notifications.models.schedule import NotificationQueue
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(minutes=processing_timeout_minutes)
        return list(
            NotificationQueue.objects.filter(
                status='processing',
                updated_at__lt=cutoff,
            ).select_related('notification')
        )

    def cancel_pending(self, notification_id: int) -> bool:
        """Cancel a waiting queue entry for a notification."""
        from api.notifications.models.schedule import NotificationQueue
        try:
            NotificationQueue.objects.filter(
                notification_id=notification_id,
                status='waiting',
            ).update(status='cancelled', updated_at=timezone.now())
            return True
        except Exception as exc:
            logger.error(f'NotificationQueueService.cancel_pending: {exc}')
            return False


# Singleton
notification_queue_service = NotificationQueueService()
