# api/payment_gateways/refunds/RefundProcessor.py
# FILE 49 of 257 — Abstract base class for all refund processors

from abc import ABC, abstractmethod
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_txn


class RefundProcessor(ABC):
    """
    Abstract base class for all gateway-specific refund processors.

    Every gateway (bKash, Nagad, Stripe, etc.) must inherit from this class
    and implement all abstract methods.

    Usage:
        class BkashRefund(RefundProcessor):
            def process_refund(self, transaction, amount, reason=''):
                ...
    """

    REFUND_REASONS = (
        ('duplicate',          'Duplicate payment'),
        ('fraudulent',         'Fraudulent transaction'),
        ('customer_request',   'Customer requested refund'),
        ('order_cancelled',    'Order cancelled'),
        ('service_not_provided', 'Service not provided'),
        ('partial_refund',     'Partial refund'),
        ('other',              'Other'),
    )

    def __init__(self, gateway_name: str):
        self.gateway_name = gateway_name

    # ── Abstract methods every gateway MUST implement ─────────────────────────

    @abstractmethod
    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate a refund for a completed transaction.

        Args:
            transaction (GatewayTransaction): The original completed transaction
            amount (Decimal): Amount to refund (can be partial)
            reason (str): Refund reason code from REFUND_REASONS
            **kwargs: Gateway-specific extra parameters

        Returns:
            dict: {
                'refund_request': RefundRequest instance,
                'gateway_refund_id': str,
                'message': str,
                'status': 'pending' | 'completed' | 'failed'
            }

        Raises:
            ValueError: If amount > original transaction net_amount
            Exception: If gateway API call fails
        """
        pass

    @abstractmethod
    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """
        Check current status of a refund with the gateway.

        Args:
            refund_request (RefundRequest): The refund request to check

        Returns:
            dict: { 'status': str, 'gateway_status': str, 'raw_response': dict }
        """
        pass

    @abstractmethod
    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """
        Cancel a pending refund (if gateway supports it).

        Returns:
            bool: True if cancelled successfully
        """
        pass

    # ── Shared utility methods ────────────────────────────────────────────────

    def validate_refund_amount(self, transaction, amount: Decimal):
        """Validate refund amount is within allowed bounds"""
        amount = Decimal(str(amount))

        if amount <= 0:
            raise ValueError('Refund amount must be greater than zero.')

        # Get total already refunded for this transaction
        from .models import RefundRequest
        from django.db.models import Sum
        already_refunded = RefundRequest.objects.filter(
            original_transaction=transaction,
            status__in=('pending', 'processing', 'completed'),
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        max_refundable = transaction.net_amount - already_refunded

        if amount > max_refundable:
            raise ValueError(
                f'Refund amount ({amount}) exceeds refundable balance ({max_refundable}). '
                f'Already refunded: {already_refunded}'
            )

        return True

    def create_refund_request(self, transaction, amount: Decimal, reason: str, initiated_by=None, **kwargs):
        """Create a RefundRequest record in the database"""
        from .models import RefundRequest

        self.validate_refund_amount(transaction, amount)

        refund = RefundRequest.objects.create(
            gateway=self.gateway_name,
            original_transaction=transaction,
            user=transaction.user,
            amount=amount,
            reason=reason,
            status='pending',
            reference_id=self._generate_refund_reference(),
            initiated_by=initiated_by,
            metadata={
                'gateway': self.gateway_name,
                'original_reference': transaction.reference_id,
                **kwargs.get('metadata', {}),
            }
        )
        return refund

    def update_refund_status(self, refund_request, status: str, gateway_refund_id: str = None, raw_response: dict = None):
        """Update refund request status and optionally reverse user balance"""
        from .models import RefundRequest

        refund_request.status = status

        if gateway_refund_id:
            refund_request.gateway_refund_id = gateway_refund_id

        if raw_response:
            refund_request.metadata['gateway_response'] = raw_response

        if status == 'completed':
            refund_request.completed_at = timezone.now()
            # Deduct refund amount from user balance (reverse the deposit)
            user = refund_request.user
            if hasattr(user, 'balance') and refund_request.original_transaction.transaction_type == 'deposit':
                with db_txn.atomic():
                    user.balance -= refund_request.amount
                    user.save(update_fields=['balance'])

        if status == 'failed':
            refund_request.failed_at = timezone.now()

        refund_request.save()
        return refund_request

    def _generate_refund_reference(self) -> str:
        """Generate a unique refund reference ID"""
        ts = int(timezone.now().timestamp() * 1000)
        return f'REF_{self.gateway_name.upper()}_{ts}'

    def is_refundable(self, transaction) -> tuple:
        """
        Check if a transaction is eligible for refund.

        Returns:
            (bool, str): (is_refundable, reason_if_not)
        """
        if transaction.transaction_type != 'deposit':
            return False, 'Only deposit transactions can be refunded.'

        if transaction.status != 'completed':
            return False, f'Transaction status is "{transaction.status}". Only completed transactions can be refunded.'

        if transaction.gateway != self.gateway_name:
            return False, f'Gateway mismatch. Expected "{self.gateway_name}", got "{transaction.gateway}".'

        # Check if already fully refunded
        from .models import RefundRequest
        from django.db.models import Sum
        total_refunded = RefundRequest.objects.filter(
            original_transaction=transaction,
            status__in=('pending', 'processing', 'completed'),
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        if total_refunded >= transaction.net_amount:
            return False, 'Transaction has already been fully refunded.'

        return True, ''

    def get_refundable_amount(self, transaction) -> Decimal:
        """Return the remaining refundable amount for a transaction"""
        from .models import RefundRequest
        from django.db.models import Sum

        already_refunded = RefundRequest.objects.filter(
            original_transaction=transaction,
            status__in=('pending', 'processing', 'completed'),
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return max(Decimal('0'), transaction.net_amount - already_refunded)
