"""
Payout Queue Celery Tasks — Async batch processing and retry tasks.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from .exceptions import (
    PayoutBatchNotFoundError,
    PayoutBatchStateError,
    PayoutBatchLockedError,
    PayoutBatchLimitError,
    PayoutQueueError,
)

logger = logging.getLogger(__name__)

DEFAULT_RETRY_DELAY = 120
DEFAULT_MAX_RETRIES = 3
BACKOFF_MULTIPLIER = 2


@shared_task(
    bind=True,
    max_retries=DEFAULT_MAX_RETRIES,
    default_retry_delay=DEFAULT_RETRY_DELAY,
    name="payout_queue.process_batch_async",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_batch_async(
    self,
    batch_id: Any,
    *,
    actor_id: Optional[Any] = None,
) -> dict:
    """
    Celery task: process a PayoutBatch asynchronously.

    Uses the task ID as the worker_id for the advisory lock.
    Retries on transient failures. Does NOT retry on permanent failures
    (batch not found, wrong state, concurrent limit).

    Args:
        batch_id: PK of the PayoutBatch.
        actor_id: PK of the triggering user (optional).

    Returns:
        Processing result dict from services.process_batch().
    """
    task_id = self.request.id or str(uuid.uuid4())
    logger.info(
        "[task=%s] process_batch_async started: batch=%s actor=%s",
        task_id, batch_id, actor_id,
    )

    if not batch_id:
        logger.error("[task=%s] process_batch_async: batch_id is required.", task_id)
        return {"error": "batch_id is required.", "task_id": task_id}

    try:
        from . import services
        result = services.process_batch(
            batch_id=batch_id,
            worker_id=task_id,
            actor_id=actor_id,
        )
    except (PayoutBatchNotFoundError, PayoutBatchStateError) as exc:
        # Permanent failures — do not retry
        logger.error(
            "[task=%s] process_batch_async: permanent failure: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except PayoutBatchLockedError as exc:
        # Another worker has the lock — retry after backoff
        retry_count = self.request.retries
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] process_batch_async: batch locked (attempt %d/%d). Retry in %ds.",
            task_id, retry_count + 1, DEFAULT_MAX_RETRIES, delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            return {"error": str(exc), "max_retries_exceeded": True, "task_id": task_id}
    except PayoutBatchLimitError as exc:
        # Concurrent limit reached — retry
        retry_count = self.request.retries
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] process_batch_async: concurrent limit (attempt %d/%d). Retry in %ds.",
            task_id, retry_count + 1, DEFAULT_MAX_RETRIES, delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] process_batch_async: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=DEFAULT_RETRY_DELAY)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    logger.info(
        "[task=%s] process_batch_async completed: batch=%s status=%s success=%d failed=%d",
        task_id,
        batch_id,
        result.get("status"),
        result.get("success_count", 0),
        result.get("failure_count", 0),
    )
    return result


@shared_task(
    bind=True,
    max_retries=1,
    name="payout_queue.process_due_batches",
    acks_late=True,
)
def process_due_batches(self) -> dict:
    """
    Celery beat task: find all PENDING batches due for processing and dispatch them.
    Runs every minute via Celery Beat.

    Returns:
        Dict with dispatched_count and errors.
    """
    task_id = self.request.id or "beat"
    logger.info("[task=%s] process_due_batches started.", task_id)

    from .models import PayoutBatch
    due = PayoutBatch.objects.due_for_processing()

    dispatched = 0
    errors = []

    for batch in due:
        try:
            process_batch_async.delay(str(batch.id))
            dispatched += 1
            logger.info(
                "[task=%s] Dispatched batch %s for async processing.", task_id, batch.id
            )
        except Exception as exc:
            err = f"batch {batch.id}: {exc}"
            logger.error("[task=%s] Failed to dispatch: %s", task_id, err)
            errors.append(err)

    logger.info(
        "[task=%s] process_due_batches: dispatched=%d errors=%d",
        task_id, dispatched, len(errors),
    )
    return {"dispatched_count": dispatched, "errors": errors, "task_id": task_id}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="payout_queue.retry_due_items",
    acks_late=True,
)
def retry_due_items(self, batch_id: Optional[Any] = None) -> dict:
    """
    Celery beat task: retry all RETRYING items that are due.

    Args:
        batch_id: If set, only retry items from this batch.

    Returns:
        Dict with retried_count, success_count, failure_count.
    """
    task_id = self.request.id or str(uuid.uuid4())
    logger.info("[task=%s] retry_due_items started batch=%s.", task_id, batch_id)

    try:
        from . import services
        result = services.retry_failed_items(
            batch_id=batch_id, worker_id=task_id
        )
    except PayoutQueueError as exc:
        logger.error("[task=%s] retry_due_items: error: %s", task_id, exc)
        return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception("[task=%s] retry_due_items: unexpected: %s", task_id, exc)
        try:
            raise self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}

    result["task_id"] = task_id
    return result


@shared_task(
    bind=True,
    max_retries=1,
    name="payout_queue.expire_withdrawal_priorities",
    acks_late=True,
)
def expire_withdrawal_priorities(self) -> dict:
    """
    Celery beat task: deactivate expired WithdrawalPriority records.
    """
    task_id = self.request.id or "beat"
    try:
        from .managers import WithdrawalPriorityManager
        from .models import WithdrawalPriority
        count = WithdrawalPriority.objects.expire_stale()
        logger.info(
            "[task=%s] expire_withdrawal_priorities: deactivated %d records.", task_id, count
        )
        return {"deactivated_count": count, "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] expire_withdrawal_priorities: error: %s", task_id, exc
        )
        return {"error": str(exc), "task_id": task_id}


@shared_task(
    bind=True,
    max_retries=1,
    name="payout_queue.release_stale_locks",
    acks_late=True,
)
def release_stale_locks(self, timeout_seconds: int = 3600) -> dict:
    """
    Celery beat task: release advisory locks on batches stuck longer than
    timeout_seconds (e.g. due to worker crash).

    Args:
        timeout_seconds: Lock age threshold in seconds.

    Returns:
        Dict with released_count.
    """
    task_id = self.request.id or "beat"
    try:
        from .models import PayoutBatch
        from django.utils import timezone
        from datetime import timedelta

        stale = PayoutBatch.objects.stale_locked(timeout_seconds)
        count = stale.count()
        if count:
            stale.update(locked_at=None, locked_by="")
            logger.warning(
                "[task=%s] release_stale_locks: released %d stale locks.", task_id, count
            )
        return {"released_count": count, "task_id": task_id}
    except Exception as exc:
        logger.exception("[task=%s] release_stale_locks: error: %s", task_id, exc)
        return {"error": str(exc), "task_id": task_id}
