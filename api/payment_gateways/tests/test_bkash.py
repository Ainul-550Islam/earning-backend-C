# tests/test_bkash.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction

@pytest.mark.django_db
class TestBkashService:
    def test_factory_returns_bkash_processor(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('bkash')
        assert proc.gateway_name == 'bkash'

    def test_bkash_alias_bKash(self):
        from payment_gateways.services.PaymentFactory import PaymentFactory
        proc = PaymentFactory.get_processor('bKash')
        assert proc.gateway_name == 'bkash'

    def test_load_config(self):
        from payment_gateways.services.BkashService import BkashService
        svc = BkashService()
        assert hasattr(svc, 'config')
        assert 'app_key' in svc.config

    @patch('requests.post')
    def test_process_deposit_success(self, mock_post, test_user):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'id_token': 'mock_token',
                'paymentID': 'PAY_BKASH_001',
                'bkashURL': 'https://sandbox.bka.sh/pay',
                'statusCode': '0000',
            }
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.BkashService import BkashService
        svc = BkashService()
        with patch.object(svc, 'get_access_token', return_value='mock_token'):
            result = svc.process_deposit(user=test_user, amount=Decimal('500'))
        assert result['payment_id'] == 'PAY_BKASH_001'

    @patch('requests.post')
    def test_process_deposit_creates_transaction(self, mock_post, test_user):
        from payment_gateways.models import GatewayTransaction
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'id_token': 'tok', 'paymentID': 'PAY_002', 'bkashURL': 'https://pay', 'statusCode': '0000'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.services.BkashService import BkashService
        svc = BkashService()
        with patch.object(svc, 'get_access_token', return_value='tok'):
            result = svc.process_deposit(user=test_user, amount=Decimal('200'))
        txn = GatewayTransaction.objects.get(reference_id=result['transaction'].reference_id)
        assert txn.gateway == 'bkash'
        assert txn.transaction_type == 'deposit'

    def test_refund_factory_supports_bkash(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund('bkash') is True

    def test_bkash_refund_processor_instance(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        proc = RefundFactory.get_processor('bkash')
        assert proc.gateway_name == 'bkash'

    def test_bkash_supports_partial_refund(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_partial_refund('bkash') is True

    def test_bkash_no_refund_cancellation(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        assert RefundFactory.supports_refund_cancellation('bkash') is False

    @patch('requests.post')
    def test_bkash_refund_success(self, mock_post, completed_transaction):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'refundTrxID': 'REFUND_001', 'statusCode': '0000', 'statusMessage': 'Successful'}
        )
        mock_post.return_value.raise_for_status = lambda: None
        from payment_gateways.refunds.BkashRefund import BkashRefund
        proc = BkashRefund()
        completed_transaction.gateway_reference = 'PAY_BKASH_001'
        completed_transaction.save()
        with patch.object(proc, '_get_token', return_value='tok'):
            result = proc.process_refund(completed_transaction, Decimal('100'))
        assert result['status'] == 'completed'
        assert result['gateway_refund_id'] == 'REFUND_001'
