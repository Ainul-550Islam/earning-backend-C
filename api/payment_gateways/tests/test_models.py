# FILE 128 of 257 — tests/test_models.py
import pytest
from decimal import Decimal
from .factories import make_transaction, make_refund_request

@pytest.mark.django_db
class TestGatewayTransaction:
    def test_str(self, test_user):
        txn = make_transaction(test_user, 'bkash', 500)
        assert 'testuser' in str(txn)

    def test_deposit_creates_correctly(self, test_user):
        txn = make_transaction(test_user, 'stripe', 1000)
        assert txn.gateway == 'stripe'
        assert txn.amount == Decimal('1000')
        assert txn.net_amount == Decimal('992.5')

@pytest.mark.django_db
class TestRefundRequest:
    def test_is_partial(self, completed_transaction):
        ref = make_refund_request(completed_transaction, amount=Decimal('100'))
        assert ref.is_partial is True

    def test_full_refund_not_partial(self, completed_transaction):
        ref = make_refund_request(completed_transaction, amount=completed_transaction.net_amount)
        assert ref.is_partial is False

@pytest.mark.django_db
class TestPaymentGateway:
    def test_is_available(self, db):
        from payment_gateways.models import PaymentGateway
        from decimal import Decimal
        gw = PaymentGateway.objects.create(
            name='bkash', display_name='bKash', status='active',
            minimum_amount=Decimal('10'), maximum_amount=Decimal('50000'),
            transaction_fee_percentage=Decimal('1.5'),
        )
        assert gw.is_available is True
        gw.status = 'inactive'
        assert gw.is_available is False
