# api/djoyalty/integrations/sms.py
"""
SMS Integrations -- Bangladesh + International।
BulkSMSBD (Bangladesh popular), SSL Wireless, Twilio।

Usage:
    from djoyalty.integrations.sms import SMSService
    SMSService.send('01700000000', 'আপনার 100 পয়েন্ট যোগ হয়েছে!')
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BulkSMSBD:
    """
    BulkSMSBD.com -- Bangladesh most popular SMS API।
    WooCommerce + Loyalty integrations widely use this।
    docs: https://bulksmsbd.com/api

    Settings:
        DJOYALTY_SMS_BULKSMSBD_API_KEY
        DJOYALTY_SMS_BULKSMSBD_SENDER_ID (optional)
    """

    BASE_URL = 'https://bulksmsbd.net/api/smsapi'

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('BULKSMSBD', {})
        self.api_key   = cfg.get('API_KEY', '')
        self.sender_id = cfg.get('SENDER_ID', 'BulkSMS')

    def send(self, to: str, message: str) -> dict:
        """Send SMS via BulkSMSBD।"""
        resp = requests.post(
            self.BASE_URL,
            data={
                'api_key': self.api_key,
                'type': 'text',
                'number': to,
                'senderid': self.sender_id,
                'message': message,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('response_code') == 202:
            logger.info('BulkSMSBD: SMS sent to %s', to)
        else:
            logger.warning('BulkSMSBD: SMS failed to %s -- %s', to, data)
        return data

    def send_bulk(self, numbers: list, message: str) -> dict:
        """Send SMS to multiple numbers।"""
        resp = requests.post(
            self.BASE_URL,
            data={
                'api_key': self.api_key,
                'type': 'text',
                'number': ','.join(numbers),
                'senderid': self.sender_id,
                'message': message,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('BULKSMSBD', {})
        return bool(cfg.get('API_KEY'))


class SSLWirelessSMS:
    """
    SSL Wireless SMS -- Bangladesh carrier-grade SMS।
    docs: https://sslwireless.com/sms-api/

    Settings:
        DJOYALTY_SMS_SSLWIRELESS_API_TOKEN
        DJOYALTY_SMS_SSLWIRELESS_SID
    """

    BASE_URL = 'https://msg.sslwireless.com/smsapi'

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('SSLWIRELESS', {})
        self.token = cfg.get('API_TOKEN', '')
        self.sid   = cfg.get('SID', '')

    def send(self, to: str, message: str, csmsid: str = '') -> dict:
        resp = requests.post(
            self.BASE_URL,
            data={
                'token': self.token,
                'sid': self.sid,
                'msisdn': to,
                'sms': message,
                'csmsid': csmsid or '',
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info('SSLWirelessSMS: sent to %s', to)
        return resp.json() if resp.text.startswith('{') else {'raw': resp.text}

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('SSLWIRELESS', {})
        return bool(cfg.get('API_TOKEN'))


class TwilioSMSIntegration:
    """
    Twilio SMS -- International SMS।
    docs: https://www.twilio.com/docs/sms

    Settings:
        DJOYALTY_SMS_TWILIO_ACCOUNT_SID
        DJOYALTY_SMS_TWILIO_AUTH_TOKEN
        DJOYALTY_SMS_TWILIO_FROM_NUMBER
    """

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('TWILIO', {})
        self.account_sid = cfg.get('ACCOUNT_SID', '')
        self.auth_token  = cfg.get('AUTH_TOKEN', '')
        self.from_number = cfg.get('FROM_NUMBER', '')

    def send(self, to: str, message: str) -> dict:
        try:
            from twilio.rest import Client
        except ImportError:
            logger.error('TwilioSMS: twilio package not installed. pip install twilio')
            return {'error': 'twilio not installed'}

        client = Client(self.account_sid, self.auth_token)
        msg = client.messages.create(body=message, from_=self.from_number, to=to)
        logger.info('TwilioSMS: sent to %s -- SID=%s', to, msg.sid)
        return {'sid': msg.sid, 'status': msg.status}

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_SMS', {}).get('TWILIO', {})
        return bool(cfg.get('ACCOUNT_SID') and cfg.get('AUTH_TOKEN'))


# ─── Unified SMS Service ──────────────────────────────────────────────────────

class SMSService:
    """
    Unified SMS service -- settings এ configured provider auto-select করে।

    settings.py এ যোগ করুন:
        DJOYALTY_SMS_PROVIDER = 'bulksmsbd'  # 'bulksmsbd' | 'sslwireless' | 'twilio'

    Usage:
        SMSService.send('01700000000', 'আপনার 200 পয়েন্ট এসেছে!')
    """

    @staticmethod
    def get_provider():
        provider_name = getattr(settings, 'DJOYALTY_SMS_PROVIDER', 'bulksmsbd')
        providers = {
            'bulksmsbd':   BulkSMSBD,
            'sslwireless': SSLWirelessSMS,
            'twilio':      TwilioSMSIntegration,
        }
        cls = providers.get(provider_name, BulkSMSBD)
        return cls()

    @classmethod
    def send(cls, to: str, message: str) -> dict:
        provider = cls.get_provider()
        if not provider.is_configured():
            logger.warning('SMSService: SMS provider not configured -- skipping SMS to %s', to)
            return {'skipped': True, 'reason': 'not configured'}
        try:
            return provider.send(to, message)
        except Exception as e:
            logger.error('SMSService.send error to %s: %s', to, e)
            return {'error': str(e)}

    @classmethod
    def send_bulk(cls, numbers: list, message: str) -> dict:
        provider = cls.get_provider()
        if not provider.is_configured():
            return {'skipped': True}
        if hasattr(provider, 'send_bulk'):
            return provider.send_bulk(numbers, message)
        # Fallback: send one by one
        results = []
        for number in numbers:
            results.append(provider.send(number, message))
        return {'results': results}

    # ─── Pre-built loyalty SMS templates ─────────────────────────

    @classmethod
    def notify_points_earned(cls, customer, points: float, balance: float):
        if not customer.phone or not customer.sms_opt_in:
            return
        message = (
            f'প্রিয় {customer.firstname or customer.code},\n'
            f'আপনার Loyalty Account এ {points} পয়েন্ট যোগ হয়েছে।\n'
            f'মোট Balance: {balance} পয়েন্ট।\n'
            f'- Djoyalty'
        )
        cls.send(customer.phone, message)

    @classmethod
    def notify_tier_upgrade(cls, customer, new_tier: str):
        if not customer.phone or not customer.sms_opt_in:
            return
        message = (
            f'অভিনন্দন {customer.firstname or customer.code}! 🎉\n'
            f'আপনি এখন {new_tier.title()} Tier এ Upgrade হয়েছেন!\n'
            f'বিস্তারিত দেখুন App এ।\n'
            f'- Djoyalty'
        )
        cls.send(customer.phone, message)

    @classmethod
    def notify_cashout_processed(cls, customer, amount: float, method: str):
        if not customer.phone or not customer.sms_opt_in:
            return
        message = (
            f'প্রিয় {customer.firstname or customer.code},\n'
            f'আপনার {amount} টাকা {method} এ পাঠানো হয়েছে।\n'
            f'- Djoyalty'
        )
        cls.send(customer.phone, message)

    @classmethod
    def notify_voucher_code(cls, customer, code: str, discount: str):
        if not customer.phone or not customer.sms_opt_in:
            return
        message = (
            f'প্রিয় {customer.firstname or customer.code},\n'
            f'আপনার Voucher Code: {code}\n'
            f'Discount: {discount}\n'
            f'- Djoyalty'
        )
        cls.send(customer.phone, message)

    @classmethod
    def notify_points_expiring(cls, customer, points: float, days: int):
        if not customer.phone or not customer.sms_opt_in:
            return
        message = (
            f'প্রিয় {customer.firstname or customer.code},\n'
            f'সতর্কতা: আপনার {points} পয়েন্ট {days} দিনের মধ্যে মেয়াদ শেষ হবে!\n'
            f'এখনই ব্যবহার করুন।\n'
            f'- Djoyalty'
        )
        cls.send(customer.phone, message)
