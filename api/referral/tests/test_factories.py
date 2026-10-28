# api/referral/tests/test_factories.py
# Tests for factory-generated model instances
# Verifies that all factories create valid data
# Run: python manage.py test api.referral.tests.test_factories
# ============================================================

from decimal import Decimal
from django.test import TestCase


class TestReferralFactory(TestCase):

    def test_creates_valid_referral(self):
        from api.referral.factories import ReferralFactory
        ref = ReferralFactory()
        self.assertIsNotNone(ref.id)
        self.assertIsNotNone(ref.referrer)
        self.assertIsNotNone(ref.referred_user)
        self.assertEqual(ref.level, 1)

    def test_different_users_each_time(self):
        from api.referral.factories import ReferralFactory
        r1 = ReferralFactory()
        r2 = ReferralFactory()
        self.assertNotEqual(r1.referred_user, r2.referred_user)

    def test_not_self_referral(self):
        from api.referral.factories import ReferralFactory
        ref = ReferralFactory()
        self.assertNotEqual(ref.referrer, ref.referred_user)


class TestReferralCodeFactory(TestCase):

    def test_creates_primary_code(self):
        from api.referral.factories import ReferralCodeFactory
        code = ReferralCodeFactory()
        self.assertIsNotNone(code.id)
        self.assertTrue(code.is_primary)
        self.assertTrue(code.is_active)
        self.assertTrue(code.code.startswith('EARN'))

    def test_unique_codes(self):
        from api.referral.factories import ReferralCodeFactory
        c1 = ReferralCodeFactory()
        c2 = ReferralCodeFactory()
        self.assertNotEqual(c1.code, c2.code)


class TestReferralSettingsFactory(TestCase):

    def test_creates_active_settings(self):
        from api.referral.factories import ReferralSettingsFactory
        s = ReferralSettingsFactory()
        self.assertTrue(s.is_active)
        self.assertEqual(s.level1_commission_rate, Decimal('10.00'))
        self.assertEqual(s.level2_commission_rate, Decimal('5.00'))
        self.assertEqual(s.level3_commission_rate, Decimal('2.00'))

    def test_custom_rates(self):
        from api.referral.factories import ReferralSettingsFactory
        s = ReferralSettingsFactory(
            level1_commission_rate=Decimal('15'),
            level2_commission_rate=Decimal('7'),
        )
        self.assertEqual(s.level1_commission_rate, Decimal('15'))
        self.assertEqual(s.level2_commission_rate, Decimal('7'))


class TestReferralEarningFactory(TestCase):

    def test_creates_valid_earning(self):
        from api.referral.factories import ReferralEarningFactory
        e = ReferralEarningFactory()
        self.assertIsNotNone(e.id)
        self.assertEqual(e.level, 1)
        self.assertEqual(e.amount, Decimal('10.00'))
        self.assertEqual(e.status, 'released')

    def test_different_source_types(self):
        from api.referral.factories import ReferralEarningFactory
        e1 = ReferralEarningFactory(source_type='task')
        e2 = ReferralEarningFactory(source_type='offer')
        self.assertEqual(e1.source_type, 'task')
        self.assertEqual(e2.source_type, 'offer')


class TestCommissionLogFactory(TestCase):

    def test_creates_valid_log(self):
        from api.referral.factories import CommissionLogFactory
        log = CommissionLogFactory()
        self.assertIsNotNone(log.id)
        self.assertEqual(log.status, 'pending')
        self.assertEqual(log.level, 1)
        self.assertGreater(log.amount, 0)


class TestReferralCampaignFactory(TestCase):

    def test_creates_active_campaign(self):
        from api.referral.factories import ReferralCampaignFactory
        campaign = ReferralCampaignFactory()
        self.assertIsNotNone(campaign.id)
        self.assertTrue(campaign.is_active)
        self.assertGreater(campaign.end_date, campaign.start_date)
        self.assertEqual(campaign.bonus_multiplier, Decimal('1.5'))


class TestFraudRuleFactory(TestCase):

    def test_creates_active_rule(self):
        from api.referral.factories import ReferralFraudRuleFactory
        rule = ReferralFraudRuleFactory()
        self.assertIsNotNone(rule.id)
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.action, 'flag')
        self.assertEqual(rule.fraud_score_points, 20)


class TestTopReferrerFactory(TestCase):

    def test_creates_valid_entry(self):
        from api.referral.factories import TopReferrerFactory
        entry = TopReferrerFactory()
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.period, 'daily')
        self.assertGreater(entry.rank, 0)

    def test_sequential_ranks(self):
        from api.referral.factories import TopReferrerFactory
        e1 = TopReferrerFactory()
        e2 = TopReferrerFactory()
        self.assertNotEqual(e1.rank, e2.rank)


class TestCreateReferralNetwork(TestCase):

    def test_creates_network(self):
        from api.referral.factories import create_referral_network
        from api.referral.models import Referral

        network = create_referral_network(depth=2, width=2)
        self.assertIsNotNone(network['root'])
        self.assertEqual(len(network['l1']), 2)
        self.assertEqual(len(network['l2']), 4)  # 2 l1 × 2 width

        # Verify referrals created
        l1_refs = Referral.objects.filter(referrer=network['root']).count()
        self.assertEqual(l1_refs, 2)

    def test_creates_deep_network(self):
        from api.referral.factories import create_referral_network
        network = create_referral_network(depth=3, width=2)
        self.assertEqual(len(network['l1']), 2)
        self.assertEqual(len(network['l2']), 4)
        self.assertEqual(len(network['l3']), 8)


class TestUserCommissionTierFactory(TestCase):

    def test_creates_bronze_tier(self):
        from api.referral.factories import UserCommissionTierFactory
        tier = UserCommissionTierFactory()
        self.assertIsNotNone(tier.id)
        self.assertEqual(float(tier.effective_l1_rate), 10.0)
        self.assertEqual(float(tier.effective_l2_rate), 5.0)


class TestAffiliateProfileFactory(TestCase):

    def test_creates_active_profile(self):
        from api.referral.factories import AffiliateProfileFactory
        profile = AffiliateProfileFactory()
        self.assertIsNotNone(profile.id)
        self.assertEqual(profile.status, 'active')
        self.assertTrue(profile.is_public)