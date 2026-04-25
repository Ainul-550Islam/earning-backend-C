# earning_backend/api/notifications/services/providers/LineProvider.py
"""
LINE Messaging Provider — Send notifications via LINE Messaging API.

LINE is extremely popular in: Thailand, Japan, Taiwan, Indonesia.
For Bangladesh earning sites targeting Southeast Asian publishers.

Settings:
    LINE_CHANNEL_ACCESS_TOKEN — LINE Channel Access Token
    LINE_CHANNEL_SECRET       — LINE Channel Secret (for webhook verification)
"""

import json
import logging
from typing import Dict

from django.conf import settings

logger = logging.getLogger(__name__)


class LineProvider:
    """LINE Messaging API notification provider."""

    API_URL = 'https://api.line.me/v2/bot/message/push'
    MULTICAST_URL = 'https://api.line.me/v2/bot/message/multicast'
    BROADCAST_URL = 'https://api.line.me/v2/bot/message/broadcast'

    def __init__(self):
        self._token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', '')
        self._secret = getattr(settings, 'LINE_CHANNEL_SECRET', '')
        self._available = bool(self._token)
        if not self._available:
            logger.info('LineProvider: LINE_CHANNEL_ACCESS_TOKEN not set.')
        self._requests = None

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, line_user_id: str = '', **kwargs) -> Dict:
        """
        Send a notification to a LINE user.

        Args:
            notification:  Notification instance.
            line_user_id:  LINE user ID (starts with 'U...'). Falls back to user profile.
        """
        if not self._available:
            return {'success': False, 'provider': 'line', 'error': 'Not configured'}

        if not line_user_id:
            user = getattr(notification, 'user', None)
            profile = getattr(user, 'profile', None) if user else None
            line_user_id = getattr(profile, 'line_user_id', '') or ''

        if not line_user_id:
            return {'success': False, 'provider': 'line', 'error': 'No LINE user ID'}

        messages = self._build_messages(notification)
        payload = {'to': line_user_id, 'messages': messages}

        return self._post(self.API_URL, payload)

    def send_flex(self, line_user_id: str, title: str, body: str,
                   action_url: str = '', image_url: str = '') -> Dict:
        """Send a rich Flex Message."""
        if not self._available:
            return {'success': False, 'error': 'Not configured'}

        flex_content = {
            'type': 'bubble',
            'hero': {'type': 'image', 'url': image_url, 'size': 'full',
                     'aspectRatio': '20:13', 'aspectMode': 'cover'} if image_url else None,
            'body': {
                'type': 'box', 'layout': 'vertical',
                'contents': [
                    {'type': 'text', 'text': title, 'weight': 'bold', 'size': 'xl'},
                    {'type': 'text', 'text': body, 'size': 'sm', 'color': '#888888', 'wrap': True},
                ]
            },
            'footer': {
                'type': 'box', 'layout': 'vertical',
                'contents': [
                    {'type': 'button', 'style': 'primary',
                     'action': {'type': 'uri', 'label': 'View Details', 'uri': action_url or '#'}}
                ] if action_url else []
            }
        }
        # Remove None values
        flex_content = {k: v for k, v in flex_content.items() if v}

        payload = {
            'to': line_user_id,
            'messages': [{'type': 'flex', 'altText': title, 'contents': flex_content}]
        }
        return self._post(self.API_URL, payload)

    def broadcast(self, notification) -> Dict:
        """Broadcast a notification to all LINE followers."""
        if not self._available:
            return {'success': False, 'error': 'Not configured'}
        messages = self._build_messages(notification)
        return self._post(self.BROADCAST_URL, {'messages': messages})

    def multicast(self, line_user_ids: list, notification) -> Dict:
        """Send to multiple LINE users at once (max 500 per call)."""
        if not self._available:
            return {'success': False, 'error': 'Not configured'}
        messages = self._build_messages(notification)
        results = []
        for i in range(0, len(line_user_ids), 500):
            batch = line_user_ids[i:i + 500]
            result = self._post(self.MULTICAST_URL, {'to': batch, 'messages': messages})
            results.append(result)
        success_count = sum(1 for r in results if r.get('success'))
        return {'success': success_count > 0, 'batches': len(results), 'provider': 'line'}

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE webhook signature."""
        import hashlib
        import hmac
        import base64
        if not self._secret:
            return True
        expected = base64.b64encode(
            hmac.new(self._secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)

    def _build_messages(self, notification) -> list:
        """Build LINE message objects from notification."""
        title = getattr(notification, 'title', '')
        message = getattr(notification, 'message', '')
        action_url = getattr(notification, 'action_url', '') or ''

        if action_url:
            return [{
                'type': 'template',
                'altText': title,
                'template': {
                    'type': 'buttons',
                    'title': title[:40],
                    'text': message[:160],
                    'actions': [{'type': 'uri', 'label': 'View', 'uri': action_url}]
                }
            }]
        return [{'type': 'text', 'text': f'{title}\n\n{message}'}]

    def _post(self, url: str, payload: dict) -> Dict:
        req = self._get_requests()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._token}',
        }
        try:
            resp = req.post(url, json=payload, headers=headers, timeout=10)
            success = resp.status_code == 200
            return {'success': success, 'provider': 'line',
                    'status_code': resp.status_code,
                    'error': '' if success else resp.text[:200]}
        except Exception as exc:
            logger.error(f'LineProvider._post: {exc}')
            return {'success': False, 'provider': 'line', 'error': str(exc)}

    def _get_requests(self):
        if not self._requests:
            import requests
            self._requests = requests
        return self._requests


line_provider = LineProvider()
