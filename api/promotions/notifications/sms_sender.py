# =============================================================================
# promotions/notifications/sms_sender.py
# SMS Notifications — Twilio integration for critical alerts
# =============================================================================
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSSender:
    """
    SMS alerts via Twilio.
    Used for: payout confirmations, security alerts, fraud warnings.
    """

    def __init__(self):
        self.account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        self.auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        self.from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '+15005550006')

    def send_sms(self, to_number: str, message: str) -> dict:
        """Send SMS via Twilio."""
        if not self.account_sid or not self.auth_token:
            logger.warning('Twilio not configured')
            return {'success': False, 'error': 'SMS not configured. Add TWILIO_ACCOUNT_SID to settings.'}
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(
                body=message[:160],
                from_=self.from_number,
                to=to_number,
            )
            return {'success': True, 'message_sid': msg.sid}
        except ImportError:
            return {'success': False, 'error': 'pip install twilio to enable SMS'}
        except Exception as e:
            logger.error(f'SMS error: {e}')
            return {'success': False, 'error': str(e)}

    def send_payout_confirmation(self, phone: str, amount: str, method: str) -> dict:
        return self.send_sms(phone, f'YourPlatform: ${amount} payout via {method} is on its way! ETA: 1-3 business days.')

    def send_fraud_alert(self, phone: str) -> dict:
        return self.send_sms(phone, 'YourPlatform SECURITY: Suspicious activity detected on your account. Please review immediately.')

    def send_otp(self, phone: str, otp: str) -> dict:
        return self.send_sms(phone, f'YourPlatform OTP: {otp} (valid 10 mins). Do not share this code.')

    def send_milestone_sms(self, phone: str, milestone: str, bonus: str) -> dict:
        return self.send_sms(phone, f'🏆 YourPlatform: You reached "{milestone}"! ${bonus} bonus added to your wallet.')
