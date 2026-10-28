# =============================================================================
# auto_mod/webhooks.py
# =============================================================================
"""
Webhook notification system for auto_mod events.

Sends callbacks to registered advertiser/publisher endpoints on:
  - submission.approved / submission.rejected / submission.escalated
  - appeal.resolved
  - bot.error
"""
from __future__ import annotations
import hashlib, hmac, json, logging, time
from typing import Any
from django.utils import timezone

logger = logging.getLogger("auto_mod.webhooks")

EVENT_TYPES = frozenset([
    "submission.approved", "submission.rejected", "submission.escalated",
    "submission.pending_review", "appeal.created", "appeal.resolved",
    "appeal.escalated", "bot.started", "bot.stopped", "bot.error",
    "queue.assigned", "queue.escalated", "queue.completed",
    "model.deployed", "model.retired",
])


class WebhookPayload:
    def __init__(self, event_type: str, data: dict, webhook_id: str = ""):
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type!r}")
        self.event_type  = event_type
        self.data        = data
        self.webhook_id  = webhook_id
        self.timestamp   = timezone.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "event":      self.event_type,
            "data":       self.data,
            "webhook_id": self.webhook_id,
            "timestamp":  self.timestamp,
        }

    def sign(self, secret: str) -> str:
        body = json.dumps(self.to_dict(), sort_keys=True)
        return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


class WebhookDispatcher:
    """Dispatch webhook events to registered endpoints."""

    def __init__(self, secret: str = ""):
        self._secret = secret
        self._handlers: dict[str, list] = {}

    def register(self, event_type: str, handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def dispatch(self, event_type: str, data: dict) -> list[dict]:
        payload = WebhookPayload(event_type, data)
        results = []
        for handler in self._handlers.get(event_type, []):
            try:
                result = handler(payload.to_dict())
                results.append({"success": True, "result": result})
            except Exception as exc:
                logger.exception("webhook.dispatch_error event=%s", event_type)
                results.append({"success": False, "error": str(exc)})
        return results

    def dispatch_submission_event(self, submission, event_type: str) -> list[dict]:
        return self.dispatch(event_type, {
            "submission_id":   str(submission.pk),
            "content_id":      submission.content_id,
            "content_type":    submission.content_type,
            "submission_type": submission.submission_type,
            "status":          submission.status,
        })


# Singleton dispatcher (configure in apps.py ready())
dispatcher = WebhookDispatcher()
