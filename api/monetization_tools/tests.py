"""
api/monetization_tools/tests.py
=================================
Unit tests for monetization_tools models, services, utils, and views.
Run: python manage.py test api.monetization_tools
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.utils import timezone

User = get_user_model()


# ===========================================================================
# Helpers
# ===========================================================================

def make_user(username='testuser', **kwargs):
    defaults = dict(
        email=f'{username}@example.com',
        password='testpass123',
        coin_balance=Decimal('0.00'),
        total_earned=Decimal('0.00'),
    )
    defaults.update(kwargs)
    return User.objects.create_user(username=username, **defaults)


# ===========================================================================
# 1. Utils tests
# ===========================================================================

class UtilsTests(TestCase):

    def test_round_currency(self):
        from .utils import round_currency
        self.assertEqual(round_currency(Decimal('1.005')), Decimal('1.01'))
        self.assertEqual(round_currency(Decimal('0.001')), Decimal('0.00'))

    def test_usd_to_coins(self):
        from .utils import usd_to_coins
        result = usd_to_coins(Decimal('1.00'))
        self.assertEqual(result, Decimal('100.00'))

    def test_calculate_ecpm(self):
        from .utils import calculate_ecpm
        self.assertEqual(calculate_ecpm(Decimal('10.00'), 1000), Decimal('10.0000'))
        self.assertEqual(calculate_ecpm(Decimal('0'), 0), Decimal('0.0000'))

    def test_calculate_ctr(self):
        from .utils import calculate_ctr
        self.assertEqual(calculate_ctr(10, 1000), Decimal('1.00'))
        self.assertEqual(calculate_ctr(0, 0), Decimal('0.00'))

    def test_get_date_range_today(self):
        from .utils import get_date_range
        start, end = get_date_range('today')
        self.assertEqual(start, end)
        self.assertEqual(start, timezone.now().date())

    def test_get_date_range_last_7d(self):
        from .utils import get_date_range
        start, end = get_date_range('last_7d')
        self.assertEqual((end - start).days, 6)

    def test_fraud_score_calculation(self):
        from .utils import calculate_fraud_score, is_high_risk
        score = calculate_fraud_score(['vpn', 'proxy'])
        self.assertEqual(score, 35)
        self.assertFalse(is_high_risk(35))
        self.assertTrue(is_high_risk(70))

    def test_verify_hmac_valid(self):
        from .utils import verify_hmac_signature
        import hmac as _hmac, hashlib
        secret  = 'mysecret'
        payload = 'test_payload'
        sig = _hmac.new(secret.encode(), payload.encode(), 'sha256').hexdigest()
        self.assertTrue(verify_hmac_signature(payload, sig, secret))

    def test_verify_hmac_invalid(self):
        from .utils import verify_hmac_signature
        self.assertFalse(verify_hmac_signature('payload', 'badsig', 'secret'))


# ===========================================================================
# 2. Constants / Config tests
# ===========================================================================

class ConstantsTests(TestCase):

    def test_constants_defined(self):
        from . import constants
        self.assertGreater(constants.MIN_CAMPAIGN_BUDGET_USD, 0)
        self.assertGreater(constants.MAX_DAILY_OFFERS_PER_USER, 0)
        self.assertGreater(constants.SPIN_WHEEL_DAILY_LIMIT, 0)

    def test_config_feature_flags(self):
        from .config import is_feature_enabled, FEATURE_FLAGS
        self.assertIn('offerwall', FEATURE_FLAGS)
        self.assertIn('subscription', FEATURE_FLAGS)
        # is_feature_enabled should return bool
        result = is_feature_enabled('offerwall')
        self.assertIsInstance(result, bool)


# ===========================================================================
# 3. Model tests
# ===========================================================================

class AdCampaignModelTests(TestCase):

    def setUp(self):
        self.now = timezone.now()
        from .models import AdCampaign
        self.campaign = AdCampaign(
            name='Test Campaign',
            total_budget=Decimal('1000.00'),
            spent_budget=Decimal('250.00'),
            pricing_model='cpm',
            start_date=self.now,
            status='active',
            total_impressions=10000,
            total_clicks=200,
        )

    def test_remaining_budget(self):
        self.assertEqual(self.campaign.remaining_budget, Decimal('750.00'))

    def test_ctr(self):
        self.assertEqual(self.campaign.ctr, Decimal('2.00'))

    def test_ctr_zero_impressions(self):
        self.campaign.total_impressions = 0
        self.assertEqual(self.campaign.ctr, Decimal('0.00'))


class OfferModelTests(TestCase):

    def _make_offer(self, status='active', expiry_date=None):
        from .models import Offer, Offerwall, AdNetwork
        net = AdNetwork(network_type='custom', display_name='Test Net', priority=1)
        net.save()
        wall = Offerwall(network=net, name='Wall', slug='wall')
        wall.save()
        offer = Offer(
            offerwall=wall,
            external_offer_id='EXT001',
            title='Test Offer',
            offer_type='survey',
            status=status,
            payout_usd=Decimal('1.00'),
            point_value=Decimal('100.00'),
            expiry_date=expiry_date,
        )
        offer.save()
        return offer

    def test_offer_available(self):
        offer = self._make_offer(status='active')
        self.assertTrue(offer.is_available)

    def test_offer_paused_not_available(self):
        offer = self._make_offer(status='paused')
        self.assertFalse(offer.is_available)

    def test_expired_offer_not_available(self):
        past = timezone.now() - timezone.timedelta(days=1)
        offer = self._make_offer(status='active', expiry_date=past)
        self.assertFalse(offer.is_available)


# ===========================================================================
# 4. Service tests
# ===========================================================================

class RewardServiceTests(TestCase):

    def setUp(self):
        self.user = make_user(coin_balance=Decimal('500.00'))

    def test_credit(self):
        from .services import RewardService
        from .enums import RewardTransactionType
        txn = RewardService.credit(
            self.user, Decimal('100.00'),
            RewardTransactionType.OFFER_REWARD,
            description='Test credit',
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal('600.00'))
        self.assertEqual(txn.balance_after, Decimal('600.00'))

    def test_debit(self):
        from .services import RewardService
        from .enums import RewardTransactionType
        txn = RewardService.debit(
            self.user, Decimal('200.00'),
            RewardTransactionType.WITHDRAWAL,
            description='Test debit',
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal('300.00'))
        self.assertEqual(txn.amount, Decimal('-200.00'))

    def test_debit_insufficient_balance(self):
        from .services import RewardService
        from .enums import RewardTransactionType
        from .exceptions import InsufficientBalance
        with self.assertRaises(InsufficientBalance):
            RewardService.debit(
                self.user, Decimal('9999.00'),
                RewardTransactionType.WITHDRAWAL,
            )


class SubscriptionServiceTests(TestCase):

    def setUp(self):
        self.user = make_user()
        from .models import SubscriptionPlan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic', slug='basic',
            price=Decimal('99.00'), currency='BDT',
            interval='monthly', trial_days=7,
        )

    def test_create_subscription(self):
        from .services import SubscriptionService
        sub = SubscriptionService.create_subscription(self.user, self.plan)
        self.assertEqual(sub.status, 'trial')
        self.assertIsNotNone(sub.trial_end_at)

    def test_create_subscription_no_trial(self):
        from .services import SubscriptionService
        self.plan.trial_days = 0
        self.plan.save()
        sub = SubscriptionService.create_subscription(self.user, self.plan)
        self.assertEqual(sub.status, 'active')

    def test_double_subscription_raises(self):
        from .services import SubscriptionService
        from .exceptions import SubscriptionAlreadyActive
        SubscriptionService.create_subscription(self.user, self.plan)
        with self.assertRaises(SubscriptionAlreadyActive):
            SubscriptionService.create_subscription(self.user, self.plan)

    def test_cancel_subscription(self):
        from .services import SubscriptionService
        sub = SubscriptionService.create_subscription(self.user, self.plan)
        SubscriptionService.cancel_subscription(sub, reason='User request')
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'cancelled')
        self.assertFalse(sub.is_auto_renew)


# ===========================================================================
# 5. Gamification tests
# ===========================================================================

class UserLevelTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_add_xp_no_level_up(self):
        from .models import UserLevel
        lvl = UserLevel.objects.create(user=self.user, current_xp=0, xp_to_next_level=100)
        lvl.add_xp(50)
        self.assertEqual(lvl.current_xp, 50)
        self.assertEqual(lvl.current_level, 1)

    def test_add_xp_level_up(self):
        from .models import UserLevel
        lvl = UserLevel.objects.create(user=self.user, current_xp=90, xp_to_next_level=100)
        lvl.add_xp(20)
        self.assertEqual(lvl.current_level, 2)
        self.assertEqual(lvl.current_xp, 10)


# ===========================================================================
# 6. Enums tests
# ===========================================================================

class EnumsTests(TestCase):

    def test_all_enums_importable(self):
        from . import enums
        self.assertTrue(hasattr(enums, 'CampaignStatus'))
        self.assertTrue(hasattr(enums, 'OfferType'))
        self.assertTrue(hasattr(enums, 'PaymentGateway'))
        self.assertTrue(hasattr(enums, 'ABTestStatus'))

    def test_enum_values_valid(self):
        from .enums import CampaignStatus, PaymentStatus
        self.assertIn('active', [c.value for c in CampaignStatus])
        self.assertIn('success', [c.value for c in PaymentStatus])


# ===========================================================================
# 7. Cache tests
# ===========================================================================

class CacheTests(TestCase):

    def test_cache_key_formats(self):
        from .cache import (ad_unit_key, offerwall_list_key,
                            leaderboard_key, user_subscription_key)
        self.assertEqual(ad_unit_key(1),             'mt:ad_unit:1')
        self.assertEqual(offerwall_list_key(),        'mt:offerwalls:all')
        self.assertEqual(leaderboard_key('global', 'earnings'), 'mt:leaderboard:global:earnings:')
        self.assertEqual(user_subscription_key(42),  'mt:user_sub:42')

    def test_set_and_get_cache(self):
        from .cache import set_cached, get_cached, delete_cached
        set_cached('mt:test:key', {'value': 42}, ttl=60)
        result = get_cached('mt:test:key')
        self.assertEqual(result, {'value': 42})
        delete_cached('mt:test:key')
        self.assertIsNone(get_cached('mt:test:key'))


# ===========================================================================
# 8. Exceptions tests
# ===========================================================================

class ExceptionsTests(TestCase):

    def test_exceptions_importable(self):
        from .exceptions import (
            OfferNotAvailable, InsufficientBalance, PaymentFailed,
            SubscriptionAlreadyActive, SpinWheelDailyLimitReached,
        )
        for exc_cls in [OfferNotAvailable, InsufficientBalance, PaymentFailed,
                        SubscriptionAlreadyActive, SpinWheelDailyLimitReached]:
            self.assertTrue(issubclass(exc_cls, Exception))

    def test_exception_status_codes(self):
        from .exceptions import OfferFraudDetected, PaymentGatewayError
        self.assertEqual(OfferFraudDetected.status_code, 403)
        self.assertEqual(PaymentGatewayError.status_code, 502)


# ============================================================================
# NEW TESTS  (Phase-2 models)
# ============================================================================

class MonetizationConfigTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_get_or_create(self):
        from .models import MonetizationConfig
        cfg, created = MonetizationConfig.objects.get_or_create(tenant=None)
        self.assertIsNotNone(cfg)
        self.assertTrue(cfg.offerwall_enabled)
        self.assertTrue(cfg.subscription_enabled)

    def test_default_values(self):
        from .models import MonetizationConfig
        cfg = MonetizationConfig(tenant=None)
        self.assertEqual(cfg.coins_per_usd, Decimal('100.00'))
        self.assertEqual(cfg.max_offers_per_day, 50)
        self.assertEqual(cfg.spin_wheel_daily_limit, 3)


class AdCreativeTests(TestCase):
    def setUp(self):
        from .models import AdNetwork, AdCampaign, AdUnit
        net = AdNetwork.objects.create(network_type='custom', display_name='Test', priority=1)
        now = timezone.now()
        camp = AdCampaign.objects.create(
            name='Camp', total_budget=Decimal('1000'), pricing_model='cpm',
            start_date=now, status='active', bid_amount=Decimal('0.1'),
        )
        self.unit = AdUnit.objects.create(
            campaign=camp, ad_network=net, name='Unit', ad_format='banner',
        )

    def test_creative_creation(self):
        from .models import AdCreative
        c = AdCreative.objects.create(
            ad_unit=self.unit, name='Banner A', creative_type='image',
            asset_url='https://example.com/img.jpg', status='approved',
        )
        self.assertEqual(c.ctr, Decimal('0.0000'))

    def test_ctr_calculation(self):
        from .models import AdCreative
        c = AdCreative(impressions=1000, clicks=50)
        self.assertEqual(c.ctr, Decimal('5.0000'))


class DailyStreakServiceTests(TestCase):
    def setUp(self):
        self.user = make_user(coin_balance=Decimal('0.00'))

    def test_first_check_in(self):
        from .services import DailyStreakService
        result = DailyStreakService.check_in(self.user)
        self.assertEqual(result['current_streak'], 1)
        self.assertFalse(result['streak_broken'])

    def test_double_check_in_same_day(self):
        from .services import DailyStreakService
        DailyStreakService.check_in(self.user)
        result = DailyStreakService.check_in(self.user)
        self.assertTrue(result.get('already_claimed'))

    def test_reward_calculation(self):
        from .services import DailyStreakService
        self.assertEqual(DailyStreakService._calculate_reward(1),  Decimal('10.00'))
        self.assertEqual(DailyStreakService._calculate_reward(7),  Decimal('20.00'))
        self.assertEqual(DailyStreakService._calculate_reward(30), Decimal('50.00'))
        self.assertEqual(DailyStreakService._calculate_reward(90), Decimal('100.00'))
        self.assertEqual(DailyStreakService._calculate_reward(365), Decimal('500.00'))


class CouponServiceTests(TestCase):
    def setUp(self):
        self.user = make_user(coin_balance=Decimal('0.00'))

    def _make_coupon(self, **kwargs):
        from .models import Coupon
        defaults = dict(
            code='TEST10', name='Test Coupon', coupon_type='coin_grant',
            coin_amount=Decimal('100.00'), is_active=True,
        )
        defaults.update(kwargs)
        return Coupon.objects.create(**defaults)

    def test_validate_valid_coupon(self):
        coupon = self._make_coupon()
        result, error = CouponService.validate('TEST10', self.user)
        self.assertIsNotNone(result)
        self.assertIsNone(error)

    def test_validate_nonexistent_coupon(self):
        result, error = CouponService.validate('DOESNOTEXIST', self.user)
        self.assertIsNone(result)
        self.assertIsNotNone(error)

    def test_redeem_grants_coins(self):
        self._make_coupon()
        result = CouponService.redeem('TEST10', self.user)
        self.assertNotIn('error', result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal('100.00'))

    def test_max_uses_exhausted(self):
        from .models import Coupon
        coupon = self._make_coupon(code='MAXTEST', max_uses=1, current_uses=1)
        result, error = CouponService.validate('MAXTEST', self.user)
        self.assertIsNone(result)
        self.assertIn('exhausted', error.lower())


class ReferralServiceTests(TestCase):
    def setUp(self):
        self.referrer = make_user('referrer', coin_balance=Decimal('0.00'))
        self.referee  = make_user('referee',  coin_balance=Decimal('0.00'))

    def _make_program(self):
        from .models import ReferralProgram
        return ReferralProgram.objects.create(
            name='Test Program', slug='test-program', is_active=True,
            referrer_bonus_coins=Decimal('100.00'),
            referee_bonus_coins=Decimal('50.00'),
            l1_commission_pct=Decimal('10.00'),
        )

    def test_get_or_create_link(self):
        program = self._make_program()
        link = ReferralService.get_or_create_link(self.referrer, program)
        self.assertIsNotNone(link.code)
        self.assertEqual(len(link.code), 10)

    def test_award_commission(self):
        program = self._make_program()
        commission = ReferralService.award_commission(
            self.referrer, self.referee, program,
            commission_type='offer_earn',
            base_amount=Decimal('100.00'),
            level=1,
        )
        self.referrer.refresh_from_db()
        self.assertEqual(commission.commission_coins, Decimal('10.00'))
        self.assertEqual(self.referrer.coin_balance, Decimal('10.00'))

    def test_get_summary(self):
        program = self._make_program()
        ReferralService.get_or_create_link(self.referrer, program)
        summary = ReferralService.get_summary(self.referrer)
        self.assertIn('total_referrals', summary)
        self.assertIn('total_earned', summary)


class PayoutRequestTests(TestCase):
    def setUp(self):
        self.user = make_user(coin_balance=Decimal('5000.00'))

    def _make_payout_method(self):
        from .models import PayoutMethod
        return PayoutMethod.objects.create(
            user=self.user, method_type='bkash',
            account_number='01711111111', currency='BDT',
        )

    def test_create_payout_request(self):
        from .models import MonetizationConfig
        MonetizationConfig.objects.get_or_create(tenant=None)
        method = self._make_payout_method()
        pr = PayoutService.create_request(
            self.user, method,
            coins=Decimal('1000.00'),
            exchange_rate=Decimal('110.00'),
        )
        self.assertEqual(pr.status, 'pending')
        self.assertEqual(pr.coins_deducted, Decimal('1000.00'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal('4000.00'))

    def test_insufficient_balance_raises(self):
        from .models import MonetizationConfig
        from .exceptions import InsufficientBalance
        MonetizationConfig.objects.get_or_create(tenant=None)
        method = self._make_payout_method()
        with self.assertRaises(InsufficientBalance):
            PayoutService.create_request(self.user, method, coins=Decimal('99999.00'))


class FraudAlertServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_create_alert(self):
        from .models import FraudAlert
        from .services import FraudAlertService
        alert = FraudAlertService.create_alert(
            self.user, 'high_fraud_score', 'high',
            'Test alert', evidence={'test': True}
        )
        self.assertEqual(FraudAlert.objects.filter(user=self.user).count(), 1)
        self.assertEqual(alert.severity, 'high')
        self.assertEqual(alert.resolution, 'open')

    def test_auto_block_user(self):
        from .services import FraudAlertService
        FraudAlertService.create_alert(
            self.user, 'multiple_accounts', 'critical',
            'Test auto block', auto_block=True
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_level, 'blocked')


class FlashSaleTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _make_flash_sale(self, multiplier=Decimal('2.00'), hours_from_now=24):
        from .models import FlashSale
        now = timezone.now()
        return FlashSale.objects.create(
            name='Test Sale', slug='test-sale', sale_type='offer_boost',
            multiplier=multiplier, starts_at=now - timezone.timedelta(hours=1),
            ends_at=now + timezone.timedelta(hours=hours_from_now), is_active=True,
        )

    def test_is_live_property(self):
        sale = self._make_flash_sale()
        self.assertTrue(sale.is_live)

    def test_expired_not_live(self):
        from .models import FlashSale
        now = timezone.now()
        sale = FlashSale(
            starts_at=now - timezone.timedelta(hours=2),
            ends_at=now - timezone.timedelta(hours=1),
            is_active=True,
        )
        self.assertFalse(sale.is_live)


class RevenueGoalTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_goal_progress(self):
        from .models import RevenueGoal
        today = timezone.now().date()
        goal = RevenueGoal(
            name='Q1 Revenue', period='monthly', goal_type='total_revenue',
            target_value=Decimal('10000.00'), current_value=Decimal('5000.00'),
            period_start=today.replace(day=1), period_end=today,
        )
        self.assertEqual(goal.progress_pct, Decimal('50.00'))
        self.assertFalse(goal.is_achieved)

    def test_goal_achieved(self):
        from .models import RevenueGoal
        today = timezone.now().date()
        goal = RevenueGoal(
            target_value=Decimal('1000.00'), current_value=Decimal('1500.00'),
            period_start=today.replace(day=1), period_end=today,
        )
        self.assertTrue(goal.is_achieved)


class PublisherAccountTests(TestCase):
    def test_create_publisher(self):
        from .models import PublisherAccount
        acc = PublisherAccount.objects.create(
            account_type='advertiser', company_name='Test Corp',
            contact_name='John Doe', email='john@testcorp.com',
            status='pending',
        )
        self.assertEqual(acc.status, 'pending')
        self.assertFalse(acc.is_verified)
        self.assertEqual(acc.total_spend_usd, Decimal('0.0000'))


# ============================================================================
# ADDITIONAL TESTS — remaining model coverage
# ============================================================================

class AdPerformanceTests(TestCase):
    def setUp(self):
        from .models import AdNetwork, AdCampaign, AdUnit
        self.net  = AdNetwork.objects.create(network_type='custom', display_name='Net', priority=1)
        now       = timezone.now()
        self.camp = AdCampaign.objects.create(
            name='Perf Camp', total_budget=Decimal('5000'), pricing_model='cpm',
            start_date=now, status='active', bid_amount=Decimal('1.00'),
        )
        self.unit = AdUnit.objects.create(
            campaign=self.camp, ad_network=self.net, name='PerfUnit', ad_format='banner',
        )

    def test_hourly_kpi_recompute(self):
        from .models import AdPerformanceHourly
        obj = AdPerformanceHourly(
            ad_unit=self.unit, ad_network=self.net,
            hour_bucket=timezone.now().replace(minute=0, second=0, microsecond=0),
            impressions=1000, clicks=30, requests=1200,
            revenue_usd=Decimal('5.00'),
        )
        AdPerformanceHourly.recompute_kpis(obj)
        self.assertEqual(obj.ecpm, Decimal('5.0000'))
        self.assertEqual(obj.ctr,  Decimal('3.0000'))
        self.assertAlmostEqual(float(obj.fill_rate), 83.3333, places=2)

    def test_daily_performance_creation(self):
        from .models import AdPerformanceDaily
        obj = AdPerformanceDaily.objects.create(
            ad_unit=self.unit, ad_network=self.net, campaign=self.camp,
            date=timezone.now().date(), impressions=5000, clicks=100,
            total_revenue=Decimal('25.00'), ecpm=Decimal('5.0000'),
        )
        self.assertEqual(obj.impressions, 5000)
        self.assertEqual(obj.total_revenue, Decimal('25.00'))

    def test_network_daily_stat_creation(self):
        from .models import AdNetworkDailyStat
        stat = AdNetworkDailyStat.objects.create(
            ad_network=self.net, date=timezone.now().date(),
            reported_revenue=Decimal('100.00'), reported_ecpm=Decimal('2.50'),
            reported_impressions=40000,
        )
        self.assertEqual(stat.reported_revenue, Decimal('100.00'))


class OfferCompletionExtraTests(TestCase):
    def test_total_reward_property(self):
        from .models import OfferCompletion
        oc = OfferCompletion(
            reward_amount=Decimal('100.00'),
            bonus_amount=Decimal('20.00'),
        )
        self.assertEqual(oc.total_reward, Decimal('120.00'))

    def test_processing_time(self):
        from .models import OfferCompletion
        import datetime
        clicked   = timezone.now()
        completed = clicked + datetime.timedelta(seconds=45)
        oc = OfferCompletion(clicked_at=clicked, completed_at=completed)
        self.assertEqual(oc.processing_time_seconds, 45.0)


class WaterfallConfigTests(TestCase):
    def setUp(self):
        from .models import AdNetwork, AdCampaign, AdUnit
        self.net1 = AdNetwork.objects.create(network_type='admob',    display_name='AdMob',    priority=1)
        self.net2 = AdNetwork.objects.create(network_type='facebook', display_name='Facebook', priority=2)
        now       = timezone.now()
        camp      = AdCampaign.objects.create(
            name='WF Camp', total_budget=Decimal('1000'), pricing_model='cpm',
            start_date=now, status='active', bid_amount=Decimal('0.5'),
        )
        self.unit = AdUnit.objects.create(
            campaign=camp, name='WFUnit', ad_format='banner',
        )

    def test_waterfall_ordering(self):
        from .models import WaterfallConfig
        WaterfallConfig.objects.create(ad_unit=self.unit, ad_network=self.net2, priority=2, floor_ecpm=Decimal('1.00'))
        WaterfallConfig.objects.create(ad_unit=self.unit, ad_network=self.net1, priority=1, floor_ecpm=Decimal('2.00'))
        entries = WaterfallConfig.objects.filter(ad_unit=self.unit).order_by('priority')
        self.assertEqual(entries[0].ad_network, self.net1)
        self.assertEqual(entries[1].ad_network, self.net2)

    def test_floor_ecpm_constraint(self):
        from .models import WaterfallConfig
        wf = WaterfallConfig(ad_unit=self.unit, ad_network=self.net1, priority=1, floor_ecpm=Decimal('0.50'))
        self.assertEqual(wf.floor_ecpm, Decimal('0.50'))


class FloorPriceConfigTests(TestCase):
    def setUp(self):
        from .models import AdNetwork
        self.net = AdNetwork.objects.create(network_type='unity', display_name='Unity', priority=3)

    def test_floor_price_creation(self):
        from .models import FloorPriceConfig
        fp = FloorPriceConfig.objects.create(
            ad_network=self.net, country='US', device_type='mobile',
            ad_format='rewarded_video', floor_ecpm=Decimal('5.00'),
        )
        self.assertEqual(fp.floor_ecpm, Decimal('5.00'))
        self.assertEqual(fp.country, 'US')


class AdPlacementTests(TestCase):
    def setUp(self):
        from .models import AdNetwork, AdCampaign, AdUnit
        net  = AdNetwork.objects.create(network_type='ironsource', display_name='IS', priority=4)
        now  = timezone.now()
        camp = AdCampaign.objects.create(
            name='Placement Camp', total_budget=Decimal('500'), pricing_model='cpc',
            start_date=now, status='active', bid_amount=Decimal('0.05'),
        )
        self.unit = AdUnit.objects.create(
            campaign=camp, ad_network=net, name='PlUnit', ad_format='interstitial',
        )

    def test_placement_creation(self):
        from .models import AdPlacement
        pl = AdPlacement.objects.create(
            ad_unit=self.unit, screen_name='home', position='fullscreen',
            refresh_rate=0, frequency_cap=3,
        )
        self.assertEqual(pl.screen_name, 'home')
        self.assertEqual(pl.position, 'fullscreen')


class PointLedgerSnapshotTests(TestCase):
    def setUp(self):
        self.user = make_user(coin_balance=Decimal('250.00'))

    def test_snapshot_creation(self):
        from .models import PointLedgerSnapshot
        snap = PointLedgerSnapshot.objects.create(
            user=self.user, snapshot_date=timezone.now().date(),
            balance=Decimal('250.00'), total_earned=Decimal('500.00'),
            total_spent=Decimal('250.00'),
        )
        self.assertEqual(snap.balance, Decimal('250.00'))


class UserSegmentTests(TestCase):
    def test_segment_creation(self):
        from .models import UserSegment
        seg = UserSegment.objects.create(
            name='High Earners', slug='high-earners',
            segment_type='behavioral', is_active=True,
        )
        self.assertEqual(seg.name, 'High Earners')
        self.assertEqual(seg.member_count, 0)

    def test_segment_membership(self):
        from .models import UserSegment, UserSegmentMembership
        seg  = UserSegment.objects.create(name='VIP', slug='vip', segment_type='manual')
        user = make_user('vip_user')
        mem  = UserSegmentMembership.objects.create(segment=seg, user=user, score=Decimal('9.5'))
        self.assertEqual(mem.score, Decimal('9.5'))


class ImpressionClickConversionLogTests(TestCase):
    def setUp(self):
        from .models import AdNetwork, AdCampaign, AdUnit
        net  = AdNetwork.objects.create(network_type='tapjoy', display_name='Tapjoy', priority=5)
        now  = timezone.now()
        self.camp = AdCampaign.objects.create(
            name='Log Camp', total_budget=Decimal('2000'), pricing_model='cpm',
            start_date=now, status='active', bid_amount=Decimal('0.10'),
        )
        self.unit = AdUnit.objects.create(campaign=self.camp, ad_network=net,
                                           name='LogUnit', ad_format='native')

    def test_impression_creation(self):
        from .models import ImpressionLog
        imp = ImpressionLog.objects.create(
            ad_unit=self.unit, country='BD', device_type='mobile',
            ecpm=Decimal('1.50'), revenue=Decimal('0.00150000'),
        )
        self.assertEqual(imp.country, 'BD')
        self.assertTrue(imp.is_viewable)

    def test_click_creation(self):
        from .models import ClickLog
        clk = ClickLog.objects.create(
            ad_unit=self.unit, country='BD', is_valid=True,
            revenue=Decimal('0.00500000'),
        )
        self.assertTrue(clk.is_valid)

    def test_conversion_creation(self):
        from .models import ConversionLog
        cnv = ConversionLog.objects.create(
            campaign=self.camp, conversion_type='install',
            payout=Decimal('1.50'), is_verified=True,
        )
        self.assertEqual(cnv.conversion_type, 'install')
        self.assertEqual(cnv.payout, Decimal('1.50'))


class InAppPurchaseExtraTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_iap_creation(self):
        from .models import InAppPurchase
        purchase = InAppPurchase.objects.create(
            user=self.user, product_id='coins_1000', product_name='1000 Coins Pack',
            amount=Decimal('99.00'), currency='BDT',
            status='completed', gateway='bkash',
            coins_granted=Decimal('1000.00'),
        )
        self.assertEqual(purchase.status, 'completed')
        self.assertEqual(purchase.coins_granted, Decimal('1000.00'))


class AchievementExtraTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_achievement_creation(self):
        from .models import Achievement
        ach = Achievement.objects.create(
            user=self.user, achievement_key='first_offer',
            title='First Offer Completed', category='offer',
            xp_reward=50, coin_reward=Decimal('25.00'),
        )
        self.assertEqual(ach.category, 'offer')
        self.assertEqual(ach.xp_reward, 50)

    def test_achievement_unique_per_user(self):
        from .models import Achievement
        from django.db import IntegrityError
        Achievement.objects.create(
            user=self.user, achievement_key='dup_test',
            title='Dup', category='earning',
        )
        with self.assertRaises(IntegrityError):
            Achievement.objects.create(
                user=self.user, achievement_key='dup_test',
                title='Dup2', category='earning',
            )


class LeaderboardTests(TestCase):
    def setUp(self):
        self.user1 = make_user('leader1')
        self.user2 = make_user('leader2')

    def test_leaderboard_rank_creation(self):
        from .models import LeaderboardRank
        r1 = LeaderboardRank.objects.create(
            user=self.user1, scope='global', board_type='earnings',
            rank=1, score=Decimal('10000.00'),
        )
        r2 = LeaderboardRank.objects.create(
            user=self.user2, scope='global', board_type='earnings',
            rank=2, score=Decimal('5000.00'),
        )
        top = LeaderboardRank.objects.filter(
            scope='global', board_type='earnings'
        ).order_by('rank')
        self.assertEqual(top[0].user, self.user1)
        self.assertEqual(top[1].user, self.user2)


class SpinWheelConfigTests(TestCase):
    def test_spin_wheel_config_creation(self):
        from .models import SpinWheelConfig
        cfg = SpinWheelConfig.objects.create(
            name='Daily Wheel', wheel_type='spin_wheel',
            is_active=True, daily_limit=3, cost_per_spin=Decimal('0.00'),
        )
        self.assertEqual(cfg.daily_limit, 3)

    def test_prize_config_creation(self):
        from .models import SpinWheelConfig, PrizeConfig
        cfg = SpinWheelConfig.objects.create(
            name='Prize Wheel', wheel_type='spin_wheel', is_active=True,
        )
        prize = PrizeConfig.objects.create(
            wheel_config=cfg, prize_type='coins', label='100 Coins',
            prize_value=Decimal('100.00'), weight=20, color='#4CAF50',
        )
        self.assertEqual(prize.weight, 20)
        self.assertEqual(prize.prize_value, Decimal('100.00'))


class ABTestAssignmentTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_ab_test_assignment(self):
        from .models import ABTest, ABTestAssignment
        test = ABTest.objects.create(
            name='Button Color Test', status='running',
            variants=[{'name': 'A', 'weight': 50}, {'name': 'B', 'weight': 50}],
            traffic_split=100,
        )
        assignment, created = ABTestAssignment.objects.get_or_create(
            test=test, user=self.user,
            defaults={'variant_name': 'A'},
        )
        self.assertIn(assignment.variant_name, ['A', 'B'])

    def test_assignment_unique_per_test_user(self):
        from .models import ABTest, ABTestAssignment
        from django.db import IntegrityError
        test = ABTest.objects.create(
            name='Unique Test', status='running',
            variants=[{'name': 'A', 'weight': 100}],
        )
        ABTestAssignment.objects.create(test=test, user=self.user, variant_name='A')
        with self.assertRaises(IntegrityError):
            ABTestAssignment.objects.create(test=test, user=self.user, variant_name='A')


class PostbackLogTests(TestCase):
    def test_postback_creation(self):
        from .models import PostbackLog
        pb = PostbackLog.objects.create(
            network_name='adgem', http_method='POST',
            endpoint_path='/api/monetization_tools/postback/',
            source_ip='1.2.3.4', status='received',
            query_params={'offer_id': '123', 'reward': '100'},
        )
        self.assertEqual(pb.status, 'received')
        self.assertEqual(pb.network_name, 'adgem')


class ReferralLinkTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_referral_link_and_commission(self):
        from .models import ReferralProgram, ReferralLink, ReferralCommission
        program = ReferralProgram.objects.create(
            name='Standard', slug='standard', is_active=True,
            l1_commission_pct=Decimal('10.00'),
        )
        link = ReferralLink.objects.create(
            program=program, user=self.user, code='TESTCODE01',
        )
        self.assertEqual(link.code, 'TESTCODE01')
        referee = make_user('ref_user2')
        commission = ReferralCommission.objects.create(
            referrer=self.user, referee=referee, program=program,
            referral_link=link, level=1, commission_type='offer_earn',
            base_amount=Decimal('100.00'), commission_pct=Decimal('10.00'),
            commission_coins=Decimal('10.00'),
        )
        self.assertEqual(commission.commission_coins, Decimal('10.00'))


class CouponUsageTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_coupon_usage_creation(self):
        from .models import Coupon, CouponUsage
        coupon = Coupon.objects.create(
            code='USAGE10', name='Usage Test', coupon_type='coin_grant',
            coin_amount=Decimal('50.00'), is_active=True,
        )
        usage = CouponUsage.objects.create(
            coupon=coupon, user=self.user, coins_granted=Decimal('50.00'),
        )
        self.assertEqual(usage.coins_granted, Decimal('50.00'))


class RecurringBillingTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_recurring_billing_creation(self):
        from .models import SubscriptionPlan, UserSubscription, RecurringBilling
        plan = SubscriptionPlan.objects.create(
            name='Monthly', slug='monthly-test', price=Decimal('199.00'),
            currency='BDT', interval='monthly',
        )
        now = timezone.now()
        sub = UserSubscription.objects.create(
            user=self.user, plan=plan, status='active',
            started_at=now, current_period_start=now,
            current_period_end=now + timezone.timedelta(days=30),
        )
        billing = RecurringBilling.objects.create(
            subscription=sub, scheduled_at=now + timezone.timedelta(days=30),
            amount=Decimal('199.00'), currency='BDT', status='scheduled',
        )
        self.assertEqual(billing.status, 'scheduled')
        self.assertEqual(billing.amount, Decimal('199.00'))


class MonetizationNotificationTemplateTests(TestCase):
    def test_template_render(self):
        from .models import MonetizationNotificationTemplate
        tmpl = MonetizationNotificationTemplate(
            event_type='reward_credited', channel='in_app',
            name='Reward Notification', language='bn',
            body_template='আপনার {{amount}} কয়েন যোগ হয়েছে, {{user_name}}!',
        )
        rendered = tmpl.render({'amount': '100', 'user_name': 'Rahim'})
        self.assertIn('100', rendered)
        self.assertIn('Rahim', rendered)

    def test_template_creation(self):
        from .models import MonetizationNotificationTemplate
        tmpl = MonetizationNotificationTemplate.objects.create(
            event_type='offer_approved', channel='push', name='Offer Done',
            body_template='Offer completed! You earned {{reward}} coins.',
            language='en', is_active=True,
        )
        self.assertTrue(tmpl.is_active)


class UserLevelExtraTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_level_up_flag(self):
        from .models import UserLevel
        lvl = UserLevel.objects.create(
            user=self.user, current_xp=90, xp_to_next_level=100
        )
        levelled = lvl.add_xp(20)
        self.assertTrue(levelled)
        self.assertEqual(lvl.current_level, 2)

    def test_no_level_up(self):
        from .models import UserLevel
        lvl = UserLevel.objects.create(
            user=make_user('lvl_user2'), current_xp=10, xp_to_next_level=100
        )
        levelled = lvl.add_xp(30)
        self.assertFalse(levelled)
        self.assertEqual(lvl.current_xp, 40)


class RevenueDailySummaryTests(TestCase):
    def test_revenue_summary_creation(self):
        from .models import RevenueDailySummary
        summary = RevenueDailySummary.objects.create(
            date=timezone.now().date(),
            impressions=10000, clicks=300, conversions=15,
            revenue_cpm=Decimal('50.00'), revenue_cpc=Decimal('30.00'),
            total_revenue=Decimal('80.00'),
            ecpm=Decimal('8.0000'), ctr=Decimal('3.0000'), fill_rate=Decimal('85.00'),
        )
        self.assertEqual(summary.total_revenue, Decimal('80.00'))
        self.assertEqual(summary.ecpm, Decimal('8.0000'))


class PaymentTransactionTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_payment_transaction_creation(self):
        from .models import PaymentTransaction
        txn = PaymentTransaction.objects.create(
            user=self.user, gateway='bkash', amount=Decimal('199.00'),
            currency='BDT', status='success', purpose='subscription',
        )
        self.assertEqual(txn.status, 'success')
        self.assertEqual(txn.gateway, 'bkash')
        self.assertIsNotNone(txn.txn_id)


class SpinWheelLogTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_spin_wheel_log_creation(self):
        from .models import SpinWheelLog
        log = SpinWheelLog.objects.create(
            user=self.user, log_type='spin_wheel',
            prize_type='coins', prize_value=Decimal('100.00'),
            result_label='100 Coins!', is_credited=True,
        )
        self.assertEqual(log.prize_type, 'coins')
        self.assertTrue(log.is_credited)

    def test_no_prize_log(self):
        from .models import SpinWheelLog
        log = SpinWheelLog.objects.create(
            user=self.user, log_type='scratch_card',
            prize_type='no_prize', prize_value=Decimal('0.00'),
        )
        self.assertEqual(log.prize_value, Decimal('0.00'))


class EnumsCompletenessTests(TestCase):
    """Verify all required enum classes exist."""

    def test_all_enums_importable(self):
        from . import enums
        required = [
            'CampaignStatus', 'PricingModel', 'AdFormat', 'AdNetworkType',
            'PlacementPosition', 'OfferType', 'OfferStatus', 'OfferCompletionStatus',
            'RewardTransactionType', 'SubscriptionInterval', 'SubscriptionStatus',
            'PaymentGateway', 'PaymentStatus', 'PaymentPurpose',
            'AchievementCategory', 'LeaderboardScope', 'LeaderboardType',
            'SpinWheelType', 'PrizeType', 'ABTestStatus', 'WinnerCriteria',
            'ConversionType', 'BillingStatus', 'PayoutMethodType', 'PayoutRequestStatus',
            'ReferralCommissionType', 'FraudAlertType', 'FraudSeverity', 'FraudResolution',
            'RevenueGoalPeriod', 'RevenueGoalType', 'PublisherAccountType', 'PublisherStatus',
            'NotificationEventType', 'NotificationChannel', 'PostbackStatus',
            'CreativeType', 'CreativeStatus', 'SegmentType', 'FlashSaleType',
        ]
        for name in required:
            self.assertTrue(hasattr(enums, name), f"Missing enum: {name}")


class ExceptionsCompletenessTests(TestCase):
    """Verify all required exception classes exist."""

    def test_all_exceptions_importable(self):
        from . import exceptions
        required = [
            'MonetizationBaseException', 'CampaignBudgetExceeded', 'OfferNotAvailable',
            'OfferAlreadyCompleted', 'InsufficientBalance', 'PaymentFailed',
            'SubscriptionAlreadyActive', 'SpinWheelDailyLimitReached',
            'PayoutRequestFailed', 'PayoutMethodNotVerified', 'PayoutMinimumNotMet',
            'CouponInvalid', 'CouponAlreadyUsed', 'ReferralProgramNotActive',
            'FlashSaleExpired', 'PublisherAccountSuspended', 'UserAccountBlocked',
            'FraudThresholdExceeded', 'CreativePendingReview', 'ReportDateRangeTooLarge',
        ]
        for name in required:
            self.assertTrue(hasattr(exceptions, name), f"Missing exception: {name}")


class HooksCompletenessTests(TestCase):
    """Verify all hook constants are defined."""

    def test_all_hooks_defined(self):
        from . import hooks
        required = [
            'HOOK_OFFER_STARTED', 'HOOK_OFFER_APPROVED', 'HOOK_REWARD_CREDITED',
            'HOOK_SUBSCRIPTION_NEW', 'HOOK_PAYMENT_SUCCESS', 'HOOK_LEVEL_UP',
            'HOOK_REFERRAL_EARNED', 'HOOK_PAYOUT_REQUESTED', 'HOOK_PAYOUT_PAID',
            'HOOK_COUPON_REDEEMED', 'HOOK_FLASH_SALE_STARTED', 'HOOK_FRAUD_ALERT_CREATED',
            'HOOK_GOAL_ACHIEVED', 'HOOK_CREATIVE_APPROVED', 'HOOK_DAILY_CHECK_IN',
            'HOOK_STREAK_MILESTONE', 'HOOK_AB_TEST_WINNER',
        ]
        for name in required:
            self.assertTrue(hasattr(hooks, name), f"Missing hook: {name}")


class ValidatorsTests(TestCase):
    """Test validator functions."""

    def test_coupon_code_valid(self):
        from .validators import validate_coupon_code
        # Should not raise
        validate_coupon_code('SAVE10')
        validate_coupon_code('PROMO2025')

    def test_coupon_code_invalid(self):
        from .validators import validate_coupon_code
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_coupon_code('ab')  # too short

    def test_flash_sale_multiplier_valid(self):
        from .validators import validate_flash_sale_multiplier
        validate_flash_sale_multiplier(2.0)

    def test_flash_sale_multiplier_invalid(self):
        from .validators import validate_flash_sale_multiplier
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_flash_sale_multiplier(0.5)

    def test_payout_account_number_valid(self):
        from .validators import validate_payout_account_number
        validate_payout_account_number('01711111111')

    def test_payout_account_number_invalid(self):
        from .validators import validate_payout_account_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_payout_account_number('12')


class UtilsTests(TestCase):
    """Test utility functions."""

    def test_calculate_arpu(self):
        from .utils import calculate_arpu
        result = calculate_arpu(Decimal('10000.00'), 500)
        self.assertEqual(result, Decimal('20.0000'))

    def test_calculate_roas(self):
        from .utils import calculate_roas
        result = calculate_roas(Decimal('500.00'), Decimal('100.00'))
        self.assertEqual(result, Decimal('5.0000'))

    def test_calculate_fill_rate(self):
        from .utils import calculate_fill_rate
        result = calculate_fill_rate(800, 1000)
        self.assertEqual(result, Decimal('80.0000'))

    def test_format_coins(self):
        from .utils import format_coins
        self.assertEqual(format_coins(Decimal('1500.00')), '1,500')

    def test_format_usd(self):
        from .utils import format_usd
        self.assertEqual(format_usd(Decimal('1234.56')), '$1,234.56')

    def test_mask_account_number(self):
        from .utils import mask_account_number
        self.assertEqual(mask_account_number('01711111111'), '0171****111')

    def test_safe_decimal(self):
        from .utils import safe_decimal
        self.assertEqual(safe_decimal('99.99'), Decimal('99.99'))
        self.assertEqual(safe_decimal('bad', Decimal('0')), Decimal('0'))

    def test_generate_unique_code(self):
        from .utils import generate_unique_code
        code = generate_unique_code(prefix='REF', length=8)
        self.assertTrue(code.startswith('REF'))
        self.assertEqual(len(code), 11)  # REF + 8 chars
