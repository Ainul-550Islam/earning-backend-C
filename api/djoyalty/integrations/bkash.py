# api/djoyalty/integrations/bkash.py
"""
bKash Integration -- FIXED।

FIX: BkashIntegration was not inheriting from PaymentAdapter।
     Now: class BkashIntegration(PaymentAdapter)

All abstract methods (create_payment, verify_payment, refund)
are now properly implemented, satisfying the PaymentAdapter contract।

Settings required:
    DJOYALTY_BKASH_APP_KEY
    DJOYALTY_BKASH_APP_SECRET
    DJOYALTY_BKASH_USERNAME
    DJOYALTY_BKASH_PASSWORD
    DJOYALTY_BKASH_SANDBOX = True/False
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

from ..integration_system.integ_adapter import PaymentAdapter  # FIX: now inherits

logger = logging.getLogger(__name__)

BKASH_SANDBOX_BASE = 'https://tokenized.sandbox.bka.sh/v1.2.0-beta/tokenized/checkout'
BKASH_PROD_BASE    = 'https://tokenized.pay.bka.sh/v1.2.0-beta/tokenized/checkout'


class BkashIntegration(PaymentAdapter):  # FIX: was `class BkashIntegration:`
    """
    bKash Checkout API integration।
    Loyalty cashout + subscription payment-এ ব্যবহার করুন।

    Usage:
        bkash = BkashIntegration()
        result = bkash.create_payment(
            amount=Decimal('500'),
            reference='CO-ABC123',
            customer_phone='01712345678',
        )
    """

    def __init__(self):
        self.app_key    = getattr(settings, 'DJOYALTY_BKASH_APP_KEY', '')
        self.app_secret = getattr(settings, 'DJOYALTY_BKASH_APP_SECRET', '')
        self.username   = getattr(settings, 'DJOYALTY_BKASH_USERNAME', '')
        self.password   = getattr(settings, 'DJOYALTY_BKASH_PASSWORD', '')
        self.sandbox    = getattr(settings, 'DJOYALTY_BKASH_SANDBOX', True)
        self.base_url   = BKASH_SANDBOX_BASE if self.sandbox else BKASH_PROD_BASE

    # ── PaymentAdapter abstract methods ───────────────────────────────────────

    def create_payment(self, amount: Decimal, reference: str,
                       customer_phone: str = '', **kwargs) -> dict:
        """
        Create bKash checkout session।
        Returns: {payment_id, redirect_url, success, raw}
        """
        token = self._get_token()
        if not token:
            return {'success': False, 'error': 'bKash authentication failed'}

        payload = {
            'mode':                   '0011',
            'payerReference':         customer_phone,
            'callbackURL':            kwargs.get('callback_url', settings.DJOYALTY_BKASH_CALLBACK_URL if hasattr(settings, 'DJOYALTY_BKASH_CALLBACK_URL') else ''),
            'amount':                 str(amount),
            'currency':               'BDT',
            'intent':                 'sale',
            'merchantInvoiceNumber':  reference,
        }
        try:
            r = requests.post(
                f'{self.base_url}/create',
                json=payload,
                headers=self._auth_headers(token),
                timeout=15,
            )
            data = r.json()
            logger.info('bKash create_payment: %s -> %s', reference, data.get('statusCode'))
            return self.to_standard_response({
                **data,
                'redirect_url': data.get('bkashURL', ''),
            })
        except requests.RequestException as e:
            logger.error('bKash create_payment error: %s', e)
            return {'success': False, 'error': str(e)}

    def verify_payment(self, payment_id: str, **kwargs) -> dict:
        """
        Verify payment status with bKash।
        Returns: {success, amount, transaction_id, status}
        """
        token = self._get_token()
        if not token:
            return {'success': False, 'error': 'bKash authentication failed'}
        try:
            r = requests.get(
                f'{self.base_url}/payment/status',
                params={'paymentID': payment_id},
                headers=self._auth_headers(token),
                timeout=15,
            )
            data = r.json()
            logger.info('bKash verify_payment: %s -> %s', payment_id, data.get('transactionStatus'))
            return self.to_standard_response(data)
        except requests.RequestException as e:
            logger.error('bKash verify_payment error: %s', e)
            return {'success': False, 'error': str(e)}

    def refund(self, payment_id: str, amount: Decimal, reason: str = '') -> dict:
        """
        Refund a bKash payment।
        Returns: {success, refund_id}
        """
        token = self._get_token()
        if not token:
            return {'success': False, 'error': 'bKash authentication failed'}
        try:
            r = requests.post(
                f'{self.base_url}/payment/refund',
                json={
                    'paymentID': payment_id,
                    'amount':    str(amount),
                    'trxID':     payment_id,
                    'sku':       reason[:100],
                    'reason':    reason,
                },
                headers=self._auth_headers(token),
                timeout=15,
            )
            data = r.json()
            logger.info('bKash refund: %s -> %s', payment_id, data.get('statusCode'))
            return {
                'success':   data.get('statusCode') == '0000',
                'refund_id': data.get('refundTrxID', ''),
                'raw':       data,
            }
        except requests.RequestException as e:
            logger.error('bKash refund error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Get bKash token (cached for 55 minutes)।"""
        cache_key = 'djoyalty_bkash_token'
        token = cache.get(cache_key)
        if token:
            return token
        try:
            r = requests.post(
                f'{self.base_url}/token/grant',
                json={'app_key': self.app_key, 'app_secret': self.app_secret},
                headers={
                    'Content-Type': 'application/json',
                    'username': self.username,
                    'password': self.password,
                },
                timeout=15,
            )
            data  = r.json()
            token = data.get('id_token', '')
            if token:
                cache.set(cache_key, token, 55 * 60)  # 55 min
            return token
        except requests.RequestException as e:
            logger.error('bKash _get_token error: %s', e)
            return ''

    def _auth_headers(self, token: str) -> dict:
        return {
            'Content-Type':  'application/json',
            'Authorization': token,
            'X-APP-Key':     self.app_key,
        }
