"""
payout_queue/receivers.py  ← FIXED v6

CHANGES v6:

  ① on_payout_item_succeeded() now writes a central audit log entry
      via _write_audit_log("ITEM_SUCCEEDED", ...).

      Before v6: the receiver only wrote to the Python logger.
      Batch completion and permanently-failed items had full BATCH_COMPLETED /
      BATCH_FAILED / ITEM_PERMANENTLY_FAILED audit rows.
      Individual item successes had no audit trail entry at all — making the
      financial audit trail incomplete for compliance purposes.
      Fix: call _write_audit_log() with ITEM_SUCCEEDED + structured payload
      (item_id, batch_id, user_id, net_amount, gateway_reference).

  ② on_payout_item_succeeded() also emits a payout_item_succeeded webhook
      event via _emit_webhook_event(). Previously only batch-level and
      permanently-failed events dispatched webhooks. Merchants receiving
      webhooks had no real-time signal for individual item success.

v3 changes (preserved):
  - _write_audit_log() helper: writes to api.audit_logs when
    PAYOUT_AUDIT_LOG_ENABLED=True (default).
  - on_payout_batch_completed: BATCH_COMPLETED audit entry.
  - on_payout_batch_failed: BATCH_FAILED audit entry.
  - on_payout_item_permanently_failed: ITEM_PERMANENTLY_FAILED audit entry.

v2 FIXES (preserved):
  5. _emit_webhook_event() → real Celery task dispatch (deliver_webhook_event)
  6. _send_notification() → configurable task path via PAYOUT_NOTIFICATION_TASK

v1 FIXES (preserved):
  1–4. _notify_batch_result(), SLA breach detection, structured payloads,
       None-guards on all kwargs.get() calls.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.dispatch import receiver
from django.utils import timezone

from .signals import (
    payout_batch_completed,
    payout_batch_failed,
    payout_item_succeeded,
    payout_item_permanently_failed,
    withdrawal_priority_assigned,
)
from .constants import PAYOUT_SLA_HOURS, URGENT_SLA_HOURS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Batch-level receivers
# ---------------------------------------------------------------------------

@receiver(payout_batch_completed)
def on_payout_batch_completed(sender: Any, **kwargs: Any) -> None:
    """Log and notify on batch completion (COMPLETED or PARTIALLY_COMPLETED)."""
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
        if batch.created_by_id:
            _notify_batch_result(batch, success=True)
        _emit_webhook_event("payout_batch_completed", _batch_payload(batch))
        # v3: central audit log
        _write_audit_log("BATCH_COMPLETED", batch.created_by_id, _batch_payload(batch))
    except Exception as exc:
        logger.exception("on_payout_batch_completed: unexpected error: %s", exc)

@receiver(payout_batch_failed)
def on_payout_batch_failed(sender: Any, **kwargs: Any) -> None:
    """Alert on complete batch failure."""
    batch         = kwargs.get("batch")
    error_summary = kwargs.get("error_summary") or ""
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
        payload                 = _batch_payload(batch)
        payload["error_summary"] = error_summary[:500]
        _emit_webhook_event("payout_batch_failed", payload)
        # v3: central audit log
        _write_audit_log("BATCH_FAILED", batch.created_by_id, payload)
    except Exception as exc:
        logger.exception("on_payout_batch_failed: unexpected error: %s", exc)

# ---------------------------------------------------------------------------
# Item-level receivers
# ---------------------------------------------------------------------------

@receiver(payout_item_succeeded)
def on_payout_item_succeeded(sender: Any, **kwargs: Any) -> None:
    """
    Log individual item success.

    FIX v6: Now writes a central audit log entry (ITEM_SUCCEEDED) and
    dispatches a payout_item_succeeded webhook event.

    Before v6: only wrote to the Python logger.  Batch-level events had full
    audit rows (BATCH_COMPLETED, BATCH_FAILED) but individual item successes
    were invisible in the central audit trail — compliance gap.

    Payload written to audit log:
        item_id, batch_id, user_id, net_amount, gateway_reference
    """
    item = kwargs.get("item")
    if item is None:
        return
    try:
        logger.info(
            "PayoutItem %s SUCCESS: user=%s amount=%s gateway_ref=%s",
            item.id, item.user_id, item.net_amount, item.gateway_reference,
        )

        item_payload = {
            "item_id":           str(item.id),
            "batch_id":          str(item.batch_id),
            "user_id":           item.user_id,
            "net_amount":        str(item.net_amount),
            "gross_amount":      str(item.gross_amount),
            "gateway":           item.gateway,
            "gateway_reference": item.gateway_reference,
            "account_number":    item.account_number,
            "processed_at":      (
                item.processed_at.isoformat() if item.processed_at else None
            ),
        }

        # ── FIX v6: central audit log ────────────────────────────────────────
        # Previously _write_audit_log was never called here — individual item
        # successes were invisible in the central audit trail.
        _write_audit_log("ITEM_SUCCEEDED", item.user_id, item_payload)

        # ── FIX v6: webhook event for item success ───────────────────────────
        # Previously only batch-level and permanently-failed events fired
        # webhooks. Merchants had no real-time signal per item.
        _emit_webhook_event("payout_item_succeeded", item_payload)

    except Exception as exc:
        logger.exception("on_payout_item_succeeded: error: %s", exc)

@receiver(payout_item_permanently_failed)
def on_payout_item_permanently_failed(sender: Any, **kwargs: Any) -> None:
    """
    Alert on permanent item failure (retries exhausted).
    SLA breach detection using constants.PAYOUT_SLA_HOURS / URGENT_SLA_HOURS.
    """
    item = kwargs.get("item")
    if item is None:
        return
    try:
        logger.error(
            "PayoutItem %s PERMANENTLY FAILED: user=%s amount=%s error=%s — %s",
            item.id, item.user_id, item.gross_amount,
            item.error_code, (item.error_message or "")[:100],
        )

        if item.created_at:
            age_hours     = (timezone.now() - item.created_at).total_seconds() / 3600
            sla_threshold = URGENT_SLA_HOURS if getattr(
                item, "priority", None
            ) in ("URGENT", "CRITICAL") else PAYOUT_SLA_HOURS

            if age_hours > sla_threshold:
                logger.critical(
                    "SLA BREACH: PayoutItem %s permanently failed after %.1fh "
                    "(SLA: %dh). user=%s amount=%s",
                    item.id, age_hours, sla_threshold, item.user_id, item.gross_amount,
                )
                _emit_webhook_event("payout_sla_breach", {
                    "item_id":    str(item.id),
                    "user_id":    item.user_id,
                    "amount":     str(item.gross_amount),
                    "age_hours":  round(age_hours, 2),
                    "sla_hours":  sla_threshold,
                    "error_code": item.error_code,
                })

        _emit_webhook_event("payout_item_permanently_failed", {
            "item_id":     str(item.id),
            "user_id":     item.user_id,
            "batch_id":    str(item.batch_id),
            "amount":      str(item.gross_amount),
            "error_code":  item.error_code,
            "retry_count": item.retry_count,
        })
        # v3: central audit log
        _write_audit_log("ITEM_PERMANENTLY_FAILED", item.user_id, {
            "item_id":     str(item.id),
            "batch_id":    str(item.batch_id),
            "user_id":     item.user_id,
            "amount":      str(item.gross_amount),
            "error_code":  item.error_code,
            "retry_count": item.retry_count,
        })

    except Exception as exc:
        logger.exception("on_payout_item_permanently_failed: error: %s", exc)

# ---------------------------------------------------------------------------
# Priority receivers
# ---------------------------------------------------------------------------

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
        _emit_webhook_event("withdrawal_priority_assigned", {
            "user_id":           priority.user_id,
            "priority":          priority.priority,
            "reason":            priority.reason,
            "previous_priority": priority.previous_priority,
        })
    except Exception as exc:
        logger.exception("on_withdrawal_priority_assigned: error: %s", exc)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _batch_payload(batch: Any) -> dict:
    """Normalised event payload for downstream consumers (webhooks, outbox)."""
    return {
        "batch_id":      str(batch.id),
        "batch_name":    batch.name,
        "gateway":       batch.gateway,
        "status":        batch.status,
        "item_count":    batch.item_count,
        "success_count": batch.success_count,
        "failure_count": batch.failure_count,
        "net_amount":    str(batch.net_amount),
        "created_by_id": batch.created_by_id,
    }

def _notify_batch_result(batch: Any, *, success: bool) -> None:
    """
    FIX v2: now calls _send_notification() which dispatches a Celery task
    instead of just logging. Zero-overhead if no PAYOUT_NOTIFICATION_TASK is set.
    """
    try:
        event = "completed" if success else "failed"
        logger.info(
            "_notify_batch_result: batch=%s creator=%s event=%s",
            batch.id, batch.created_by_id, event,
        )
        _send_notification(
            user_id=batch.created_by_id,
            event=event,
            payload=_batch_payload(batch),
        )
    except Exception as exc:
        logger.error("_notify_batch_result: failed: %s", exc)

def _write_audit_log(event_type: str, actor_id: Any, payload: dict) -> None:
    """
    v3: Write a payout event to the central api.audit_logs trail.

    Enabled via settings.PAYOUT_AUDIT_LOG_ENABLED (default True).
    Calls api.audit_logs.payout_integration.log_payout_event().
    Gracefully skips on ImportError so the module works without api.audit_logs.
    Never raises — failure is logged at ERROR level only.
    """
    from django.conf import settings as _settings
    if not getattr(_settings, "PAYOUT_AUDIT_LOG_ENABLED", True):
        return
    try:
        from api.audit_logs.payout_integration import log_payout_event
        log_payout_event(event_type=event_type, actor_id=actor_id, payload=payload)
    except ImportError:
        logger.debug(
            "_write_audit_log: api.audit_logs.payout_integration not found. "
            "Set PAYOUT_AUDIT_LOG_ENABLED=False to suppress."
        )
    except Exception as exc:
        logger.error(
            "_write_audit_log: failed to write audit event=%s: %s", event_type, exc
        )

def _send_notification(user_id: Any, event: str, payload: dict) -> None:
    """
    FIX v2: Dispatches a Celery task whose name is read from settings.

    Configure in settings.py::

        PAYOUT_NOTIFICATION_TASK = "myapp.tasks.send_payout_notification"

    Your task must accept (user_id, event, data)::

        @shared_task
        def send_payout_notification(user_id, event, data):
            # send push / email / in-app notification
            ...

    If PAYOUT_NOTIFICATION_TASK is not set, this function logs a structured
    warning at DEBUG level (no crash, safe for development).
    """
    task_path: str = getattr(settings, "PAYOUT_NOTIFICATION_TASK", "")
    if not task_path:
        logger.debug(
            "_send_notification: PAYOUT_NOTIFICATION_TASK not configured. "
            "user=%s event=%s — skipping (set in settings to enable).",
            user_id, event,
        )
        return

    try:
        module_path, task_name = task_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        task   = getattr(module, task_name)
        task.delay(user_id=user_id, event=event, data=payload)
        logger.debug(
            "_send_notification: dispatched %s for user=%s event=%s",
            task_path, user_id, event,
        )
    except Exception as exc:
        logger.error(
            "_send_notification: failed to dispatch %s for user=%s event=%s: %s",
            task_path, user_id, event, exc,
        )

def _emit_webhook_event(event_type: str, payload: dict) -> None:
    """
    FIX v2: Dispatches a Celery task to POST the event to all URLs in
    settings.PAYOUT_WEBHOOK_URLS.

    Configure in settings.py::

        PAYOUT_WEBHOOK_URLS = [
            "https://your-merchant.com/webhooks/payout/",
            "https://your-monitoring.com/ingest/payout/",
        ]

    The Celery task (deliver_webhook_event in tasks.py) handles:
      - HTTP POST with HMAC-SHA256 signature header (X-Payout-Signature)
      - Retry on timeout / 5xx (up to 3 attempts)
      - Dead-letter logging on exhaustion

    If PAYOUT_WEBHOOK_URLS is empty or unset, this is a no-op (safe for dev).
    """
    urls: list = getattr(settings, "PAYOUT_WEBHOOK_URLS", [])
    if not urls:
        logger.debug(
            "_emit_webhook_event: PAYOUT_WEBHOOK_URLS empty — skipping. "
            "event_type=%s (set in settings to enable webhook dispatch).",
            event_type,
        )
        return

    try:
        from .tasks import deliver_webhook_event
        for url in urls:
            deliver_webhook_event.delay(
                event_type=event_type,
                payload=payload,
                target_url=url,
            )
            logger.debug(
                "_emit_webhook_event: queued delivery → %s event=%s",
                url, event_type,
            )
    except ImportError:
        logger.warning(
            "_emit_webhook_event: deliver_webhook_event task not found in "
            "payout_queue.tasks. Add it (see tasks.py) or set "
            "PAYOUT_WEBHOOK_URLS=[] to suppress this warning.",
        )
    except Exception as exc:
        logger.error(
            "_emit_webhook_event: failed to queue delivery for event=%s: %s",
            event_type, exc,
        )
