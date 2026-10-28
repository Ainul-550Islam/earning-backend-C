"""
Backup Module Webhooks
Webhook utilities for sending backup event notifications to external systems.
"""

import json
import logging
import hashlib
import hmac
from typing import Dict, Any, Optional, List
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Raised when a webhook delivery fails"""
    pass


class WebhookPayload:
    """Structured webhook payload"""

    def __init__(self, event_type: str, data: Dict[str, Any], timestamp: Optional[datetime] = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class WebhookSigner:
    """Signs webhook payloads with HMAC-SHA256"""

    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret

    def sign(self, payload: str) -> str:
        sig = hmac.new(self.secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def verify(self, payload: str, signature: str) -> bool:
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)


class WebhookClient:
    """HTTP client for sending webhook requests"""

    DEFAULT_TIMEOUT = 10
    DEFAULT_HEADERS = {"Content-Type": "application/json", "User-Agent": "BackupModule/1.0"}

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, secret: Optional[str] = None):
        self.timeout = timeout
        self.signer = WebhookSigner(secret) if secret else None

    def send(self, url: str, payload: WebhookPayload, extra_headers: Optional[Dict] = None) -> bool:
        """
        Send a webhook POST request.

        Returns True on 2xx, raises WebhookDeliveryError otherwise.
        """
        body = payload.to_json()
        headers = dict(self.DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        if self.signer:
            headers["X-Backup-Signature"] = self.signer.sign(body)
        headers["X-Backup-Event"] = payload.event_type

        try:
            resp = requests.post(url, data=body, headers=headers, timeout=self.timeout)
            if not resp.ok:
                raise WebhookDeliveryError(
                    f"Webhook delivery failed: {resp.status_code} {resp.text[:200]}"
                )
            logger.info("Webhook delivered to %s [%s]", url, payload.event_type)
            return True
        except requests.RequestException as exc:
            raise WebhookDeliveryError(f"Request error: {exc}") from exc


class BackupWebhookDispatcher:
    """
    Dispatch backup lifecycle events to registered webhook endpoints.
    Reads endpoint list from settings.BACKUP_WEBHOOK_ENDPOINTS or accepts them directly.
    """

    def __init__(self, endpoints: Optional[List[str]] = None, secret: Optional[str] = None):
        self.endpoints = endpoints or getattr(settings, "BACKUP_WEBHOOK_ENDPOINTS", [])
        self.client = WebhookClient(secret=secret)

    def dispatch(self, event_type: str, data: Dict[str, Any]) -> Dict[str, bool]:
        """Send event to all registered endpoints. Returns {url: success} map."""
        payload = WebhookPayload(event_type=event_type, data=data)
        results: Dict[str, bool] = {}
        for url in self.endpoints:
            try:
                self.client.send(url, payload)
                results[url] = True
            except WebhookDeliveryError as exc:
                logger.error("Failed webhook to %s: %s", url, exc)
                results[url] = False
        return results

    # Convenience helpers for common events
    def backup_started(self, backup_id: str, **kwargs):
        return self.dispatch("backup.started", {"backup_id": backup_id, **kwargs})

    def backup_completed(self, backup_id: str, size: int, **kwargs):
        return self.dispatch("backup.completed", {"backup_id": backup_id, "size": size, **kwargs})

    def backup_failed(self, backup_id: str, error: str, **kwargs):
        return self.dispatch("backup.failed", {"backup_id": backup_id, "error": error, **kwargs})

    def backup_restored(self, backup_id: str, **kwargs):
        return self.dispatch("backup.restored", {"backup_id": backup_id, **kwargs})
