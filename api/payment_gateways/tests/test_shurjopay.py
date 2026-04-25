# tests/test_shurjopay.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestShurjoPayService:
    def test_factory_returns_shurjopay(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('shurjopay')
        assert proc.gateway_name == 'shurjopay'

    def test_shurjo_alias(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('shurjo')
        assert proc.gateway_name == 'shurjopay'

    @patch('requests.post')
    def test_get_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'token': 'sp_token', 'token_type': 'Bearer', 'store_id': 'store_01', 'execute_url': 'https://engine.shurjo.com/pay'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.ShurjoPayService import ShurjoPayService
        svc = ShurjoPayService()
        token_data = svc._get_token()
        assert token_data['token'] == 'sp_token'

    @patch('requests.post')
    def test_process_deposit_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'token': 'sp_token', 'token_type': 'Bearer', 'store_id': 'store_01',
                'checkout_url': 'https://engine.shurjo.com/checkout', 'sp_order_id': 'SP_001'
            }
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.ShurjoPayService import ShurjoPayService
        svc = ShurjoPayService()
        result = svc.process_deposit(user=test_user, amount=Decimal('600'))
        assert result['payment_url'] == 'https://engine.shurjo.com/checkout'

    def test_shurjopay_refund_processor(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        proc = RefundFactory.get_processor('shurjopay')
        assert proc.gateway_name == 'shurjopay'

    @patch('requests.post')
    def test_shurjopay_refund_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: [{'sp_code': '1000', 'refund_id': 'RF_SP_001', 'sp_massage': 'Success'}]
        )
        mock_post.return_value.raise_for_status = lambda: None
        txn = make_transaction(test_user, 'shurjopay', 600, status='completed')
        txn.gateway_reference = 'SP_001'
        txn.metadata = {'shurjopay_data': {'sp_order_id': 'SP_001'}}
        txn.save()
        from payment_gateways.refunds.ShurjoPayRefund import ShurjoPayRefund
        proc = ShurjoPayRefund()
        with patch.object(proc, '_get_token', return_value={'token': 'tok', 'token_type': 'Bearer'}):
            result = proc.process_refund(txn, Decimal('100'))
        assert result['status'] == 'completed'

    def test_shurjopay_no_cancel(self):
        from payment_gateways.refunds.ShurjoPayRefund import ShurjoPayRefund
        from payment_gateways.refunds.models import RefundRequest
        proc = ShurjoPayRefund()
        with pytest.raises(NotImplementedError):
            proc.cancel_refund(MagicMock())
