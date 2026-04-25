# api/wallet/webhooks.py
"""
Outgoing webhook delivery system (Stripe-style).
Publishers subscribe to wallet events via WebhookEndpoint model.
When events fire → sign payload → HTTP POST to endpoint → retry on failure.
"""
import hashlib, hmac, json, logging, requests
from datetime import datetime
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger("wallet.webhooks")

WEBHOOK_TIMEOUT = 10  # seconds
MAX_RETRIES     = 5


class WebhookDelivery:
    """Deliver signed webhook payloads to subscriber endpoints."""

    @staticmethod
    def sign(payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature."""
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def build_payload(event_type: str, data: dict, wallet_id: int = None) -> dict:
        """Build standardized webhook payload."""
        return {
            "event":      event_type,
            "api_version":"2024-01-01",
            "created":    int(timezone.now().timestamp()),
            "wallet_id":  wallet_id,
            "data":       {k: str(v) if isinstance(v, Decimal) else v for k, v in data.items()},
        }

    @classmethod
    def deliver(cls, endpoint_url: str, secret: str, event_type: str,
                data: dict, wallet_id: int = None) -> dict:
        """Deliver a webhook to an endpoint."""
        payload_dict = cls.build_payload(event_type, data, wallet_id)
        payload_str  = json.dumps(payload_dict, sort_keys=True, default=str)
        signature    = cls.sign(payload_str, secret)

        headers = {
            "Content-Type":         "application/json",
            "X-Wallet-Signature":   f"sha256={signature}",
            "X-Wallet-Event":        event_type,
            "X-Wallet-Delivery-ID": hashlib.md5(f"{event_type}{timezone.now()}".encode()).hexdigest(),
        }
        try:
            resp = requests.post(
                endpoint_url,
                data=payload_str,
                headers=headers,
                timeout=WEBHOOK_TIMEOUT,
            )
            success = 200 <= resp.status_code < 300
            logger.info(f"Webhook delivered: {event_type} → {endpoint_url} [{resp.status_code}]")
            return {
                "success":     success,
                "status_code": resp.status_code,
                "response":    resp.text[:500],
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def deliver_to_all(cls, event_type: str, data: dict, wallet_id: int = None) -> list:
        """Deliver event to all subscribed endpoints."""
        results = []
        try:
            from .models_cpalead_extra import WebhookEndpoint
            endpoints = WebhookEndpoint.objects.filter(
                is_active=True
            ).filter(
                events__contains=[event_type]
            ) if hasattr(WebhookEndpoint, "events") else WebhookEndpoint.objects.filter(is_active=True)

            for ep in endpoints:
                result = cls.deliver(ep.url, ep.secret, event_type, data, wallet_id)
                results.append({"endpoint": ep.url, **result})
        except Exception as e:
            logger.debug(f"deliver_to_all skip: {e}")
        return results

    @staticmethod
    def verify_incoming(payload: bytes, signature: str, secret: str) -> bool:
        """Verify an incoming webhook signature."""
        sig = signature.replace("sha256=", "")
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
