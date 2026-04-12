"""
webhook_manager/webhook_delivery.py
─────────────────────────────────────
Low-level HTTP delivery of webhook payloads.
Handles: JSON serialisation, HMAC signing, timeout, connection errors.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)
_DELIVERY_TIMEOUT = 10  # seconds


class WebhookDelivery:

    def deliver(
        self,
        url: str,
        payload: dict,
        secret: str = "",
        timeout: int = _DELIVERY_TIMEOUT,
        headers: dict = None,
    ) -> bool:
        """
        Deliver a JSON webhook payload to a URL.
        Returns True on success (2xx), False on failure.
        """
        import requests

        body = json.dumps(payload, default=str)
        ts = str(int(time.time()))

        req_headers = {
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": ts,
            "User-Agent": "PostbackEngine/2.0",
            **(headers or {}),
        }

        if secret:
            sig = self._sign(body, ts, secret)
            req_headers["X-Webhook-Signature"] = sig

        try:
            resp = requests.post(url, data=body, headers=req_headers, timeout=timeout)
            success = 200 <= resp.status_code < 300
            if not success:
                logger.warning(
                    "Webhook delivery failed: url=%s status=%d body=%s",
                    url[:80], resp.status_code, resp.text[:200],
                )
            return success
        except requests.Timeout:
            logger.warning("Webhook delivery timed out: url=%s", url[:80])
            return False
        except requests.ConnectionError as exc:
            logger.warning("Webhook delivery connection error: url=%s err=%s", url[:80], exc)
            return False
        except Exception as exc:
            logger.error("Webhook delivery unexpected error: url=%s err=%s", url[:80], exc)
            return False

    @staticmethod
    def _sign(body: str, timestamp: str, secret: str) -> str:
        message = f"{timestamp}.{body}"
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


webhook_delivery = WebhookDelivery()
