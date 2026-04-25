# tests/test_amarpay.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestAmarPayService:
    def test_factory_returns_amarpay(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('amarpay')
        assert proc.gateway_name == 'amarpay'

    def test_aamarpay_alias(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('aamarpay')
        assert proc.gateway_name == 'amarpay'

    def test_load_config(self):
        from payment_gateways.services.AmarPayService import AmarPayService
        svc = AmarPayService()
        assert 'store_id' in svc.config
        assert 'signature_key' in svc.config

    @patch('requests.post')
    def test_process_deposit_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'payment_url': 'https://secure.aamarpay.com/pay'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.AmarPayService import AmarPayService
        svc = AmarPayService()
        result = svc.process_deposit(user=test_user, amount=Decimal('750'))
        assert result['payment_url'] == 'https://secure.aamarpay.com/pay'

    @patch('requests.post')
    def test_process_deposit_no_url_raises(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'error': 'Invalid credentials'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.AmarPayService import AmarPayService
        svc = AmarPayService()
        with pytest.raises(Exception):
            svc.process_deposit(user=test_user, amount=Decimal('750'))

    def test_amarpay_refund_processor(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        proc = RefundFactory.get_processor('amarpay')
        assert proc.gateway_name == 'amarpay'

    @patch('requests.post')
    def test_amarpay_refund_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'status': 'successful', 'refund_id': 'REF_001'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        txn = make_transaction(test_user, 'amarpay', 500, status='completed')
        from payment_gateways.refunds.AmarPayRefund import AmarPayRefund
        proc = AmarPayRefund()
        result = proc.process_refund(txn, Decimal('100'))
        assert result['status'] == 'completed'
