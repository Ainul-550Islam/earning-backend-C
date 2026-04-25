# api/notifications/services/providers/SlackProvider.py
"""
SlackProvider — Slack webhook and Bot API notifications.

Use cases for earning site:
  - Admin fraud alerts → #fraud-alerts channel
  - Withdrawal approvals → #withdrawals channel
  - System health degraded → #ops channel
  - Campaign completed → #marketing channel
  - New KYC submissions → #kyc-review channel

Settings:
    SLACK_BOT_TOKEN       — xoxb-... bot token (for API)
    SLACK_WEBHOOK_URL     — https://hooks.slack.com/... (for simple webhook)
    SLACK_DEFAULT_CHANNEL — e.g. '#notifications'
"""
import json, logging
from typing import Dict, List, Optional
from django.conf import settings
logger = logging.getLogger(__name__)

SLACK_COLORS = {
    'critical': '#FF0000', 'urgent': '#FF6B35', 'high': '#FFA500',
    'medium': '#36A64F',   'low': '#439FE0',    'info': '#2EB67D',
    'success': '#2EB67D',  'warning': '#FFA500', 'danger': '#FF0000',
}

class SlackProvider:
    """Slack notification provider — webhook + Bot API."""

    CHANNEL_MAP = {
        'fraud_detected':     getattr(settings, 'SLACK_FRAUD_CHANNEL', '#fraud-alerts'),
        'withdrawal_success': getattr(settings, 'SLACK_WITHDRAWALS_CHANNEL', '#withdrawals'),
        'kyc_submitted':      getattr(settings, 'SLACK_KYC_CHANNEL', '#kyc-review'),
        'system_health':      getattr(settings, 'SLACK_OPS_CHANNEL', '#ops'),
        'campaign_live':      getattr(settings, 'SLACK_MARKETING_CHANNEL', '#marketing'),
        'default':            getattr(settings, 'SLACK_DEFAULT_CHANNEL', '#notifications'),
    }

    def __init__(self):
        self._webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', '')
        self._bot_token   = getattr(settings, 'SLACK_BOT_TOKEN', '')
        self._available   = bool(self._webhook_url or self._bot_token)
        if not self._available:
            logger.warning('SlackProvider: SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN not set.')
        self._requests = None

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, channel: str = '', **kwargs) -> Dict:
        """Send notification to Slack."""
        if not self._available:
            return {'success': False, 'error': 'SlackProvider not configured', 'provider': 'slack'}

        target_channel = channel or self._get_channel(notification)
        priority = getattr(notification, 'priority', 'medium') or 'medium'
        color = SLACK_COLORS.get(priority, SLACK_COLORS['medium'])

        payload = {
            'channel': target_channel,
            'attachments': [{
                'color': color,
                'title': notification.title,
                'text': notification.message,
                'footer': f'Notification #{notification.id} | {notification.notification_type}',
                'ts': int(notification.created_at.timestamp()) if hasattr(notification, 'created_at') and notification.created_at else None,
                'actions': self._build_actions(notification),
            }],
        }

        # Add user info if available
        user = getattr(notification, 'user', None)
        if user:
            payload['attachments'][0]['fields'] = [
                {'title': 'User', 'value': getattr(user, 'username', str(user.pk)), 'short': True},
                {'title': 'User ID', 'value': str(user.pk), 'short': True},
            ]

        return self._send_payload(payload)

    def send_alert(self, title: str, message: str, level: str = 'warning',
                   channel: str = '', fields: Optional[List[Dict]] = None) -> Dict:
        """Send a direct alert to Slack (for system/admin alerts)."""
        if not self._available:
            return {'success': False, 'error': 'SlackProvider not configured', 'provider': 'slack'}

        target = channel or self.CHANNEL_MAP.get('default', '#notifications')
        color = SLACK_COLORS.get(level, SLACK_COLORS['medium'])

        payload = {
            'channel': target,
            'attachments': [{
                'color': color,
                'title': f'{"🚨" if level == "critical" else "⚠️" if level == "warning" else "ℹ️"} {title}',
                'text': message,
                'fields': fields or [],
                'footer': 'Earning Site Notification System',
            }],
        }
        return self._send_payload(payload)

    def send_bulk(self, notifications: list, channel: str = '') -> Dict:
        """Send multiple notifications as one grouped Slack message."""
        if not self._available or not notifications:
            return {'success': False, 'error': 'No notifications or not configured', 'provider': 'slack'}

        blocks = [{'type': 'header', 'text': {'type': 'plain_text', 'text': f'📬 {len(notifications)} Notifications'}}]
        for notif in notifications[:10]:
            blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': f'*{notif.title}*\n{notif.message}'}})

        payload = {'channel': channel or self.CHANNEL_MAP['default'], 'blocks': blocks}
        return self._send_payload(payload)

    def _send_payload(self, payload: Dict) -> Dict:
        req = self._get_requests()
        url = self._webhook_url

        # Use Bot API if token available
        if self._bot_token and not url:
            url = 'https://slack.com/api/chat.postMessage'
            headers = {'Authorization': f'Bearer {self._bot_token}', 'Content-Type': 'application/json'}
        else:
            headers = {'Content-Type': 'application/json'}

        try:
            resp = req.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            body = resp.json() if resp.content else {}
            success = body.get('ok', True) if self._bot_token else resp.status_code == 200
            return {'success': success, 'provider': 'slack', 'error': body.get('error', '') if not success else ''}
        except Exception as exc:
            logger.error(f'SlackProvider._send_payload: {exc}')
            return {'success': False, 'provider': 'slack', 'error': str(exc)}

    def _get_channel(self, notification) -> str:
        notif_type = getattr(notification, 'notification_type', '') or ''
        return self.CHANNEL_MAP.get(notif_type, self.CHANNEL_MAP['default'])

    def _build_actions(self, notification) -> List[Dict]:
        action_url = getattr(notification, 'action_url', '') or ''
        if not action_url:
            return []
        return [{'type': 'button', 'text': 'View Details', 'url': action_url}]

    def _get_requests(self):
        if not self._requests:
            import requests
            self._requests = requests
        return self._requests


slack_provider = SlackProvider()
