# api/admin_panel/sms_gateway.py
"""
SMS Gateway for admin_panel.
Supports: Twilio, BD local gateways (SSL Wireless, Bulk SMS BD, SMSBD).
Used for: OTP, withdrawal alerts, account security, admin alerts.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

SMS_PROVIDER = getattr(settings, 'SMS_PROVIDER', 'twilio')  # twilio | sslwireless | bulksmsbd


class SMSGateway:
    """Multi-provider SMS gateway."""

    @classmethod
    def send(cls, to: str, message: str, provider: str = None) -> Dict:
        """Send SMS. Auto-selects provider based on phone number country."""
        provider = provider or cls._select_provider(to)
        if provider == 'twilio':
            return cls._send_twilio(to, message)
        elif provider == 'sslwireless':
            return cls._send_ssl_wireless(to, message)
        elif provider == 'bulksmsbd':
            return cls._send_bulksms_bd(to, message)
        else:
            return cls._send_twilio(to, message)

    @classmethod
    def send_otp(cls, to: str, otp: str) -> Dict:
        """Send OTP SMS."""
        message = f"Your AdminPanel OTP: {otp}. Valid for 5 minutes. Never share this code."
        return cls.send(to, message)

    @classmethod
    def send_withdrawal_alert(cls, to: str, amount: float, status: str) -> Dict:
        """Send withdrawal status SMS."""
        emoji = '✅' if status == 'SUCCESS' else '❌'
        msg = f"{emoji} Withdrawal of ৳{amount:,.2f} {status}. Check app for details."
        return cls.send(to, msg)

    @classmethod
    def send_security_alert(cls, to: str, event: str, ip: str) -> Dict:
        """Send security alert SMS to admin."""
        msg = f"🔐 Admin Security Alert: {event} from IP {ip}. If not you, contact support immediately."
        return cls.send(to, msg)

    @classmethod
    def _select_provider(cls, phone: str) -> str:
        """Auto-select provider based on phone prefix."""
        clean = phone.replace('+', '').replace(' ', '')
        if clean.startswith('880') or clean.startswith('01'):
            return SMS_PROVIDER if SMS_PROVIDER != 'twilio' else 'sslwireless'
        return 'twilio'

    @classmethod
    def _send_twilio(cls, to: str, message: str) -> Dict:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token  = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '')
        if not all([account_sid, auth_token, from_number]):
            return {'success': False, 'error': 'Twilio not configured'}
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            msg = client.messages.create(body=message, from_=from_number, to=to)
            return {'success': True, 'sid': msg.sid, 'provider': 'twilio'}
        except ImportError:
            return {'success': False, 'error': 'twilio package not installed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _send_ssl_wireless(cls, to: str, message: str) -> Dict:
        """SSL Wireless Bangladesh SMS gateway."""
        api_key = getattr(settings, 'SSL_WIRELESS_API_KEY', '')
        sid     = getattr(settings, 'SSL_WIRELESS_SID', '')
        if not api_key:
            return {'success': False, 'error': 'SSL Wireless not configured'}
        try:
            import requests
            resp = requests.post('https://sms.sslwireless.com/pushapi/dynamic/server.php', json={
                'api_token': api_key, 'sid': sid, 'msisdn': to,
                'sms': message, 'csmsid': __import__('uuid').uuid4().hex[:16],
            }, timeout=10)
            data = resp.json()
            success = data.get('status') == 'ACCEPTED'
            return {'success': success, 'response': data, 'provider': 'sslwireless'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _send_bulksms_bd(cls, to: str, message: str) -> Dict:
        """Bulk SMS BD gateway."""
        username = getattr(settings, 'BULKSMS_BD_USERNAME', '')
        password = getattr(settings, 'BULKSMS_BD_PASSWORD', '')
        if not username:
            return {'success': False, 'error': 'BulkSMSBD not configured'}
        try:
            import requests
            resp = requests.get('https://bulksmsbd.net/api/smsapi', params={
                'api_key': username, 'type': 'text',
                'number': to, 'senderid': 'AdminPnl', 'message': message,
            }, timeout=10)
            success = resp.status_code == 200 and '1000' in resp.text
            return {'success': success, 'response': resp.text, 'provider': 'bulksmsbd'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_delivery_stats(cls, days: int = 7) -> Dict:
        stats = cache.get(f'admin_panel:sms_stats:{days}') or {}
        return {'sent': stats.get('sent', 0), 'failed': stats.get('failed', 0), 'period_days': days}


sms_gateway = SMSGateway()