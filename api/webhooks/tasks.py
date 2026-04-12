# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
tasks.py: Celery async task definitions.

Tasks:
    retry_failed_dispatch  — Re-attempts a failed WebhookDeliveryLog entry.
    dispatch_event         — Fan-out a new event to all subscribed endpoints.
    reap_exhausted_logs    — Periodic cleanup / alerting for exhausted logs.
    auto_suspend_endpoints — Suspend endpoints with critically low success rate.
"""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from datetime import timedelta

from .constants import (
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE_SECONDS,
    DeliveryStatus,
    EndpointStatus,
)

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  RETRY FAILED DISPATCH
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="ainul.webhooks.retry_failed_dispatch",
    bind=True,
    max_retries=MAX_RETRY_ATTEMPTS,
    default_retry_delay=RETRY_BACKOFF_BASE_SECONDS,
    acks_late=True,
    reject_on_worker_lost=True,
    queue="webhooks",
)
def retry_failed_dispatch(self, log_pk: str) -> dict:
    """
    Ainul Enterprise Engine — Retry a failed WebhookDeliveryLog entry.

    Implements exponential backoff:
        delay = RETRY_BACKOFF_BASE * 2^(attempt_number - 1)

    Args:
        log_pk (str): UUID primary key of the WebhookDeliveryLog to retry.

    Returns:
        dict: Outcome summary with status and attempt metadata.
    """
    from .models import WebhookDeliveryLog
    from .services import DispatchService

    try:
        log = WebhookDeliveryLog.objects.select_related("endpoint").get(pk=log_pk)
    except WebhookDeliveryLog.DoesNotExist:
        logger.error("retry_failed_dispatch: log %s not found — aborting", log_pk)
        return {"status": "aborted", "reason": "log_not_found", "log_pk": log_pk}

    # ── Guard: skip if already resolved ─────────────────────────────────────
    if log.status == DeliveryStatus.SUCCESS:
        logger.info("retry_failed_dispatch: log %s already SUCCESS — skip", log_pk)
        return {"status": "skipped", "reason": "already_success"}

    if log.status == DeliveryStatus.EXHAUSTED:
        logger.warning(
            "retry_failed_dispatch: log %s is EXHAUSTED — skip", log_pk
        )
        return {"status": "skipped", "reason": "exhausted"}

    if not log.is_retryable:
        logger.warning(
            "retry_failed_dispatch: log %s is not retryable (status=%s, attempt=%d/%d)",
            log_pk, log.status, log.attempt_number, log.max_attempts,
        )
        return {
            "status": "skipped",
            "reason": "not_retryable",
            "attempt": log.attempt_number,
            "max": log.max_attempts,
        }

    # ── Guard: endpoint still active ─────────────────────────────────────────
    if log.endpoint.status != EndpointStatus.ACTIVE:
        logger.warning(
            "retry_failed_dispatch: endpoint %s is %s — cancelling log %s",
            log.endpoint.pk, log.endpoint.status, log_pk,
        )
        with transaction.atomic():
            log.status = DeliveryStatus.CANCELLED
            log.error_message = (
                f"Endpoint status changed to '{log.endpoint.status}' — retry cancelled."
            )
            log.save(update_fields=["status", "error_message"])
        return {"status": "cancelled", "reason": "endpoint_inactive"}

    # ── Execute Retry ─────────────────────────────────────────────────────────
    logger.info(
        "retry_failed_dispatch: attempting log %s (attempt %d/%d)",
        log_pk, log.attempt_number + 1, log.max_attempts,
    )

    updated_log = DispatchService.retry_delivery(log)

    return {
        "status": updated_log.status,
        "delivery_id": str(updated_log.delivery_id),
        "attempt": updated_log.attempt_number,
        "http_status": updated_log.http_status_code,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  FAN-OUT EVENT DISPATCH
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="ainul.webhooks.dispatch_event",
    bind=True,
    acks_late=True,
    queue="webhooks",
)
def dispatch_event(
    self,
    event_type: str,
    payload: dict,
    tenant_id: int | None = None,
) -> dict:
    """
    Ainul Enterprise Engine — Async fan-out dispatcher.

    Wraps DispatchService.emit() as a Celery task so callers can fire
    events without blocking the request/response cycle.

    Args:
        event_type: Platform event (e.g. "payout.success").
        payload:    Event data dictionary.
        tenant_id:  Optional tenant scope.

    Returns:
        dict: Summary of dispatched log count.
    """
    from .services import DispatchService

    logger.info("dispatch_event task: event_type=%s tenant=%s", event_type, tenant_id)

    logs = DispatchService.emit(
        event_type=event_type,
        payload=payload,
        tenant_id=tenant_id,
    )

    return {
        "event_type": event_type,
        "dispatched": len(logs),
        "log_ids": [str(log.pk) for log in logs],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  PERIODIC: REAP EXHAUSTED LOGS
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="ainul.webhooks.reap_exhausted_logs",
    queue="webhooks_periodic",
)
def reap_exhausted_logs() -> dict:
    """
    Ainul Enterprise Engine — Periodic task to surface exhausted deliveries.

    Runs hourly (configure via Celery Beat).  Logs all EXHAUSTED entries
    created in the last hour for monitoring/alerting pipelines.

    Returns:
        dict: Count of exhausted logs found.
    """
    from .models import WebhookDeliveryLog
    one_hour_ago = timezone.now() - timedelta(hours=1)
    exhausted_qs = WebhookDeliveryLog.objects.filter(
        status=DeliveryStatus.EXHAUSTED,
        created_at__gte=one_hour_ago,
    ).select_related("endpoint")

    count = exhausted_qs.count()

    for log in exhausted_qs:
        logger.critical(
            "EXHAUSTED DELIVERY: event=%s endpoint=%s (%s) delivery_id=%s",
            log.event_type,
            log.endpoint.label,
            log.endpoint.target_url,
            log.delivery_id,
        )

    logger.info("reap_exhausted_logs: found %d exhausted deliveries in last hour", count)
    return {"exhausted_count": count, "checked_since": one_hour_ago.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
#  PERIODIC: AUTO-SUSPEND HIGH-FAILURE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="ainul.webhooks.auto_suspend_endpoints",
    queue="webhooks_periodic",
)
def auto_suspend_endpoints(failure_threshold_pct: int = 80) -> dict:
    """
    Ainul Enterprise Engine — Auto-suspend endpoints with high failure rates.

    Scans active endpoints where failure rate exceeds `failure_threshold_pct`
    percent over the last 50 deliveries, and marks them as SUSPENDED.
    Operators are notified via logger.critical for integration with alerting.

    Args:
        failure_threshold_pct: Minimum failure % to trigger suspension (default 80).

    Returns:
        dict: List of suspended endpoint PKs.
    """
    from .models import WebhookEndpoint

    suspended_pks = []

    active_endpoints = WebhookEndpoint.objects.filter(
        status=EndpointStatus.ACTIVE,
        total_deliveries__gte=50,
    )

    for endpoint in active_endpoints:
        if endpoint.total_deliveries == 0:
            continue

        failure_pct = (
            endpoint.failed_deliveries / endpoint.total_deliveries
        ) * 100

        if failure_pct >= failure_threshold_pct:
            endpoint.status = EndpointStatus.SUSPENDED
            endpoint.save(update_fields=["status", "updated_at"])
            suspended_pks.append(str(endpoint.pk))

            logger.critical(
                "AUTO_SUSPEND: endpoint %s (%s) suspended — failure rate %.1f%%",
                endpoint.pk, endpoint.label, failure_pct,
            )

    return {
        "suspended_count": len(suspended_pks),
        "suspended_endpoint_pks": suspended_pks,
        "failure_threshold_pct": failure_threshold_pct,
    }
