"""
postback_handlers/retry_handler.py
────────────────────────────────────
Exponential backoff retry system for failed postback processing
and wallet reward dispatch.

Retry schedule (configurable):
  Attempt 1:  +1 minute
  Attempt 2:  +5 minutes
  Attempt 3:  +30 minutes
  Attempt 4:  +2 hours
  Attempt 5:  +6 hours
  → MAX_RETRIES exceeded → Dead Letter + admin alert

Handles:
  - PostbackRawLog failures (processing errors)
  - Wallet credit failures (RewardDispatchException)
  - Webhook delivery failures
  - Conversion creation failures
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, List, Optional

from django.utils import timezone
from celery import shared_task

from ..constants import MAX_POSTBACK_RETRIES
from ..models import PostbackRawLog, RetryLog
from ..enums import PostbackStatus, QueueStatus

logger = logging.getLogger(__name__)

# ── Retry schedule ─────────────────────────────────────────────────────────────
# Exponential backoff: 1m → 5m → 30m → 2h → 6h
# Index = attempt number (0-based)
RETRY_DELAYS_SECONDS: List[int] = [
    60,        # Attempt 1 — 1 minute
    300,       # Attempt 2 — 5 minutes
    1800,      # Attempt 3 — 30 minutes
    7200,      # Attempt 4 — 2 hours
    21600,     # Attempt 5 — 6 hours
]

# Wallet-specific retry schedule (shorter — wallet failures are usually transient)
WALLET_RETRY_DELAYS_SECONDS: List[int] = [
    30,        # Attempt 1 — 30 seconds
    120,       # Attempt 2 — 2 minutes
    600,       # Attempt 3 — 10 minutes
    3600,      # Attempt 4 — 1 hour
    10800,     # Attempt 5 — 3 hours
]

# Webhook retry schedule
WEBHOOK_RETRY_DELAYS_SECONDS: List[int] = [
    60,        # Attempt 1 — 1 minute
    300,       # Attempt 2 — 5 minutes
    900,       # Attempt 3 — 15 minutes
]


class RetryHandler:
    """
    Manages retry scheduling and tracking for all retry-able operations.
    """

    # ── Postback processing retry ──────────────────────────────────────────────

    def schedule_postback_retry(
        self,
        raw_log: PostbackRawLog,
        error: str,
        exc: Optional[Exception] = None,
    ) -> Optional["RetryLog"]:
        """
        Schedule a failed postback for retry with exponential backoff.
        Returns None if max retries exceeded (moves to dead letter).
        """
        attempt = raw_log.retry_count + 1

        if attempt > MAX_POSTBACK_RETRIES:
            self._move_to_dead_letter(raw_log, error)
            return None

        delay = self._get_delay(attempt, RETRY_DELAYS_SECONDS)
        next_retry_at = timezone.now() + timedelta(seconds=delay)

        # Update raw_log
        raw_log.mark_failed(error=error, next_retry_at=next_retry_at)

        # Write retry log
        retry_log = RetryLog.objects.create(
            retry_type="postback",
            object_id=raw_log.id,
            attempt_number=attempt,
            succeeded=False,
            error_message=error,
            error_traceback=self._format_traceback(exc),
            next_retry_at=next_retry_at,
        )

        # Schedule Celery task
        self._schedule_celery_postback(raw_log, delay)

        logger.info(
            "RetryHandler: postback=%s attempt=%d/%d delay=%ds next=%s",
            raw_log.id, attempt, MAX_POSTBACK_RETRIES, delay, next_retry_at,
        )
        return retry_log

    # ── Wallet reward retry ────────────────────────────────────────────────────

    def schedule_wallet_retry(
        self,
        conversion,
        error: str,
        attempt_number: int = 1,
        exc: Optional[Exception] = None,
    ) -> Optional["RetryLog"]:
        """
        Schedule a failed wallet credit for retry.
        Returns None if max retries exceeded.
        """
        max_wallet_retries = len(WALLET_RETRY_DELAYS_SECONDS)

        if attempt_number > max_wallet_retries:
            logger.error(
                "RetryHandler: wallet credit max retries exceeded for conversion=%s. "
                "MANUAL INTERVENTION REQUIRED.",
                conversion.id,
            )
            self._alert_ops(
                subject="Wallet credit permanently failed",
                message=(
                    f"Conversion {conversion.id} for user {conversion.user_id} "
                    f"could not be credited after {max_wallet_retries} attempts.\n"
                    f"Amount: {conversion.actual_payout} {conversion.currency}\n"
                    f"Points: {conversion.points_awarded}\n"
                    f"Error: {error}"
                ),
            )
            return None

        delay = self._get_delay(attempt_number, WALLET_RETRY_DELAYS_SECONDS)
        next_retry_at = timezone.now() + timedelta(seconds=delay)

        retry_log = RetryLog.objects.create(
            retry_type="reward",
            object_id=conversion.id,
            attempt_number=attempt_number,
            succeeded=False,
            error_message=error,
            error_traceback=self._format_traceback(exc),
            next_retry_at=next_retry_at,
        )

        # Schedule Celery task
        self._schedule_celery_wallet_retry(conversion, attempt_number, delay)

        logger.warning(
            "RetryHandler: wallet retry conversion=%s attempt=%d/%d delay=%ds",
            conversion.id, attempt_number, max_wallet_retries, delay,
        )
        return retry_log

    def mark_wallet_retry_success(self, conversion_id: str) -> None:
        """Mark the latest wallet retry as succeeded."""
        RetryLog.objects.filter(
            retry_type="reward",
            object_id=conversion_id,
            succeeded=False,
        ).order_by("-attempted_at").update(
            succeeded=True,
            next_retry_at=None,
        )

    # ── Webhook retry ──────────────────────────────────────────────────────────

    def schedule_webhook_retry(
        self,
        conversion_id: str,
        webhook_url: str,
        error: str,
        attempt_number: int = 1,
        exc: Optional[Exception] = None,
    ) -> Optional["RetryLog"]:
        """Schedule a failed webhook delivery for retry."""
        import uuid
        max_retries = len(WEBHOOK_RETRY_DELAYS_SECONDS)

        if attempt_number > max_retries:
            logger.warning(
                "RetryHandler: webhook max retries exceeded: url=%s", webhook_url
            )
            return None

        delay = self._get_delay(attempt_number, WEBHOOK_RETRY_DELAYS_SECONDS)
        next_retry_at = timezone.now() + timedelta(seconds=delay)

        retry_log = RetryLog.objects.create(
            retry_type="webhook",
            object_id=uuid.UUID(conversion_id),
            attempt_number=attempt_number,
            succeeded=False,
            error_message=error,
            error_traceback=self._format_traceback(exc),
            response_data={"url": webhook_url},
            next_retry_at=next_retry_at,
        )

        from ..tasks import send_webhook_notification
        send_webhook_notification.apply_async(
            args=[conversion_id],
            countdown=delay,
        )

        return retry_log

    # ── Batch retry runner (called by Celery beat) ─────────────────────────────

    def run_due_retries(self, batch_size: int = 100) -> dict:
        """
        Pick up all postbacks that are due for retry and re-queue them.
        Called by the `retry_failed_postbacks` Celery beat task.
        """
        from ..tasks import process_postback_task

        now = timezone.now()
        due = PostbackRawLog.objects.filter(
            status=PostbackStatus.FAILED,
            next_retry_at__lte=now,
            retry_count__lt=MAX_POSTBACK_RETRIES,
        ).select_related("network")[:batch_size]

        queued = 0
        skipped = 0
        for raw_log in due:
            if raw_log.network_id is None:
                skipped += 1
                continue
            process_postback_task.apply_async(
                args=[str(raw_log.id)],
                countdown=0,
            )
            queued += 1

        logger.info("RetryHandler.run_due_retries: queued=%d skipped=%d", queued, skipped)
        return {"queued": queued, "skipped": skipped}

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _get_delay(attempt: int, schedule: List[int]) -> int:
        """
        Get the delay for a given attempt number (1-based).
        Clamps to the last value in the schedule for overflow.
        """
        idx = max(0, min(attempt - 1, len(schedule) - 1))
        return schedule[idx]

    def _move_to_dead_letter(self, raw_log: PostbackRawLog, error: str) -> None:
        """Move a permanently failed postback to dead-letter status."""
        raw_log.status = PostbackStatus.FAILED
        raw_log.processing_error = f"[DEAD LETTER after {raw_log.retry_count} retries] {error}"
        raw_log.next_retry_at = None
        raw_log.save(update_fields=[
            "status", "processing_error", "next_retry_at", "updated_at",
        ])

        # Attempt to move queue entry to dead letter state
        try:
            from ..models import PostbackQueue
            PostbackQueue.objects.filter(raw_log=raw_log).update(
                status=QueueStatus.DEAD,
                error_message=f"Max retries exceeded: {error}",
            )
        except Exception:
            pass

        self._alert_ops(
            subject=f"Postback dead-letter: {raw_log.network.network_key}",
            message=(
                f"PostbackRawLog {raw_log.id} failed permanently after "
                f"{raw_log.retry_count} retries.\n"
                f"Network: {raw_log.network.network_key}\n"
                f"Lead: {raw_log.lead_id}\n"
                f"Error: {error}"
            ),
        )
        logger.error(
            "RetryHandler: dead-letter raw_log=%s network=%s lead=%s after %d retries",
            raw_log.id, raw_log.network.network_key, raw_log.lead_id, raw_log.retry_count,
        )

    @staticmethod
    def _alert_ops(subject: str, message: str) -> None:
        """
        Send an alert to the ops team.
        In production: integrate with PagerDuty, Slack, or email.
        """
        try:
            from ..signals import reward_failed
            reward_failed.send(
                sender=RetryHandler,
                subject=subject,
                message=message,
            )
        except Exception as exc:
            logger.error("RetryHandler._alert_ops failed: %s", exc)

    @staticmethod
    def _format_traceback(exc: Optional[Exception]) -> str:
        if exc is None:
            return ""
        import traceback
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    @staticmethod
    def _schedule_celery_postback(raw_log: PostbackRawLog, delay: int) -> None:
        try:
            from ..tasks import process_postback_task
            process_postback_task.apply_async(
                args=[str(raw_log.id)],
                countdown=delay,
            )
        except Exception as exc:
            logger.error(
                "RetryHandler: could not schedule Celery retry for raw_log=%s: %s",
                raw_log.id, exc,
            )

    @staticmethod
    def _schedule_celery_wallet_retry(conversion, attempt: int, delay: int) -> None:
        try:
            from ..tasks import retry_wallet_credit_task
            retry_wallet_credit_task.apply_async(
                args=[str(conversion.id)],
                kwargs={"attempt_number": attempt + 1},
                countdown=delay,
            )
        except Exception as exc:
            logger.error(
                "RetryHandler: could not schedule wallet retry for conversion=%s: %s",
                conversion.id, exc,
            )


# ── Module-level singleton ─────────────────────────────────────────────────────
retry_handler = RetryHandler()


# ── Celery task for wallet credit retry ───────────────────────────────────────

@shared_task(
    name="postback_engine.tasks.retry_wallet_credit",
    bind=True,
    max_retries=0,      # RetryHandler manages its own retry schedule
    acks_late=True,
)
def retry_wallet_credit_task(self, conversion_id: str, attempt_number: int = 2):
    """
    Celery task: retry a failed wallet credit.
    Called by RetryHandler._schedule_celery_wallet_retry().
    """
    from ..models import Conversion
    from ..services import _dispatch_reward

    try:
        conversion = Conversion.objects.select_related(
            "user", "network"
        ).get(pk=conversion_id)
    except Conversion.DoesNotExist:
        logger.error("retry_wallet_credit: conversion %s not found", conversion_id)
        return

    if conversion.wallet_credited:
        logger.info("retry_wallet_credit: %s already credited, skipping", conversion_id)
        retry_handler.mark_wallet_retry_success(conversion_id)
        return

    try:
        _dispatch_reward(conversion=conversion, network=conversion.network)
        retry_handler.mark_wallet_retry_success(conversion_id)
        logger.info(
            "retry_wallet_credit: SUCCESS conversion=%s attempt=%d",
            conversion_id, attempt_number,
        )
    except Exception as exc:
        retry_handler.schedule_wallet_retry(
            conversion=conversion,
            error=str(exc),
            attempt_number=attempt_number,
            exc=exc,
        )
