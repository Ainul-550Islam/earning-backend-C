# FILE 99 of 257 — notifications/WebhookNotifier.py
# Outgoing merchant webhook notifications
import requests, hashlib, hmac, json
from django.conf import settings
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

class WebhookNotifier:
    """Send signed webhook notifications to merchant callback URLs."""

    def send(self, url: str, event_type: str, payload: dict, secret: str = None) -> bool:
        body      = json.dumps(payload, default=str)
        signature = self._sign(body, secret or getattr(settings, 'WEBHOOK_SECRET', ''))
        headers   = {
            'Content-Type':     'application/json',
            'X-Payment-Event':  event_type,
            'X-Signature':      signature,
            'X-Timestamp':      str(int(timezone.now().timestamp())),
        }
        try:
            resp = requests.post(url, data=body, headers=headers, timeout=10)
            logger.info(f'Webhook {event_type} → {url}: {resp.status_code}')
            return resp.status_code < 400
        except Exception as e:
            logger.error(f'WebhookNotifier error: {e}')
            return False

    def _sign(self, body: str, secret: str) -> str:
        return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
