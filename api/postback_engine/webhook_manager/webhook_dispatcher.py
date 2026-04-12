"""
webhook_manager/webhook_dispatcher.py – Outbound webhook delivery.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta

import requests
from django.utils import timezone

from ..constants import MAX_WEBHOOK_RETRIES, WEBHOOK_RETRY_DELAYS
from ..models import Conversion, RetryLog

logger = logging.getLogger(__name__)


class WebhookDeliveryLog:
    """In-memory delivery log (extend with DB model if needed)."""
    def __init__(self, url, event, payload, status_code=None, error=None, attempt=1):
        self.url = url
        self.event = event
        self.payload = payload
        self.status_code = status_code
        self.error = error
        self.attempt = attempt
        self.delivered_at = timezone.now()


def dispatch_conversion_webhooks(conversion: Conversion):
    """
    Send outbound webhook notifications for a conversion to all registered endpoints.
    """
    from ..constants import WEBHOOK_EVENT_CONVERSION
    endpoints = _get_webhook_endpoints(conversion.network)
    if not endpoints:
        return

    payload = _build_conversion_payload(conversion)

    for endpoint in endpoints:
        _deliver_webhook(
            url=endpoint["url"],
            secret=endpoint.get("secret", ""),
            event=WEBHOOK_EVENT_CONVERSION,
            payload=payload,
            conversion=conversion,
        )


def _deliver_webhook(
    url: str,
    secret: str,
    event: str,
    payload: dict,
    conversion: Conversion,
    attempt: int = 1,
):
    """Deliver a single webhook with HMAC signature."""
    body = json.dumps(payload, default=str)
    signature = _sign_webhook(secret, body) if secret else ""

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Signature": signature,
        "X-Webhook-Delivery": str(uuid.uuid4()),
        "User-Agent": "PostbackEngine/2.0",
    }

    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info("Webhook delivered: event=%s url=%s status=%d", event, url, resp.status_code)
        return True

    except requests.RequestException as exc:
        logger.warning(
            "Webhook delivery failed (attempt %d/%d): event=%s url=%s error=%s",
            attempt, MAX_WEBHOOK_RETRIES, event, url, exc,
        )
        RetryLog.objects.create(
            retry_type="webhook",
            object_id=conversion.id,
            attempt_number=attempt,
            error_message=str(exc),
            next_retry_at=timezone.now() + timedelta(
                seconds=WEBHOOK_RETRY_DELAYS[min(attempt - 1, len(WEBHOOK_RETRY_DELAYS) - 1)]
            ) if attempt < MAX_WEBHOOK_RETRIES else None,
        )
        return False


def _sign_webhook(secret: str, body: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_conversion_payload(conversion: Conversion) -> dict:
    """Build standardised webhook payload from a Conversion."""
    return {
        "event": "conversion.completed",
        "conversion_id": str(conversion.id),
        "transaction_id": conversion.transaction_id,
        "lead_id": conversion.lead_id,
        "offer_id": conversion.offer_id,
        "network": conversion.network.network_key,
        "user_id": str(conversion.user_id),
        "payout_usd": float(conversion.actual_payout),
        "points_awarded": conversion.points_awarded,
        "currency": conversion.currency,
        "status": conversion.status,
        "converted_at": conversion.converted_at.isoformat(),
        "country": conversion.country,
    }


def _get_webhook_endpoints(network) -> list:
    """
    Return list of webhook endpoint configs for a network.
    Stored in network.metadata['webhooks'] or from a WebhookSubscription model.
    """
    return network.metadata.get("webhooks", []) if network.metadata else []
