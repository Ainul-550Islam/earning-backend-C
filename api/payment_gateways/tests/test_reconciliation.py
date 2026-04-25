# tests/test_reconciliation.py
import pytest
from decimal import Decimal
from unittest.mock import patch


@pytest.mark.django_db
class TestReconciliationService:
    def test_reconcile_all_match(self, test_user):
        from api.payment_gateways.models.core import PaymentGateway, GatewayTransaction
        from api.payment_gateways.models.reconciliation import GatewayStatement, ReconciliationBatch
        from api.payment_gateways.services.ReconciliationService import ReconciliationService
        from datetime import date, timedelta
        import time

        gw    = PaymentGateway.objects.filter(name='bkash').first()
        if not gw:
            pytest.skip('bkash gateway not in DB')

        today = date.today() - timedelta(days=1)
        ref   = f'RECON_TEST_{int(time.time()*1000)}'

        txn = GatewayTransaction.objects.create(
            user=test_user, gateway='bkash', transaction_type='deposit',
            amount=Decimal('500'), fee=Decimal('7.5'), net_amount=Decimal('492.5'),
            status='completed', reference_id=ref, gateway_reference='GW_001',
        )

        statement = GatewayStatement.objects.create(
            gateway=gw, period_start=today, period_end=today,
            raw_data=[{'txn_id': 'GW_001', 'amount': '500', 'status': 'completed'}],
            total_amount=Decimal('500'),
        )

        svc    = ReconciliationService()
        result = svc.reconcile('bkash', today)

        assert result['mismatched'] == 0
        assert result['matched'] >= 1

    def test_reconcile_detects_amount_mismatch(self, test_user):
        from api.payment_gateways.models.core import PaymentGateway, GatewayTransaction
        from api.payment_gateways.models.reconciliation import GatewayStatement
        from api.payment_gateways.services.ReconciliationService import ReconciliationService
        from datetime import date, timedelta
        import time

        gw    = PaymentGateway.objects.filter(name='bkash').first()
        if not gw:
            pytest.skip('bkash gateway not in DB')

        today = date.today() - timedelta(days=2)
        ref   = f'RECON_MISMATCH_{int(time.time()*1000)}'

        GatewayTransaction.objects.create(
            user=test_user, gateway='bkash', transaction_type='deposit',
            amount=Decimal('500'), fee=Decimal('7.5'), net_amount=Decimal('492.5'),
            status='completed', reference_id=ref, gateway_reference='GW_MISMATCH',
        )

        GatewayStatement.objects.create(
            gateway=gw, period_start=today, period_end=today,
            raw_data=[{'txn_id': 'GW_MISMATCH', 'amount': '450', 'status': 'completed'}],
            total_amount=Decimal('450'),
        )

        svc    = ReconciliationService()
        result = svc.reconcile('bkash', today)
        assert result['mismatched'] >= 1
