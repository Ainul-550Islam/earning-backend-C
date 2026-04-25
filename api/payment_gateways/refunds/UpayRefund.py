# api/payment_gateways/refunds/UpayRefund.py
# FILE 54 of 257 — Upay Refund Processor

import requests
import json
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class UpayRefund(RefundProcessor):
    """
    Upay (United Commercial Bank) Refund Processor.

    Uses Upay merchant refund API.
    Docs: https://upay.com.bd/merchant-api-docs

    Supports:
        - Full refund
        - Partial refund
    """

    SANDBOX_URL = 'https://uat.upay.com.bd/api/v1'
    LIVE_URL    = 'https://upay.com.bd/api/v1'

    def __init__(self):
        super().__init__('upay')
        is_sandbox = getattr(settings, 'UPAY_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.LIVE_URL
        self.config = {
            'merchant_id':  getattr(settings, 'UPAY_MERCHANT_ID', ''),
            'merchant_key': getattr(settings, 'UPAY_MERCHANT_KEY', ''),
        }
        self._token_cache = None

    # ── Auth token ────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._token_cache:
            return self._token_cache
        url = f'{self.base_url}/rgw/token/generate'
        response = requests.post(
            url,
            json={
                'merchant_id':  self.config['merchant_id'],
                'merchant_key': self.config['merchant_key'],
            },
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get('merchant_token')
        if not token:
            raise Exception('Upay: failed to get auth token')
        self._token_cache = token
        return token

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate Upay refund.
        Requires original merchant_order_id and upay transaction_id.
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        upay_txn_id = (
            transaction.metadata.get('upay_data', {}).get('transaction_id')
            or transaction.gateway_reference
        )

        if not upay_txn_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'Upay transaction_id not found'})
            raise Exception('Upay refund failed: original transaction_id not found')

        try:
            token = self._get_token()
            url   = f'{self.base_url}/rgw/refund/init'

            payload = {
                'merchant_id':       self.config['merchant_id'],
                'transaction_id':    upay_txn_id,
                'merchant_order_id': transaction.reference_id,
                'refund_amount':     str(amount),
                'refund_reason':     reason,
                'refund_ref_id':     refund.reference_id,
            }

            headers = {
                'merchant-token': token,
                'Content-Type':   'application/json',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            api_status  = data.get('status', '')
            refund_id   = data.get('refund_id', '') or data.get('refund_transaction_id', '')

            if api_status.upper() in ('SUCCESS', 'COMPLETED'):
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=str(refund_id),
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'completed',
                    'message':           f'Upay refund of {amount} BDT completed.',
                }
            elif api_status.upper() in ('PROCESSING', 'PENDING', 'INITIATED'):
                self.update_refund_status(
                    refund, 'processing',
                    gateway_refund_id=str(refund_id),
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'processing',
                    'message':           'Upay refund initiated and is being processed.',
                }
            else:
                error = data.get('message', 'Unknown Upay error')
                self.update_refund_status(refund, 'failed', raw_response=data)
                raise Exception(f'Upay refund failed: {error}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Check Upay refund status"""
        try:
            token = self._get_token()
            url   = f'{self.base_url}/rgw/refund/status'

            payload = {
                'merchant_id': self.config['merchant_id'],
                'refund_id':   refund_request.gateway_refund_id,
            }
            headers = {'merchant-token': token, 'Content-Type': 'application/json'}

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            api_status = data.get('status', '').upper()
            if api_status in ('SUCCESS', 'COMPLETED'):
                self.update_refund_status(refund_request, 'completed', raw_response=data)
            elif api_status in ('PROCESSING', 'PENDING', 'INITIATED'):
                self.update_refund_status(refund_request, 'processing', raw_response=data)
            else:
                self.update_refund_status(refund_request, 'failed', raw_response=data)

            return {
                'status':         refund_request.status,
                'gateway_status': api_status,
                'raw_response':   data,
            }
        except Exception as e:
            return {'status': refund_request.status, 'gateway_status': 'unknown', 'error': str(e)}

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        raise NotImplementedError('Upay does not support refund cancellation.')
