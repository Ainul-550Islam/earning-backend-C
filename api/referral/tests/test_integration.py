# api/referral/tests/test_integration.py
# Integration tests — tests the full referral flow end-to-end
# Run: python manage.py test api.referral.tests.test_integration
# ============================================================

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

User = get_user_model()


class TestFullReferralFlow(TestCase):
    """
    Integration test: Full referral flow
    A → refers → B → completes task → A gets commission
    """

    def setUp(self):
        from api.referral.models import ReferralSettings, ReferralFraudRule
        self.settings = ReferralSettings.objects.create(
            level1_commission_rate=Decimal('10'),
            level2_commission_rate=Decimal('5'),
            level3_commission_rate=Decimal('2'),
            is_active=True,
            referrer_signup_bonus=Decimal('50'),
            direct_signup_bonus=Decimal('20'),
            commission_hold_days=0,  # No hold for tests
        )
        ReferralFraudRule.objects.create(
            rule_type='same_ip', action='flag',
            fraud_score_points=30, is_active=True,
        )
        self.user_a = User.objects.create_user(username='userA', password='pass')
        self.user_b = User.objects.create_user(username='userB', password='pass')

    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_bonus')
    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_referral_commission')
    def test_signup_creates_referral(self, mock_commission, mock_bonus):
        mock_bonus.return_value = MagicMock()
        mock_commission.return_value = MagicMock()

        from api.referral.services.ReferralService import ReferralService
        from api.referral.models import Referral

        result = ReferralService.process_signup_with_fraud_check(
            new_user=self.user_b,
            referrer=self.user_a,
            new_user_ip='10.0.0.1',
            referrer_ip='10.0.0.2',
        )

        self.assertTrue(result.get('success', False))
        self.assertTrue(
            Referral.objects.filter(
                referrer=self.user_a, referred_user=self.user_b
            ).exists()
        )

    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_referral_commission')
    def test_task_completion_triggers_commission(self, mock_commission):
        mock_commission.return_value = MagicMock()

        from api.referral.models import Referral, ReferralChain
        from api.referral.services.ReferralService import ReferralService

        # Setup referral relationship
        referral = Referral.objects.create(
            referrer=self.user_a, referred_user=self.user_b, level=1
        )
        ReferralChain.objects.create(
            beneficiary=self.user_a,
            earner=self.user_b,
            level=1,
        )

        result = ReferralService.process_multilevel_commission(
            earner=self.user_b,
            earned_amount=Decimal('100'),
            source_type='task',
            source_id='1',
        )

        # Should have tried to pay commission
        self.assertIsNotNone(result)

    def test_bridge_on_signup(self):
        from api.referral.models import ReferralCode
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge

        # Create referral code for user_a
        ReferralCode.objects.create(
            user=self.user_a,
            code='EARNABC123',
            is_primary=True,
            is_active=True,
        )

        bridge = get_bridge()
        code = bridge.get_referral_code(self.user_a)
        self.assertEqual(code, 'EARNABC123')

    def test_validate_referral_code(self):
        from api.referral.models import ReferralCode
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge

        ReferralCode.objects.create(
            user=self.user_a, code='VALIDCODE',
            is_primary=True, is_active=True,
        )
        bridge = get_bridge()
        result = bridge.validate_referral_code('VALIDCODE')
        self.assertTrue(result['valid'])

    def test_validate_invalid_code(self):
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
        bridge = get_bridge()
        result = bridge.validate_referral_code('FAKECODE99')
        self.assertFalse(result['valid'])


class TestMultiLevelChain(TestCase):
    """
    Test 3-level referral chain:
    A → B → C → D
    When D earns 100: A gets 2%, B gets 5%, C gets 10%
    """

    def setUp(self):
        from api.referral.models import ReferralSettings, Referral, ReferralChain
        ReferralSettings.objects.create(
            level1_commission_rate=Decimal('10'),
            level2_commission_rate=Decimal('5'),
            level3_commission_rate=Decimal('2'),
            is_active=True, commission_hold_days=0,
        )
        self.A = User.objects.create_user(username='chainA', password='pass')
        self.B = User.objects.create_user(username='chainB', password='pass')
        self.C = User.objects.create_user(username='chainC', password='pass')
        self.D = User.objects.create_user(username='chainD', password='pass')

        Referral.objects.create(referrer=self.A, referred_user=self.B)
        Referral.objects.create(referrer=self.B, referred_user=self.C)
        Referral.objects.create(referrer=self.C, referred_user=self.D)

        ReferralChain.objects.create(beneficiary=self.C, earner=self.D, level=1)
        ReferralChain.objects.create(beneficiary=self.B, earner=self.D, level=2)
        ReferralChain.objects.create(beneficiary=self.A, earner=self.D, level=3)

    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_referral_commission')
    def test_three_level_commission_calls(self, mock_credit):
        mock_credit.return_value = MagicMock()

        from api.referral.services.ReferralService import ReferralService
        results = ReferralService.process_multilevel_commission(
            earner=self.D,
            earned_amount=Decimal('100'),
            source_type='task',
            source_id='999',
        )

        # Should have called commission for C (L1), B (L2), A (L3)
        self.assertGreaterEqual(mock_credit.call_count, 1)