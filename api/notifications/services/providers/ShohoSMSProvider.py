# earning_backend/api/notifications/services/providers/ShohoSMSProvider.py
"""
ShohoSMSProvider — Bangladesh SMS gateway integration (smsgreen.net / shoho.com.bd).

ShohoSMS (also known as SMS Green) is one of the most popular bulk SMS gateways
in Bangladesh. It exposes a simple HTTP GET/POST API.

Settings required:
    SHOHO_SMS_API_KEY     — API key / token from your ShohoSMS account
    SHOHO_SMS_SENDER_ID   — Registered sender ID (Masking), e.g. 'YourBrand'
                            (Leave blank for non-masking / numeric sender)
    SHOHO_SMS_API_URL     — (optional) Base API URL; defaults to the standard
                            smsgreen endpoint below.

API docs:   https://smsgreen.net/api/
"""

import logging
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)

# Default API endpoint
_DEFAULT_API_URL = 'https://api.smsgreen.net/smsapi'


# ---------------------------------------------------------------------------
# ShohoSMSProvider class
# ---------------------------------------------------------------------------

class ShohoSMSProvider:
    """
    HTTP-based SMS provider for the Bangladeshi ShohoSMS / SMS Green gateway.

    Uses the requests library (standard Django stack dependency).
    All phone numbers should be in local 01XXXXXXXXX format or E.164 +880XXXXXXXXX.
    """

    # BD country code
    BD_COUNTRY_CODE = '880'

    # Delivery status codes returned by ShohoSMS API
    DELIVERED_STATUS = '1'

    # Max recipients per single API call (gateway limit)
    MAX_RECIPIENTS_PER_CALL = 200

    def __init__(self):
        self._api_key: str = getattr(settings, 'SHOHO_SMS_API_KEY', '')
        self._sender_id: str = getattr(settings, 'SHOHO_SMS_SENDER_ID', '')
        self._api_url: str = getattr(settings, 'SHOHO_SMS_API_URL', _DEFAULT_API_URL)
        self._available: bool = bool(self._api_key)

        if not self._available:
            logger.warning(
                'ShohoSMSProvider: SHOHO_SMS_API_KEY not configured. '
                'Bangladesh SMS gateway disabled.'
            )
        else:
            logger.info('ShohoSMSProvider: configured.')

        # Lazily imported
        self._requests = None

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
    ) -> Dict:
        """
        Send a single SMS via ShohoSMS.

        Args:
            to_phone:       Phone number (local '01XXXXXXXXX' or E.164 '+880XXXXXXXXX').
            body:           Message text (Bangla Unicode or ASCII, max ~160 chars/segment).
            notification_id: Optional reference ID stored in the log.

        Returns:
            Dict with keys: success, provider, sid, status, error, is_invalid_number.
        """
        if not self._available:
            return self._unavailable_response()

        to_phone = self._normalise_bd_phone(to_phone)
        requests = self._get_requests()

        payload = {
            'api_key': self._api_key,
            'type': 'text',
            'contacts': to_phone,
            'senderid': self._sender_id,
            'msg': body,
        }

        try:
            response = requests.post(
                self._api_url,
                data=payload,
                timeout=15,
            )
            response.raise_for_status()
            resp_data = self._parse_response(response)

            if resp_data.get('status') in ('success', '1', 1, 'Success'):
                sid = resp_data.get('response_code', '') or resp_data.get('batch_id', '')
                return {
                    'success': True,
                    'provider': 'shoho_sms',
                    'sid': str(sid),
                    'status': 'sent',
                    'is_invalid_number': False,
                    'error': '',
                    'raw_response': resp_data,
                }
            else:
                error_msg = resp_data.get('error', '') or resp_data.get('message', str(resp_data))
                is_invalid = 'invalid' in error_msg.lower() or 'number' in error_msg.lower()
                logger.warning(f'ShohoSMSProvider.send_sms error: {error_msg}')
                return {
                    'success': False,
                    'provider': 'shoho_sms',
                    'sid': '',
                    'status': 'failed',
                    'is_invalid_number': is_invalid,
                    'error': error_msg,
                    'raw_response': resp_data,
                }

        except Exception as exc:
            logger.error(f'ShohoSMSProvider.send_sms exception: {exc}')
            return {
                'success': False,
                'provider': 'shoho_sms',
                'sid': '',
                'status': 'failed',
                'is_invalid_number': False,
                'error': str(exc),
                'raw_response': {},
            }

    def send_bulk_sms(
        self,
        recipients: List[Dict],
        body: str,
        delay_between_ms: int = 100,
    ) -> Dict:
        """
        Send the same SMS body to multiple Bangladeshi recipients.

        Each recipient dict: {'phone': str, 'notification_id': str (opt)}

        Batches up to MAX_RECIPIENTS_PER_CALL recipients per API call using
        the ShohoSMS comma-separated contacts feature.
        """
        if not self._available:
            return {
                'success': False,
                'provider': 'shoho_sms',
                'error': 'ShohoSMSProvider not available',
                'total': len(recipients),
                'success_count': 0,
                'failure_count': len(recipients),
                'invalid_numbers': [],
                'responses': [],
            }

        requests_lib = self._get_requests()
        success_count = 0
        failure_count = 0
        invalid_numbers: List[str] = []
        all_responses: List[Dict] = []

        # Normalise all phones first
        normalised = []
        for r in recipients:
            phone = self._normalise_bd_phone(r.get('phone', ''))
            normalised.append({'phone': phone, 'notification_id': r.get('notification_id', '')})

        for i in range(0, len(normalised), self.MAX_RECIPIENTS_PER_CALL):
            batch = normalised[i: i + self.MAX_RECIPIENTS_PER_CALL]
            phones_str = ','.join(r['phone'] for r in batch)

            payload = {
                'api_key': self._api_key,
                'type': 'text',
                'contacts': phones_str,
                'senderid': self._sender_id,
                'msg': body,
            }

            try:
                response = requests_lib.post(self._api_url, data=payload, timeout=20)
                response.raise_for_status()
                resp_data = self._parse_response(response)

                if resp_data.get('status') in ('success', '1', 1, 'Success'):
                    success_count += len(batch)
                    all_responses.append({
                        'batch_start': i,
                        'batch_end': i + len(batch) - 1,
                        'success': True,
                        'raw': resp_data,
                    })
                else:
                    failure_count += len(batch)
                    all_responses.append({
                        'batch_start': i,
                        'batch_end': i + len(batch) - 1,
                        'success': False,
                        'error': resp_data.get('error', str(resp_data)),
                        'raw': resp_data,
                    })

            except Exception as exc:
                failure_count += len(batch)
                logger.error(f'ShohoSMSProvider.send_bulk_sms batch {i} failed: {exc}')
                all_responses.append({
                    'batch_start': i,
                    'batch_end': i + len(batch) - 1,
                    'success': False,
                    'error': str(exc),
                })

            if delay_between_ms > 0:
                time.sleep(delay_between_ms / 1000)

        return {
            'success': success_count > 0,
            'provider': 'shoho_sms',
            'error': '',
            'total': len(recipients),
            'success_count': success_count,
            'failure_count': failure_count,
            'invalid_numbers': invalid_numbers,
            'responses': all_responses,
        }

    def check_balance(self) -> Dict:
        """
        Query the remaining SMS balance for the account.

        Returns:
            Dict with: success, balance, unit, error.
        """
        if not self._available:
            return {'success': False, 'balance': 0, 'unit': 'SMS', 'error': 'Not configured'}

        requests_lib = self._get_requests()
        balance_url = self._api_url.replace('/smsapi', '/balance') + f'?api_key={self._api_key}'

        try:
            response = requests_lib.get(balance_url, timeout=10)
            response.raise_for_status()
            resp_data = self._parse_response(response)
            balance = resp_data.get('balance', resp_data.get('sms_balance', 0))
            return {
                'success': True,
                'balance': float(balance),
                'unit': 'SMS',
                'error': '',
                'raw': resp_data,
            }
        except Exception as exc:
            return {'success': False, 'balance': 0, 'unit': 'SMS', 'error': str(exc)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalise_bd_phone(self, phone: str) -> str:
        """
        Normalise a Bangladeshi phone number to '01XXXXXXXXX' (11-digit local format).

        Accepts:
          +8801XXXXXXXXX  → 01XXXXXXXXX
          008801XXXXXXXXX → 01XXXXXXXXX
          8801XXXXXXXXX   → 01XXXXXXXXX
          01XXXXXXXXX     → 01XXXXXXXXX (pass-through)
        """
        phone = phone.strip().replace(' ', '').replace('-', '').replace('+', '')
        if phone.startswith('880') and len(phone) == 13:
            phone = '0' + phone[3:]
        elif phone.startswith('0088') and len(phone) == 15:
            phone = '0' + phone[4:]
        elif phone.startswith('88') and len(phone) == 13:
            phone = '0' + phone[2:]
        return phone

    def _get_requests(self):
        """Lazily import and cache the requests library."""
        if self._requests is None:
            import requests as req_lib
            self._requests = req_lib
        return self._requests

    def _parse_response(self, response) -> Dict:
        """
        Parse the HTTP response from ShohoSMS.
        ShohoSMS may return JSON or plain text depending on the endpoint.
        """
        content_type = response.headers.get('Content-Type', '')
        try:
            if 'json' in content_type:
                return response.json()
            else:
                text = response.text.strip()
                # Try JSON parse anyway
                import json
                try:
                    return json.loads(text)
                except (ValueError, TypeError):
                    # Plain-text response like '1001' or 'success'
                    return {'status': text, 'raw_text': text}
        except Exception:
            return {'status': 'unknown', 'raw_text': getattr(response, 'text', '')}

    def _unavailable_response(self) -> Dict:
        return {
            'success': False,
            'provider': 'shoho_sms',
            'sid': '',
            'status': 'failed',
            'is_invalid_number': False,
            'error': 'ShohoSMSProvider not available — SHOHO_SMS_API_KEY not configured',
            'raw_response': {},
        }


    def handle_reply(self, from_phone: str, message: str, user=None) -> dict:
        """
        Handle incoming SMS reply from a user.
        Routes STOP/UNSUB to opt-out, HELP to support, other text to support ticket.

        Called from Twilio/ShohoSMS inbound webhook.
        """
        msg = message.strip().upper()

        if msg in ('STOP', 'UNSUBSCRIBE', 'UNSUB', 'CANCEL', 'QUIT', 'END', 'NO'):
            # Opt-out from SMS
            if user:
                try:
                    from notifications.services.OptOutService import opt_out_service
                    opt_out_service.opt_out(user, 'sms', reason='sms_stop_keyword')
                    logger.info(f'ShohoSMS: STOP from {from_phone} — user #{user.pk} opted out')
                except Exception as exc:
                    logger.warning(f'handle_reply opt-out: {exc}')
            return {'action': 'opted_out', 'reply': 'You have been unsubscribed from SMS notifications.'}

        elif msg in ('START', 'UNSTOP', 'YES'):
            # Re-subscribe
            if user:
                try:
                    from notifications.services.OptOutService import opt_out_service
                    opt_out_service.resubscribe(user, 'sms')
                    logger.info(f'ShohoSMS: START from {from_phone} — user #{user.pk} re-subscribed')
                except Exception as exc:
                    logger.warning(f'handle_reply resubscribe: {exc}')
            return {'action': 'resubscribed', 'reply': 'You have been re-subscribed to SMS notifications.'}

        elif msg in ('HELP', '?'):
            return {'action': 'help_sent',
                    'reply': 'Reply STOP to unsubscribe. Reply START to re-subscribe. Visit our website for support.'}

        else:
            # Route to support ticket via integration system
            try:
                from notifications.integration_system.event_bus import event_bus
                event_bus.publish('sms.reply_received', {
                    'from_phone': from_phone,
                    'message': message,
                    'user_id': getattr(user, 'pk', None),
                    'source': 'shoho_sms',
                })
            except Exception as exc:
                logger.debug(f'handle_reply event_bus: {exc}')
            return {'action': 'forwarded_to_support', 'reply': ''}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
shoho_sms_provider = ShohoSMSProvider()
