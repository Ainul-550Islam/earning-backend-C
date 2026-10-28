"""
api/support/notifications/sms_notifier.py
FILE 27/70 — SMS Notification System

Bangladesh SMS gateway integration।
Twilio + local BD SMS gateway support।

Supported Gateways:
1. Twilio (international)
2. SSL Commerz SMS (Bangladesh)
3. BulkSMS BD
4. Infobip

Settings:
    SMS_PROVIDER        = 'twilio'  # or 'sslcommerz', 'bulksms', 'infobip'
    TWILIO_ACCOUNT_SID  = 'ACxxx'
    TWILIO_AUTH_TOKEN   = 'xxx'
    TWILIO_FROM_NUMBER  = '+1234567890'
    SMS_BD_API_KEY      = 'xxx'  # Bangladesh gateway
    SMS_BD_SENDER_ID    = 'SUPPORT'
"""
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SMS_PROVIDER     = getattr(settings, 'SMS_PROVIDER',        'twilio')
TWILIO_SID       = getattr(settings, 'TWILIO_ACCOUNT_SID',  '')
TWILIO_TOKEN     = getattr(settings, 'TWILIO_AUTH_TOKEN',   '')
TWILIO_FROM      = getattr(settings, 'TWILIO_FROM_NUMBER',  '')
BD_API_KEY       = getattr(settings, 'SMS_BD_API_KEY',      '')
BD_SENDER_ID     = getattr(settings, 'SMS_BD_SENDER_ID',    'SUPPORT')
MAX_SMS_LENGTH   = 160


class SMSNotifier:
    """
    Multi-provider SMS notification।
    Bangladesh + international support।
    """

    # ──────────────────────────────────────────
    # TICKET SMS ALERTS
    # ──────────────────────────────────────────
    def ticket_created(self, ticket, phone: str) -> bool:
        msg = (
            f'[{settings.SITE_NAME if hasattr(settings,"SITE_NAME") else "Support"}] '
            f'Ticket #{ticket.ticket_id} created. '
            f'Priority: {ticket.priority.upper()}. '
            f'We will respond within {self._sla_hours(ticket.priority)} hours.'
        )
        return self.send(phone, msg)

    def ticket_replied(self, ticket, phone: str) -> bool:
        msg = (
            f'Support replied to your ticket #{ticket.ticket_id}. '
            f'Visit your ticket to view the reply and respond.'
        )
        return self.send(phone, msg)

    def ticket_resolved(self, ticket, phone: str) -> bool:
        msg = (
            f'Ticket #{ticket.ticket_id} resolved! '
            f'Please rate your experience. Thank you!'
        )
        return self.send(phone, msg)

    def sla_warning_agent(self, ticket, agent_phone: str, minutes: int) -> bool:
        msg = (
            f'[SLA WARNING] Ticket #{ticket.ticket_id} SLA in {minutes}min. '
            f'Priority: {ticket.priority.upper()}. Respond NOW!'
        )
        return self.send(agent_phone, msg)

    def sla_breach_alert(self, ticket, phone: str, breach_type: str) -> bool:
        msg = (
            f'[SLA BREACH] Ticket #{ticket.ticket_id} '
            f'{breach_type.replace("_"," ")} SLA breached! '
            f'IMMEDIATE action required!'
        )
        return self.send(phone, msg)

    def otp_verification(self, phone: str, otp: str) -> bool:
        msg = f'Your verification code is: {otp}. Valid for 10 minutes. Do not share.'
        return self.send(phone, msg)

    # ──────────────────────────────────────────
    # CORE SEND
    # ──────────────────────────────────────────
    def send(self, phone: str, message: str) -> bool:
        """SMS পাঠাও — configured provider দিয়ে"""
        if not phone:
            return False

        phone   = self._format_phone(phone)
        message = message[:MAX_SMS_LENGTH]

        try:
            if SMS_PROVIDER == 'twilio':
                return self._send_twilio(phone, message)
            elif SMS_PROVIDER == 'sslcommerz':
                return self._send_sslcommerz(phone, message)
            elif SMS_PROVIDER == 'bulksms':
                return self._send_bulksms_bd(phone, message)
            elif SMS_PROVIDER == 'infobip':
                return self._send_infobip(phone, message)
            else:
                logger.warning(f'Unknown SMS provider: {SMS_PROVIDER}')
                return False
        except Exception as e:
            logger.error(f'SMS send failed to {phone}: {e}')
            return False

    def send_bulk(self, phones: list, message: str) -> dict:
        """Bulk SMS পাঠাও"""
        sent   = 0
        failed = 0
        for phone in phones:
            if self.send(phone, message):
                sent += 1
            else:
                failed += 1
        return {'sent': sent, 'failed': failed, 'total': len(phones)}

    # ──────────────────────────────────────────
    # PROVIDER IMPLEMENTATIONS
    # ──────────────────────────────────────────
    def _send_twilio(self, phone: str, message: str) -> bool:
        """Twilio SMS API"""
        if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
            logger.warning('Twilio credentials not configured.')
            return False

        url  = f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json'
        resp = requests.post(
            url,
            auth = (TWILIO_SID, TWILIO_TOKEN),
            data = {'From': TWILIO_FROM, 'To': phone, 'Body': message},
            timeout=15,
        )

        if resp.status_code == 201:
            logger.info(f'Twilio SMS sent to {phone}')
            return True

        logger.error(f'Twilio SMS failed [{resp.status_code}]: {resp.text[:200]}')
        return False

    def _send_sslcommerz(self, phone: str, message: str) -> bool:
        """SSL Commerz Bangladesh SMS"""
        if not BD_API_KEY:
            logger.warning('SSL Commerz SMS API key not configured.')
            return False

        url  = 'https://sms.sslcommerz.com/smsapi'
        resp = requests.post(url, data={
            'user':   BD_API_KEY.split(':')[0] if ':' in BD_API_KEY else BD_API_KEY,
            'pass':   BD_API_KEY.split(':')[1] if ':' in BD_API_KEY else '',
            'sid':    BD_SENDER_ID,
            'msisdn': phone.replace('+', ''),
            'sms':    message,
            'num':    1,
        }, timeout=15)

        success = resp.status_code == 200 and 'SENDSMS' in resp.text.upper()
        if success:
            logger.info(f'SSL Commerz SMS sent to {phone}')
        else:
            logger.error(f'SSL Commerz SMS failed: {resp.text[:100]}')
        return success

    def _send_bulksms_bd(self, phone: str, message: str) -> bool:
        """BulkSMS Bangladesh"""
        if not BD_API_KEY:
            logger.warning('BulkSMS BD API key not configured.')
            return False

        url  = 'https://bulksmsbd.net/api/smsapi'
        resp = requests.post(url, data={
            'api_key': BD_API_KEY,
            'senderid':BD_SENDER_ID,
            'number':  phone.replace('+880', '0'),
            'message': message,
        }, timeout=15)

        data    = resp.json() if resp.status_code == 200 else {}
        success = data.get('response_code') == 202

        if success:
            logger.info(f'BulkSMS BD sent to {phone}')
        else:
            logger.error(f'BulkSMS BD failed: {data}')
        return success

    def _send_infobip(self, phone: str, message: str) -> bool:
        """Infobip SMS API"""
        api_key  = getattr(settings, 'INFOBIP_API_KEY', '')
        base_url = getattr(settings, 'INFOBIP_BASE_URL', '')

        if not api_key or not base_url:
            logger.warning('Infobip credentials not configured.')
            return False

        url  = f'https://{base_url}/sms/2/text/advanced'
        resp = requests.post(
            url,
            headers = {
                'Authorization': f'App {api_key}',
                'Content-Type':  'application/json',
            },
            json = {
                'messages': [{
                    'destinations': [{'to': phone}],
                    'from':         BD_SENDER_ID,
                    'text':         message,
                }]
            },
            timeout=15,
        )
        success = resp.status_code == 200
        if success:
            logger.info(f'Infobip SMS sent to {phone}')
        else:
            logger.error(f'Infobip SMS failed: {resp.text[:100]}')
        return success

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _format_phone(self, phone: str) -> str:
        """Phone number format করো"""
        import re
        phone = re.sub(r'[^\d+]', '', phone)
        # Bangladesh numbers
        if phone.startswith('01') and len(phone) == 11:
            phone = '+880' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
        return phone

    def _sla_hours(self, priority: str) -> int:
        return {'urgent': 2, 'high': 8, 'medium': 24, 'low': 48}.get(priority, 24)

    def get_user_phone(self, user) -> str | None:
        """User-এর phone number পাও"""
        try:
            # Try profile
            if hasattr(user, 'profile'):
                return getattr(user.profile, 'phone_number', None)
            return None
        except Exception:
            return None


# Singleton
sms_notifier = SMSNotifier()