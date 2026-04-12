# =============================================================================
# promotions/notifications/fcm_push.py
# Firebase Cloud Messaging — Android + Web push notifications
# =============================================================================
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class FCMPushNotification:
    """
    Send push notifications via Firebase Cloud Messaging.
    Requires: FCM_SERVER_KEY in settings.
    """
    FCM_ENDPOINT = 'https://fcm.googleapis.com/fcm/send'
    FCM_V1_ENDPOINT = 'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'

    def __init__(self):
        self.server_key = getattr(settings, 'FCM_SERVER_KEY', '')
        self.project_id = getattr(settings, 'FCM_PROJECT_ID', '')

    def send_to_device(self, device_token: str, title: str, body: str,
                       data: dict = None, image_url: str = '') -> dict:
        """Send push to single device."""
        if not self.server_key:
            logger.warning('FCM_SERVER_KEY not configured')
            return {'success': False, 'error': 'FCM not configured'}
        import urllib.request
        payload = {
            'to': device_token,
            'notification': {
                'title': title,
                'body': body,
                'sound': 'default',
                'badge': '1',
            },
            'data': data or {},
        }
        if image_url:
            payload['notification']['image'] = image_url
        try:
            req = urllib.request.Request(
                self.FCM_ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    'Authorization': f'key={self.server_key}',
                    'Content-Type': 'application/json',
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f'FCM send error: {e}')
            return {'success': False, 'error': str(e)}

    def send_to_topic(self, topic: str, title: str, body: str, data: dict = None) -> dict:
        """Send to all subscribers of a topic."""
        return self.send_to_device(f'/topics/{topic}', title, body, data)

    def send_to_multiple(self, tokens: list, title: str, body: str, data: dict = None) -> dict:
        """Send to multiple devices (up to 1000)."""
        if not tokens:
            return {'success': False, 'error': 'No tokens provided'}
        if not self.server_key:
            return {'success': False, 'error': 'FCM not configured'}
        import urllib.request
        payload = {
            'registration_ids': tokens[:1000],
            'notification': {'title': title, 'body': body, 'sound': 'default'},
            'data': data or {},
        }
        try:
            req = urllib.request.Request(
                self.FCM_ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    'Authorization': f'key={self.server_key}',
                    'Content-Type': 'application/json',
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {'success': True, 'result': json.loads(resp.read())}
        except Exception as e:
            logger.error(f'FCM multicast error: {e}')
            return {'success': False, 'error': str(e)}

    # ── Platform-specific notification templates ──────────────────────────────

    def notify_task_approved(self, device_token: str, campaign_title: str, reward: str) -> dict:
        return self.send_to_device(
            device_token=device_token,
            title='✅ Task Approved!',
            body=f'Your submission for "{campaign_title}" was approved. ${reward} added to your wallet.',
            data={'type': 'task_approved', 'reward': reward},
        )

    def notify_task_rejected(self, device_token: str, campaign_title: str, reason: str) -> dict:
        return self.send_to_device(
            device_token=device_token,
            title='❌ Task Rejected',
            body=f'Your submission for "{campaign_title}" was rejected. Reason: {reason}',
            data={'type': 'task_rejected'},
        )

    def notify_payout_processed(self, device_token: str, amount: str, method: str) -> dict:
        return self.send_to_device(
            device_token=device_token,
            title='💰 Payout Processed!',
            body=f'${amount} has been sent to your {method} account.',
            data={'type': 'payout_processed', 'amount': amount},
        )

    def notify_new_campaign(self, tokens: list, campaign_title: str, reward: str) -> dict:
        return self.send_to_multiple(
            tokens=tokens,
            title='🆕 New Campaign Available!',
            body=f'"{campaign_title}" — Earn ${reward} per completion',
            data={'type': 'new_campaign', 'reward': reward},
        )

    def notify_milestone_achieved(self, device_token: str, milestone_name: str, bonus: str) -> dict:
        return self.send_to_device(
            device_token=device_token,
            title=f'🏆 Milestone Achieved: {milestone_name}',
            body=f'Congratulations! You earned a ${bonus} bonus.',
            data={'type': 'milestone', 'bonus': bonus},
        )

    def notify_fraud_alert(self, device_token: str, message: str) -> dict:
        return self.send_to_device(
            device_token=device_token,
            title='⚠️ Account Security Alert',
            body=message,
            data={'type': 'fraud_alert'},
        )
