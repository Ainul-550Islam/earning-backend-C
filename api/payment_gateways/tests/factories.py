# FILE 127 of 257 — tests/factories.py
from decimal import Decimal
from django.utils import timezone

def make_transaction(user, gateway='bkash', amount=500, status='completed', txn_type='deposit'):
    from payment_gateways.models import GatewayTransaction
    import uuid
    return GatewayTransaction.objects.create(
        user=user, gateway=gateway, transaction_type=txn_type,
        amount=Decimal(str(amount)), fee=Decimal('7.5'),
        net_amount=Decimal(str(amount)) - Decimal('7.5'),
        status=status, reference_id=f'{gateway.upper()}_{uuid.uuid4().hex[:8].upper()}',
        metadata={}
    )

def make_refund_request(transaction, amount=None, status='pending'):
    from payment_gateways.refunds.models import RefundRequest
    import uuid
    return RefundRequest.objects.create(
        gateway=transaction.gateway,
        original_transaction=transaction,
        user=transaction.user,
        amount=amount or transaction.net_amount,
        reason='customer_request',
        status=status,
        reference_id=f'REF_{uuid.uuid4().hex[:8].upper()}',
    )

def make_payout(user, amount=500, gateway='bkash', status='pending'):
    from payment_gateways.models import PayoutRequest
    import uuid
    return PayoutRequest.objects.create(
        user=user, amount=Decimal(str(amount)), fee=Decimal('0'),
        net_amount=Decimal(str(amount)), payout_method=gateway,
        account_number='01700000000', account_name='Test User',
        status=status, reference_id=f'PAY_{uuid.uuid4().hex[:8].upper()}'
    )
