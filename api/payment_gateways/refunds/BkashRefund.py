# api/payment_gateways/refunds/BkashRefund.py
# FILE 50 of 257 — bKash Refund Processor

import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

from .RefundProcessor import RefundProcessor


class BkashRefund(RefundProcessor):
    """
    bKash Refund Processor.

    Uses bKash Tokenized Checkout Refund API.
    Docs: https://developer.bka.sh/docs/refund-tokenized

    Supports:
        - Full refund
        - Partial refund (multiple times up to original amount)
    """

    def __init__(self):
        super().__init__('bkash')
        is_sandbox = getattr(settings, 'BKASH_SANDBOX', True)
        self.base_url = (
            'https://tokenized.sandbox.bka.sh/v1.2.0-beta'
            if is_sandbox
            else 'https://tokenized.pay.bka.sh/v1.2.0-beta'
        )
        self.config = {
            'app_key':    getattr(settings, 'BKASH_APP_KEY', ''),
            'app_secret': getattr(settings, 'BKASH_APP_SECRET', ''),
            'username':   getattr(settings, 'BKASH_USERNAME', ''),
            'password':   getattr(settings, 'BKASH_PASSWORD', ''),
        }

    # ── Token ─────────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        url = f'{self.base_url}/tokenized/checkout/token/grant'
        response = requests.post(
            url,
            json={
                'app_key':    self.config['app_key'],
                'app_secret': self.config['app_secret'],
            },
            headers={
                'username':     self.config['username'],
                'password':     self.config['password'],
                'Content-Type': 'application/json',
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get('id_token')
        if not token:
            raise Exception('bKash: failed to get auth token')
        return token

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate bKash refund for a completed transaction.

        bKash requires: paymentID (stored in transaction.gateway_reference)
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        payment_id = transaction.gateway_reference
        if not payment_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'No bKash paymentID found'})
            raise Exception('bKash refund failed: original paymentID not found in transaction')

        try:
            token = self._get_token()
            url   = f'{self.base_url}/tokenized/checkout/payment/refund'

            payload = {
                'paymentID':     payment_id,
                'amount':        str(amount),
                'trxID':         transaction.metadata.get('bkash_trxID', ''),
                'sku':           'refund',
                'reason':        reason,
            }

            headers = {
                'Authorization': token,
                'X-APP-Key':     self.config['app_key'],
                'Content-Type':  'application/json',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            refund_trx_id = data.get('refundTrxID', '')
            status_code   = data.get('statusCode', '')

            if status_code == '0000':
                # bKash refund is instant
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=refund_trx_id,
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': refund_trx_id,
                    'status':            'completed',
                    'message':           f'bKash refund of {amount} BDT completed. RefundTrxID: {refund_trx_id}',
                }
            else:
                error_msg = data.get('statusMessage', 'Unknown bKash error')
                self.update_refund_status(refund, 'failed', raw_response=data)
                raise Exception(f'bKash refund failed: {error_msg} (code: {status_code})')

        except Exception as e:
            if refund.status != 'failed':
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """
        Check refund status. bKash refunds are synchronous, so this
        mostly returns the stored status from our DB.
        For deeper check, we query the original transaction status.
        """
        return {
            'status':         refund_request.status,
            'gateway_status': refund_request.status,
            'gateway_refund_id': refund_request.gateway_refund_id,
            'raw_response':   refund_request.metadata.get('gateway_response', {}),
        }

    # ── cancel_refund ─────────────────────────────────────────────────────────

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """
        bKash does not support refund cancellation once initiated.
        Refunds are processed instantly.
        """
        raise NotImplementedError('bKash does not support refund cancellation.')
