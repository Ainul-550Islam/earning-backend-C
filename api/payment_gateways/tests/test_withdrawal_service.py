# tests/test_withdrawal_service.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestWithdrawalGatewayService:
    def test_execute_payout_success(self, test_user):
        from api.payment_gateways.models.core import PayoutRequest
        from api.payment_gateways.services.WithdrawalGatewayService import WithdrawalGatewayService
        import time

        payout = PayoutRequest.objects.create(
            user=test_user, amount=Decimal('1000'), fee=Decimal('15'),
            net_amount=Decimal('985'), payout_method='bkash',
            account_number='01712345678', status='approved',
            reference_id=f'PAY-TEST-{int(time.time()*1000)}',
        )

        with patch('api.payment_gateways.services.BkashService.BkashService.process_withdrawal') as mock:
            mock.return_value = {'transaction': MagicMock(reference_id='GW_REF_001'), 'payout': MagicMock(reference_id='GW_PAY_001')}
            svc    = WithdrawalGatewayService()
            result = svc.execute(payout)

        assert result['success'] is True
        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_execute_creates_failure_on_error(self, test_user):
        from api.payment_gateways.models.core import PayoutRequest
        from api.payment_gateways.models.withdrawal import WithdrawalFailure
        from api.payment_gateways.services.WithdrawalGatewayService import WithdrawalGatewayService
        import time

        payout = PayoutRequest.objects.create(
            user=test_user, amount=Decimal('500'), fee=Decimal('7.5'),
            net_amount=Decimal('492.5'), payout_method='nagad',
            account_number='01712345679', status='approved',
            reference_id=f'PAY-FAIL-{int(time.time()*1000)}',
        )

        with patch('api.payment_gateways.services.NagadService.NagadService.process_withdrawal',
                   side_effect=Exception('Nagad API error')):
            svc = WithdrawalGatewayService()
            with pytest.raises(Exception, match='Nagad API error'):
                svc.execute(payout)

        failures = WithdrawalFailure.objects.filter(payout_request=payout)
        assert failures.count() == 1
        assert failures.first().failure_type == 'gateway_error'

    def test_batch_execute(self, test_user):
        from api.payment_gateways.models.core import PayoutRequest
        from api.payment_gateways.services.WithdrawalGatewayService import WithdrawalGatewayService
        import time

        ids = []
        for i in range(3):
            p = PayoutRequest.objects.create(
                user=test_user, amount=Decimal('200'), fee=Decimal('3'),
                net_amount=Decimal('197'), payout_method='bkash',
                account_number=f'0171234567{i}', status='approved',
                reference_id=f'PAY-BATCH-{i}-{int(time.time()*1000)}',
            )
            ids.append(p.id)

        with patch('api.payment_gateways.services.BkashService.BkashService.process_withdrawal') as mock:
            mock.return_value = {'payout': MagicMock(reference_id='GW_BATCH')}
            svc    = WithdrawalGatewayService()
            result = svc.execute_batch(ids)

        assert result['success'] == 3
        assert result['failed'] == 0
