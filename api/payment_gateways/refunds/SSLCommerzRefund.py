# api/payment_gateways/refunds/SSLCommerzRefund.py
# FILE 52 of 257 — SSLCommerz Refund Processor

import requests
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class SSLCommerzRefund(RefundProcessor):
    """
    SSLCommerz Refund Processor.

    Uses SSLCommerz Refund API.
    Docs: https://developer.sslcommerz.com/doc/v4/#refund-api

    Supports:
        - Full refund
        - Partial refund
        - Refund status check
    """

    def __init__(self):
        super().__init__('sslcommerz')
        is_sandbox = getattr(settings, 'SSLCOMMERZ_SANDBOX', True)
        self.base_url = (
            'https://sandbox.sslcommerz.com'
            if is_sandbox
            else 'https://securepay.sslcommerz.com'
        )
        self.config = {
            'store_id':     getattr(settings, 'SSLCOMMERZ_STORE_ID', ''),
            'store_passwd': getattr(settings, 'SSLCOMMERZ_STORE_PASSWORD', ''),
        }

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate SSLCommerz refund.
        Requires bank_tran_id from the original transaction metadata.
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        # SSLCommerz needs the bank transaction ID from the original payment
        bank_tran_id = (
            transaction.metadata.get('validation_data', {}).get('bank_tran_id')
            or transaction.metadata.get('ipn_data', {}).get('bank_tran_id')
            or transaction.gateway_reference
        )

        if not bank_tran_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'bank_tran_id not found'})
            raise Exception('SSLCommerz refund failed: bank_tran_id not found in transaction metadata')

        try:
            url = f'{self.base_url}/validator/api/merchantTransIDvalidationAPI.php'

            params = {
                'tran_id':      transaction.reference_id,
                'store_id':     self.config['store_id'],
                'store_passwd': self.config['store_passwd'],
                'v':            1,
                'format':       'json',
            }

            # Step 1: Validate original transaction
            val_response = requests.get(url, params=params, timeout=30)
            val_response.raise_for_status()
            val_data = val_response.json()

            if val_data.get('status') not in ('VALID', 'VALIDATED'):
                self.update_refund_status(refund, 'failed', raw_response=val_data)
                raise Exception(f'SSLCommerz: Original transaction not valid for refund. Status: {val_data.get("status")}')

            # Step 2: Initiate refund
            refund_url = f'{self.base_url}/validator/api/merchantTransIDvalidationAPI.php'

            refund_params = {
                'bank_tran_id':  bank_tran_id,
                'store_id':      self.config['store_id'],
                'store_passwd':  self.config['store_passwd'],
                'refund_amount': str(amount),
                'refund_remarks': reason,
                'remark':        refund.reference_id,
                'v':             1,
                'format':        'json',
            }

            ref_response = requests.post(refund_url, data=refund_params, timeout=30)
            ref_response.raise_for_status()
            ref_data = ref_response.json()

            refund_ref_id = ref_data.get('refundRefId', '') or ref_data.get('trans_id', '')
            api_status    = ref_data.get('status', '')

            if api_status in ('success', 'refunded'):
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=refund_ref_id,
                    raw_response=ref_data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': refund_ref_id,
                    'status':            'completed',
                    'message':           f'SSLCommerz refund of {amount} BDT completed.',
                }
            elif api_status in ('processing', 'pending'):
                self.update_refund_status(
                    refund, 'processing',
                    gateway_refund_id=refund_ref_id,
                    raw_response=ref_data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': refund_ref_id,
                    'status':            'processing',
                    'message':           'SSLCommerz refund is being processed.',
                }
            else:
                error = ref_data.get('errorReason', ref_data.get('message', 'Unknown error'))
                self.update_refund_status(refund, 'failed', raw_response=ref_data)
                raise Exception(f'SSLCommerz refund failed: {error}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Check SSLCommerz refund status"""
        try:
            url = f'{self.base_url}/validator/api/merchantTransIDvalidationAPI.php'
            params = {
                'refundRefId':  refund_request.gateway_refund_id,
                'store_id':     self.config['store_id'],
                'store_passwd': self.config['store_passwd'],
                'v':            1,
                'format':       'json',
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            api_status = data.get('status', '')
            if api_status in ('success', 'refunded'):
                self.update_refund_status(refund_request, 'completed', raw_response=data)
            elif api_status in ('processing', 'pending'):
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

    # ── cancel_refund ─────────────────────────────────────────────────────────

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """SSLCommerz does not support refund cancellation."""
        raise NotImplementedError('SSLCommerz does not support refund cancellation.')
