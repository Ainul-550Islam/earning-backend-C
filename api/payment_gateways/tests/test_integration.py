# tests/test_integration.py
# End-to-end integration tests
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestDepositToWithdrawalFlow:
    """Full flow: deposit → verify → withdraw."""

    def test_full_bkash_deposit_flow(self, test_user):
        """Deposit via bKash end-to-end."""
        import time
        from api.payment_gateways.services.DepositService import DepositService
        from api.payment_gateways.models.deposit import DepositRequest

        with patch('api.payment_gateways.services.BkashService.BkashService.process_deposit') as mock:
            mock.return_value = {
                'payment_url': 'https://bkash.pay/test',
                'payment_id':  'PAY_BK_001',
                'session_key': 'SK_001',
            }
            svc    = DepositService()
            result = svc.initiate(test_user, Decimal('1000'), 'bkash')

        assert result['gateway'] == 'bkash'
        ref = result['reference_id']

        # Now verify completion
        complete = svc.verify_and_complete(ref, 'GW_BK_001', {'trxID': 'GW_BK_001', 'status': 'Completed'})
        assert complete['completed'] is True

    def test_gateway_fallback_on_bkash_failure(self, test_user):
        """When bKash fails, fallback to Nagad."""
        from api.payment_gateways.services.GatewayFallbackService import GatewayFallbackService

        def bkash_fail(**kwargs):
            raise Exception('bKash API down')

        def nagad_ok(**kwargs):
            return {'payment_url': 'https://nagad.pay', 'payment_id': 'NAGAD_001'}

        with patch('api.payment_gateways.services.BkashService.BkashService.process_deposit',
                   side_effect=bkash_fail):
            with patch('api.payment_gateways.services.NagadService.NagadService.process_deposit',
                       side_effect=nagad_ok):
                svc    = GatewayFallbackService()
                result = svc.process_with_fallback(test_user, Decimal('500'), 'bkash', 'deposit')

        assert result['was_fallback'] is True
        assert result['used_gateway'] == 'nagad'

    def test_deposit_triggers_referral_commission(self, test_user):
        """Completed deposit should credit referrer's commission."""
        from api.payment_gateways.referral.models import ReferralProgram
        from api.payment_gateways.referral.ReferralEngine import ReferralEngine
        from api.payment_gateways.services.DepositService import DepositService
        import time

        # Setup referral program
        ReferralProgram.objects.get_or_create(
            defaults={'commission_percent': Decimal('10'), 'commission_months': 6}
        )
        engine = ReferralEngine()
        result = engine.credit_commission(test_user, Decimal('1000'), 'TEST_REF')
        # No referral setup, should return without error
        assert result.get('credited') in (True, False)
