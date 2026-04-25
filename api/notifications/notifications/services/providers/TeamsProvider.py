# earning_backend/api/notifications/services/providers/TeamsProvider.py
"""
Microsoft Teams Provider — Send notifications via Teams Incoming Webhooks.

Use cases:
  - Admin team fraud alerts → #fraud-alerts channel
  - System health alerts → #ops channel
  - Campaign completed → #marketing channel
  - Large payout approvals → #finance channel

Settings:
    TEAMS_WEBHOOK_URL       — Default Teams webhook URL
    TEAMS_ALERT_WEBHOOK_URL — Admin/ops alerts webhook
"""

import json
import logging
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Color mapping (Teams uses hex)
TEAMS_COLORS = {
    'critical': 'FF0000',  # Red
    'urgent':   'FF6B35',  # Orange-red
    'high':     'FFA500',  # Orange
    'medium':   '36A64F',  # Green
    'low':      '439FE0',  # Blue
    'info':     '2EB67D',  # Teal
    'success':  '2EB67D',  # Teal
    'warning':  'FFA500',  # Orange
}


class TeamsProvider:
    """Microsoft Teams Incoming Webhook notification provider."""

    WEBHOOK_MAP = {
        'fraud_detected':     getattr(settings, 'TEAMS_ALERT_WEBHOOK_URL', ''),
        'system_alert':       getattr(settings, 'TEAMS_OPS_WEBHOOK_URL', ''),
        'campaign_live':      getattr(settings, 'TEAMS_MARKETING_WEBHOOK_URL', ''),
        'withdrawal_success': getattr(settings, 'TEAMS_FINANCE_WEBHOOK_URL', ''),
        'default':            getattr(settings, 'TEAMS_WEBHOOK_URL', ''),
    }

    def __init__(self):
        self._default_url = getattr(settings, 'TEAMS_WEBHOOK_URL', '')
        self._available = bool(self._default_url)
        if not self._available:
            logger.info('TeamsProvider: TEAMS_WEBHOOK_URL not set.')
        self._requests = None

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, webhook_url: str = '', **kwargs) -> Dict:
        """Send a notification as a Teams Adaptive Card."""
        if not self._available:
            return {'success': False, 'provider': 'teams', 'error': 'Not configured'}

        url = webhook_url or self._get_webhook_url(notification)
        priority = getattr(notification, 'priority', 'medium') or 'medium'
        color = TEAMS_COLORS.get(priority, TEAMS_COLORS['medium'])

        # Build Adaptive Card payload
        payload = {
            '@type': 'MessageCard',
            '@context': 'http://schema.org/extensions',
            'themeColor': color,
            'summary': notification.title,
            'sections': [{
                'activityTitle': notification.title,
                'activitySubtitle': getattr(notification, 'notification_type', ''),
                'activityText': notification.message,
                'facts': self._build_facts(notification),
                'markdown': True,
            }],
            'potentialAction': self._build_actions(notification),
        }

        return self._post(url, payload)

    def send_alert(self, title: str, message: str, level: str = 'warning',
                    webhook_url: str = '', fields: Optional[List[Dict]] = None) -> Dict:
        """Send a direct alert message to Teams."""
        if not self._available:
            return {'success': False, 'error': 'Not configured'}

        url = webhook_url or self._default_url
        color = TEAMS_COLORS.get(level, TEAMS_COLORS['warning'])

        payload = {
            '@type': 'MessageCard',
            '@context': 'http://schema.org/extensions',
            'themeColor': color,
            'summary': title,
            'sections': [{
                'activityTitle': f'**{title}**',
                'activityText': message,
                'facts': [{'name': f['title'], 'value': f['value']} for f in (fields or [])],
            }],
        }
        return self._post(url, payload)

    def send_adaptive_card(self, webhook_url: str, card_body: dict) -> Dict:
        """Send a fully custom Adaptive Card."""
        if not self._available:
            return {'success': False, 'error': 'Not configured'}

        payload = {
            'type': 'message',
            'attachments': [{
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': {'$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                             'type': 'AdaptiveCard', 'version': '1.3', **card_body},
            }]
        }
        return self._post(webhook_url, payload)

    def _post(self, url: str, payload: dict) -> Dict:
        req = self._get_requests()
        try:
            resp = req.post(url, json=payload,
                            headers={'Content-Type': 'application/json'}, timeout=10)
            success = resp.status_code in (200, 202)
            return {'success': success, 'provider': 'teams',
                    'status_code': resp.status_code,
                    'error': '' if success else f'HTTP {resp.status_code}'}
        except Exception as exc:
            logger.error(f'TeamsProvider._post: {exc}')
            return {'success': False, 'provider': 'teams', 'error': str(exc)}

    def _get_webhook_url(self, notification) -> str:
        notif_type = getattr(notification, 'notification_type', '') or ''
        return (self.WEBHOOK_MAP.get(notif_type, '')
                or self.WEBHOOK_MAP.get('default', '')
                or self._default_url)

    def _build_facts(self, notification) -> list:
        facts = []
        user = getattr(notification, 'user', None)
        if user:
            facts.append({'name': 'User', 'value': getattr(user, 'username', str(user.pk))})
        facts.append({'name': 'Priority', 'value': getattr(notification, 'priority', 'medium')})
        facts.append({'name': 'Type', 'value': getattr(notification, 'notification_type', '')})
        return facts

    def _build_actions(self, notification) -> list:
        action_url = getattr(notification, 'action_url', '') or ''
        if not action_url:
            return []
        return [{'@type': 'OpenUri', 'name': 'View Details',
                 'targets': [{'os': 'default', 'uri': action_url}]}]

    def _get_requests(self):
        if not self._requests:
            import requests
            self._requests = requests
        return self._requests


teams_provider = TeamsProvider()
