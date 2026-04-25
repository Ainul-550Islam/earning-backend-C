# api/payment_gateways/services/PayoneerService.py
# Payoneer payment processor via Payoneer API v2

import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_txn
from .PaymentProcessor import PaymentProcessor
import logging

logger = logging.getLogger(__name__)


class PayoneerService(PaymentProcessor):
    """
    Payoneer payment processor.

    Payoneer is used primarily for:
        - Publisher/affiliate payouts (global)
        - Mass payouts to freelancers
        - Receiving international payments

    API: Payoneer v2 (OAuth2)
    Docs: https://developer.payoneer.com

    Supported:
        - Account-to-account transfers
        - Mass payout (batch)
        - Payment status check
    """

    SANDBOX_URL = 'https://api.sandbox.payoneer.com/v2'
    LIVE_URL    = 'https://api.payoneer.com/v2'

    def __init__(self):
        super().__init__('payoneer')
        is_sandbox    = getattr(settings, 'PAYONEER_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.LIVE_URL
        self.config   = {
            'client_id':     getattr(settings, 'PAYONEER_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'PAYONEER_CLIENT_SECRET', ''),
            'partner_id':    getattr(settings, 'PAYONEER_PARTNER_ID', ''),
            'username':      getattr(settings, 'PAYONEER_USERNAME', ''),
            'password':      getattr(settings, 'PAYONEER_PASSWORD', ''),
        }
        self._token_cache = None

    def _get_access_token(self) -> str:
        if self._token_cache:
            return self._token_cache

        response = requests.post(
            f'{self.base_url}/oauth2/token',
            data={
                'grant_type':    'password',
                'username':      self.config['username'],
                'password':      self.config['password'],
                'client_id':     self.config['client_id'],
                'client_secret': self.config['client_secret'],
                'scope':         'read write',
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get('access_token')
        if not token:
            raise Exception('Payoneer: Failed to get access token')
        self._token_cache = token
        return token

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type':  'application/json',
        }

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """
        Payoneer deposit — receive payment from user's Payoneer account.
        Creates a payment request that user approves.
        """
        self.validate_amount(amount)

        txn = self.create_transaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )

        try:
            # Create payment request
            payee_id = getattr(payment_method, 'account_number', '') if payment_method else ''

            payload = {
                'client_reference_id': txn.reference_id,
                'payee_id':            payee_id,
                'amount':              float(amount),
                'currency':            kwargs.get('currency', 'USD'),
                'description':         f'Deposit from user {user.id}',
                'expiration_date':     '2030-12-31',
            }

            response = requests.post(
                f'{self.base_url}/programs/{self.config["partner_id"]}/charges',
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            charge_data = response.json()

            charge_id = charge_data.get('charge_id', '') or charge_data.get('id', '')

            txn.gateway_reference       = charge_id
            txn.metadata['charge_data'] = charge_data
            txn.status                  = 'processing'
            txn.save()

            return {
                'transaction': txn,
                'payment_url': charge_data.get('approval_url', ''),
                'charge_id':   charge_id,
                'message':     'Payoneer payment request created. Please approve it in your Payoneer account.',
            }

        except Exception as e:
            txn.status          = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f'Payoneer deposit failed: {str(e)}')

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """
        Payoneer payout to publisher's Payoneer account.
        Used for affiliate/publisher mass payouts.
        """
        self.validate_amount(amount)

        from api.payment_gateways.models import PayoutRequest

        payee_id = getattr(payment_method, 'account_number', '') if payment_method else ''

        try:
            # Create single payout
            payload = {
                'client_reference_id': self.generate_reference_id(),
                'payee_id':            payee_id,
                'amount':              float(amount),
                'currency':            kwargs.get('currency', 'USD'),
                'description':         f'Publisher payout for user {user.id}',
            }

            response = requests.post(
                f'{self.base_url}/programs/{self.config["partner_id"]}/payouts',
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            payout_data = response.json()

            payout_id    = payout_data.get('payout_id', '') or payout_data.get('id', '')
            payout_status = payout_data.get('status', 'PENDING')

            with db_txn.atomic():
                payout = PayoutRequest.objects.create(
                    user           = user,
                    amount         = amount,
                    fee            = self.calculate_fee(amount),
                    net_amount     = amount - self.calculate_fee(amount),
                    payout_method  = 'payoneer',
                    account_number = payee_id,
                    account_name   = getattr(payment_method, 'account_name', 'Payoneer Account'),
                    status         = 'processing' if payout_status == 'PROCESSING' else 'pending',
                    reference_id   = payload['client_reference_id'],
                )

                txn = self.create_transaction(
                    user=user,
                    transaction_type='withdrawal',
                    amount=amount,
                    payment_method=payment_method,
                    metadata={
                        'payout_id':    payout.id,
                        'payoneer_id':  payout_id,
                        'payout_data':  payout_data,
                    }
                )

            return {
                'transaction':  txn,
                'payout':       payout,
                'payoneer_id':  payout_id,
                'status':       payout_status,
                'message':      'Payoneer payout initiated. Funds arrive in 1-2 business days.',
            }

        except Exception as e:
            raise Exception(f'Payoneer withdrawal failed: {str(e)}')

    def mass_payout(self, payouts: list) -> dict:
        """
        Send batch payouts to multiple Payoneer accounts.

        Args:
            payouts: [{'payee_id': str, 'amount': float, 'currency': str, 'description': str}, ...]

        Returns:
            dict: {'batch_id': str, 'results': [...]}
        """
        try:
            payload = {
                'payouts': [
                    {
                        'client_reference_id': self.generate_reference_id(),
                        'payee_id':   p['payee_id'],
                        'amount':     p['amount'],
                        'currency':   p.get('currency', 'USD'),
                        'description': p.get('description', 'Publisher payout'),
                    }
                    for p in payouts
                ]
            }

            response = requests.post(
                f'{self.base_url}/programs/{self.config["partner_id"]}/payouts/batch',
                json=payload,
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f'Payoneer mass payout: {len(payouts)} recipients, batch={result.get("batch_id")}')
            return result

        except Exception as e:
            raise Exception(f'Payoneer mass payout failed: {str(e)}')

    def verify_payment(self, charge_id: str, **kwargs):
        """Check Payoneer charge/payout status."""
        try:
            response = requests.get(
                f'{self.base_url}/programs/{self.config["partner_id"]}/charges/{charge_id}',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            status_map = {
                'COMPLETED': 'completed',
                'PROCESSING': 'processing',
                'PENDING':   'processing',
                'FAILED':    'failed',
                'CANCELED':  'cancelled',
            }

            from api.payment_gateways.models import GatewayTransaction
            try:
                txn           = GatewayTransaction.objects.get(gateway_reference=charge_id)
                api_status    = data.get('status', '').upper()
                txn.status    = status_map.get(api_status, 'processing')
                if txn.status == 'completed':
                    txn.completed_at = timezone.now()
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                txn.metadata['payoneer_status'] = data
                txn.save()
                return txn
            except GatewayTransaction.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f'Payoneer verification failed: {str(e)}')

    def get_payment_url(self, transaction, **kwargs):
        return transaction.metadata.get('charge_data', {}).get('approval_url')
