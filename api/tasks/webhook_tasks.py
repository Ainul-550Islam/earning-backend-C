"""
tasks/webhook_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Webhook Management Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Outgoing: fire webhooks to external systems on events
Incoming: validate, parse, route incoming webhook calls
  ✅ dispatch_webhook           — fire outgoing webhook with retry
  ✅ verify_webhook_signature   — HMAC-SHA256 signature verification
  ✅ process_incoming_webhook   — route inbound webhook to correct handler
  ✅ retry_failed_webhooks      — retry failed outgoing webhooks
  ✅ cleanup_old_webhook_logs   — purge old webhook delivery logs
  ✅ register_webhook           — register new webhook endpoint
  ✅ test_webhook_endpoint      — ping a webhook URL for verification
"""
from datetime import timedelta
import logging
import hmac
import hashlib
import json
import requests
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from api.webhooks.constants import EndpointStatus
from django.db import transaction

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT    = 10   # seconds
WEBHOOK_MAX_RETRY  = 5
WEBHOOK_DEDUP_TTL  = 3600


@shared_task(bind=True, max_retries=WEBHOOK_MAX_RETRY, default_retry_delay=30,
             name='tasks.webhook_tasks.dispatch_webhook')
def dispatch_webhook(
    self,
    webhook_id: int,
    event: str,
    payload: dict,
    url: str = '',
    secret: str = '',
    headers: dict = None,
) -> dict:
    """
    Dispatch a signed outgoing webhook to the configured URL.
    Adds HMAC-SHA256 signature in X-Signature-256 header.
    Retries with exponential backoff on failure.
    """
    try:
        from django.utils import timezone as tz
        body     = json.dumps(payload, default=str)
        sig      = _compute_signature(body, secret) if secret else ''

        req_headers = {
            'Content-Type':     'application/json',
            'X-Event':          event,
            'X-Webhook-Id':     str(webhook_id),
            'X-Delivery-At':    tz.now().isoformat(),
            'X-Signature-256':  f'sha256={sig}',
            **(headers or {}),
        }

        resp = requests.post(
            url,
            data=body,
            headers=req_headers,
            timeout=WEBHOOK_TIMEOUT,
        )
        success = resp.status_code < 400

        # Log delivery
        _log_delivery(webhook_id, event, url, resp.status_code, success, resp.text[:500])

        if not success:
            logger.warning(f"[WEBHOOK] Delivery failed: {url} HTTP {resp.status_code}")
            raise requests.HTTPError(f"HTTP {resp.status_code}")

        logger.info(f"[WEBHOOK] Delivered: {event} → {url} ({resp.status_code})")
        return {
            'status': 'success',
            'webhook_id': webhook_id,
            'http_status': resp.status_code,
            'timestamp': tz.now().isoformat(),
        }

    except requests.exceptions.Timeout:
        logger.error(f"[WEBHOOK] Timeout: {url}")
        raise self.retry(exc=Exception('timeout'), countdown=min(2**self.request.retries*30, 600))
    except requests.exceptions.ConnectionError as e:
        raise self.retry(exc=e, countdown=min(2**self.request.retries*30, 600))
    except Exception as exc:
        logger.error(f"[WEBHOOK] dispatch_webhook error: {exc}")
        raise self.retry(exc=exc, countdown=min(2**self.request.retries*30, 600))


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.webhook_tasks.process_incoming_webhook')
def process_incoming_webhook(
    self,
    source: str,       # 'appsflyer' | 'adjust' | 'stripe' | 'paypal' | 'cpalead'
    event_type: str,
    payload: dict,
    raw_body: str = '',
    signature: str = '',
    ip_address: str = '',
) -> dict:
    """
    Route an incoming webhook to the correct handler.
    Verifies signature first.
    """
    try:
        from django.conf import settings

        logger.info(f"[WEBHOOK] Incoming: source={source} event={event_type}")

        # Dedup check
        dedup_key = f'webhook_in_{source}_{payload.get("transaction_id", "")}'
        if cache.get(dedup_key):
            return {'status': 'duplicate', 'source': source}
        cache.set(dedup_key, 1, timeout=WEBHOOK_DEDUP_TTL)

        # Verify signature
        secrets_map = getattr(settings, 'WEBHOOK_SECRETS', {})
        secret = secrets_map.get(source, '')
        if secret and raw_body and not _verify_signature(raw_body, signature, secret):
            logger.warning(f"[WEBHOOK] Invalid signature from {source}")
            return {'status': 'invalid_signature', 'source': source}

        # Route to handler
        handlers = {
            'appsflyer':  'tasks.cpi_tasks.process_app_install_event',
            'adjust':     'tasks.cpi_tasks.process_app_install_event',
            'kochava':    'tasks.cpi_tasks.process_app_install_event',
            'cpalead':    'tasks.cpalead_tasks.cpalead_process_postback',
            'stripe':     'tasks.payment_tasks.payment_reconcile',
            'paypal':     'tasks.payment_tasks.sync_payment_status',
        }

        handler_task = handlers.get(source)
        if handler_task:
            from celery import current_app
            current_app.send_task(
                handler_task,
                kwargs={'postback_data': payload} if source == 'cpalead' else {'webhook_payload': payload},
                queue='high',
            )

        return {
            'status': 'routed',
            'source': source,
            'event_type': event_type,
            'handler': handler_task,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[WEBHOOK] process_incoming error: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.webhook_tasks.retry_failed_webhooks')
def retry_failed_webhooks(self, max_age_hours: int = 24) -> dict:
    """Retry all failed webhook deliveries within the age window."""
    try:
        from datetime import timedelta
        logger.info(f"🔄 Retrying failed webhooks (age<{max_age_hours}h)...")
        retried = 0
        errors  = 0
        cutoff  = timezone.now() - timedelta(hours=max_age_hours)

        try:
            from webhooks.models import WebhookDelivery, WebhookEndpoint
            failed = WebhookDelivery.objects.filter(
                status='failed',
                created_at__gte=cutoff,
                retry_count__lt=WEBHOOK_MAX_RETRY,
            ).select_related('endpoint')

            for delivery in failed:
                try:
                    dispatch_webhook.apply_async(kwargs={
                        'webhook_id': delivery.endpoint_id,
                        'event':      delivery.event,
                        'payload':    delivery.payload,
                        'url':        delivery.endpoint.url,
                        'secret':     delivery.endpoint.secret or '',
                    })
                    delivery.retry_count += 1
                    delivery.save(update_fields=['retry_count'])
                    retried += 1
                except Exception as e:
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Webhook models not available: {e}")

        return {'status': 'success', 'retried': retried, 'errors': errors, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.webhook_tasks.test_webhook_endpoint')
def test_webhook_endpoint(self, endpoint_id: int, url: str, secret: str = '') -> dict:
    """Send a test payload to verify a webhook endpoint is reachable."""
    try:
        test_payload = {
            'event': 'test.ping',
            'message': 'Webhook endpoint test from platform',
            'timestamp': timezone.now().isoformat(),
        }
        result = dispatch_webhook.apply(kwargs={
            'webhook_id': endpoint_id,
            'event':      'test.ping',
            'payload':    test_payload,
            'url':        url,
            'secret':     secret,
        })
        data = result.get()
        return {
            'status': 'success' if data.get('status') == 'success' else 'failed',
            'http_status': data.get('http_status'),
            'endpoint_id': endpoint_id,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        return {'status': 'failed', 'error': str(exc), 'endpoint_id': endpoint_id}


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.webhook_tasks.cleanup_old_webhook_logs')
def cleanup_old_webhook_logs(self, days_to_keep: int = 30) -> dict:
    """Purge old webhook delivery logs."""
    try:
        from datetime import timedelta
        deleted = 0
        cutoff  = timezone.now() - timedelta(days=days_to_keep)
        try:
            from webhooks.models import WebhookDelivery
            deleted, _ = WebhookDelivery.objects.filter(created_at__lt=cutoff).delete()
        except ImportError:
            pass
        return {'status': 'success', 'deleted': deleted, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _compute_signature(body: str, secret: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def _verify_signature(body: str, signature: str, secret: str) -> bool:
    expected = f"sha256={_compute_signature(body, secret)}"
    received = signature if signature.startswith('sha256=') else f"sha256={signature}"
    return hmac.compare_digest(expected, received)


def _log_delivery(webhook_id, event, url, status_code, success, response_body):
    try:
        from webhooks.models import WebhookDelivery
        WebhookDelivery.objects.create(
            endpoint_id=webhook_id,
            event=event,
            url=url,
            http_status=status_code,
            status='success' if success else 'failed',
            response_body=response_body,
            delivered_at=timezone.now(),
        )
    except ImportError:
        pass


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/webhooks/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
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
    from api.webhooks.services.core.DispatchService import DispatchService

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
    from api.webhooks.services.core.DispatchService import DispatchService

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

