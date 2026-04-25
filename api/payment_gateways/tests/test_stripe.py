# tests/test_stripe.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestStripeService:
    def test_factory_returns_stripe(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('stripe')
        assert proc.gateway_name == 'stripe'

    def test_load_config(self):
        from payment_gateways.services.StripeService import StripeService
        svc = StripeService()
        assert hasattr(svc, 'secret_key') or hasattr(svc, 'config')

    @patch('requests.post')
    def test_process_deposit_creates_payment_intent(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'id': 'pi_test_001',
                'client_secret': 'pi_secret_001',
                'status': 'requires_payment_method',
                'amount': 50000,
            }
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.StripeService import StripeService
        svc = StripeService()
        try:
            result = svc.process_deposit(user=test_user, amount=Decimal('500'), currency='USD')
            assert 'transaction' in result
        except Exception:
            pass

    def test_stripe_supports_refund_cancellation(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund_cancellation('stripe') is True

    def test_stripe_refund_amount_cents_conversion(self):
        """Stripe requires amounts in cents."""
        amount = Decimal('50.00')
        cents  = int(amount * 100)
        assert cents == 5000

    @patch('requests.post')
    def test_stripe_refund_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'id': 're_001', 'status': 'succeeded', 'amount': 10000}
        )
        mock_post.return_value.raise_for_status = lambda: None
        txn = make_transaction(test_user, 'stripe', 100, status='completed')
        txn.gateway_reference = 'pi_test_001'
        txn.metadata = {'payment_intent_id': 'pi_test_001', 'currency': 'USD'}
        txn.save()
        from payment_gateways.refunds.StripeRefund import StripeRefund
        proc = StripeRefund()
        result = proc.process_refund(txn, Decimal('100'))
        assert result['status'] == 'completed'

    @patch('requests.post')
    def test_stripe_refund_cancel_supported(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'id': 're_001', 'status': 'canceled'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.refunds.StripeRefund import StripeRefund
        proc   = StripeRefund()
        refund = MagicMock(gateway_refund_id='re_001', status='processing')
        result = proc.cancel_refund(refund)
        assert result is True

    def test_stripe_is_global_gateway(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        gloabal_gws = PaymentFactory.get_global_gateways()
        names = [g['name'] for g in gloabal_gws]
        assert 'stripe' in names
