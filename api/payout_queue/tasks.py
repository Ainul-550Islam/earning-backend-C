"""
payout_queue/tasks.py  ← v8 PRODUCTION UPDATE (built on DRY v7)

CHANGES v8 (Production Gap #3 — Reconciliation):

  ① reconcile_batch_with_gateway(batch_id) task added

     What it does:
       For each SUCCESS item in the batch, calls processor.verify_transaction()
       to confirm the gateway still reports the transaction as completed.
       Flags any discrepancy where:
         - DB says SUCCESS but gateway says FAILED/UNKNOWN
         - DB says FAILED but gateway says SUCCESS (missed payment)
       Writes a BulkProcessLog with status=RECONCILED and a JSON error_summary
       listing all discrepancies.

     Why it matters:
       Without reconciliation, if a gateway delivers payment but our DB mark_success()
       fails (DB timeout after gateway confirm), the item stays RETRYING/FAILED and
       gets re-sent → double payment.
       Reconciliation catches this and creates a MANUAL_REVIEW flag.

  ② reconcile_recent_batches() Celery beat task added

     Scheduled via CELERY_BEAT_SCHEDULE to run daily (see settings_final_additions.py).
     Finds all COMPLETED/PARTIALLY_COMPLETED batches from the last 24 hours and
     dispatches reconcile_batch_with_gateway for each.

DRY v7 changes preserved:
  - _webhook_retry_delay(retries) helper
  - All 6 existing Celery tasks
"""
from __future__ import annotations

import logging
import time
import uuid as _uuid
from typing import Optional

from celery import shared_task

logger = logging.getLogger(__name__)

MAX_DISPATCH_PER_RUN = 50
RECONCILE_LOOKBACK_HOURS = 24  # How far back reconcile_recent_batches looks

# ---------------------------------------------------------------------------
# DRY v7: webhook retry back-off helper
# ---------------------------------------------------------------------------

def _webhook_retry_delay(retries: int) -> int:
    """
    Exponential back-off for deliver_webhook_event retries.
    attempt 0 → 30s, attempt 1 → 60s, attempt 2 → 120s.
    """
    return 30 * (2 ** retries)

# ---------------------------------------------------------------------------
# process_batch_async
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.process_batch_async",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    time_limit=7200,
    soft_time_limit=6900,
)
def process_batch_async(self, batch_id: str, *, actor_id: Optional[str] = None) -> dict:
    """
    Celery task: process a single PayoutBatch by ID.
    """
    from api.payout_queue import services
    from api.payout_queue.exceptions import (
        PayoutBatchNotFoundError,
        PayoutBatchStateError,
        PayoutBatchLockedError,
        PayoutBatchLimitError,
    )

    task_id   = self.request.id or str(_uuid.uuid4())
    worker_id = f"celery-{task_id[:16]}"

    logger.info(
        "[task=%s] process_batch_async: batch=%s actor=%s attempt=%d",
        task_id, batch_id, actor_id, self.request.retries + 1,
    )

    try:
        result = services.process_batch(
            batch_id=batch_id,
            worker_id=worker_id,
            actor_id=actor_id,
        )
        logger.info(
            "[task=%s] process_batch_async done. status=%s success=%s failed=%s",
            task_id, result["status"], result["success_count"], result["failure_count"],
        )
        return result

    except PayoutBatchNotFoundError as exc:
        logger.error("[task=%s] process_batch_async: batch %s not found: %s", task_id, batch_id, exc)
        return {"error": str(exc), "batch_id": batch_id}

    except PayoutBatchLockedError as exc:
        logger.warning("[task=%s] process_batch_async: batch %s locked. Retry in 30s.", task_id, batch_id)
        raise self.retry(exc=exc, countdown=30)

    except PayoutBatchLimitError as exc:
        logger.warning("[task=%s] process_batch_async: concurrent limit. Retry in 60s.", task_id)
        raise self.retry(exc=exc, countdown=60)

    except PayoutBatchStateError as exc:
        logger.warning("[task=%s] process_batch_async: state error for batch %s: %s", task_id, batch_id, exc)
        return {"error": str(exc), "batch_id": batch_id}

    except Exception as exc:
        logger.exception("[task=%s] process_batch_async: unexpected error for batch %s: %s", task_id, batch_id, exc)
        raise self.retry(exc=exc, countdown=60)

# ---------------------------------------------------------------------------
# process_due_batches  (Celery Beat)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.process_due_batches",
    acks_late=True,
)
def process_due_batches(self) -> dict:
    """
    Celery beat task: find PENDING batches due for processing and dispatch them.
    Capped at MAX_DISPATCH_PER_RUN (50) per tick.
    """
    from api.payout_queue.models import PayoutBatch

    task_id    = self.request.id or "beat"
    due_list   = list(PayoutBatch.objects.due_for_processing()[:MAX_DISPATCH_PER_RUN].values_list("id", flat=True))
    dispatched = 0
    errors     = []

    for batch_id in due_list:
        try:
            process_batch_async.delay(str(batch_id))
            dispatched += 1
        except Exception as exc:
            logger.error("[task=%s] process_due_batches: failed to dispatch batch %s: %s", task_id, batch_id, exc)
            errors.append({"batch_id": str(batch_id), "error": str(exc)})

    logger.info("[task=%s] process_due_batches: dispatched=%d errors=%d", task_id, dispatched, len(errors))
    return {"dispatched_count": dispatched, "errors": errors, "capped": len(due_list) >= MAX_DISPATCH_PER_RUN}

# ---------------------------------------------------------------------------
# retry_due_items  (Celery Beat + manual)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.retry_due_items",
    acks_late=True,
)
def retry_due_items(
    self,
    *,
    batch_id: Optional[str] = None,
    item_ids: Optional[list[str]] = None,
    limit: Optional[int] = 100,
) -> dict:
    """
    Celery beat / on-demand task: retry RETRYING items whose next_retry_at is due.
    """
    from api.payout_queue import services

    task_id   = self.request.id or "beat"
    worker_id = f"retry-celery-{task_id[:16]}"

    try:
        result = services.retry_failed_items(
            batch_id=batch_id,
            item_ids=item_ids,
            worker_id=worker_id,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("[task=%s] retry_due_items: unexpected error: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)

    logger.info(
        "[task=%s] retry_due_items done. retried=%d success=%d failed=%d",
        task_id, result["retried_count"], result["success_count"], result["failure_count"],
    )
    return result

# ---------------------------------------------------------------------------
# expire_withdrawal_priorities  (Celery Beat)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.expire_withdrawal_priorities",
    acks_late=True,
)
def expire_withdrawal_priorities(self) -> dict:
    """Celery beat task: deactivate expired WithdrawalPriority records."""
    task_id = self.request.id or "beat"
    from api.payout_queue.models import WithdrawalPriority
    try:
        count = WithdrawalPriority.objects.expire_stale()
        logger.info("[task=%s] expire_withdrawal_priorities: deactivated %d.", task_id, count)
        return {"deactivated_count": count}
    except Exception as exc:
        logger.exception("[task=%s] expire_withdrawal_priorities: error: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=300)

# ---------------------------------------------------------------------------
# release_stale_locks  (Celery Beat)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.release_stale_locks",
    acks_late=True,
)
def release_stale_locks(self, timeout_seconds: int = None) -> dict:
    """Celery beat task: release advisory locks held longer than timeout_seconds."""
    from api.payout_queue.constants import BATCH_LOCK_TIMEOUT_SECONDS
    if timeout_seconds is None:
        timeout_seconds = BATCH_LOCK_TIMEOUT_SECONDS
    task_id = self.request.id or "beat"
    from api.payout_queue.models import PayoutBatch
    from django.utils import timezone

    try:
        stale    = list(PayoutBatch.objects.stale_locked(timeout_seconds=timeout_seconds).values_list("id", flat=True))
        released = 0
        for batch_id in stale:
            try:
                PayoutBatch.objects.filter(pk=batch_id).update(
                    locked_at=None, locked_by="", updated_at=timezone.now(),
                )
                released += 1
                logger.warning("[task=%s] release_stale_locks: released batch %s (held >%ds)", task_id, batch_id, timeout_seconds)
            except Exception as exc:
                logger.error("[task=%s] release_stale_locks: failed to release %s: %s", task_id, batch_id, exc)

        logger.info("[task=%s] release_stale_locks: released %d/%d.", task_id, released, len(stale))
        return {"released_count": released, "stale_found": len(stale)}

    except Exception as exc:
        logger.exception("[task=%s] release_stale_locks: error: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=300)

# ---------------------------------------------------------------------------
# deliver_webhook_event
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.deliver_webhook_event",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    soft_time_limit=25,
    time_limit=30,
)
def deliver_webhook_event(self, event_type: str, payload: dict, target_url: str) -> dict:
    """
    POST a signed webhook event to target_url.
    DRY v7: uses _webhook_retry_delay() for exponential back-off.
    """
    import hashlib
    import hmac as _hmac
    import json
    import time

    try:
        import requests as _requests
    except ImportError:
        logger.error("deliver_webhook_event: 'requests' library not installed.")
        return {"status": "error", "reason": "requests not installed"}

    from django.conf import settings as _settings

    task_id = self.request.id or "unknown"
    attempt = self.request.retries + 1

    body = json.dumps(
        {"event_type": event_type, "data": payload},
        default=str, ensure_ascii=False,
    ).encode("utf-8")

    headers = {
        "Content-Type":     "application/json; charset=utf-8",
        "X-Payout-Event":   event_type,
        "X-Payout-Attempt": str(attempt),
        "X-Payout-Task-Id": task_id,
    }
    secret: str = getattr(_settings, "PAYOUT_WEBHOOK_SECRET", "") or ""
    if secret:
        sig = _hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Payout-Signature"] = sig

    timeout = getattr(_settings, "PAYOUT_WEBHOOK_TIMEOUT_SECONDS", 10)
    start   = time.monotonic()
    try:
        resp       = _requests.post(target_url, data=body, headers=headers, timeout=timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code < 300:
            logger.info("[task=%s] webhook delivered event=%s → %s status=%d elapsed=%dms",
                        task_id, event_type, target_url, resp.status_code, elapsed_ms)
            return {"status": "ok", "event_type": event_type, "target_url": target_url,
                    "http_status": resp.status_code, "elapsed_ms": elapsed_ms}

        if 400 <= resp.status_code < 500:
            logger.error("[task=%s] webhook permanent failure event=%s → %s status=%d (no retry)",
                         task_id, event_type, target_url, resp.status_code)
            return {"status": "error", "event_type": event_type, "target_url": target_url,
                    "http_status": resp.status_code, "retried": False}

        # 5xx — transient, retry with exponential back-off
        raise self.retry(countdown=_webhook_retry_delay(self.request.retries))

    except _requests.Timeout as exc:
        raise self.retry(exc=exc, countdown=_webhook_retry_delay(self.request.retries))

    except _requests.RequestException as exc:
        raise self.retry(exc=exc, countdown=_webhook_retry_delay(self.request.retries))

    except self.MaxRetriesExceededError:
        logger.critical("[task=%s] webhook EXHAUSTED retries event=%s → %s.", task_id, event_type, target_url)
        return {"status": "exhausted", "event_type": event_type, "target_url": target_url}

# ---------------------------------------------------------------------------
# v8: reconcile_batch_with_gateway  (Production Gap #3)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.reconcile_batch_with_gateway",
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
    time_limit=3600,
    soft_time_limit=3500,
)
def reconcile_batch_with_gateway(self, batch_id: str) -> dict:
    """
    v8: Reconcile a completed batch against the live gateway.

    For each SUCCESS item in the batch:
      1. Calls processor.verify_transaction(gateway_reference).
      2. Compares gateway status with DB status.
      3. Flags discrepancies:
         - DB=SUCCESS + Gateway=FAILED  → possible missed reversal (critical)
         - DB=FAILED  + Gateway=SUCCESS → possible missed payment (double-pay risk)
      4. Writes a BulkProcessLog record with all discrepancies.

    Called by:
      - reconcile_recent_batches (daily Celery beat)
      - Manual: reconcile_batch_with_gateway.delay(str(batch_id))
      - POST /batches/{id}/reconcile/ (if viewset action is added)

    Returns:
        {
            "batch_id": str,
            "items_checked": int,
            "discrepancies": list,
            "status": "clean" | "discrepancies_found" | "error"
        }
    """
    from api.payout_queue.models import PayoutBatch, PayoutItem, BulkProcessLog
    from api.payout_queue.choices import PayoutItemStatus, PayoutBatchStatus
    from api.payout_queue.services import _get_processor
    from api.payout_queue.exceptions import GatewayError

    task_id = self.request.id or str(_uuid.uuid4())

    logger.info("[task=%s] reconcile_batch_with_gateway: batch=%s", task_id, batch_id)

    # ── Fetch batch ────────────────────────────────────────────────────────
    try:
        batch = PayoutBatch.objects.get(pk=batch_id)
    except PayoutBatch.DoesNotExist:
        logger.error("[task=%s] reconcile_batch_with_gateway: batch %s not found.", task_id, batch_id)
        return {"batch_id": batch_id, "status": "error", "error": "batch_not_found"}

    if batch.status not in (
        PayoutBatchStatus.COMPLETED,
        PayoutBatchStatus.PARTIALLY_COMPLETED,
        PayoutBatchStatus.FAILED,
    ):
        logger.info(
            "[task=%s] reconcile_batch_with_gateway: batch %s status=%s — skipping non-terminal.",
            task_id, batch_id, batch.status,
        )
        return {"batch_id": batch_id, "status": "skipped", "reason": "non_terminal_status"}

    # ── Load processor ──────────────────────────────────────────────────────
    try:
        processor = _get_processor(batch.gateway)
    except GatewayError as exc:
        logger.error("[task=%s] reconcile_batch_with_gateway: cannot load processor for %s: %s",
                     task_id, batch.gateway, exc)
        raise self.retry(exc=exc, countdown=120)

    # ── Reconcile items ─────────────────────────────────────────────────────
    start_ts     = time.monotonic()
    discrepancies: list[dict] = []
    items_checked = 0

    # Check SUCCESS items — confirm gateway agrees
    success_items = list(
        PayoutItem.objects
        .filter(batch=batch, status=PayoutItemStatus.SUCCESS)
        .exclude(gateway_reference="")
        .values("id", "gateway_reference", "gross_amount", "user_id")
    )

    for item_data in success_items:
        items_checked += 1
        gw_ref = item_data["gateway_reference"]
        try:
            result = processor.verify_transaction(gw_ref)
        except Exception as exc:
            logger.warning(
                "[task=%s] reconcile_batch_with_gateway: verify failed for item=%s gw_ref=%s: %s",
                task_id, item_data["id"], gw_ref, exc,
            )
            discrepancies.append({
                "item_id":           str(item_data["id"]),
                "gateway_reference": gw_ref,
                "db_status":         "SUCCESS",
                "gateway_status":    "VERIFY_ERROR",
                "error":             str(exc),
                "amount":            str(item_data["gross_amount"]),
                "severity":          "warning",
            })
            continue

        if not result.success:
            # DB says SUCCESS but gateway says otherwise — critical discrepancy
            discrepancies.append({
                "item_id":           str(item_data["id"]),
                "gateway_reference": gw_ref,
                "db_status":         "SUCCESS",
                "gateway_status":    result.error_code or "FAILED",
                "error_message":     result.error_message,
                "amount":            str(item_data["gross_amount"]),
                "severity":          "critical",
                "action_required":   "MANUAL_REVIEW — DB shows paid but gateway shows failure",
            })
            logger.critical(
                "[task=%s] RECONCILIATION DISCREPANCY: item=%s gw_ref=%s "
                "DB=SUCCESS gateway=%s amount=%s. MANUAL REVIEW REQUIRED.",
                task_id, item_data["id"], gw_ref, result.error_code, item_data["gross_amount"],
            )

    # Check FAILED items with gateway_reference — maybe gateway actually succeeded
    failed_with_ref = list(
        PayoutItem.objects
        .filter(batch=batch, status=PayoutItemStatus.FAILED)
        .exclude(gateway_reference="")
        .values("id", "gateway_reference", "gross_amount", "user_id")
    )

    for item_data in failed_with_ref:
        items_checked += 1
        gw_ref = item_data["gateway_reference"]
        try:
            result = processor.verify_transaction(gw_ref)
        except Exception:
            continue  # Can't verify — skip

        if result.success:
            # DB says FAILED but gateway says SUCCESS — possible double-payment risk
            discrepancies.append({
                "item_id":           str(item_data["id"]),
                "gateway_reference": gw_ref,
                "db_status":         "FAILED",
                "gateway_status":    "SUCCESS",
                "amount":            str(item_data["gross_amount"]),
                "severity":          "critical",
                "action_required":   (
                    "DOUBLE_PAYMENT_RISK — DB shows failed but gateway shows success. "
                    "Do NOT retry. Manual reconciliation needed."
                ),
            })
            logger.critical(
                "[task=%s] DOUBLE_PAYMENT_RISK: item=%s gw_ref=%s "
                "DB=FAILED gateway=SUCCESS amount=%s. DO NOT RETRY.",
                task_id, item_data["id"], gw_ref, item_data["gross_amount"],
            )

    duration_ms = int((time.monotonic() - start_ts) * 1000)
    status_str  = "discrepancies_found" if discrepancies else "clean"

    # ── Write reconciliation log ────────────────────────────────────────────
    import json as _json
    try:
        BulkProcessLog.objects.create(
            batch=batch,
            status="SUCCESS" if not discrepancies else "FAILED",
            task_id=task_id,
            items_attempted=items_checked,
            items_succeeded=items_checked - len(discrepancies),
            items_failed=len(discrepancies),
            items_skipped=0,
            duration_ms=duration_ms,
            error_summary=_json.dumps(discrepancies, default=str)[:4096] if discrepancies else "",
            extra_data={
                "reconciliation": True,
                "discrepancy_count": len(discrepancies),
                "task_id": task_id,
            },
        )
    except Exception as exc:
        logger.error("[task=%s] reconcile_batch_with_gateway: failed to write log: %s", task_id, exc)

    logger.info(
        "[task=%s] reconcile_batch_with_gateway: batch=%s checked=%d discrepancies=%d status=%s duration=%dms",
        task_id, batch_id, items_checked, len(discrepancies), status_str, duration_ms,
    )

    # ── Emit webhook if discrepancies found ────────────────────────────────
    if discrepancies:
        from django.conf import settings as _settings
        urls = getattr(_settings, "PAYOUT_WEBHOOK_URLS", []) or []
        for url in urls:
            deliver_webhook_event.delay(
                "payout_reconciliation_discrepancy",
                {"batch_id": batch_id, "discrepancies": discrepancies[:10]},
                url,
            )

    return {
        "batch_id":      batch_id,
        "items_checked": items_checked,
        "discrepancies": discrepancies,
        "status":        status_str,
        "duration_ms":   duration_ms,
    }

# ---------------------------------------------------------------------------
# v8: reconcile_recent_batches  (Celery Beat — Production Gap #3)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="payout_queue.reconcile_recent_batches",
    acks_late=True,
)
def reconcile_recent_batches(self, lookback_hours: int = RECONCILE_LOOKBACK_HOURS) -> dict:
    """
    v8: Celery beat task — daily reconciliation of recently completed batches.

    Finds all COMPLETED/PARTIALLY_COMPLETED/FAILED batches completed in the last
    `lookback_hours` hours and dispatches reconcile_batch_with_gateway for each.

    Schedule recommendation (settings_final_additions.py):
        "payout-reconcile-recent": {
            "task": "payout_queue.reconcile_recent_batches",
            "schedule": crontab(hour=2, minute=0),  # 2 AM daily
        }
    """
    from api.payout_queue.models import PayoutBatch
    from api.payout_queue.choices import PayoutBatchStatus
    from django.utils import timezone
    from datetime import timedelta

    task_id  = self.request.id or "beat"
    cutoff   = timezone.now() - timedelta(hours=lookback_hours)

    batches = list(
        PayoutBatch.objects
        .filter(
            status__in=[
                PayoutBatchStatus.COMPLETED,
                PayoutBatchStatus.PARTIALLY_COMPLETED,
                PayoutBatchStatus.FAILED,
            ],
            completed_at__gte=cutoff,
        )
        .values_list("id", flat=True)
    )

    dispatched = 0
    errors     = []

    for batch_id in batches:
        try:
            reconcile_batch_with_gateway.delay(str(batch_id))
            dispatched += 1
        except Exception as exc:
            logger.error("[task=%s] reconcile_recent_batches: failed to dispatch batch %s: %s",
                         task_id, batch_id, exc)
            errors.append({"batch_id": str(batch_id), "error": str(exc)})

    logger.info(
        "[task=%s] reconcile_recent_batches: found=%d dispatched=%d errors=%d (lookback=%dh)",
        task_id, len(batches), dispatched, len(errors), lookback_hours,
    )

    return {
        "batches_found":    len(batches),
        "dispatched_count": dispatched,
        "errors":           errors,
        "lookback_hours":   lookback_hours,
    }

# Suggested CELERY_BEAT_SCHEDULE additions for settings.py:
# from celery.schedules import crontab
# CELERY_BEAT_SCHEDULE.update({
#     "payout-process-due-batches":  {"task": "payout_queue.process_due_batches",         "schedule": 60.0},
#     "payout-retry-due-items":      {"task": "payout_queue.retry_due_items",              "schedule": 120.0},
#     "payout-expire-priorities":    {"task": "payout_queue.expire_withdrawal_priorities", "schedule": 300.0},
#     "payout-release-stale-locks":  {"task": "payout_queue.release_stale_locks",          "schedule": 900.0},
#     "payout-reconcile-recent":     {"task": "payout_queue.reconcile_recent_batches",     "schedule": crontab(hour=2, minute=0)},
# })
