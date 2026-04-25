# api/payment_gateways/refunds/AmarPayRefund.py
# FILE 53 of 257 — AmarPay Refund Processor

import requests
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class AmarPayRefund(RefundProcessor):
    """
    AmarPay (aamarpay) Refund Processor.

    Uses aamarpay refund API.
    Docs: https://aamarpay.com/developer-api#refund

    Supports:
        - Full refund
        - Partial refund
    """

    def __init__(self):
        super().__init__('amarpay')
        is_sandbox = getattr(settings, 'AMARPAY_SANDBOX', True)
        self.base_url = (
            'https://sandbox.aamarpay.com'
            if is_sandbox
            else 'https://secure.aamarpay.com'
        )
        self.config = {
            'store_id':      getattr(settings, 'AMARPAY_STORE_ID', 'aamarpay'),
            'signature_key': getattr(settings, 'AMARPAY_SIGNATURE_KEY', ''),
        }

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate AmarPay refund.
        Requires merchant transaction ID (our reference_id).
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        try:
            url = f'{self.base_url}/api/v1/refund/request.php'

            payload = {
                'store_id':      self.config['store_id'],
                'signature_key': self.config['signature_key'],
                'request_id':    transaction.reference_id,
                'refund_amount': str(amount),
                'refund_remarks': reason,
                'type':          'json',
            }

            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            refund_id  = data.get('refund_id', '') or data.get('refund_ref', '')
            api_status = data.get('status', '').lower()

            if api_status in ('successful', 'success', 'refunded'):
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=str(refund_id),
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'completed',
                    'message':           f'AmarPay refund of {amount} BDT completed.',
                }
            elif api_status in ('processing', 'pending', 'queued'):
                self.update_refund_status(
                    refund, 'processing',
                    gateway_refund_id=str(refund_id),
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'processing',
                    'message':           'AmarPay refund is being processed.',
                }
            else:
                error = data.get('error', data.get('message', 'Unknown AmarPay error'))
                self.update_refund_status(refund, 'failed', raw_response=data)
                raise Exception(f'AmarPay refund failed: {error}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Check AmarPay refund status"""
        try:
            url = f'{self.base_url}/api/v1/refund/request.php'
            params = {
                'store_id':      self.config['store_id'],
                'signature_key': self.config['signature_key'],
                'refund_id':     refund_request.gateway_refund_id,
                'type':          'json',
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            api_status = data.get('status', '').lower()
            if api_status in ('successful', 'success', 'refunded'):
                self.update_refund_status(refund_request, 'completed', raw_response=data)
            elif api_status in ('processing', 'pending', 'queued'):
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
        raise NotImplementedError('AmarPay does not support refund cancellation.')
