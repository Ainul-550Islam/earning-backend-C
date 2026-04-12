"""
WEBHOOKS/webhook_manager.py — Outbound webhook dispatcher
"""
import logging
import hmac
import hashlib
import json
import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """
    Dispatches outbound webhooks to registered URLs.
    Signs payload with HMAC-SHA256 using the tenant's webhook secret.
    """

    def __init__(self, secret: str):
        self.secret = secret

    def _sign(self, payload: str) -> str:
        return hmac.new(
            self.secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

    def dispatch(self, url: str, event: str, data: dict, timeout: int = 5) -> bool:
        payload = json.dumps({"event": event, "timestamp": timezone.now().isoformat(), "data": data})
        signature = self._sign(payload)
        try:
            resp = requests.post(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Marketplace-Signature": signature,
                    "X-Marketplace-Event": event,
                },
                timeout=timeout,
            )
            success = resp.status_code in (200, 201, 202, 204)
            logger.info("Webhook %s → %s : %s", event, url, resp.status_code)
            return success
        except Exception as e:
            logger.error("Webhook dispatch failed: %s", e)
            return False
