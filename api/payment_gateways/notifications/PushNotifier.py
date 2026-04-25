# FILE 97 of 257 — notifications/PushNotifier.py
# Firebase FCM push notifications
import requests
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

PUSH_MESSAGES = {
    'deposit_completed':    {'title':'Deposit Successful ✅', 'body':'Your deposit has been credited.'},
    'deposit_failed':       {'title':'Deposit Failed ❌',     'body':'Your deposit could not be processed.'},
    'withdrawal_completed': {'title':'Withdrawal Sent ✅',    'body':'Your withdrawal is on its way.'},
    'refund_completed':     {'title':'Refund Processed ✅',   'body':'Your refund has been credited.'},
    'payout_approved':      {'title':'Payout Approved ✅',    'body':'Your payout request was approved.'},
}

class PushNotifier:
    FCM_URL = 'https://fcm.googleapis.com/fcm/send'

    def send(self, user_id: int, notification_type: str, context: dict = None):
        msg = PUSH_MESSAGES.get(notification_type)
        if not msg:
            return False
        tokens = self._get_user_tokens(user_id)
        if not tokens:
            return False
        return self._send_fcm(tokens, msg['title'], msg['body'], context or {})

    def _get_user_tokens(self, user_id: int) -> list:
        try:
            from .models import DeviceToken
            return list(DeviceToken.objects.filter(
                user_id=user_id, is_active=True
            ).values_list('token', flat=True))
        except Exception:
            return []

    def _send_fcm(self, tokens: list, title: str, body: str, data: dict) -> bool:
        server_key = getattr(settings, 'FCM_SERVER_KEY', '')
        if not server_key:
            logger.warning('FCM_SERVER_KEY not configured')
            return False
        try:
            payload = {
                'registration_ids': tokens,
                'notification': {'title': title, 'body': body},
                'data': data,
            }
            resp = requests.post(
                self.FCM_URL,
                json=payload,
                headers={'Authorization': f'key={server_key}', 'Content-Type': 'application/json'},
                timeout=10,
            )
            logger.info(f'FCM push sent to {len(tokens)} devices: {resp.status_code}')
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'PushNotifier FCM error: {e}')
            return False
