# earning_backend/api/notifications/services/providers/TwilioProvider.py
"""
TwilioProvider — SMS and WhatsApp delivery via Twilio.

Handles:
  - Single SMS send
  - Bulk SMS sends (sequential with rate-limit back-off)
  - WhatsApp message sends via Twilio WhatsApp sandbox/production
  - Delivery status webhook processing

Settings required:
    TWILIO_ACCOUNT_SID   — Twilio Account SID  (starts with 'AC')
    TWILIO_AUTH_TOKEN    — Twilio Auth Token
    TWILIO_FROM_NUMBER   — Twilio phone number in E.164, e.g. '+14155552671'
    TWILIO_WHATSAPP_FROM — (optional) WhatsApp sender,
                           e.g. 'whatsapp:+14155238886'

Dependencies:
    pip install twilio
"""

import logging
import time
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TwilioProvider class
# ---------------------------------------------------------------------------

class TwilioProvider:
    """
    Wrapper around the twilio Python SDK.
    Exposes send_sms / send_bulk_sms / send_whatsapp / process_status_webhook.
    """

    # Twilio error codes for permanently invalid numbers
    INVALID_NUMBER_CODES = {
        21211,  # Invalid 'To' Phone Number
        21612,  # The 'To' phone number is not currently reachable
        21614,  # 'To' number is not a valid mobile number
        21408,  # Permission to send an SMS has not been enabled
        21610,  # The message From/To pair violates a blacklist rule
        21211,  # Invalid To number
    }

    # Max retries on rate-limit (HTTP 429)
    MAX_RATE_LIMIT_RETRIES = 3
    RATE_LIMIT_BACKOFF_SECONDS = 2

    def __init__(self):
        self._account_sid: str = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        self._auth_token: str = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        self._from_number: str = getattr(settings, 'TWILIO_FROM_NUMBER', '')
        self._whatsapp_from: str = getattr(settings, 'TWILIO_WHATSAPP_FROM', '')
        self._available: bool = False
        self._client = None

        if self._account_sid and self._auth_token and self._from_number:
            try:
                from twilio.rest import Client as TwilioClient
                self._client = TwilioClient(self._account_sid, self._auth_token)
                self._available = True
                logger.info('TwilioProvider: client initialised.')
            except ImportError:
                logger.error(
                    'TwilioProvider: twilio package not installed — pip install twilio'
                )
            except Exception as exc:
                logger.error(f'TwilioProvider: init failed — {exc}')
        else:
            logger.warning(
                'TwilioProvider: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / '
                'TWILIO_FROM_NUMBER not fully configured. SMS disabled.'
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    def send_sms(
        self,
        to_phone: str,
        body: str,
        notification_id: str = '',
        status_callback_url: str = '',
    ) -> Dict:
        """
        Send a single SMS message.

        Args:
            to_phone:             Recipient phone in E.164 format, e.g. '+8801XXXXXXXXX'.
            body:                 Message text (max ~1600 chars; auto-segmented).
            notification_id:      Optional reference for the status callback.
            status_callback_url:  Twilio webhook URL for delivery status updates.

        Returns:
            Dict with keys: success, provider, sid, status, error, is_invalid_number.
        """
        if not self._available:
            return self._unavailable_response('sms')

        # Normalise phone number
        to_phone = self._normalise_phone(to_phone)

        params: Dict = {
            'body': body,
            'from_': self._from_number,
            'to': to_phone,
        }
        if status_callback_url:
            params['status_callback'] = status_callback_url

        for attempt in range(1, self.MAX_RATE_LIMIT_RETRIES + 1):
            try:
                message = self._client.messages.create(**params)
                return {
                    'success': True,
                    'provider': 'twilio',
                    'sid': message.sid,
                    'status': message.status,
                    'is_invalid_number': False,
                    'error': '',
                }

            except Exception as exc:
                error_str = str(exc)
                error_code = self._extract_error_code(exc)

                if error_code in self.INVALID_NUMBER_CODES:
                    logger.warning(
                        f'TwilioProvider: invalid number {to_phone} — code {error_code}'
                    )
                    return {
                        'success': False,
                        'provider': 'twilio',
                        'sid': '',
                        'status': 'failed',
                        'is_invalid_number': True,
                        'error': error_str,
                    }

                # Handle rate limiting (HTTP 429)
                if '429' in error_str or 'Too Many Requests' in error_str:
                    if attempt < self.MAX_RATE_LIMIT_RETRIES:
                        wait = self.RATE_LIMIT_BACKOFF_SECONDS * attempt
                        logger.warning(
                            f'TwilioProvider: rate limited, retrying in {wait}s '
                            f'(attempt {attempt}/{self.MAX_RATE_LIMIT_RETRIES})'
                        )
                        time.sleep(wait)
                        continue

                logger.error(f'TwilioProvider.send_sms failed to {to_phone}: {error_str}')
                return {
                    'success': False,
                    'provider': 'twilio',
                    'sid': '',
                    'status': 'failed',
                    'is_invalid_number': False,
                    'error': error_str,
                }

        return {
            'success': False,
            'provider': 'twilio',
            'sid': '',
            'status': 'failed',
            'is_invalid_number': False,
            'error': 'Max retries exceeded due to rate limiting',
        }

    def send_bulk_sms(
        self,
        recipients: List[Dict],
        body: str,
        status_callback_url: str = '',
        delay_between_ms: int = 50,
    ) -> Dict:
        """
        Send the same SMS body to multiple recipients sequentially.

        Each recipient dict: {'phone': str, 'notification_id': str (opt)}

        Args:
            recipients:           List of recipient dicts.
            body:                 Message text.
            status_callback_url:  Optional Twilio webhook URL.
            delay_between_ms:     Milliseconds to sleep between sends to
                                  avoid hitting Twilio rate limits.

        Returns:
            Dict with success, total, success_count, failure_count,
            invalid_numbers, responses.
        """
        if not self._available:
            return {
                'success': False,
                'provider': 'twilio',
                'error': 'TwilioProvider not available',
                'total': len(recipients),
                'success_count': 0,
                'failure_count': len(recipients),
                'invalid_numbers': [],
                'responses': [],
            }

        responses = []
        success_count = 0
        failure_count = 0
        invalid_numbers: List[str] = []

        for recipient in recipients:
            phone = recipient.get('phone', '')
            notif_id = recipient.get('notification_id', '')
            result = self.send_sms(
                to_phone=phone,
                body=body,
                notification_id=notif_id,
                status_callback_url=status_callback_url,
            )
            responses.append({'phone': phone, **result})
            if result['success']:
                success_count += 1
            else:
                failure_count += 1
                if result.get('is_invalid_number'):
                    invalid_numbers.append(phone)

            if delay_between_ms > 0:
                time.sleep(delay_between_ms / 1000)

        return {
            'success': success_count > 0,
            'provider': 'twilio',
            'error': '',
            'total': len(recipients),
            'success_count': success_count,
            'failure_count': failure_count,
            'invalid_numbers': invalid_numbers,
            'responses': responses,
        }

    def send_whatsapp(
        self,
        to_phone: str,
        body: str,
        media_url: str = '',
        notification_id: str = '',
    ) -> Dict:
        """
        Send a WhatsApp message via Twilio WhatsApp API.

        Args:
            to_phone:       Recipient phone in E.164 format.
            body:           Message text.
            media_url:      Optional media attachment URL.
            notification_id: Optional reference ID.
        """
        if not self._available:
            return self._unavailable_response('whatsapp')

        if not self._whatsapp_from:
            return {
                'success': False,
                'provider': 'twilio_whatsapp',
                'sid': '',
                'status': 'failed',
                'is_invalid_number': False,
                'error': 'TWILIO_WHATSAPP_FROM not configured',
            }

        to_whatsapp = f'whatsapp:{self._normalise_phone(to_phone)}'
        params: Dict = {
            'body': body,
            'from_': self._whatsapp_from,
            'to': to_whatsapp,
        }
        if media_url:
            params['media_url'] = [media_url]

        try:
            message = self._client.messages.create(**params)
            return {
                'success': True,
                'provider': 'twilio_whatsapp',
                'sid': message.sid,
                'status': message.status,
                'is_invalid_number': False,
                'error': '',
            }
        except Exception as exc:
            error_str = str(exc)
            error_code = self._extract_error_code(exc)
            is_invalid = error_code in self.INVALID_NUMBER_CODES
            logger.error(f'TwilioProvider.send_whatsapp failed to {to_phone}: {error_str}')
            return {
                'success': False,
                'provider': 'twilio_whatsapp',
                'sid': '',
                'status': 'failed',
                'is_invalid_number': is_invalid,
                'error': error_str,
            }

    def process_status_webhook(self, data: Dict) -> Dict:
        """
        Process Twilio status callback webhook POST data.

        Updates SMSDeliveryLog based on MessageStatus.
        Returns a summary dict.

        Twilio MessageStatus values:
            queued, failed, sent, delivered, undelivered, receiving, received,
            accepted, scheduled, read, partially_delivered, canceled
        """
        message_sid = data.get('MessageSid', '')
        message_status = data.get('MessageStatus', '').lower()

        result = {
            'sid': message_sid,
            'status': message_status,
            'processed': False,
            'error': '',
        }

        if not message_sid:
            result['error'] = 'No MessageSid in webhook data'
            return result

        try:
            from api.notifications.models.channel import SMSDeliveryLog

            log = SMSDeliveryLog.objects.filter(provider_sid=message_sid).first()
            if not log:
                result['error'] = f'No SMSDeliveryLog found for SID {message_sid}'
                return result

            if message_status == 'delivered':
                log.mark_delivered()
            elif message_status in ('failed', 'undelivered'):
                error_code = data.get('ErrorCode', '')
                error_message = data.get('ErrorMessage', '')
                log.mark_failed(error_code=error_code, error_message=error_message)
            elif message_status == 'sent':
                log.status = 'sent'
                log.save(update_fields=['status', 'updated_at'])

            result['processed'] = True

        except Exception as exc:
            logger.error(f'TwilioProvider.process_status_webhook failed: {exc}')
            result['error'] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_phone(phone: str) -> str:
        """Ensure phone number starts with '+'. Strips spaces/dashes."""
        phone = phone.strip().replace(' ', '').replace('-', '')
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone

    @staticmethod
    def _extract_error_code(exc) -> Optional[int]:
        """Try to extract the integer error code from a Twilio exception."""
        try:
            return int(getattr(exc, 'code', None) or 0)
        except (TypeError, ValueError):
            return None

    def _unavailable_response(self, channel: str) -> Dict:
        return {
            'success': False,
            'provider': f'twilio_{channel}',
            'sid': '',
            'status': 'failed',
            'is_invalid_number': False,
            'error': 'TwilioProvider not available — settings not configured',
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
twilio_provider = TwilioProvider()
