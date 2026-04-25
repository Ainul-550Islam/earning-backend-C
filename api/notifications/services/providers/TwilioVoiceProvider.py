# earning_backend/api/notifications/services/providers/TwilioVoiceProvider.py
"""
TwilioVoiceProvider — Voice call notifications via Twilio Voice API.

Use cases for earning site:
  - Critical fraud alerts (account at risk)
  - Large withdrawal OTP verification
  - Admin urgent escalation calls
  - KYC re-verification reminders

Settings:
    TWILIO_ACCOUNT_SID    — Twilio Account SID
    TWILIO_AUTH_TOKEN     — Twilio Auth Token
    TWILIO_FROM_NUMBER    — Twilio phone number (e.g. +14155552671)
    TWILIO_TWIML_BASE_URL — Base URL for TwiML callbacks
"""

import logging
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class TwilioVoiceProvider:
    """
    Voice call notification provider using Twilio Voice API.

    Sends automated voice calls with text-to-speech messages.
    Used for critical notifications that must reach the user.
    """

    # Supported languages for TTS
    TTS_VOICES = {
        'en': 'Polly.Joanna',
        'bn': 'Polly.Aditi',     # Hindi voice — closest available for Bangla
        'default': 'Polly.Joanna',
    }

    def __init__(self):
        self._account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        self._auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        self._from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '')
        self._twiml_base = getattr(settings, 'TWILIO_TWIML_BASE_URL', '')
        self._available = bool(self._account_sid and self._auth_token and self._from_number)
        self._client = None

        if not self._available:
            logger.info('TwilioVoiceProvider: credentials not configured.')

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, phone: str = '', language: str = 'en', **kwargs) -> Dict:
        """
        Send a voice call notification.

        Args:
            notification: Notification instance.
            phone:        Target phone number. Falls back to user's phone.
            language:     TTS language code ('en' or 'bn').

        Returns:
            {'success': bool, 'call_sid': str, 'error': str}
        """
        if not self._available:
            return {'success': False, 'provider': 'twilio_voice', 'error': 'Not configured'}

        # Resolve phone number
        if not phone:
            user = getattr(notification, 'user', None)
            if user:
                profile = getattr(user, 'profile', None)
                phone = getattr(profile, 'phone', '') or getattr(user, 'phone', '') or ''

        if not phone:
            return {'success': False, 'provider': 'twilio_voice', 'error': 'No phone number'}

        # Normalize phone
        from api.notifications.helpers import phone_to_international_bd
        if phone.startswith('01') and len(phone) == 11:
            phone = phone_to_international_bd(phone)
        elif not phone.startswith('+'):
            phone = f'+{phone}'

        title = getattr(notification, 'title', 'Notification')
        message = getattr(notification, 'message', '')
        voice = self.TTS_VOICES.get(language, self.TTS_VOICES['default'])

        # Build TwiML
        twiml = self._build_twiml(title, message, voice, language)

        try:
            client = self._get_client()
            call = client.calls.create(
                twiml=twiml,
                to=phone,
                from_=self._from_number,
                timeout=60,
                record=False,
            )
            logger.info(f'TwilioVoiceProvider: call initiated SID={call.sid} to={phone}')
            return {
                'success': True,
                'provider': 'twilio_voice',
                'call_sid': call.sid,
                'status': call.status,
                'to': phone,
                'error': '',
            }
        except Exception as exc:
            logger.error(f'TwilioVoiceProvider.send: {exc}')
            return {'success': False, 'provider': 'twilio_voice', 'error': str(exc)}

    def send_otp_call(self, phone: str, otp: str, language: str = 'bn') -> Dict:
        """
        Send an OTP verification call.
        The OTP is read out digit by digit.
        """
        if not self._available:
            return {'success': False, 'error': 'Not configured'}

        # Read OTP digit by digit with pauses
        if language == 'bn':
            digits_spoken = '. '.join(list(str(otp)))
            message = (
                f'আপনার এক-বার পাসওয়ার্ড হলো: {digits_spoken}. '
                f'আমি আবার বলছি: {digits_spoken}.'
            )
            intro = 'এটি আপনার Earning Site থেকে একটি নিরাপত্তা বার্তা।'
        else:
            digits_spoken = '. '.join(list(str(otp)))
            message = (
                f'Your one-time password is: {digits_spoken}. '
                f'I repeat: {digits_spoken}.'
            )
            intro = 'This is a security message from Earning Site.'

        twiml = self._build_twiml(intro, message, self.TTS_VOICES.get(language, 'Polly.Joanna'), language)

        try:
            client = self._get_client()
            call = client.calls.create(
                twiml=twiml,
                to=phone,
                from_=self._from_number,
                timeout=60,
            )
            return {'success': True, 'call_sid': call.sid}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def send_fraud_alert_call(self, phone: str, username: str = '') -> Dict:
        """
        Send an urgent fraud alert voice call.
        """
        if language := 'bn':
            message = (
                f'সতর্কতা! {username or "আপনার"} account এ সন্দেহজনক কার্যক্রম সনাক্ত করা হয়েছে। '
                f'যদি আপনি এটি না করে থাকেন, তাহলে এখনই আপনার password পরিবর্তন করুন '
                f'এবং support এ যোগাযোগ করুন।'
            )
        twiml = self._build_twiml('নিরাপত্তা সতর্কতা', message, 'Polly.Aditi', 'bn')

        try:
            client = self._get_client()
            call = client.calls.create(
                twiml=twiml,
                to=phone,
                from_=self._from_number,
                timeout=30,
            )
            return {'success': True, 'call_sid': call.sid}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def get_call_status(self, call_sid: str) -> Dict:
        """Check the status of a call."""
        try:
            client = self._get_client()
            call = client.calls(call_sid).fetch()
            return {
                'call_sid': call_sid,
                'status': call.status,
                'duration': call.duration,
                'direction': call.direction,
            }
        except Exception as exc:
            return {'call_sid': call_sid, 'status': 'unknown', 'error': str(exc)}

    def health_check(self) -> str:
        """Check if Twilio Voice is reachable."""
        try:
            client = self._get_client()
            client.api.accounts(self._account_sid).fetch()
            return 'healthy'
        except Exception:
            return 'unhealthy'

    def _build_twiml(self, title: str, message: str, voice: str, language: str) -> str:
        """Build TwiML XML for text-to-speech call."""
        lang_code = 'bn-IN' if language == 'bn' else 'en-US'
        full_message = f'{title}. {message}'
        # Escape XML special characters
        import html
        safe_msg = html.escape(full_message)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response>'
            f'<Say voice="{voice}" language="{lang_code}">{safe_msg}</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="{voice}" language="{lang_code}">'
            f'This message will now repeat.'
            f'</Say>'
            f'<Say voice="{voice}" language="{lang_code}">{safe_msg}</Say>'
            f'</Response>'
        )

    def _get_client(self):
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self._account_sid, self._auth_token)
            except ImportError:
                raise ImportError('twilio package not installed. Run: pip install twilio')
        return self._client


twilio_voice_provider = TwilioVoiceProvider()
