"""
queue_management/queue_manager.py – Database + Celery queue management.
"""
import logging
from datetime import timedelta
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from ..enums import QueuePriority, QueueStatus
from ..models import PostbackQueue, PostbackRawLog, RetryLog

logger = logging.getLogger(__name__)

# Lock timeout: if a worker hasn't finished within this window, the item is re-claimable
LOCK_TIMEOUT_SECONDS = 300  # 5 minutes


class QueueManager:
    """
    Manages the postback processing queue.

    Provides:
      - enqueue() — add items to queue with priority
      - claim_batch() — atomically claim items for processing
      - mark_done() — release and complete items
      - release_stale_locks() — recover from dead workers
      - stats() — queue depth and throughput info
    """

    def enqueue(
        self,
        raw_log: PostbackRawLog,
        priority: int = QueuePriority.NORMAL,
        delay_seconds: int = 0,
    ) -> PostbackQueue:
        """Add a raw postback log to the processing queue."""
        process_after = timezone.now() + timedelta(seconds=delay_seconds)
        queue_item = PostbackQueue.objects.create(
            tenant=raw_log.tenant,
            raw_log=raw_log,
            priority=priority,
            status=QueueStatus.PENDING,
            process_after=process_after,
        )
        logger.debug(
            "Enqueued raw_log=%s priority=%d delay=%ds",
            raw_log.id, priority, delay_seconds,
        )
        return queue_item

    @transaction.atomic
    def claim_batch(
        self,
        worker_id: str,
        batch_size: int = 50,
    ) -> List[PostbackQueue]:
        """
        Atomically claim a batch of queue items for processing.
        Uses SELECT FOR UPDATE SKIP LOCKED for concurrency safety.
        """
        now = timezone.now()
        lock_expiry = now + timedelta(seconds=LOCK_TIMEOUT_SECONDS)

        items = list(
            PostbackQueue.objects
            .select_for_update(skip_locked=True)
            .claimable(limit=batch_size)
        )

        ids = [item.pk for item in items]
        if ids:
            PostbackQueue.objects.filter(pk__in=ids).update(
                status=QueueStatus.PROCESSING,
                worker_id=worker_id,
                locked_at=now,
                lock_expires_at=lock_expiry,
                processing_started_at=now,
            )

        logger.info("Worker %s claimed %d queue items", worker_id, len(items))
        return items

    def mark_done(self, queue_item: PostbackQueue):
        """Mark a queue item as successfully processed."""
        queue_item.status = QueueStatus.COMPLETED
        queue_item.processing_finished_at = timezone.now()
        queue_item.save(update_fields=[
            "status", "processing_finished_at", "updated_at",
        ])

    def mark_failed(self, queue_item: PostbackQueue, error: str):
        """Mark a queue item as failed."""
        queue_item.status = QueueStatus.FAILED
        queue_item.error_message = error
        queue_item.processing_finished_at = timezone.now()
        queue_item.save(update_fields=[
            "status", "error_message", "processing_finished_at", "updated_at",
        ])

    def move_to_dead_letter(self, queue_item: PostbackQueue, reason: str):
        """Move an item to the dead letter queue (max retries exceeded)."""
        queue_item.status = QueueStatus.DEAD
        queue_item.error_message = f"Dead letter: {reason}"
        queue_item.save(update_fields=["status", "error_message", "updated_at"])
        logger.warning(
            "Moved queue_item=%s to dead letter: %s", queue_item.id, reason,
        )

    def release_stale_locks(self) -> int:
        """
        Release locks held by dead/stale workers.
        Returns the number of items released back to PENDING.
        """
        stale = PostbackQueue.objects.stale_locks()
        count = stale.update(
            status=QueueStatus.PENDING,
            worker_id="",
            locked_at=None,
            lock_expires_at=None,
        )
        if count > 0:
            logger.warning("Released %d stale queue locks", count)
        return count

    def get_stats(self) -> dict:
        """Return current queue depth and status breakdown."""
        from django.db.models import Count
        breakdown = dict(
            PostbackQueue.objects.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )
        return {
            "pending": breakdown.get(QueueStatus.PENDING, 0),
            "processing": breakdown.get(QueueStatus.PROCESSING, 0),
            "completed": breakdown.get(QueueStatus.COMPLETED, 0),
            "failed": breakdown.get(QueueStatus.FAILED, 0),
            "dead": breakdown.get(QueueStatus.DEAD, 0),
        }

    def purge_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed items older than N hours to keep the table small."""
        cutoff = timezone.now() - timedelta(hours=older_than_hours)
        deleted, _ = PostbackQueue.objects.filter(
            status=QueueStatus.COMPLETED,
            processing_finished_at__lt=cutoff,
        ).delete()
        logger.info("Purged %d completed queue items", deleted)
        return deleted


# Module-level singleton
queue_manager = QueueManager()
