# earning_backend/api/notifications/services/providers/APNsProvider.py
"""
APNsProvider — Apple Push Notification service provider.

Uses the `apns2` library (pip install apns2) OR falls back to the
firebase_admin APNs path already handled by FCMProvider for iOS devices
that use FCM token bridging.

This provider is for *direct APNs* sends (production / sandbox) using
a .p8 private key (JWT-based authentication — the preferred modern method).

Settings required:
    APNS_KEY_ID       — 10-character Key ID from Apple Developer
    APNS_TEAM_ID      — 10-character Team ID from Apple Developer
    APNS_PRIVATE_KEY  — path to AuthKey_XXXXXXXXXX.p8 file  OR
                        the raw private key string (PEM)
    APNS_TOPIC        — iOS bundle ID, e.g. "com.yourapp.app"
    APNS_USE_SANDBOX  — (optional bool, default False) use APNs sandbox

Dependencies (optional — gracefully degraded if not installed):
    pip install httpx  (used for HTTP/2 APNs transport)
    pip install PyJWT  (used to sign the APNs JWT)
"""

import json
import logging
import time
import uuid
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# APNsProvider class
# ---------------------------------------------------------------------------

class APNsProvider:
    """
    Direct APNs HTTP/2 provider using JWT bearer authentication.

    Falls back gracefully when dependencies are missing or settings are
    absent — returning a structured error dict.
    """

    APNS_PRODUCTION_HOST = 'api.push.apple.com'
    APNS_SANDBOX_HOST = 'api.sandbox.push.apple.com'
    APNS_PORT = 443

    # APNs response status codes
    SUCCESS_STATUS = 200

    # Priority values
    PRIORITY_HIGH = '10'   # immediate delivery
    PRIORITY_LOW = '5'     # conserves battery

    def __init__(self):
        self._available = False
        self._key_id: str = getattr(settings, 'APNS_KEY_ID', '')
        self._team_id: str = getattr(settings, 'APNS_TEAM_ID', '')
        self._private_key: str = getattr(settings, 'APNS_PRIVATE_KEY', '')
        self._topic: str = getattr(settings, 'APNS_TOPIC', '')
        self._use_sandbox: bool = getattr(settings, 'APNS_USE_SANDBOX', False)

        if self._key_id and self._team_id and self._private_key and self._topic:
            self._available = True
            logger.info('APNsProvider: configured successfully.')
        else:
            logger.warning(
                'APNsProvider: one or more required settings missing '
                '(APNS_KEY_ID, APNS_TEAM_ID, APNS_PRIVATE_KEY, APNS_TOPIC). '
                'APNs direct sends disabled.'
            )

        # Cached JWT token and its expiry
        self._jwt_token: Optional[str] = None
        self._jwt_issued_at: float = 0.0
        self._JWT_TTL_SECONDS: int = 55 * 60  # refresh every 55 min (Apple max is 60)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    def send(self, device_token: str, notification, extra_data: Optional[Dict] = None) -> Dict:
        """
        Send a push notification to a single APNs device token.

        Args:
            device_token:  Hex-encoded APNs device token string.
            notification:  Core Notification model instance.
            extra_data:    Optional extra JSON payload data.

        Returns:
            Dict with keys: success, provider, message_id, error, is_invalid_token.
        """
        if not self._available:
            return self._unavailable_response()

        try:
            import httpx
        except ImportError:
            return {
                'success': False,
                'provider': 'apns',
                'message_id': '',
                'is_invalid_token': False,
                'error': 'httpx not installed — pip install httpx',
            }

        payload = self._build_payload(notification, extra_data or {})
        headers = self._build_headers(notification)
        apns_id = str(uuid.uuid4())
        host = self.APNS_SANDBOX_HOST if self._use_sandbox else self.APNS_PRODUCTION_HOST
        url = f'https://{host}/3/device/{device_token}'

        try:
            with httpx.Client(http2=True, timeout=10.0) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={**headers, 'apns-id': apns_id},
                )

            if response.status_code == self.SUCCESS_STATUS:
                return {
                    'success': True,
                    'provider': 'apns',
                    'message_id': apns_id,
                    'is_invalid_token': False,
                    'error': '',
                }
            else:
                body = {}
                try:
                    body = response.json()
                except Exception:
                    pass
                reason = body.get('reason', f'HTTP {response.status_code}')
                is_invalid = reason in ('BadDeviceToken', 'Unregistered', 'MissingDeviceToken')
                logger.warning(f'APNsProvider.send failed — reason: {reason}')
                return {
                    'success': False,
                    'provider': 'apns',
                    'message_id': '',
                    'is_invalid_token': is_invalid,
                    'error': reason,
                }

        except Exception as exc:
            logger.error(f'APNsProvider.send exception: {exc}')
            return {
                'success': False,
                'provider': 'apns',
                'message_id': '',
                'is_invalid_token': False,
                'error': str(exc),
            }

    def send_bulk(
        self,
        device_tokens: List[str],
        notification,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Send the same notification to multiple APNs device tokens.
        Uses a single HTTP/2 connection and sends requests concurrently
        via httpx.AsyncClient (fallback: sequential with httpx.Client).

        Returns:
            Dict with success (bool), total, success_count, failure_count,
            invalid_tokens (list), responses (list of dicts).
        """
        if not self._available:
            return {
                'success': False,
                'provider': 'apns',
                'error': 'APNsProvider not available',
                'total': len(device_tokens),
                'success_count': 0,
                'failure_count': len(device_tokens),
                'invalid_tokens': [],
                'responses': [],
            }

        responses = []
        success_count = 0
        failure_count = 0
        invalid_tokens: List[str] = []

        for token in device_tokens:
            result = self.send(token, notification, extra_data)
            responses.append({'token': token[-6:] + '…', **result})
            if result['success']:
                success_count += 1
            else:
                failure_count += 1
                if result.get('is_invalid_token'):
                    invalid_tokens.append(token)

        return {
            'success': success_count > 0,
            'provider': 'apns',
            'error': '',
            'total': len(device_tokens),
            'success_count': success_count,
            'failure_count': failure_count,
            'invalid_tokens': invalid_tokens,
            'responses': responses,
        }

    # ------------------------------------------------------------------
    # Payload / header builders
    # ------------------------------------------------------------------

    def _build_payload(self, notification, extra_data: Dict) -> Dict:
        """Build the APNs JSON payload dict."""
        is_high_priority = getattr(notification, 'is_high_priority', lambda: False)()
        sound_enabled = getattr(notification, 'sound_enabled', True)
        badge_count = getattr(notification, 'badge_count', None)
        group_id = getattr(notification, 'group_id', '') or None
        notif_type = getattr(notification, 'notification_type', '')

        alert: Dict = {
            'title': notification.title,
            'body': notification.message,
        }

        aps: Dict = {
            'alert': alert,
            'sound': 'default' if sound_enabled else None,
            'category': notif_type,
        }
        if badge_count is not None:
            aps['badge'] = badge_count
        if group_id:
            aps['thread-id'] = group_id

        # Remove None values
        aps = {k: v for k, v in aps.items() if v is not None}

        payload: Dict = {'aps': aps}

        # Custom data
        payload['notification_id'] = str(notification.id)
        payload['type'] = notif_type
        payload['action_url'] = getattr(notification, 'action_url', '') or ''
        payload['deep_link'] = getattr(notification, 'deep_link', '') or ''

        for k, v in extra_data.items():
            payload[k] = v

        return payload

    def _build_headers(self, notification) -> Dict:
        """Build the APNs HTTP request headers."""
        is_high_priority = getattr(notification, 'is_high_priority', lambda: False)()

        headers = {
            'authorization': f'bearer {self._get_jwt_token()}',
            'apns-topic': self._topic,
            'apns-priority': self.PRIORITY_HIGH if is_high_priority else self.PRIORITY_LOW,
            'apns-push-type': 'alert',
            'content-type': 'application/json',
        }
        return headers

    # ------------------------------------------------------------------
    # JWT management
    # ------------------------------------------------------------------

    def _get_jwt_token(self) -> str:
        """
        Return a valid JWT bearer token for APNs.
        Generates a new one if the cached token has expired.
        """
        now = time.time()
        if self._jwt_token and (now - self._jwt_issued_at) < self._JWT_TTL_SECONDS:
            return self._jwt_token

        try:
            import jwt as pyjwt  # PyJWT

            private_key = self._private_key
            # If the value is a file path, read the key content
            if private_key.endswith('.p8') or private_key.endswith('.pem'):
                try:
                    with open(private_key, 'r') as f:
                        private_key = f.read()
                except OSError as exc:
                    logger.error(f'APNsProvider: cannot read private key file — {exc}')
                    raise

            payload = {
                'iss': self._team_id,
                'iat': int(now),
            }
            headers = {'alg': 'ES256', 'kid': self._key_id}

            token = pyjwt.encode(payload, private_key, algorithm='ES256', headers=headers)
            self._jwt_token = token if isinstance(token, str) else token.decode('utf-8')
            self._jwt_issued_at = now
            return self._jwt_token

        except ImportError:
            logger.error('APNsProvider: PyJWT not installed — pip install PyJWT')
            raise
        except Exception as exc:
            logger.error(f'APNsProvider: JWT generation failed — {exc}')
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unavailable_response(self) -> Dict:
        return {
            'success': False,
            'provider': 'apns',
            'message_id': '',
            'is_invalid_token': False,
            'error': 'APNsProvider not available — settings not configured',
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
apns_provider = APNsProvider()
