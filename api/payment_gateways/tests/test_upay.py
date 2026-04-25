# tests/test_upay.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestUpayService:
    def test_factory_returns_upay(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('upay')
        assert proc.gateway_name == 'upay'

    def test_ucbupay_alias(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('ucbupay')
        assert proc.gateway_name == 'upay'

    def test_load_config(self):
        from payment_gateways.services.UpayService import UpayService
        svc = UpayService()
        assert 'merchant_id' in svc.config
        assert 'merchant_key' in svc.config

    @patch('requests.post')
    def test_get_token_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'merchant_token': 'upay_token_abc'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.UpayService import UpayService
        svc = UpayService()
        token = svc._get_auth_token()
        assert token == 'upay_token_abc'

    @patch('requests.post')
    def test_process_deposit_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'merchant_token': 'tok', 'status': 'SUCCESS', 'redirectGatewayURL': 'https://upay.com/pay', 'transaction_id': 'UP_001'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.UpayService import UpayService
        svc = UpayService()
        result = svc.process_deposit(user=test_user, amount=Decimal('400'))
        assert 'transaction' in result

    def test_upay_refund_supported(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund('upay') is True
        assert RefundFactory.supports_partial_refund('upay') is True

    def test_upay_no_cancel_support(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund_cancellation('upay') is False
