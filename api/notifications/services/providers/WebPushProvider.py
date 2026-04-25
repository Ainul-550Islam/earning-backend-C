# earning_backend/api/notifications/services/providers/WebPushProvider.py
"""
WebPushProvider — Browser Web Push Notifications (RFC 8030 / VAPID).

Sends push notifications to browsers that have subscribed via the
Push API (Chrome, Firefox, Edge, Safari 16+).

Uses the `pywebpush` library (pip install pywebpush) and VAPID keys
for authentication.

Settings required:
    WEBPUSH_VAPID_PRIVATE_KEY  — Base64url-encoded VAPID private key
    WEBPUSH_VAPID_PUBLIC_KEY   — Base64url-encoded VAPID public key
    WEBPUSH_VAPID_CLAIMS_EMAIL — mailto: email for VAPID claims
                                 e.g. 'mailto:admin@yourapp.com'

Generate VAPID keys (once):
    python -c "from pywebpush import webpush, Vapid; v=Vapid(); v.generate_keys(); print(v.private_key, v.public_key)"
    OR use:  vapid --gen

Dependencies:
    pip install pywebpush
"""

import json
import logging
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebPushProvider class
# ---------------------------------------------------------------------------

class WebPushProvider:
    """
    Wrapper around pywebpush for RFC 8030 Web Push delivery.
    """

    TTL = 86400  # 24 hours in seconds (how long the push service retains it)

    def __init__(self):
        self._private_key: str = getattr(settings, 'WEBPUSH_VAPID_PRIVATE_KEY', '')
        self._public_key: str = getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')
        self._claims_email: str = getattr(
            settings, 'WEBPUSH_VAPID_CLAIMS_EMAIL', 'mailto:noreply@example.com'
        )
        self._available: bool = False

        if self._private_key and self._public_key and self._claims_email:
            try:
                import py_vapid  # noqa: F401  (part of pywebpush)
                self._available = True
                logger.info('WebPushProvider: VAPID keys configured successfully.')
            except ImportError:
                logger.error(
                    'WebPushProvider: pywebpush not installed — pip install pywebpush'
                )
        else:
            logger.warning(
                'WebPushProvider: WEBPUSH_VAPID_PRIVATE_KEY / WEBPUSH_VAPID_PUBLIC_KEY / '
                'WEBPUSH_VAPID_CLAIMS_EMAIL not configured. Web push disabled.'
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    def send(
        self,
        subscription_info: Dict,
        notification,
        extra_data: Optional[Dict] = None,
        ttl: int = TTL,
    ) -> Dict:
        """
        Send a web push notification to a single browser subscription.

        Args:
            subscription_info:  Dict with 'endpoint', 'keys' (p256dh, auth).
                                This is the JSON stored in PushDevice.web_push_subscription.
            notification:       Core Notification model instance.
            extra_data:         Optional extra fields merged into the payload.
            ttl:                Time-to-live in seconds.

        Returns:
            Dict with keys: success, provider, endpoint (masked), error, status_code.
        """
        if not self._available:
            return self._unavailable_response()

        if not self._is_valid_subscription(subscription_info):
            return {
                'success': False,
                'provider': 'web_push',
                'endpoint': '',
                'status_code': 0,
                'error': 'Invalid subscription_info — missing endpoint or keys',
                'is_invalid_subscription': True,
            }

        payload = self._build_payload(notification, extra_data or {})
        endpoint = subscription_info.get('endpoint', '')

        try:
            from pywebpush import webpush, WebPushException

            vapid_claims = {
                'sub': self._claims_email,
            }

            response = webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self._private_key,
                vapid_claims=vapid_claims,
                ttl=ttl,
            )

            status_code = getattr(response, 'status_code', 201)
            is_success = 200 <= status_code < 300

            return {
                'success': is_success,
                'provider': 'web_push',
                'endpoint': self._mask_endpoint(endpoint),
                'status_code': status_code,
                'error': '' if is_success else f'HTTP {status_code}',
                'is_invalid_subscription': False,
            }

        except Exception as exc:
            error_str = str(exc)
            is_gone = '410' in error_str or '404' in error_str  # subscription expired

            if is_gone:
                logger.info(f'WebPushProvider: subscription gone (410/404) — {self._mask_endpoint(endpoint)}')
            else:
                logger.error(f'WebPushProvider.send failed: {error_str}')

            return {
                'success': False,
                'provider': 'web_push',
                'endpoint': self._mask_endpoint(endpoint),
                'status_code': 410 if is_gone else 0,
                'error': error_str,
                'is_invalid_subscription': is_gone,
            }

    def send_bulk(
        self,
        subscriptions: List[Dict],
        notification,
        extra_data: Optional[Dict] = None,
        ttl: int = TTL,
    ) -> Dict:
        """
        Send the same notification to a list of web push subscriptions.

        Args:
            subscriptions:  List of subscription_info dicts.
            notification:   Core Notification model instance.
            extra_data:     Optional extra payload fields.
            ttl:            Time-to-live in seconds.

        Returns:
            Dict with success, total, success_count, failure_count,
            expired_subscriptions, responses.
        """
        if not self._available:
            return {
                'success': False,
                'provider': 'web_push',
                'error': 'WebPushProvider not available',
                'total': len(subscriptions),
                'success_count': 0,
                'failure_count': len(subscriptions),
                'expired_subscriptions': [],
                'responses': [],
            }

        responses = []
        success_count = 0
        failure_count = 0
        expired_subscriptions: List[Dict] = []

        for sub in subscriptions:
            result = self.send(sub, notification, extra_data, ttl)
            responses.append(result)
            if result['success']:
                success_count += 1
            else:
                failure_count += 1
                if result.get('is_invalid_subscription'):
                    expired_subscriptions.append(sub)

        return {
            'success': success_count > 0,
            'provider': 'web_push',
            'error': '',
            'total': len(subscriptions),
            'success_count': success_count,
            'failure_count': failure_count,
            'expired_subscriptions': expired_subscriptions,
            'responses': responses,
        }

    def get_vapid_public_key(self) -> str:
        """Return the VAPID public key string for the frontend subscription step."""
        return self._public_key

    # ------------------------------------------------------------------
    # Payload builder
    # ------------------------------------------------------------------

    def _build_payload(self, notification, extra_data: Dict) -> Dict:
        """Build the JSON payload sent inside the push message."""
        payload: Dict = {
            'title': notification.title,
            'body': notification.message,
            'icon': getattr(notification, 'icon_url', '') or '',
            'image': getattr(notification, 'image_url', '') or '',
            'badge': getattr(notification, 'icon_url', '') or '',
            'notification_id': str(notification.id),
            'type': getattr(notification, 'notification_type', ''),
            'action_url': getattr(notification, 'action_url', '') or '',
            'deep_link': getattr(notification, 'deep_link', '') or '',
            'priority': getattr(notification, 'priority', 'medium'),
        }

        sound_enabled = getattr(notification, 'sound_enabled', True)
        if sound_enabled:
            payload['vibrate'] = [200, 100, 200]  # vibration pattern

        # Actions (only supported in some browsers)
        action_url = payload.get('action_url', '')
        if action_url:
            payload['actions'] = [
                {'action': 'open', 'title': getattr(notification, 'action_text', 'Open') or 'Open'},
            ]

        # Merge extra data
        for k, v in extra_data.items():
            payload[k] = v

        return payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_subscription(sub: Dict) -> bool:
        """Return True if the subscription dict has required fields."""
        if not sub or not isinstance(sub, dict):
            return False
        if not sub.get('endpoint'):
            return False
        keys = sub.get('keys', {})
        if not keys or not keys.get('p256dh') or not keys.get('auth'):
            return False
        return True

    @staticmethod
    def _mask_endpoint(endpoint: str) -> str:
        """Return a masked endpoint URL for safe logging (keep domain, hide path)."""
        if not endpoint:
            return ''
        try:
            from urllib.parse import urlparse
            parsed = urlparse(endpoint)
            return f'{parsed.scheme}://{parsed.netloc}/…'
        except Exception:
            return endpoint[:40] + '…'

    def _unavailable_response(self) -> Dict:
        return {
            'success': False,
            'provider': 'web_push',
            'endpoint': '',
            'status_code': 0,
            'error': 'WebPushProvider not available — VAPID keys not configured',
            'is_invalid_subscription': False,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
web_push_provider = WebPushProvider()
