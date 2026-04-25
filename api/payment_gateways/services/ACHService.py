# api/payment_gateways/services/ACHService.py
# ACH (Automated Clearing House) payment processor — US bank transfers

import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_txn
from .PaymentProcessor import PaymentProcessor
import logging

logger = logging.getLogger(__name__)


class ACHService(PaymentProcessor):
    """
    ACH (US bank transfer) processor via Stripe ACH or Dwolla.

    Stripe ACH Debit:
        - US bank accounts only
        - 1-4 business days settlement
        - Micro-deposit verification or Plaid instant
        - 0.8% fee (max $5)

    Used for:
        - US publisher payouts
        - Large USD withdrawals
    """

    def __init__(self):
        super().__init__('ach')
        self.provider   = getattr(settings, 'ACH_PROVIDER', 'stripe')  # stripe | dwolla
        self.secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.api_base   = 'https://api.stripe.com/v1'

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type':  'application/x-www-form-urlencoded',
        }

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """
        Initiate ACH debit from user's bank account.
        Requires pre-verified bank account (Stripe payment method with type=us_bank_account).
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
            # Create payment intent with ACH
            bank_account_id = kwargs.get('bank_account_id') or (
                payment_method.metadata.get('stripe_payment_method_id') if payment_method else None
            )

            if not bank_account_id:
                # No pre-verified account — return setup instructions
                txn.status = 'pending'
                txn.metadata['requires_bank_setup'] = True
                txn.save()
                return {
                    'transaction':     txn,
                    'payment_url':     None,
                    'requires_setup':  True,
                    'message':         'Please link your US bank account first.',
                    'setup_url':       self._get_bank_setup_url(user, txn.reference_id),
                }

            # Amount in cents
            amount_cents = int(amount * 100)

            data = {
                'amount':               amount_cents,
                'currency':             'usd',
                'payment_method':       bank_account_id,
                'payment_method_types[]': 'us_bank_account',
                'confirm':              'true',
                'mandate_data[customer_acceptance][type]': 'online',
                'mandate_data[customer_acceptance][online][ip_address]': kwargs.get('ip', '127.0.0.1'),
                'mandate_data[customer_acceptance][online][user_agent]': kwargs.get('user_agent', ''),
                'metadata[reference_id]': txn.reference_id,
                'metadata[user_id]':      str(user.id),
            }

            response = requests.post(
                f'{self.api_base}/payment_intents',
                data=data,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            pi_data = response.json()

            txn.gateway_reference = pi_data['id']
            txn.metadata['stripe_payment_intent'] = pi_data
            txn.status = 'processing'  # ACH takes 1-4 days
            txn.save()

            return {
                'transaction':  txn,
                'payment_url':  None,
                'pi_id':        pi_data['id'],
                'status':       pi_data['status'],
                'message':      'ACH transfer initiated. Funds arrive in 1-4 business days.',
            }

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f'ACH deposit failed: {str(e)}')

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """
        ACH payout to user's bank account via Stripe Connect or Payouts API.
        """
        self.validate_amount(amount)

        from api.payment_gateways.models import PayoutRequest

        with db_txn.atomic():
            fee        = self.calculate_fee(amount)
            net_amount = amount - fee

            payout = PayoutRequest.objects.create(
                user           = user,
                amount         = amount,
                fee            = fee,
                net_amount     = net_amount,
                payout_method  = 'ach',
                account_number = getattr(payment_method, 'account_number', ''),
                account_name   = getattr(payment_method, 'account_name', ''),
                status         = 'pending',
                reference_id   = self.generate_reference_id(),
            )

            txn = self.create_transaction(
                user=user,
                transaction_type='withdrawal',
                amount=amount,
                payment_method=payment_method,
                metadata={'payout_id': payout.id}
            )

        return {
            'transaction': txn,
            'payout':      payout,
            'message':     'ACH withdrawal submitted. Processing in 1-4 business days.',
        }

    def verify_payment(self, payment_intent_id: str, **kwargs) -> dict:
        """Check ACH payment status via Stripe."""
        try:
            response = requests.get(
                f'{self.api_base}/payment_intents/{payment_intent_id}',
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            pi_data = response.json()

            from api.payment_gateways.models import GatewayTransaction
            try:
                txn        = GatewayTransaction.objects.get(gateway_reference=payment_intent_id)
                pi_status  = pi_data.get('status', '')

                if pi_status == 'succeeded':
                    txn.status       = 'completed'
                    txn.completed_at = timezone.now()
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                elif pi_status in ('processing', 'requires_action'):
                    txn.status = 'processing'
                elif pi_status in ('canceled', 'payment_failed'):
                    txn.status = 'failed'

                txn.metadata['stripe_pi'] = pi_data
                txn.save()
                return txn
            except GatewayTransaction.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f'ACH verification failed: {str(e)}')

    def get_payment_url(self, transaction, **kwargs):
        return None  # ACH has no redirect URL

    def _get_bank_setup_url(self, user, reference_id: str) -> str:
        """Generate Stripe bank account setup URL."""
        return f'/payment/ach/setup/?ref={reference_id}'
