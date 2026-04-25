# tests/test_sslcommerz.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestSSLCommerzService:
    def test_factory_returns_sslcommerz(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('sslcommerz')
        assert proc.gateway_name == 'sslcommerz'

    def test_ssl_alias_works(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('ssl')
        assert proc.gateway_name == 'sslcommerz'

    def test_load_config(self):
        from payment_gateways.services.SSLCommerzService import SSLCommerzService
        svc = SSLCommerzService()
        assert 'store_id' in svc.config
        assert 'store_passwd' in svc.config

    @patch('requests.post')
    def test_process_deposit_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'status': 'SUCCESS', 'sessionkey': 'sess_001', 'GatewayPageURL': 'https://pay.sslcommerz.com/pay'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.SSLCommerzService import SSLCommerzService
        svc = SSLCommerzService()
        result = svc.process_deposit(user=test_user, amount=Decimal('1000'))
        assert result['payment_url'] == 'https://pay.sslcommerz.com/pay'
        assert result['session_key'] == 'sess_001'

    @patch('requests.post')
    def test_process_deposit_failure(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'status': 'FAILED', 'failedreason': 'Invalid credentials'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.SSLCommerzService import SSLCommerzService
        svc = SSLCommerzService()
        with pytest.raises(Exception, match='SSLCommerz'):
            svc.process_deposit(user=test_user, amount=Decimal('1000'))

    def test_sslcommerz_refund_supported(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund('sslcommerz') is True

    def test_refundable_amount_full(self, test_user):
        txn = make_transaction(test_user, 'sslcommerz', 500, status='completed')
        from payment_gateways.refunds.SSLCommerzRefund import SSLCommerzRefund
        proc = SSLCommerzRefund()
        amt = proc.get_refundable_amount(txn)
        assert amt == txn.net_amount
