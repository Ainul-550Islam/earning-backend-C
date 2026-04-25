# api/payment_gateways/refunds/ShurjoPayRefund.py
# FILE 55 of 257 — ShurjoPay Refund Processor

import requests
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class ShurjoPayRefund(RefundProcessor):
    """
    ShurjoPay Refund Processor.

    Uses ShurjoPay merchant refund API.
    Docs: https://docs.shurjopayment.com/refund

    Supports:
        - Full refund
        - Partial refund
    ShurjoPay sp_codes for success: '1000' (completed), '1001' (processing)
    """

    SANDBOX_URL = 'https://sandbox.shurjopayment.com/api'
    LIVE_URL    = 'https://engine.shurjopayment.com/api'

    def __init__(self):
        super().__init__('shurjopay')
        is_sandbox = getattr(settings, 'SHURJOPAY_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.LIVE_URL
        self.config = {
            'username': getattr(settings, 'SHURJOPAY_USERNAME', ''),
            'password': getattr(settings, 'SHURJOPAY_PASSWORD', ''),
        }
        self._token_cache = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _get_token(self) -> dict:
        if self._token_cache:
            return self._token_cache
        url = f'{self.base_url}/get_token/'
        response = requests.post(
            url,
            json={'username': self.config['username'], 'password': self.config['password']},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get('token')
        if not token:
            raise Exception('ShurjoPay: failed to get auth token')
        self._token_cache = {'token': token, 'token_type': data.get('token_type', 'Bearer')}
        return self._token_cache

    def _headers(self) -> dict:
        t = self._get_token()
        return {
            'Authorization': f"{t['token_type']} {t['token']}",
            'Content-Type':  'application/json',
        }

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate ShurjoPay refund.
        Requires sp_order_id from original transaction.
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        sp_order_id = (
            transaction.metadata.get('shurjopay_data', {}).get('sp_order_id')
            or transaction.gateway_reference
        )

        if not sp_order_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'sp_order_id not found'})
            raise Exception('ShurjoPay refund failed: sp_order_id not found in transaction metadata')

        try:
            url = f'{self.base_url}/merchant/refund/'

            payload = {
                'order_id':      sp_order_id,
                'refund_amount': str(amount),
                'refund_reason': reason,
                'client_ref_id': refund.reference_id,
            }

            response = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            response.raise_for_status()
            data = response.json()

            # ShurjoPay may return list or dict
            result    = data[0] if isinstance(data, list) and data else data
            sp_code   = str(result.get('sp_code', ''))
            sp_msg    = result.get('sp_massage') or result.get('sp_message', '')
            refund_id = result.get('refund_id', '') or result.get('id', '')

            if sp_code == '1000':
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=str(refund_id),
                    raw_response=result,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'completed',
                    'message':           f'ShurjoPay refund of {amount} BDT completed.',
                }
            elif sp_code in ('1001', '1002'):
                self.update_refund_status(
                    refund, 'processing',
                    gateway_refund_id=str(refund_id),
                    raw_response=result,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': str(refund_id),
                    'status':            'processing',
                    'message':           f'ShurjoPay refund processing: {sp_msg}',
                }
            else:
                self.update_refund_status(refund, 'failed', raw_response=result)
                raise Exception(f'ShurjoPay refund failed: {sp_msg} (code: {sp_code})')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Check ShurjoPay refund status"""
        try:
            url     = f'{self.base_url}/merchant/refund/status/'
            payload = {'refund_id': refund_request.gateway_refund_id}

            response = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            response.raise_for_status()
            data   = response.json()
            result = data[0] if isinstance(data, list) and data else data

            sp_code = str(result.get('sp_code', ''))
            if sp_code == '1000':
                self.update_refund_status(refund_request, 'completed', raw_response=result)
            elif sp_code in ('1001', '1002'):
                self.update_refund_status(refund_request, 'processing', raw_response=result)
            else:
                self.update_refund_status(refund_request, 'failed', raw_response=result)

            return {
                'status':         refund_request.status,
                'gateway_status': sp_code,
                'raw_response':   result,
            }
        except Exception as e:
            return {'status': refund_request.status, 'gateway_status': 'unknown', 'error': str(e)}

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        raise NotImplementedError('ShurjoPay does not support refund cancellation.')
