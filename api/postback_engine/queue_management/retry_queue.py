"""
queue_management/retry_queue.py
────────────────────────────────
Manages the retry queue — postbacks that failed and need re-processing.
Provides scheduled pickup, backoff enforcement, and promotion to dead letter.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.utils import timezone
from ..models import PostbackRawLog, PostbackQueue
from ..enums import PostbackStatus, QueueStatus, QueuePriority
from ..constants import MAX_POSTBACK_RETRIES

logger = logging.getLogger(__name__)


class RetryQueue:

    def enqueue_failed(self, raw_log: PostbackRawLog, delay_seconds: int) -> bool:
        """
        Add a failed postback to the retry queue after the specified delay.
        Returns False if max retries exceeded (moves to dead letter instead).
        """
        if raw_log.retry_count >= MAX_POSTBACK_RETRIES:
            self._move_to_dead_letter(raw_log)
            return False

        process_after = timezone.now() + timedelta(seconds=delay_seconds)

        PostbackQueue.objects.filter(raw_log=raw_log).update(
            status=QueueStatus.PENDING,
            process_after=process_after,
            priority=QueuePriority.NORMAL,
            worker_id="",
            locked_at=None,
            lock_expires_at=None,
            error_message=raw_log.processing_error,
        )

        logger.info(
            "RetryQueue: raw_log=%s attempt=%d/%d retry_in=%ds",
            raw_log.id, raw_log.retry_count, MAX_POSTBACK_RETRIES, delay_seconds,
        )
        return True

    def get_due(self, limit: int = 100):
        """Return retry items that are now due for processing."""
        return (
            PostbackQueue.objects.filter(
                status=QueueStatus.PENDING,
                process_after__lte=timezone.now(),
                raw_log__status=PostbackStatus.FAILED,
                raw_log__retry_count__lt=MAX_POSTBACK_RETRIES,
            )
            .select_related("raw_log__network")
            .order_by("process_after")
        )[:limit]

    def process_due(self) -> int:
        """Pick up all due retry items and re-queue them in Celery. Returns count."""
        from ..tasks import process_postback_task
        due = self.get_due()
        count = 0
        for item in due:
            try:
                process_postback_task.apply_async(
                    args=[str(item.raw_log_id)], countdown=0
                )
                count += 1
            except Exception as exc:
                logger.error("RetryQueue: failed to dispatch raw_log=%s: %s", item.raw_log_id, exc)
        logger.info("RetryQueue.process_due: dispatched %d tasks", count)
        return count

    def get_stats(self) -> dict:
        from django.db.models import Count
        qs = PostbackQueue.objects.filter(
            status=QueueStatus.PENDING,
            raw_log__status=PostbackStatus.FAILED,
        )
        return {
            "pending_retries": qs.count(),
            "due_now": qs.filter(process_after__lte=timezone.now()).count(),
            "max_attempts": MAX_POSTBACK_RETRIES,
        }

    def _move_to_dead_letter(self, raw_log: PostbackRawLog) -> None:
        PostbackQueue.objects.filter(raw_log=raw_log).update(
            status=QueueStatus.DEAD,
            error_message=f"[DEAD] Max {MAX_POSTBACK_RETRIES} retries exceeded.",
        )
        logger.error(
            "RetryQueue: raw_log=%s moved to dead letter after %d retries",
            raw_log.id, raw_log.retry_count,
        )


retry_queue = RetryQueue()
