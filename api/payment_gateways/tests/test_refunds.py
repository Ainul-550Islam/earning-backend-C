# FILE 139 of 257 — tests/test_refunds.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from .factories import make_transaction, make_refund_request

@pytest.mark.django_db
class TestRefundProcessor:
    def test_validate_amount_ok(self, completed_transaction):
        from payment_gateways.refunds.BkashRefund import BkashRefund
        proc = BkashRefund()
        assert proc.validate_refund_amount(completed_transaction, Decimal('100')) is True

    def test_validate_amount_exceeds_raises(self, completed_transaction):
        from payment_gateways.refunds.BkashRefund import BkashRefund
        proc = BkashRefund()
        with pytest.raises(ValueError):
            proc.validate_refund_amount(completed_transaction, Decimal('99999'))

    def test_is_refundable_completed(self, completed_transaction):
        from payment_gateways.refunds.BkashRefund import BkashRefund
        proc = BkashRefund()
        ok, reason = proc.is_refundable(completed_transaction)
        assert ok is True

    def test_is_refundable_non_deposit_fails(self, test_user):
        from payment_gateways.refunds.BkashRefund import BkashRefund
        txn = make_transaction(test_user, 'bkash', 500, status='completed', txn_type='withdrawal')
        proc = BkashRefund()
        ok, reason = proc.is_refundable(txn)
        assert ok is False

    def test_refund_factory_get_all_gateways(self):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        gws = RefundFactory.get_all_supported_gateways()
        assert len(gws) == 8
        assert 'bkash' in gws
        assert 'stripe' in gws

    def test_refund_factory_get_processor_for_transaction(self, completed_transaction):
        from payment_gateways.refunds.RefundFactory import RefundFactory
        proc = RefundFactory.get_processor_for_transaction(completed_transaction)
        assert proc.gateway_name == 'bkash'
