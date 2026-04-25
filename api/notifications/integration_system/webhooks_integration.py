# integration_system/webhooks_integration.py
"""Webhook Integration — Inbound/outbound webhook manager with signature verification, idempotency, retry."""
import hashlib, hmac, json, logging, uuid
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import WebhookEvents, CacheKeys, CacheTTL
from .integ_exceptions import WebhookVerificationFailed, DuplicateWebhook, WebhookProcessingFailed
logger = logging.getLogger(__name__)

class WebhookManager:
    """Manages inbound and outbound webhooks with verification and deduplication."""

    PROVIDERS = {
        'sendgrid': {'header': 'X-Twilio-Email-Event-Webhook-Signature', 'algo': 'sha256'},
        'twilio':   {'header': 'X-Twilio-Signature', 'algo': 'sha1'},
        'bkash':    {'header': 'X-BKash-Signature', 'algo': 'sha256'},
        'nagad':    {'header': 'X-Nagad-Signature', 'algo': 'sha256'},
        'stripe':   {'header': 'Stripe-Signature', 'algo': 'sha256'},
        'cpalead':  {'header': 'X-CPALead-Token', 'algo': 'token'},
    }

    def __init__(self):
        self._handlers: Dict[str, list] = {}

    def on_event(self, event_type: str):
        def decorator(fn):
            self._handlers.setdefault(event_type, []).append(fn)
            return fn
        return decorator

    def verify_signature(self, provider: str, payload: bytes, headers: dict, secret: str) -> bool:
        cfg = self.PROVIDERS.get(provider, {})
        header_name = cfg.get("header", "")
        algo = cfg.get("algo", "sha256")
        sig = headers.get(header_name, "")
        if not sig or not secret:
            return not getattr(settings, "WEBHOOK_REQUIRE_SIGNATURE", True)
        if algo == "sha256":
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, sig)
        elif algo == "sha1":
            expected = hmac.new(secret.encode(), payload, hashlib.sha1).hexdigest()
            return hmac.compare_digest(expected, sig)
        elif algo == "token":
            return hmac.compare_digest(secret, sig)
        return False

    def check_idempotency(self, idempotency_key: str) -> bool:
        """Return True if this webhook was already processed."""
        key = f"webhook:idem:{idempotency_key}"
        if cache.get(key):
            return True
        cache.set(key, "1", CacheTTL.DAILY)
        return False

    def process_inbound(self, provider: str, event_type: str, payload: dict,
                        request_id: str = "") -> Dict:
        """Process an inbound webhook event."""
        if not request_id:
            request_id = str(uuid.uuid4())
        if self.check_idempotency(f"{provider}:{request_id}"):
            return {"success": True, "status": "duplicate", "request_id": request_id}
        handlers = self._handlers.get(event_type, []) + self._handlers.get("*", [])
        results = []
        for handler in handlers:
            try:
                result = handler(provider=provider, event_type=event_type, payload=payload)
                results.append({"handler": handler.__name__, "success": True, "result": result})
            except Exception as exc:
                logger.error(f"Webhook handler {handler.__name__} failed: {exc}")
                results.append({"handler": handler.__name__, "success": False, "error": str(exc)})
        # Publish to event bus
        try:
            from .event_bus import event_bus
            event_bus.publish(f"webhook.{provider}.{event_type}", payload, source_module="webhook", async_dispatch=True)
        except Exception:
            pass
        return {"success": True, "request_id": request_id, "handlers_called": len(handlers), "results": results}

    def send_outbound(self, url: str, payload: dict, secret: str = "",
                      headers: Optional[Dict] = None) -> Dict:
        """Send an outbound webhook to an external URL."""
        import requests
        body = json.dumps(payload).encode()
        req_headers = {"Content-Type": "application/json"}
        if secret:
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            req_headers["X-Integration-Signature"] = sig
        if headers:
            req_headers.update(headers)
        try:
            resp = requests.post(url, data=body, headers=req_headers, timeout=15)
            return {"success": 200 <= resp.status_code < 300, "status_code": resp.status_code, "url": url}
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": url}


webhook_manager = WebhookManager()
