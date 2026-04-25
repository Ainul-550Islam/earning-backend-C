# api/payment_gateways/services/WireTransferService.py
# Wire Transfer & ACH payment processor

from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_txn
from .PaymentProcessor import PaymentProcessor
import logging
import uuid

logger = logging.getLogger(__name__)


class WireTransferService(PaymentProcessor):
    """
    Wire Transfer / Bank Transfer payment processor.
    Wire transfers are manual — admin processes them after verifying bank receipt.

    Supports:
        - Domestic wire (BD banks)
        - International SWIFT wire
        - Deposit (user sends to company account)
        - Withdrawal (company sends to user bank)
    """

    BANK_DETAILS = {
        'bank_name':       getattr(settings, 'WIRE_BANK_NAME', 'Dutch-Bangla Bank Limited'),
        'account_name':    getattr(settings, 'WIRE_ACCOUNT_NAME', 'Company Name Ltd'),
        'account_number':  getattr(settings, 'WIRE_ACCOUNT_NUMBER', '1234567890'),
        'routing_number':  getattr(settings, 'WIRE_ROUTING_NUMBER', ''),
        'swift_code':      getattr(settings, 'WIRE_SWIFT_CODE', 'DBBLBDDH'),
        'branch':          getattr(settings, 'WIRE_BRANCH', 'Gulshan Branch, Dhaka'),
        'currency':        getattr(settings, 'WIRE_CURRENCY', 'BDT'),
    }

    def __init__(self):
        super().__init__('wire')

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """
        Create a pending wire deposit instruction.
        User must manually send money to company bank account.
        Admin confirms receipt and marks as completed.
        """
        self.validate_amount(amount)

        txn = self.create_transaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata={
                'bank_details':     self.BANK_DETAILS,
                'user_reference':   f'DEP-{user.id}-{uuid.uuid4().hex[:6].upper()}',
                'notes':            kwargs.get('notes', ''),
                'requires_manual_confirmation': True,
            }
        )

        instructions = self._get_wire_instructions(amount, txn.reference_id)

        logger.info(f'Wire deposit initiated: {txn.reference_id} user={user.id} amount={amount}')

        return {
            'transaction':    txn,
            'payment_url':    None,
            'instructions':   instructions,
            'message':        'Please send the amount to our bank account using the instructions below.',
            'reference_id':   txn.reference_id,
        }

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """
        Create a payout request via wire transfer.
        Requires user's bank account details.
        Admin processes and marks complete after sending.
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
                payout_method  = 'wire',
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
                metadata={
                    'payout_id':        payout.id,
                    'bank_name':        kwargs.get('bank_name', ''),
                    'bank_branch':      kwargs.get('bank_branch', ''),
                    'routing_number':   kwargs.get('routing_number', ''),
                    'swift_code':       kwargs.get('swift_code', ''),
                }
            )

        return {
            'transaction': txn,
            'payout':      payout,
            'message':     'Wire withdrawal request submitted. Processing takes 1-3 business days.',
        }

    def verify_payment(self, payment_id, **kwargs):
        """Wire payments are verified manually by admin."""
        from api.payment_gateways.models import GatewayTransaction
        try:
            txn = GatewayTransaction.objects.get(reference_id=payment_id)
            return txn
        except GatewayTransaction.DoesNotExist:
            return None

    def get_payment_url(self, transaction, **kwargs):
        """No redirect URL for wire transfers."""
        return None

    def confirm_receipt(self, reference_id: str, confirmed_by=None, bank_reference: str = '') -> dict:
        """
        Admin confirms wire receipt and marks transaction as completed.
        Call this after verifying the bank deposit.
        """
        from api.payment_gateways.models import GatewayTransaction

        try:
            txn = GatewayTransaction.objects.get(reference_id=reference_id, gateway='wire')
        except GatewayTransaction.DoesNotExist:
            raise Exception(f'Wire transaction not found: {reference_id}')

        if txn.status == 'completed':
            raise Exception('Transaction already completed.')

        with db_txn.atomic():
            txn.status            = 'completed'
            txn.completed_at      = timezone.now()
            txn.gateway_reference = bank_reference
            txn.metadata['confirmed_by']       = str(confirmed_by) if confirmed_by else 'admin'
            txn.metadata['bank_reference']     = bank_reference
            txn.metadata['confirmed_at']       = timezone.now().isoformat()
            txn.save()

            # Credit user balance
            user = txn.user
            if hasattr(user, 'balance'):
                user.balance += txn.net_amount
                user.save(update_fields=['balance'])

        logger.info(f'Wire deposit confirmed: {reference_id} by {confirmed_by}')
        return {'transaction': txn, 'message': f'Wire deposit confirmed. {txn.net_amount} credited.'}

    def _get_wire_instructions(self, amount: Decimal, reference_id: str) -> dict:
        return {
            'bank_name':      self.BANK_DETAILS['bank_name'],
            'account_name':   self.BANK_DETAILS['account_name'],
            'account_number': self.BANK_DETAILS['account_number'],
            'swift_code':     self.BANK_DETAILS['swift_code'],
            'branch':         self.BANK_DETAILS['branch'],
            'amount':         str(amount),
            'currency':       self.BANK_DETAILS['currency'],
            'reference':      reference_id,
            'important':      f'You MUST include reference "{reference_id}" in your wire transfer description.',
        }
