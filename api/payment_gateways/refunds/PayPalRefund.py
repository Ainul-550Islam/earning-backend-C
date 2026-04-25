# api/payment_gateways/refunds/PayPalRefund.py
# FILE 57 of 257 — PayPal Refund Processor

import requests
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class PayPalRefund(RefundProcessor):
    """
    PayPal Refund Processor.

    Uses PayPal Orders API v2 / Payments API v2.
    Docs: https://developer.paypal.com/docs/api/payments/v2/#captures_refund

    Supports:
        - Full refund
        - Partial refund
        - Refund status check
    """

    def __init__(self):
        super().__init__('paypal')
        is_sandbox = getattr(settings, 'PAYPAL_SANDBOX', True)
        self.base_url = (
            'https://api-m.sandbox.paypal.com'
            if is_sandbox
            else 'https://api-m.paypal.com'
        )
        self.config = {
            'client_id':     getattr(settings, 'PAYPAL_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'PAYPAL_CLIENT_SECRET', ''),
        }
        self._token_cache = None

    # ── OAuth2 token ──────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._token_cache:
            return self._token_cache
        response = requests.post(
            f'{self.base_url}/v1/oauth2/token',
            data={'grant_type': 'client_credentials'},
            auth=(self.config['client_id'], self.config['client_secret']),
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get('access_token', '')
        if not token:
            raise Exception('PayPal: failed to get access token')
        self._token_cache = token
        return token

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type':  'application/json',
        }

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Refund a PayPal capture.
        Requires the PayPal capture_id stored in transaction metadata or gateway_reference.
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        # PayPal refunds are applied to capture_id, not order_id
        capture_id = (
            transaction.metadata.get('paypal_data', {}).get('capture_id')
            or transaction.metadata.get('capture_id')
            or transaction.gateway_reference
        )

        if not capture_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'PayPal capture_id not found'})
            raise Exception('PayPal refund failed: capture_id not found in transaction metadata')

        try:
            # Determine currency from original transaction metadata
            currency = (
                transaction.metadata.get('currency', 'USD').upper()
            )

            payload = {
                'amount': {
                    'value':         str(amount),
                    'currency_code': currency,
                },
                'note_to_payer':     reason.replace('_', ' ').title(),
                'invoice_id':        refund.reference_id,
            }

            response = requests.post(
                f'{self.base_url}/v2/payments/captures/{capture_id}/refund',
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            paypal_refund_id = data.get('id', '')
            paypal_status    = data.get('status', '')   # COMPLETED | PENDING | CANCELLED

            status_map = {
                'COMPLETED': 'completed',
                'PENDING':   'processing',
                'CANCELLED': 'cancelled',
                'FAILED':    'failed',
            }
            internal_status = status_map.get(paypal_status, 'processing')

            self.update_refund_status(
                refund, internal_status,
                gateway_refund_id=paypal_refund_id,
                raw_response=data,
            )

            return {
                'refund_request':    refund,
                'gateway_refund_id': paypal_refund_id,
                'status':            internal_status,
                'paypal_status':     paypal_status,
                'message':           (
                    f'PayPal refund of {amount} {currency} {internal_status}. '
                    f'Refund ID: {paypal_refund_id}'
                ),
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            error_msg = (
                error_data.get('message')
                or error_data.get('details', [{}])[0].get('description', str(e))
                if isinstance(error_data.get('details'), list)
                else str(e)
            )
            self.update_refund_status(refund, 'failed', raw_response=error_data)
            raise Exception(f'PayPal refund failed: {error_msg}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Get PayPal refund details and sync status"""
        try:
            paypal_refund_id = refund_request.gateway_refund_id
            response = requests.get(
                f'{self.base_url}/v2/payments/refunds/{paypal_refund_id}',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            paypal_status = data.get('status', '')
            status_map = {
                'COMPLETED': 'completed',
                'PENDING':   'processing',
                'CANCELLED': 'cancelled',
                'FAILED':    'failed',
            }
            internal_status = status_map.get(paypal_status, refund_request.status)
            self.update_refund_status(refund_request, internal_status, raw_response=data)

            return {
                'status':         internal_status,
                'gateway_status': paypal_status,
                'raw_response':   data,
            }
        except Exception as e:
            return {'status': refund_request.status, 'gateway_status': 'unknown', 'error': str(e)}

    # ── cancel_refund ─────────────────────────────────────────────────────────

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """PayPal does not support refund cancellation after initiation."""
        raise NotImplementedError('PayPal does not support refund cancellation after initiation.')
