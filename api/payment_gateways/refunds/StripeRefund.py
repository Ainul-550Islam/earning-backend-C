# api/payment_gateways/refunds/StripeRefund.py
# FILE 56 of 257 — Stripe Refund Processor

import requests
from decimal import Decimal
from django.conf import settings

from .RefundProcessor import RefundProcessor


class StripeRefund(RefundProcessor):
    """
    Stripe Refund Processor.

    Uses Stripe Refunds API v1.
    Docs: https://stripe.com/docs/api/refunds

    Supports:
        - Full refund
        - Partial refund (multiple times up to charge amount)
        - Refund cancellation (only while refund is 'pending')
        - Refund status polling

    Stripe refund reasons:
        duplicate | fraudulent | requested_by_customer
    """

    STRIPE_REASON_MAP = {
        'duplicate':          'duplicate',
        'fraudulent':         'fraudulent',
        'customer_request':   'requested_by_customer',
        'order_cancelled':    'requested_by_customer',
        'service_not_provided': 'requested_by_customer',
        'partial_refund':     'requested_by_customer',
        'other':              'requested_by_customer',
    }

    def __init__(self):
        super().__init__('stripe')
        self.secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.api_base   = 'https://api.stripe.com/v1'

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type':  'application/x-www-form-urlencoded',
        }

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Create a Stripe refund.

        Stripe amount is in the smallest currency unit (cents for USD, paisa for BDT).
        We store the amount in major units, so multiply by 100.
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        # Get Stripe payment_intent_id or charge_id
        payment_intent_id = (
            transaction.metadata.get('stripe_data', {}).get('payment_intent')
            or transaction.metadata.get('payment_intent_id')
            or transaction.gateway_reference
        )

        if not payment_intent_id:
            self.update_refund_status(refund, 'failed', raw_response={'error': 'payment_intent_id not found'})
            raise Exception('Stripe refund failed: payment_intent_id not found in transaction metadata')

        try:
            # Stripe amounts are in smallest unit (cents)
            amount_cents  = int(amount * 100)
            stripe_reason = self.STRIPE_REASON_MAP.get(reason, 'requested_by_customer')

            data = {
                'payment_intent': payment_intent_id,
                'amount':         amount_cents,
                'reason':         stripe_reason,
                'metadata[refund_reference]': refund.reference_id,
                'metadata[internal_reason]':  reason,
            }

            response = requests.post(
                f'{self.api_base}/refunds',
                data=data,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            stripe_data = response.json()

            stripe_refund_id = stripe_data.get('id', '')
            stripe_status    = stripe_data.get('status', '')

            status_map = {
                'succeeded': 'completed',
                'pending':   'processing',
                'failed':    'failed',
                'canceled':  'cancelled',
                'requires_action': 'processing',
            }

            internal_status = status_map.get(stripe_status, 'processing')

            self.update_refund_status(
                refund, internal_status,
                gateway_refund_id=stripe_refund_id,
                raw_response=stripe_data,
            )

            currency = transaction.metadata.get('currency', 'USD').upper()

            return {
                'refund_request':    refund,
                'gateway_refund_id': stripe_refund_id,
                'status':            internal_status,
                'stripe_status':     stripe_status,
                'message':           (
                    f'Stripe refund of {amount} {currency} {internal_status}. '
                    f'Refund ID: {stripe_refund_id}'
                ),
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json().get('error', {})
            except Exception:
                pass
            error_msg = error_data.get('message', str(e))
            self.update_refund_status(refund, 'failed', raw_response={'error': error_msg})
            raise Exception(f'Stripe refund failed: {error_msg}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Retrieve refund from Stripe and sync status"""
        try:
            stripe_refund_id = refund_request.gateway_refund_id
            response = requests.get(
                f'{self.api_base}/refunds/{stripe_refund_id}',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            stripe_status = data.get('status', '')
            status_map = {
                'succeeded': 'completed',
                'pending':   'processing',
                'failed':    'failed',
                'canceled':  'cancelled',
                'requires_action': 'processing',
            }
            internal_status = status_map.get(stripe_status, refund_request.status)
            self.update_refund_status(refund_request, internal_status, raw_response=data)

            return {
                'status':         internal_status,
                'gateway_status': stripe_status,
                'raw_response':   data,
            }
        except Exception as e:
            return {'status': refund_request.status, 'gateway_status': 'unknown', 'error': str(e)}

    # ── cancel_refund ─────────────────────────────────────────────────────────

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """
        Cancel a Stripe refund.
        Only possible while refund status is 'pending' (rare — only for certain payment methods).
        """
        stripe_refund_id = refund_request.gateway_refund_id
        if not stripe_refund_id:
            raise Exception('No Stripe refund ID to cancel.')

        try:
            response = requests.post(
                f'{self.api_base}/refunds/{stripe_refund_id}/cancel',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'canceled':
                self.update_refund_status(refund_request, 'cancelled', raw_response=data)
                return True

            return False

        except requests.exceptions.HTTPError as e:
            error_msg = ''
            try:
                error_msg = e.response.json().get('error', {}).get('message', str(e))
            except Exception:
                error_msg = str(e)
            raise Exception(f'Stripe refund cancellation failed: {error_msg}')
