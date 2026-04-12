"""
queue_management/dead_letter_queue.py
───────────────────────────────────────
Dead letter queue for postbacks that exhausted all retry attempts.
Provides inspection, manual replay, and purge capabilities.
"""
from __future__ import annotations
import logging
from django.utils import timezone
from ..models import PostbackQueue, PostbackRawLog
from ..enums import QueueStatus, PostbackStatus

logger = logging.getLogger(__name__)


class DeadLetterQueue:

    def get_all(self, limit: int = 100):
        """Return all dead-letter items."""
        return PostbackQueue.objects.filter(
            status=QueueStatus.DEAD
        ).select_related("raw_log__network").order_by("-raw_log__received_at")[:limit]

    def count(self) -> int:
        return PostbackQueue.objects.filter(status=QueueStatus.DEAD).count()

    def replay(self, queue_item: PostbackQueue) -> bool:
        """
        Move a dead-letter item back to PENDING for re-processing.
        Resets retry count.
        """
        try:
            raw_log = queue_item.raw_log
            raw_log.status = PostbackStatus.RECEIVED
            raw_log.retry_count = 0
            raw_log.next_retry_at = None
            raw_log.processing_error = ""
            raw_log.save(update_fields=[
                "status", "retry_count", "next_retry_at", "processing_error", "updated_at"
            ])
            queue_item.status = QueueStatus.PENDING
            queue_item.error_message = ""
            queue_item.save(update_fields=["status", "error_message", "updated_at"])

            from ..tasks import process_postback_task
            process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
            logger.info("DLQ: replayed raw_log=%s", raw_log.id)
            return True
        except Exception as exc:
            logger.error("DLQ.replay failed: %s", exc)
            return False

    def replay_all(self, limit: int = 100) -> int:
        """Replay all dead-letter items. Returns count replayed."""
        items = self.get_all(limit=limit)
        count = sum(1 for item in items if self.replay(item))
        logger.info("DLQ.replay_all: replayed %d/%d items", count, len(list(items)))
        return count

    def purge(self, older_than_days: int = 30) -> int:
        """Permanently delete old dead-letter items."""
        cutoff = timezone.now() - timezone.timedelta(days=older_than_days)
        deleted, _ = PostbackQueue.objects.filter(
            status=QueueStatus.DEAD,
            raw_log__received_at__lt=cutoff,
        ).delete()
        logger.info("DLQ.purge: deleted %d items older than %dd", deleted, older_than_days)
        return deleted


dead_letter_queue = DeadLetterQueue()
