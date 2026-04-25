# api/notifications/services/providers/DiscordProvider.py
"""
DiscordProvider — Discord webhook notifications.

Use cases:
  - Community achievement announcements → #achievements
  - Leaderboard updates → #leaderboard
  - System alerts → #admin-alerts
  - New offers → #offers

Settings:
    DISCORD_WEBHOOK_URL         — default webhook URL
    DISCORD_ALERT_WEBHOOK_URL   — admin alerts webhook
    DISCORD_OFFERS_WEBHOOK_URL  — offers channel webhook
"""
import logging
from typing import Dict, Optional
from django.conf import settings
logger = logging.getLogger(__name__)

DISCORD_COLORS = {
    'critical': 16711680,   # Red
    'urgent':   16744272,   # Orange-red
    'high':     16753920,   # Orange
    'medium':   3580392,    # Green
    'low':      4437377,    # Blue
    'success':  3580392,    # Green
    'info':     3447003,    # Blue
}

class DiscordProvider:
    """Discord webhook notification provider."""

    WEBHOOK_MAP = {
        'fraud_detected':       getattr(settings, 'DISCORD_ALERT_WEBHOOK_URL', ''),
        'achievement_unlocked': getattr(settings, 'DISCORD_ACHIEVEMENTS_WEBHOOK_URL', ''),
        'leaderboard_update':   getattr(settings, 'DISCORD_LEADERBOARD_WEBHOOK_URL', ''),
        'offer_available':      getattr(settings, 'DISCORD_OFFERS_WEBHOOK_URL', ''),
        'default':              getattr(settings, 'DISCORD_WEBHOOK_URL', ''),
    }

    def __init__(self):
        self._default_url = getattr(settings, 'DISCORD_WEBHOOK_URL', '')
        self._available = bool(self._default_url)
        if not self._available:
            logger.warning('DiscordProvider: DISCORD_WEBHOOK_URL not set.')
        self._requests = None

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, **kwargs) -> Dict:
        if not self._available:
            return {'success': False, 'error': 'DiscordProvider not configured', 'provider': 'discord'}

        priority = getattr(notification, 'priority', 'medium') or 'medium'
        color = DISCORD_COLORS.get(priority, DISCORD_COLORS['medium'])
        webhook_url = self._get_webhook_url(notification)

        payload = {
            'embeds': [{
                'title': notification.title,
                'description': notification.message,
                'color': color,
                'footer': {'text': f'#{notification.id} • {notification.notification_type}'},
            }]
        }

        action_url = getattr(notification, 'action_url', '') or ''
        if action_url:
            payload['embeds'][0]['url'] = action_url

        user = getattr(notification, 'user', None)
        if user:
            payload['embeds'][0]['fields'] = [
                {'name': 'User', 'value': getattr(user, 'username', str(user.pk)), 'inline': True},
            ]

        return self._post(webhook_url, payload)

    def send_announcement(self, title: str, description: str, color: int = 3580392,
                          webhook_url: str = '', image_url: str = '') -> Dict:
        """Send a rich announcement embed."""
        url = webhook_url or self._default_url
        if not url:
            return {'success': False, 'error': 'No webhook URL', 'provider': 'discord'}

        embed = {'title': title, 'description': description, 'color': color}
        if image_url:
            embed['image'] = {'url': image_url}

        return self._post(url, {'embeds': [embed]})

    def _post(self, url: str, payload: Dict) -> Dict:
        req = self._get_requests()
        try:
            resp = req.post(url, json=payload, timeout=10)
            success = resp.status_code in (200, 204)
            return {'success': success, 'provider': 'discord',
                    'status_code': resp.status_code, 'error': '' if success else f'HTTP {resp.status_code}'}
        except Exception as exc:
            logger.error(f'DiscordProvider._post: {exc}')
            return {'success': False, 'provider': 'discord', 'error': str(exc)}

    def _get_webhook_url(self, notification) -> str:
        notif_type = getattr(notification, 'notification_type', '') or ''
        url = self.WEBHOOK_MAP.get(notif_type, '') or self.WEBHOOK_MAP.get('default', '')
        return url or self._default_url

    def _get_requests(self):
        if not self._requests:
            import requests
            self._requests = requests
        return self._requests


discord_provider = DiscordProvider()
