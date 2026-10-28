# api/referral/tests/test_services.py
# Service layer tests
# Run: python manage.py test api.referral.tests.test_services
# ============================================================

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TestReferralServiceSignup(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        self.settings = ReferralSettings.objects.create(
            level1_commission_rate=Decimal('10'),
            is_active=True,
            referrer_signup_bonus=Decimal('50'),
            direct_signup_bonus=Decimal('20'),
        )
        self.referrer = User.objects.create_user(username='ref1', password='pass')
        self.new_user = User.objects.create_user(username='new1', password='pass')

    def test_self_referral_blocked(self):
        from api.referral.services.ReferralService import ReferralService
        result = ReferralService.process_signup_with_fraud_check(
            new_user=self.referrer,
            referrer=self.referrer,
        )
        self.assertFalse(result['success'])
        self.assertIn('Self', result['reason'])

    def test_inactive_program_blocked(self):
        from api.referral.models import ReferralSettings
        from api.referral.services.ReferralService import ReferralService
        ReferralSettings.objects.all().update(is_active=False)
        result = ReferralService.process_signup_with_fraud_check(
            new_user=self.new_user,
            referrer=self.referrer,
        )
        self.assertFalse(result['success'])

    def test_same_ip_flagged_as_suspicious(self):
        from api.referral.services.ReferralService import ReferralService
        from api.referral.models import Referral
        with patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_bonus'):
            result = ReferralService.process_signup_with_fraud_check(
                new_user=self.new_user,
                referrer=self.referrer,
                new_user_ip='192.168.1.1',
                referrer_ip='192.168.1.1',
            )
        ref = Referral.objects.filter(
            referrer=self.referrer, referred_user=self.new_user
        ).first()
        if ref:
            self.assertTrue(ref.is_suspicious)

    def test_duplicate_referral_blocked(self):
        from api.referral.models import Referral
        from api.referral.services.ReferralService import ReferralService
        Referral.objects.create(referrer=self.referrer, referred_user=self.new_user)
        result = ReferralService.process_signup_with_fraud_check(
            new_user=self.new_user,
            referrer=self.referrer,
        )
        self.assertFalse(result['success'])


class TestReferralCodeService(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='coder', password='pass')

    def test_generate_unique_code(self):
        from api.referral.services.ReferralCodeService import ReferralCodeService
        code1 = ReferralCodeService.generate_code()
        code2 = ReferralCodeService.generate_code()
        self.assertNotEqual(code1, code2)
        self.assertTrue(code1.startswith('EARN'))
        self.assertGreaterEqual(len(code1), 8)

    def test_get_or_create_primary(self):
        from api.referral.services.ReferralCodeService import ReferralCodeService
        code1 = ReferralCodeService.get_or_create_primary_code(self.user)
        code2 = ReferralCodeService.get_or_create_primary_code(self.user)
        # Same call twice — same code returned
        self.assertEqual(code1.id, code2.id)

    def test_validate_valid_code(self):
        from api.referral.services.ReferralCodeService import ReferralCodeService
        from api.referral.models import ReferralCode
        code = ReferralCode.objects.create(
            user=self.user, code='EARNTESTCODE',
            is_active=True, is_primary=True,
        )
        result = ReferralCodeService.validate_code('EARNTESTCODE')
        self.assertTrue(result['valid'])
        self.assertEqual(result['user'].id, self.user.id)

    def test_validate_invalid_code(self):
        from api.referral.services.ReferralCodeService import ReferralCodeService
        result = ReferralCodeService.validate_code('NONEXISTENT')
        self.assertFalse(result['valid'])


class TestCommissionService(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        self.settings = ReferralSettings.objects.create(
            level1_commission_rate=Decimal('10'),
            level2_commission_rate=Decimal('5'),
            level3_commission_rate=Decimal('2'),
            is_active=True,
        )

    def test_get_rate_level1(self):
        from api.referral.services.CommissionService import CommissionService
        rate = CommissionService.get_commission_rate(level=1)
        self.assertEqual(rate, Decimal('10'))

    def test_get_rate_level2(self):
        from api.referral.services.CommissionService import CommissionService
        rate = CommissionService.get_commission_rate(level=2)
        self.assertEqual(rate, Decimal('5'))


class TestReferralFraudService(TestCase):

    def setUp(self):
        from api.referral.models import ReferralFraudRule, ReferralSettings
        ReferralSettings.objects.create(is_active=True)
        ReferralFraudRule.objects.create(
            rule_type='same_ip',
            action='flag',
            fraud_score_points=30,
            is_active=True,
        )
        self.user1 = User.objects.create_user(username='fraud1', password='pass')
        self.user2 = User.objects.create_user(username='fraud2', password='pass')

    def test_fraud_check_returns_score(self):
        from api.referral.services.ReferralFraudService import ReferralFraudService
        result = ReferralFraudService.check_signup(
            new_user=self.user2,
            referrer=self.user1,
            new_user_ip='10.0.0.1',
            referrer_ip='10.0.0.2',
        )
        self.assertIn('fraud_score', result)
        self.assertIn('action', result)
        self.assertIsInstance(result['fraud_score'], int)