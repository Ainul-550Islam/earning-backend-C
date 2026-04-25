# FILE 96 of 257 — notifications/SMSNotifier.py
# Supports: Twilio, BulkSMS, or local BD SMS providers
import requests
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

SMS_MESSAGES = {
    'deposit_completed':    'Your deposit of {amount} {gateway} was successful. Ref: {reference_id}',
    'deposit_failed':       'Your deposit of {amount} via {gateway} failed. Please try again.',
    'withdrawal_completed': 'Your withdrawal of {amount} has been sent to your {gateway} account.',
    'withdrawal_rejected':  'Your withdrawal request of {amount} was rejected. Contact support.',
    'refund_completed':     'Refund of {amount} via {gateway} has been processed.',
}

class SMSNotifier:
    def __init__(self):
        self.provider = getattr(settings, 'SMS_PROVIDER', 'twilio')

    def send(self, phone: str, notification_type: str, context: dict = None):
        template = SMS_MESSAGES.get(notification_type)
        if not template:
            return False
        try:
            message = template.format(**(context or {}))
            if self.provider == 'twilio':
                return self._send_twilio(phone, message)
            return self._send_bulksms(phone, message)
        except Exception as e:
            logger.error(f'SMSNotifier error: {e}')
            return False

    def _send_twilio(self, phone: str, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(
                getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
                getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            )
            client.messages.create(
                body=message, from_=getattr(settings, 'TWILIO_FROM', ''), to=phone
            )
            logger.info(f'SMS sent via Twilio to {phone}')
            return True
        except ImportError:
            logger.warning('Twilio not installed. pip install twilio')
            return self._send_http_fallback(phone, message)

    def _send_bulksms(self, phone: str, message: str) -> bool:
        try:
            url = getattr(settings, 'BULKSMS_URL', '')
            if not url:
                return False
            resp = requests.post(url, data={
                'user': getattr(settings, 'BULKSMS_USER', ''),
                'password': getattr(settings, 'BULKSMS_PASSWORD', ''),
                'msisdn': phone, 'message': message,
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'BulkSMS error: {e}')
            return False

    def _send_http_fallback(self, phone: str, message: str) -> bool:
        logger.info(f'[SMS FALLBACK] To:{phone} Msg:{message}')
        return True
