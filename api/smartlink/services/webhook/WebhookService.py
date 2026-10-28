"""
SmartLink Webhook Delivery Service
Handles event dispatch, HTTP delivery, retry logic, and delivery logging.
"""
import json
import logging
import time
from datetime import timedelta

import requests
from django.utils import timezone
from api.smartlink.models.webhook import WebhookEndpoint

logger = logging.getLogger('smartlink.webhooks')


class WebhookService:
    """
    Deliver webhook events to all subscribed publisher endpoints.

    Usage:
        svc = WebhookService()
        svc.dispatch('conversion', smartlink_id=1, offer_id=2, payout=3.50, publisher=user)
    """

    MAX_PAYLOAD_SIZE = 32 * 1024  # 32 KB
    RETRY_DELAYS = [30, 300, 1800]  # 30s, 5m, 30m

    def dispatch(self, event: str, publisher=None, smartlink_id: int = None, **payload_data):
        """
        Build event payload and deliver to all subscribed endpoints.
        Runs synchronously in Celery worker context.
        """
        from api.smartlink.models.webhook import WebhookEndpoint
        if publisher is None:
            logger.warning(f"dispatch called for event '{event}' with no publisher")
            return 0

        qs = WebhookEndpoint.objects.filter(
            publisher=publisher, is_active=True
        )
        payload = self._build_payload(event, smartlink_id, payload_data)
        sent = 0
        for endpoint in qs:
            if endpoint.subscribes_to(event):
                self._deliver(endpoint, event, payload)
                sent += 1
        return sent

    def dispatch_to_all(self, event: str, **payload_data):
        """
        Platform-wide event (admin use). Deliver to ALL publishers subscribed to this event.
        E.g. when platform maintenance starts.
        """
        from api.smartlink.models.webhook import WebhookEndpoint
        endpoints = WebhookEndpoint.objects.filter(is_active=True)
        payload = self._build_payload(event, None, payload_data)
        sent = 0
        for ep in endpoints:
            if ep.subscribes_to(event):
                self._deliver(ep, event, payload)
                sent += 1
        return sent

    def _build_payload(self, event: str, smartlink_id, data: dict) -> dict:
        return {
            'event': event,
            'smartlink_id': smartlink_id,
            'timestamp': timezone.now().isoformat(),
            'data': data,
        }

    def _deliver(self, endpoint, event: str, payload: dict, attempt: int = 1):
        """Attempt one HTTP delivery and log the result."""
        from api.smartlink.models.webhook import WebhookDeliveryLog
        payload_bytes = json.dumps(payload, default=str).encode()

        if len(payload_bytes) > self.MAX_PAYLOAD_SIZE:
            logger.warning(f"Webhook payload too large ({len(payload_bytes)}B) for [{event}] → {endpoint.url}")
            return

        headers = endpoint.build_headers(payload_bytes)
        start = time.monotonic()
        status = WebhookDeliveryLog.Status.FAILED
        http_status = None
        response_body = ''
        error_msg = ''
        next_retry_at = None

        try:
            resp = requests.post(
                endpoint.url,
                data=payload_bytes,
                headers=headers,
                timeout=endpoint.timeout_seconds,
            )
            http_status = resp.status_code
            response_body = resp.text[:2000]
            if 200 <= resp.status_code < 300:
                status = WebhookDeliveryLog.Status.SUCCESS
                from django.db.models import F
                WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
                    success_count=F('success_count') + 1,
                    last_success_at=timezone.now(),
                )
            else:
                error_msg = f"HTTP {resp.status_code}"

        except requests.Timeout:
            error_msg = f"Timeout after {endpoint.timeout_seconds}s"
        except requests.ConnectionError as e:
            error_msg = f"Connection error: {str(e)[:200]}"
        except Exception as e:
            error_msg = f"Unexpected: {str(e)[:200]}"

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        # Schedule retry if failed and retries remain
        if status == WebhookDeliveryLog.Status.FAILED:
            from django.db.models import F
            WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
                failure_count=F('failure_count') + 1,
            )
            retry_idx = attempt - 1
            if retry_idx < len(self.RETRY_DELAYS) and attempt <= endpoint.retry_count:
                delay_s = self.RETRY_DELAYS[min(retry_idx, len(self.RETRY_DELAYS) - 1)]
                next_retry_at = timezone.now() + timedelta(seconds=delay_s)
                status = WebhookDeliveryLog.Status.RETRYING
            else:
                status = WebhookDeliveryLog.Status.DROPPED

        WebhookEndpoint.objects.filter(pk=endpoint.pk).update(last_delivery_at=timezone.now())

        WebhookDeliveryLog.objects.create(
            endpoint=endpoint,
            event=event,
            payload=payload,
            status=status,
            http_status=http_status,
            response_body=response_body,
            latency_ms=latency_ms,
            attempt=attempt,
            error_message=error_msg,
            next_retry_at=next_retry_at,
        )
        logger.info(
            f"Webhook [{event}] → {endpoint.url[:60]} attempt={attempt} "
            f"status={status} http={http_status} latency={latency_ms}ms"
        )

    def retry_pending(self):
        """
        Called by a Celery beat task. Retry all RETRYING deliveries whose next_retry_at has passed.
        """
        from api.smartlink.models.webhook import WebhookDeliveryLog
        now = timezone.now()
        pending = WebhookDeliveryLog.objects.filter(
            status=WebhookDeliveryLog.Status.RETRYING,
            next_retry_at__lte=now,
        ).select_related('endpoint')[:100]

        retried = 0
        for log in pending:
            self._deliver(
                log.endpoint,
                log.event,
                log.payload,
                attempt=log.attempt + 1,
            )
            retried += 1
        return retried
