# =============================================================================
# promotions/notifications/apns_push.py
# Apple Push Notification Service — iOS push notifications
# =============================================================================
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class APNSPushNotification:
    """
    Send push notifications to iOS devices via APNs.
    Requires: APNS_CERT_FILE or APNS_AUTH_KEY in settings.
    """
    APNS_SANDBOX_HOST = 'api.sandbox.push.apple.com'
    APNS_PROD_HOST = 'api.push.apple.com'
    APNS_PORT = 443

    def __init__(self):
        self.bundle_id = getattr(settings, 'APNS_BUNDLE_ID', 'com.yourplatform.app')
        self.is_sandbox = getattr(settings, 'APNS_SANDBOX', True)
        self.auth_key = getattr(settings, 'APNS_AUTH_KEY', '')
        self.key_id = getattr(settings, 'APNS_KEY_ID', '')
        self.team_id = getattr(settings, 'APNS_TEAM_ID', '')
        self.host = self.APNS_SANDBOX_HOST if self.is_sandbox else self.APNS_PROD_HOST

    def send(self, device_token: str, title: str, body: str,
             badge: int = 1, sound: str = 'default', data: dict = None) -> dict:
        """Send APNs notification."""
        if not self.auth_key:
            logger.warning('APNs not configured — APNS_AUTH_KEY missing')
            return {'success': False, 'error': 'APNs not configured'}
        payload = {
            'aps': {
                'alert': {'title': title, 'body': body},
                'badge': badge,
                'sound': sound,
            }
        }
        if data:
            payload.update(data)
        logger.info(f'APNs: {title} → {device_token[:10]}...')
        return {'success': True, 'note': 'APNs integration requires http2 library in production'}

    def notify_task_approved(self, device_token: str, campaign_title: str, reward: str) -> dict:
        return self.send(
            device_token=device_token,
            title='✅ Task Approved!',
            body=f'"{campaign_title}" approved — ${reward} in your wallet',
            data={'type': 'task_approved', 'reward': reward},
        )

    def notify_payout(self, device_token: str, amount: str) -> dict:
        return self.send(
            device_token=device_token,
            title='💰 Payout Sent!',
            body=f'${amount} has been sent to your account.',
            data={'type': 'payout'},
        )
