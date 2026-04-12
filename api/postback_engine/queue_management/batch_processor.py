"""
queue_management/batch_processor.py
─────────────────────────────────────
Batch processing for high-volume postback queues.
Processes multiple postbacks in a single worker invocation
to reduce Celery task overhead and improve throughput.

Used for:
  - Bulk replay of failed postbacks
  - Night-time batch processing of low-priority items
  - Analytics aggregation jobs
"""
from __future__ import annotations
import logging
from typing import List
from django.db import transaction
from ..models import PostbackRawLog, PostbackQueue
from ..enums import QueueStatus, PostbackStatus

logger = logging.getLogger(__name__)


class BatchProcessor:

    def process_batch(
        self,
        worker_id: str,
        batch_size: int = 50,
        dry_run: bool = False,
    ) -> dict:
        """
        Claim and process a batch of queue items.
        Returns processing summary dict.
        """
        from .queue_manager import queue_manager

        items = queue_manager.claim_batch(worker_id=worker_id, batch_size=batch_size)
        if not items:
            return {"claimed": 0, "succeeded": 0, "failed": 0}

        succeeded = 0
        failed = 0

        for item in items:
            if dry_run:
                queue_manager.mark_done(item)
                succeeded += 1
                continue
            try:
                self._process_single(item)
                queue_manager.mark_done(item)
                succeeded += 1
            except Exception as exc:
                logger.error("BatchProcessor: item=%s failed: %s", item.id, exc)
                queue_manager.mark_failed(item, str(exc))
                failed += 1

        result = {
            "worker_id": worker_id,
            "claimed": len(items),
            "succeeded": succeeded,
            "failed": failed,
        }
        logger.info("BatchProcessor: %s", result)
        return result

    def _process_single(self, queue_item: PostbackQueue) -> None:
        """Process one queue item synchronously."""
        from ..services import process_postback
        raw_log = queue_item.raw_log
        process_postback(raw_log)

    def replay_failed(
        self,
        network_key: str = None,
        limit: int = 100,
    ) -> dict:
        """
        Bulk replay all FAILED postbacks, optionally filtered by network.
        Resets retry counts and re-queues for processing.
        """
        from ..tasks import process_postback_task
        qs = PostbackRawLog.objects.filter(status=PostbackStatus.FAILED)
        if network_key:
            qs = qs.filter(network__network_key=network_key)
        qs = qs[:limit]

        count = 0
        for raw_log in qs:
            raw_log.status = PostbackStatus.RECEIVED
            raw_log.retry_count = 0
            raw_log.next_retry_at = None
            raw_log.processing_error = "[Batch replay]"
            raw_log.save(update_fields=[
                "status", "retry_count", "next_retry_at", "processing_error", "updated_at"
            ])
            process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
            count += 1

        logger.info("BatchProcessor.replay_failed: queued %d items", count)
        return {"replayed": count, "network": network_key}

    def bulk_approve_conversions(self, conversion_ids: List[str]) -> int:
        """Bulk approve a list of pending conversions."""
        from ..models import Conversion
        from ..enums import ConversionStatus
        updated = Conversion.objects.filter(
            pk__in=conversion_ids,
            status=ConversionStatus.PENDING,
        ).update(status=ConversionStatus.APPROVED)
        logger.info("BatchProcessor.bulk_approve: approved %d conversions", updated)
        return updated

    def flush_stale_locks(self) -> int:
        """Release stale processing locks from dead workers."""
        from .queue_manager import queue_manager
        released = queue_manager.release_stale_locks()
        logger.info("BatchProcessor.flush_stale_locks: released %d locks", released)
        return released


batch_processor = BatchProcessor()
