# api/admin_panel/INTEGRATION_SYSTEM/webhooks_integration.py
"""
WebhooksIntegration — Manage outbound webhooks from admin_panel to external services.
Fires webhooks on key events: user_banned, withdrawal_approved, fraud_detected, etc.
"""
import json
import hashlib
import hmac
import logging
import requests
from typing import Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookDelivery:
    """Manages outbound webhook delivery with retry and signature."""

    TIMEOUT = 10  # seconds
    MAX_RETRIES = 3

    @classmethod
    def deliver(cls, url: str, payload: dict, secret: str = '', event_type: str = '', webhook_id: str = '') -> Dict:
        """Deliver a webhook with HMAC signature."""
        body = json.dumps(payload, default=str)
        headers = {
            'Content-Type': 'application/json',
            'X-AdminPanel-Event': event_type,
            'X-AdminPanel-Webhook-ID': webhook_id,
            'X-AdminPanel-Timestamp': str(int(timezone.now().timestamp())),
        }
        if secret:
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers['X-AdminPanel-Signature'] = f'sha256={sig}'

        for attempt in range(cls.MAX_RETRIES):
            try:
                resp = requests.post(url, data=body, headers=headers, timeout=cls.TIMEOUT)
                success = resp.status_code < 400
                result = {
                    'success': success,
                    'status_code': resp.status_code,
                    'attempt': attempt + 1,
                    'url': url,
                    'event_type': event_type,
                }
                if success:
                    logger.info(f"[Webhook] Delivered {event_type} to {url} in attempt {attempt+1}")
                    return result
                logger.warning(f"[Webhook] Failed attempt {attempt+1}: {resp.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"[Webhook] Request error attempt {attempt+1}: {e}")
        return {'success': False, 'url': url, 'event_type': event_type, 'attempts': cls.MAX_RETRIES}

    @classmethod
    def fire_event(cls, event_type: str, payload: dict) -> List[Dict]:
        """Fire a webhook event to all registered endpoints."""
        results = []
        try:
            from api.webhooks.models import WebhookEndpoint
            endpoints = WebhookEndpoint.objects.filter(
                is_active=True,
                events__contains=event_type,
            )
            for ep in endpoints:
                result = cls.deliver(
                    url=ep.url,
                    payload={'event': event_type, 'data': payload, 'timestamp': timezone.now().isoformat()},
                    secret=ep.secret,
                    event_type=event_type,
                    webhook_id=str(ep.pk),
                )
                results.append(result)
        except Exception as e:
            logger.error(f"[Webhook] fire_event error: {e}")
        return results