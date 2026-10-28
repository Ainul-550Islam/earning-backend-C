# api/cms/webhooks.py
"""Webhook management for CMS - handle external service integrations."""
import logging
import hashlib
import hmac
import json
import time
from typing import Dict, Any, List, Optional, Callable
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ── Original WebhookDispatcher (Enhanced) ─────────────────────────────────────

class WebhookDispatcher:
    """Send outbound webhooks to registered endpoints."""

    @staticmethod
    def dispatch(event_type: str, payload: Dict[str, Any],
                  endpoint_url: str, secret: str = '') -> bool:
        """
        Send webhook POST to external endpoint.
        Signed with HMAC-SHA256 if secret is provided.
        """
        import urllib.request, urllib.error
        body = json.dumps({
            'event': event_type,
            'data': payload,
            'timestamp': timezone.now().isoformat(),
            'cms_version': '2.0.0',
        }).encode()

        headers = {
            'Content-Type': 'application/json',
            'X-CMS-Event': event_type,
            'X-CMS-Timestamp': str(int(time.time())),
        }
        if secret:
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers['X-CMS-Signature'] = f"sha256={sig}"

        try:
            req = urllib.request.Request(endpoint_url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                success = 200 <= resp.status < 300
                if not success:
                    logger.warning(f"[Webhook] {event_type} → {endpoint_url} HTTP {resp.status}")
                return success
        except Exception as e:
            logger.error(f"[Webhook] dispatch failed: {event_type} → {endpoint_url}: {e}")
            return False

    @staticmethod
    def dispatch_reward(user, amount: float, currency: str = 'USD',
                         lead_id: str = '', virtual_amount: float = 0):
        """Dispatch reward_earned webhook to registered endpoints."""
        payload = {
            'user_id': user.id,
            'username': user.username,
            'amount': amount,
            'currency': currency,
            'lead_id': lead_id,
            'virtual_amount': virtual_amount,
        }
        for endpoint in WebhookDispatcher._get_endpoints('reward_earned'):
            WebhookDispatcher.dispatch('reward_earned', payload,
                                        endpoint['url'], endpoint.get('secret', ''))

    @staticmethod
    def dispatch_withdrawal(user, amount_usd: float, method: str, status: str):
        """Dispatch withdrawal webhook."""
        payload = {
            'user_id': user.id,
            'amount_usd': amount_usd,
            'method': method,
            'status': status,
        }
        for endpoint in WebhookDispatcher._get_endpoints('withdrawal'):
            WebhookDispatcher.dispatch('withdrawal_update', payload,
                                        endpoint['url'], endpoint.get('secret', ''))

    @staticmethod
    def _get_endpoints(event_type: str) -> list:
        """Get registered webhook endpoints for an event type from settings."""
        webhooks = getattr(settings, 'CMS_OUTBOUND_WEBHOOKS', {})
        return webhooks.get(event_type, [])


class WebhookRegistration:
    """Register/manage outbound webhook endpoints."""

    @staticmethod
    def register(event_type: str, url: str, secret: str = '') -> bool:
        """Register a webhook endpoint in cache (for dynamic registration)."""
        from django.core.cache import cache
        key = f"cms:webhooks:{event_type}"
        endpoints = cache.get(key, [])
        endpoint = {'url': url, 'secret': secret, 'registered_at': timezone.now().isoformat()}
        if not any(e['url'] == url for e in endpoints):
            endpoints.append(endpoint)
            cache.set(key, endpoints, timeout=None)
        return True

    @staticmethod
    def list_registered() -> Dict[str, list]:
        from django.core.cache import cache
        events = ['reward_earned', 'offer_completed', 'withdrawal', 'user_registered']
        return {e: cache.get(f"cms:webhooks:{e}", []) for e in events}
