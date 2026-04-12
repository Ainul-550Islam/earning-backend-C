# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
services.py: Core dispatch infrastructure.

Classes:
    SignatureEngine  — HMAC-SHA256 payload signing and verification.
    DispatchService  — HTTP dispatch, delivery logging, and retry scheduling.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

import requests
from django.db import transaction
from django.utils import timezone

from .constants import (
    DELIVERY_ID_HEADER,
    DISPATCH_TIMEOUT_SECONDS,
    EVENT_HEADER,
    MAX_RETRY_ATTEMPTS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    DeliveryStatus,
    EndpointStatus,
)
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNATURE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SignatureEngine:
    """
    Ainul Enterprise Engine — HMAC-SHA256 Payload Signing Engine.

    Produces and verifies the X-Webhook-Signature header for all
    outbound dispatch requests. Signature format:
        HMAC-SHA256(secret_key, "{delivery_id}.{timestamp_unix}.{body}")

    Usage:
        sig = SignatureEngine.sign(secret, delivery_id, timestamp, body)
        ok  = SignatureEngine.verify(secret, delivery_id, timestamp, body, sig)
    """

    ALGORITHM = "sha256"

    @staticmethod
    def sign(
        secret_key: str,
        delivery_id: str,
        timestamp: int,
        body: str,
    ) -> str:
        """
        Ainul Enterprise Engine — Produce an HMAC-SHA256 signature.

        Args:
            secret_key:  Endpoint's whsec_* signing key.
            delivery_id: UUID string (X-Webhook-Delivery-ID).
            timestamp:   Unix epoch int (seconds).
            body:        JSON-serialised payload string.

        Returns:
            Hex-encoded HMAC digest string.
        """
        raw_secret = secret_key
        # Strip the "whsec_" prefix before use
        if raw_secret.startswith("whsec_"):
            raw_secret = raw_secret[len("whsec_"):]

        signed_content = f"{delivery_id}.{timestamp}.{body}".encode("utf-8")
        secret_bytes = bytes.fromhex(raw_secret)

        digest = hmac.new(
            secret_bytes,
            signed_content,
            hashlib.sha256,
        ).hexdigest()

        return f"v1={digest}"

    @staticmethod
    def verify(
        secret_key: str,
        delivery_id: str,
        timestamp: int,
        body: str,
        incoming_signature: str,
    ) -> bool:
        """
        Ainul Enterprise Engine — Constant-time signature verification.

        Returns True if the incoming signature matches the computed digest.
        Prevents timing-attack vulnerabilities via hmac.compare_digest.
        """
        expected = SignatureEngine.sign(secret_key, delivery_id, timestamp, body)
        return hmac.compare_digest(expected, incoming_signature)


# ─────────────────────────────────────────────────────────────────────────────
#  DISPATCH SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class DispatchService:
    """
    Ainul Enterprise Engine — Webhook Dispatch Orchestrator.

    Responsibilities:
    1. Fan-out: find all active endpoints subscribed to a given event type.
    2. Construct signed HTTP requests with security headers.
    3. Execute dispatch and persist result in WebhookDeliveryLog.
    4. Schedule Celery retry tasks for failed dispatches.

    Usage:
        DispatchService.emit(event_type="payout.success", payload={...})
    """

    @classmethod
    def emit(
        cls,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: int | None = None,
    ) -> list[WebhookDeliveryLog]:
        """
        Ainul Enterprise Engine — Emit an event to all subscribed endpoints.

        Finds active subscriptions for the given event_type (optionally
        filtered by tenant), creates DeliveryLog records, and dispatches.

        Args:
            event_type: Dot-notation event string (e.g. "payout.success").
            payload:    Event data dict that will be JSON-serialised.
            tenant_id:  Optional tenant scoping.

        Returns:
            List of created WebhookDeliveryLog instances.
        """
        subscriptions = WebhookSubscription.objects.filter(
            event_type=event_type,
            is_active=True,
            endpoint__status=EndpointStatus.ACTIVE,
        ).select_related("endpoint").order_by("pk")

        if tenant_id is not None:
            subscriptions = subscriptions.filter(endpoint__tenant_id=tenant_id)

        logs: list[WebhookDeliveryLog] = []

        for subscription in subscriptions:
            log = cls._dispatch(
                endpoint=subscription.endpoint,
                event_type=event_type,
                payload=payload,
                attempt_number=1,
            )
            logs.append(log)

        logger.info(
            "emit event_type=%s dispatched to %d endpoint(s)",
            event_type,
            len(logs),
        )
        return logs

    # ─── Internal ──────────────────────────────────────────────────────────

    @classmethod
    def _dispatch(
        cls,
        endpoint: WebhookEndpoint,
        event_type: str,
        payload: dict[str, Any],
        attempt_number: int = 1,
        existing_log: WebhookDeliveryLog | None = None,
    ) -> WebhookDeliveryLog:
        """
        Ainul Enterprise Engine — Execute a single HTTP dispatch attempt.

        Builds the request, signs the payload, fires the HTTP call,
        and writes the outcome to WebhookDeliveryLog.  On failure,
        schedules a Celery retry task via _schedule_retry().
        """
        delivery_id = str(uuid.uuid4())
        timestamp_unix = int(datetime.now(dt_timezone.utc).timestamp())
        body_str = json.dumps(payload, default=str, sort_keys=True)

        # ── Build Signature ────────────────────────────────────────────────
        signature = SignatureEngine.sign(
            secret_key=endpoint.secret_key,
            delivery_id=delivery_id,
            timestamp=timestamp_unix,
            body=body_str,
        )

        # ── Build Headers ──────────────────────────────────────────────────
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "AinulEnterpriseEngine-Webhook/1.0",
            SIGNATURE_HEADER: signature,
            TIMESTAMP_HEADER: str(timestamp_unix),
            EVENT_HEADER: event_type,
            DELIVERY_ID_HEADER: delivery_id,
        }
        # Merge custom endpoint-level headers
        headers.update(endpoint.custom_headers or {})

        # ── Create / Update DeliveryLog ────────────────────────────────────
        if existing_log is None:
            log = WebhookDeliveryLog(
                endpoint=endpoint,
                event_type=event_type,
                delivery_id=delivery_id,
                payload=payload,
                request_headers=headers,
                signature=signature,
                attempt_number=attempt_number,
                max_attempts=endpoint.max_retries,
                status=DeliveryStatus.DISPATCHED,
                dispatched_at=timezone.now(),
            )
        else:
            log = existing_log
            log.attempt_number = attempt_number
            log.status = DeliveryStatus.DISPATCHED
            log.dispatched_at = timezone.now()
            log.request_headers = headers
            log.signature = signature

        log.save()

        # ── Execute HTTP Request ───────────────────────────────────────────
        http_status = None
        response_body = ""
        response_time_ms = None
        error_msg = ""
        success = False

        start = time.monotonic()
        try:
            response = requests.request(
                method=endpoint.http_method,
                url=endpoint.target_url,
                data=body_str,
                headers=headers,
                timeout=DISPATCH_TIMEOUT_SECONDS,
                verify=endpoint.verify_ssl,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            http_status = response.status_code
            response_body = response.text[:4096]
            response_time_ms = elapsed
            success = 200 <= http_status < 300

            if success:
                logger.info(
                    "Dispatch SUCCESS delivery_id=%s endpoint=%s status=%d",
                    delivery_id, endpoint.pk, http_status,
                )
            else:
                logger.warning(
                    "Dispatch FAILED (non-2xx) delivery_id=%s endpoint=%s status=%d",
                    delivery_id, endpoint.pk, http_status,
                )

        except requests.exceptions.Timeout:
            elapsed = int((time.monotonic() - start) * 1000)
            response_time_ms = elapsed
            error_msg = "Request timed out"
            logger.error("Dispatch TIMEOUT delivery_id=%s endpoint=%s", delivery_id, endpoint.pk)

        except requests.exceptions.ConnectionError as exc:
            error_msg = f"Connection error: {exc}"
            logger.error("Dispatch CONN_ERROR delivery_id=%s: %s", delivery_id, exc)

        except Exception as exc:  # noqa: BLE001
            error_msg = f"Unexpected error: {exc}"
            logger.exception("Dispatch EXCEPTION delivery_id=%s", delivery_id)

        # ── Persist Result ─────────────────────────────────────────────────
        final_status = DeliveryStatus.SUCCESS if success else DeliveryStatus.FAILED

        with transaction.atomic():
            log.http_status_code = http_status
            log.response_body = response_body
            log.response_time_ms = response_time_ms
            log.error_message = error_msg
            log.status = final_status
            log.completed_at = timezone.now()
            log.save(
                update_fields=[
                    "http_status_code",
                    "response_body",
                    "response_time_ms",
                    "error_message",
                    "status",
                    "completed_at",
                ]
            )

            # Update endpoint counters
            endpoint.total_deliveries   = models_F_increment(endpoint, "total_deliveries")
            endpoint.last_triggered_at  = timezone.now()
            if success:
                endpoint.success_deliveries = models_F_increment(endpoint, "success_deliveries")
            else:
                endpoint.failed_deliveries  = models_F_increment(endpoint, "failed_deliveries")
            endpoint.save(
                update_fields=[
                    "total_deliveries",
                    "success_deliveries",
                    "failed_deliveries",
                    "last_triggered_at",
                ]
            )

        # ── Schedule Retry ─────────────────────────────────────────────────
        if not success and attempt_number < endpoint.max_retries:
            cls._schedule_retry(log=log, attempt_number=attempt_number)

        elif not success and attempt_number >= endpoint.max_retries:
            log.status = DeliveryStatus.EXHAUSTED
            log.save(update_fields=["status"])
            logger.warning(
                "Delivery EXHAUSTED delivery_id=%s after %d attempts",
                delivery_id, attempt_number,
            )

        return log

    @classmethod
    def _schedule_retry(cls, log: WebhookDeliveryLog, attempt_number: int) -> None:
        """
        Ainul Enterprise Engine — Schedule exponential-backoff Celery retry.

        Delay formula: RETRY_BACKOFF_BASE * 2^(attempt-1)
        e.g. attempt 1→60s, 2→120s, 3→240s, 4→480s, 5→960s
        """
        from .tasks import retry_failed_dispatch  # avoid circular import
        from .constants import RETRY_BACKOFF_BASE_SECONDS

        delay_seconds = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt_number - 1))
        next_retry = timezone.now() + timedelta(seconds=delay_seconds)

        log.status = DeliveryStatus.RETRYING
        log.next_retry_at = next_retry
        log.save(update_fields=["status", "next_retry_at"])

        retry_failed_dispatch.apply_async(
            args=[str(log.pk)],
            countdown=delay_seconds,
        )

        logger.info(
            "Retry scheduled delivery_id=%s attempt=%d delay=%ds",
            log.delivery_id, attempt_number + 1, delay_seconds,
        )

    # ─── Public Helper ─────────────────────────────────────────────────────

    @classmethod
    def retry_delivery(cls, log: WebhookDeliveryLog) -> WebhookDeliveryLog:
        """
        Ainul Enterprise Engine — Manually retry a failed delivery log.
        Called by the Celery task and admin "retry" action.
        """
        if not log.is_retryable:
            logger.warning(
                "retry_delivery called on non-retryable log %s (status=%s)",
                log.pk, log.status,
            )
            return log

        return cls._dispatch(
            endpoint=log.endpoint,
            event_type=log.event_type,
            payload=log.payload,
            attempt_number=log.attempt_number + 1,
            existing_log=log,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  UTIL
# ─────────────────────────────────────────────────────────────────────────────

def models_F_increment(instance, field: str) -> int:
    """
    Safe counter increment — avoids race conditions by re-fetching from DB.
    Returns the new value (not an F() expression) for direct assignment.
    """
    from django.db.models import F
    type(instance).objects.filter(pk=instance.pk).update(**{field: F(field) + 1})
    return type(instance).objects.values_list(field, flat=True).get(pk=instance.pk)
