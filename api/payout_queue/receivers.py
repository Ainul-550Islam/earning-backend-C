"""
Payout Queue Signal Receivers — Connected in PayoutQueueConfig.ready().
All receivers are defensive: exceptions are caught and logged.
"""

from __future__ import annotations

import logging
from typing import Any

from django.dispatch import receiver

from .signals import (
    payout_batch_completed,
    payout_batch_failed,
    payout_item_succeeded,
    payout_item_permanently_failed,
    withdrawal_priority_assigned,
)

logger = logging.getLogger(__name__)


@receiver(payout_batch_completed)
def on_payout_batch_completed(sender: Any, **kwargs: Any) -> None:
    """Log and notify on batch completion."""
    batch = kwargs.get("batch")
    if batch is None:
        logger.error("on_payout_batch_completed: 'batch' missing in kwargs.")
        return
    try:
        logger.info(
            "PayoutBatch %s completed: status=%s success=%d failed=%d amount=%s",
            batch.id, batch.status, batch.success_count,
            batch.failure_count, batch.net_amount,
        )
        # Notify admin/creator if available
        if batch.created_by_id:
            _notify_batch_result(batch, success=True)
    except Exception as exc:
        logger.exception("on_payout_batch_completed: unexpected error: %s", exc)


@receiver(payout_batch_failed)
def on_payout_batch_failed(sender: Any, **kwargs: Any) -> None:
    """Alert on complete batch failure."""
    batch = kwargs.get("batch")
    error_summary = kwargs.get("error_summary", "")
    if batch is None:
        logger.error("on_payout_batch_failed: 'batch' missing in kwargs.")
        return
    try:
        logger.error(
            "PayoutBatch %s FAILED: items=%d summary=%r",
            batch.id, batch.item_count, error_summary[:200],
        )
        if batch.created_by_id:
            _notify_batch_result(batch, success=False)
    except Exception as exc:
        logger.exception("on_payout_batch_failed: unexpected error: %s", exc)


@receiver(payout_item_succeeded)
def on_payout_item_succeeded(sender: Any, **kwargs: Any) -> None:
    """Log individual item success for audit trail."""
    item = kwargs.get("item")
    if item is None:
        return
    try:
        logger.info(
            "PayoutItem %s SUCCESS: user=%s amount=%s gateway_ref=%s",
            item.id, item.user_id, item.net_amount, item.gateway_reference,
        )
    except Exception as exc:
        logger.exception("on_payout_item_succeeded: error: %s", exc)


@receiver(payout_item_permanently_failed)
def on_payout_item_permanently_failed(sender: Any, **kwargs: Any) -> None:
    """Alert on permanent item failure (retries exhausted)."""
    item = kwargs.get("item")
    if item is None:
        return
    try:
        logger.error(
            "PayoutItem %s PERMANENTLY FAILED: user=%s amount=%s error=%s — %s",
            item.id, item.user_id, item.gross_amount,
            item.error_code, item.error_message[:100],
        )
        # Could trigger a support ticket creation here
    except Exception as exc:
        logger.exception("on_payout_item_permanently_failed: error: %s", exc)


@receiver(withdrawal_priority_assigned)
def on_withdrawal_priority_assigned(sender: Any, **kwargs: Any) -> None:
    """Log priority assignment/escalation."""
    priority = kwargs.get("priority")
    if priority is None:
        return
    try:
        logger.info(
            "WithdrawalPriority assigned: user=%s priority=%s reason=%s (prev=%s)",
            priority.user_id, priority.priority,
            priority.reason, priority.previous_priority,
        )
    except Exception as exc:
        logger.exception("on_withdrawal_priority_assigned: error: %s", exc)


def _notify_batch_result(batch: Any, *, success: bool) -> None:
    """Placeholder: notify the batch creator via email/push."""
    try:
        logger.debug(
            "_notify_batch_result: batch=%s creator=%s success=%s",
            batch.id, batch.created_by_id, success,
        )
        # Integrate with email/push notification service here
    except Exception as exc:
        logger.error("_notify_batch_result: failed: %s", exc)
