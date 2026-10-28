# engagement/services/webhook_service.py
"""
Webhook Delivery Service
Signs payloads with HMAC-SHA256, delivers to registered endpoints,
records outcomes, and schedules retries on failure.
"""
import hmac
import hashlib
import json
import logging
import requests
from datetime import timedelta
from django.utils import timezone
from ..models.webhook import WebhookEndpoint, WebhookDelivery

logger = logging.getLogger(__name__)


class WebhookService:

    @classmethod
    def dispatch(cls, event_type: str, payload: dict, tenant=None):
        """
        Find all active endpoints subscribed to event_type and queue delivery.
        In production call via Celery: dispatch_webhooks.delay(event_type, payload)
        """
        endpoints = WebhookEndpoint.objects.filter(
            is_active=True, tenant=tenant
        ).filter(
            # subscribed to this event OR "all"
            **{}  # handled in Python below due to JSON field
        )
        for ep in endpoints:
            if "all" in ep.events or event_type in ep.events:
                delivery = WebhookDelivery.objects.create(
                    endpoint=ep, tenant=tenant,
                    event_type=event_type, payload=payload, status="pending",
                )
                cls._deliver(delivery)

    @classmethod
    def _deliver(cls, delivery: WebhookDelivery):
        """Attempt one HTTP delivery. Updates delivery record."""
        ep      = delivery.endpoint
        payload = delivery.payload
        body    = json.dumps(payload, ensure_ascii=False)
        sig     = cls._sign(body, ep.secret)
        headers = {
            "Content-Type":          "application/json",
            "X-Engagement-Signature": f"sha256={sig}",
            "X-Engagement-Event":    delivery.event_type,
            "X-Delivery-ID":         str(delivery.pk),
        }
        start = timezone.now()
        try:
            resp = requests.post(ep.url, data=body.encode(), headers=headers,
                                 timeout=ep.timeout_seconds)
            elapsed_ms = int((timezone.now() - start).total_seconds() * 1000)
            delivery.response_code = resp.status_code
            delivery.response_body = resp.text[:1000]
            delivery.duration_ms   = elapsed_ms
            delivery.attempt_count += 1

            if resp.ok:
                delivery.status       = "success"
                delivery.delivered_at = timezone.now()
                ep.success_count      = ep.success_count + 1
                ep.last_triggered     = timezone.now()
                ep.save(update_fields=["success_count", "last_triggered"])
                logger.info("WebhookService: delivered %s → %s [%d]", delivery.event_type, ep.url, resp.status_code)
            else:
                cls._schedule_retry(delivery, ep)
                ep.failure_count = ep.failure_count + 1
                ep.save(update_fields=["failure_count"])
                logger.warning("WebhookService: %s returned %d", ep.url, resp.status_code)

        except Exception as exc:
            delivery.attempt_count += 1
            delivery.response_body  = str(exc)[:500]
            cls._schedule_retry(delivery, ep)
            logger.error("WebhookService: delivery failed %s → %s: %s", delivery.event_type, ep.url, exc)

        delivery.save()

    @staticmethod
    def _sign(body: str, secret: str) -> str:
        return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _schedule_retry(delivery: WebhookDelivery, ep: WebhookEndpoint):
        if delivery.attempt_count >= ep.retry_count:
            delivery.status = "abandoned"
        else:
            delivery.status       = "retrying"
            backoff               = 2 ** delivery.attempt_count * 30   # 30s, 60s, 120s…
            delivery.next_retry_at = timezone.now() + timedelta(seconds=backoff)

    @classmethod
    def retry_failed(cls, tenant=None):
        """Retry all pending/retrying deliveries. Called by Celery beat."""
        now  = timezone.now()
        qs   = WebhookDelivery.objects.filter(
            status="retrying", next_retry_at__lte=now
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        count = 0
        for delivery in qs.select_related("endpoint")[:50]:
            cls._deliver(delivery)
            count += 1
        return count
