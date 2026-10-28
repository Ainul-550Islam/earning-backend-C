# api/referral/tests/test_models.py
# Model tests — tests that require database
# Run: python manage.py test api.referral.tests.test_models
# ============================================================

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TestReferralModel(TestCase):

    def setUp(self):
        self.referrer = User.objects.create_user(
            username='referrer', email='referrer@test.com', password='pass'
        )
        self.referred = User.objects.create_user(
            username='referred', email='referred@test.com', password='pass'
        )

    def test_create_referral(self):
        from api.referral.models import Referral
        r = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred,
            level=1,
        )
        self.assertEqual(r.referrer, self.referrer)
        self.assertEqual(r.referred_user, self.referred)
        self.assertEqual(r.level, 1)
        self.assertFalse(r.is_suspicious)

    def test_unique_together(self):
        from api.referral.models import Referral
        from django.db import IntegrityError
        Referral.objects.create(referrer=self.referrer, referred_user=self.referred)
        with self.assertRaises(IntegrityError):
            Referral.objects.create(referrer=self.referrer, referred_user=self.referred)

    def test_str_representation(self):
        from api.referral.models import Referral
        r = Referral.objects.create(referrer=self.referrer, referred_user=self.referred)
        self.assertIn('referrer', str(r))
        self.assertIn('referred', str(r))


class TestReferralSettingsModel(TestCase):

    def test_default_settings(self):
        from api.referral.models import ReferralSettings
        s = ReferralSettings.objects.create()
        self.assertEqual(s.level1_commission_rate, Decimal('10'))
        self.assertEqual(s.level2_commission_rate, Decimal('5'))
        self.assertEqual(s.level3_commission_rate, Decimal('2'))
        self.assertTrue(s.is_active)

    def test_get_rate_for_level(self):
        from api.referral.models import ReferralSettings
        s = ReferralSettings.objects.create(
            level1_commission_rate=Decimal('15'),
            level2_commission_rate=Decimal('7'),
            level3_commission_rate=Decimal('3'),
        )
        self.assertEqual(s.get_rate_for_level(1), Decimal('15'))
        self.assertEqual(s.get_rate_for_level(2), Decimal('7'))
        self.assertEqual(s.get_rate_for_level(3), Decimal('3'))
        self.assertEqual(s.get_rate_for_level(99), Decimal('0'))

    def test_lifetime_commission_rate_property(self):
        from api.referral.models import ReferralSettings
        s = ReferralSettings.objects.create(level1_commission_rate=Decimal('12'))
        self.assertEqual(s.lifetime_commission_rate, Decimal('12'))


class TestReferralCodeModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='codeuser', email='code@test.com', password='pass'
        )

    def test_create_code(self):
        from api.referral.models import ReferralCode
        code = ReferralCode.objects.create(
            user=self.user,
            code='EARNABC123',
            is_primary=True,
        )
        self.assertEqual(code.code, 'EARNABC123')
        self.assertTrue(code.is_active)
        self.assertTrue(code.is_primary)

    def test_unique_code(self):
        from api.referral.models import ReferralCode
        from django.db import IntegrityError
        ReferralCode.objects.create(user=self.user, code='UNIQUE01')
        user2 = User.objects.create_user(username='u2', password='pass')
        with self.assertRaises(IntegrityError):
            ReferralCode.objects.create(user=user2, code='UNIQUE01')


class TestReferralEarningModel(TestCase):

    def setUp(self):
        self.referrer = User.objects.create_user(username='r1', password='pass')
        self.referred = User.objects.create_user(username='r2', password='pass')

    def test_create_earning(self):
        from api.referral.models import ReferralEarning
        e = ReferralEarning.objects.create(
            referrer=self.referrer,
            referred_user=self.referred,
            level=1,
            amount=Decimal('10'),
            commission_rate=Decimal('10'),
            source_amount=Decimal('100'),
            source_type='task',
            status='released',
        )
        self.assertEqual(e.amount, Decimal('10'))
        self.assertEqual(e.level, 1)


class TestReferralFraudRuleModel(TestCase):

    def test_create_fraud_rule(self):
        from api.referral.models import ReferralFraudRule
        rule = ReferralFraudRule.objects.create(
            rule_type='same_ip_check',
            name='Same IP Detection',
            action='flag',
            threshold=1,
            fraud_score_points=30,
            is_active=True,
        )
        self.assertEqual(rule.rule_type, 'same_ip_check')
        self.assertTrue(rule.is_active)