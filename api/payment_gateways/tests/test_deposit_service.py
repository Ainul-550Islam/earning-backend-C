# tests/test_deposit_service.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestDepositService:
    def test_initiate_deposit_bkash(self, test_user):
        from api.payment_gateways.services.DepositService import DepositService
        with patch('api.payment_gateways.services.BkashService.BkashService.process_deposit') as mock:
            mock.return_value = {'payment_url': 'https://bkash.pay', 'payment_id': 'PAY_001'}
            svc    = DepositService()
            result = svc.initiate(test_user, Decimal('500'), 'bkash')
        assert result['gateway'] == 'bkash'
        assert result['amount']  == '500'
        assert 'reference_id' in result

    def test_invalid_amount_raises(self, test_user):
        from api.payment_gateways.services.DepositService import DepositService
        svc = DepositService()
        with pytest.raises(Exception):
            svc.initiate(test_user, Decimal('0'), 'bkash')

    def test_fraud_blocked(self, test_user):
        from api.payment_gateways.services.DepositService import DepositService
        with patch('api.payment_gateways.fraud.FraudDetector.FraudDetector.check') as mock:
            mock.return_value = {'action': 'block', 'risk_score': 95, 'reasons': ['IP blocked']}
            svc = DepositService()
            with pytest.raises(PermissionError):
                svc.initiate(test_user, Decimal('500'), 'bkash')

    def test_verify_and_complete(self, test_user, db):
        from api.payment_gateways.models.deposit import DepositRequest
        from api.payment_gateways.services.DepositService import DepositService
        import time
        ref = f'DEP-TEST-{int(time.time()*1000)}'
        deposit = DepositRequest.objects.create(
            user=test_user, gateway='bkash', amount=Decimal('500'),
            fee=Decimal('7.5'), net_amount=Decimal('492.5'), currency='BDT',
            reference_id=ref, status='pending',
        )
        svc    = DepositService()
        result = svc.verify_and_complete(ref, 'GW_REF_001', {'status': 'completed'})
        assert result.get('completed') is True
        deposit.refresh_from_db()
        assert deposit.status == 'completed'
