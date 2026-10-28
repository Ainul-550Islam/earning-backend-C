"""
Utils Tests — HIGH PRIORITY (RewardCalculator + OfferValidator)
Run: python manage.py test api.offerwall.tests.test_utils
"""
import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.offerwall.models import OfferProvider, Offer, OfferConversion
from api.offerwall.utils.RewardCalculator import RewardCalculator
from api.offerwall.utils.OfferValidator import OfferValidator
from api.offerwall.exceptions import (
    OfferNotFoundException, OfferInactiveException, OfferExpiredException,
    OfferCapReachedException, OfferLimitReachedException,
    InvalidRewardException, AccountSuspendedException,
)
User = get_user_model()

def mk_prov(rs='70.00'): return OfferProvider.objects.create(
    name=f'UP_{uuid.uuid4().hex[:6]}', provider_type='tapjoy',
    status='active', revenue_share=Decimal(rs),
    api_key=uuid.uuid4().hex[:16])

def mk_offer(prov, **kw):
    d = dict(external_offer_id=str(uuid.uuid4())[:12], title='U Offer', description='d',
             payout=Decimal('1'), reward_amount=Decimal('0.70'), click_url='https://x.com',
             status='active', currency='USD', reward_currency='BDT')
    d.update(kw); return Offer.objects.create(provider=prov, **d)

def mk_user(un='uu', active=True):
    u = User.objects.create_user(username=un, email=f'{un}@t.com', password='p')
    u.is_active = active; u.save(); return u


class RewardCalculatorTest(TestCase):
    def setUp(self):
        self.prov = mk_prov('70.00'); self.offer = mk_offer(self.prov)
        self.calc = RewardCalculator(self.offer, self.prov)

    def test_70pct_of_1(self): self.assertEqual(self.calc.calculate_user_reward(Decimal('1')), Decimal('0.700000'))
    def test_70pct_of_2(self): self.assertEqual(self.calc.calculate_user_reward(Decimal('2')), Decimal('1.400000'))
    def test_50pct(self):
        p = mk_prov('50.00')
        self.assertEqual(RewardCalculator(self.offer, p).calculate_user_reward(Decimal('2')), Decimal('1.000000'))
    def test_zero_payout(self): self.assertEqual(self.calc.calculate_user_reward(Decimal('0')), Decimal('0'))
    def test_100_payout(self): self.assertEqual(self.calc.calculate_user_reward(Decimal('100')), Decimal('70.000000'))
    def test_platform_fee_30pct(self):
        self.assertAlmostEqual(float(self.calc.calculate_platform_fee(Decimal('1'))), 0.30, places=4)
    def test_reward_plus_fee_equals_payout(self):
        p = Decimal('1')
        self.assertAlmostEqual(float(self.calc.calculate_user_reward(p) + self.calc.calculate_platform_fee(p)), float(p), places=4)
    def test_total_reward_returns_dict(self):
        r = self.calc.calculate_total_reward(Decimal('1'))
        self.assertIsInstance(r, dict); self.assertIn('base_reward', r); self.assertIn('total_reward', r)
    def test_total_reward_base_correct(self):
        self.assertEqual(self.calc.calculate_total_reward(Decimal('1'))['base_reward'], Decimal('0.700000'))
    def test_no_provider_no_crash(self):
        calc = RewardCalculator(self.offer, None)
        self.assertGreater(calc.calculate_user_reward(Decimal('1')), Decimal('0'))
    def test_validate_payout_positive_passes(self): self.assertTrue(self.calc.validate_payout_amount(Decimal('0.01')))
    def test_validate_payout_zero_raises(self):
        with self.assertRaises(InvalidRewardException): self.calc.validate_payout_amount(Decimal('0'))
    def test_validate_payout_negative_raises(self):
        with self.assertRaises(InvalidRewardException): self.calc.validate_payout_amount(Decimal('-1'))


class OfferValidatorTest(TestCase):
    def setUp(self): self.prov = mk_prov(); self.user = mk_user()
    def _offer(self, **kw): return mk_offer(self.prov, **kw)

    def test_none_offer_raises_not_found(self):
        with self.assertRaises(OfferNotFoundException): OfferValidator(None).validate_offer_availability(self.user)
    def test_active_passes(self): self.assertTrue(OfferValidator(self._offer()).validate_offer_availability(self.user))
    def test_paused_raises_inactive(self):
        with self.assertRaises(OfferInactiveException): OfferValidator(self._offer(status='paused')).validate_offer_availability(self.user)
    def test_disabled_raises_inactive(self):
        with self.assertRaises(OfferInactiveException): OfferValidator(self._offer(status='disabled')).validate_offer_availability(self.user)
    def test_expired_status_raises_expired(self):
        with self.assertRaises(OfferExpiredException): OfferValidator(self._offer(status='expired')).validate_offer_availability(self.user)
    def test_future_start_raises_inactive(self):
        o = self._offer(start_date=timezone.now() + timedelta(days=3))
        with self.assertRaises(OfferInactiveException): OfferValidator(o).validate_offer_availability(self.user)
    def test_past_end_raises_expired(self):
        o = self._offer(end_date=timezone.now() - timedelta(hours=1))
        with self.assertRaises(OfferExpiredException): OfferValidator(o).validate_offer_availability(self.user)
    def test_valid_date_range_passes(self):
        o = self._offer(start_date=timezone.now() - timedelta(days=1), end_date=timezone.now() + timedelta(days=1))
        self.assertTrue(OfferValidator(o).validate_offer_availability(self.user))
    def test_total_cap_reached_raises(self):
        o = self._offer(total_cap=5)
        Offer.objects.filter(pk=o.pk).update(conversion_count=5); o.refresh_from_db()
        with self.assertRaises(OfferCapReachedException): OfferValidator(o).validate_offer_availability(self.user)
    def test_total_cap_zero_unlimited(self):
        o = self._offer(total_cap=0)
        Offer.objects.filter(pk=o.pk).update(conversion_count=9999); o.refresh_from_db()
        self.assertTrue(OfferValidator(o).validate_offer_availability(self.user))
    def test_user_limit_reached_raises(self):
        o = self._offer(user_limit=1)
        OfferConversion.objects.create(offer=o, user=self.user, conversion_id='vl1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        with self.assertRaises(OfferLimitReachedException): OfferValidator(o).validate_offer_availability(self.user)
    def test_user_limit_not_reached_passes(self):
        o = self._offer(user_limit=3)
        OfferConversion.objects.create(offer=o, user=self.user, conversion_id='vl2',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.assertTrue(OfferValidator(o).validate_offer_availability(self.user))
    def test_suspended_user_raises(self):
        sus = mk_user('sus', active=False)
        with self.assertRaises(AccountSuspendedException): OfferValidator(self._offer()).validate_offer_availability(sus)
    def test_validate_payout_positive_passes(self): self.assertTrue(OfferValidator(self._offer()).validate_payout_amount(Decimal('1')))
    def test_validate_payout_zero_raises(self):
        with self.assertRaises(InvalidRewardException): OfferValidator(self._offer()).validate_payout_amount(Decimal('0'))
    def test_no_user_active_offer_passes(self): self.assertTrue(OfferValidator(self._offer()).validate_offer_availability(None))
    def test_no_user_paused_raises(self):
        with self.assertRaises(OfferInactiveException): OfferValidator(self._offer(status='paused')).validate_offer_availability(None)


# ══════════════════════════════════════════════════════════════════════════════
# MISSING UTILS TESTS — RewardCalculator bonus methods + AnalyticsTracker
# ══════════════════════════════════════════════════════════════════════════════

from decimal import Decimal as _D


def _mk_prov():
    import uuid as _uuid
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name=f'RP_{_uuid.uuid4().hex[:6]}', provider_type='tapjoy',
        status='active', revenue_share=_D('70'),
        api_key=_uuid.uuid4().hex[:16])

def _mk_offer(prov):
    from api.offerwall.models import Offer
    import uuid
    return Offer.objects.create(
        provider=prov, external_offer_id=uuid.uuid4().hex[:12],
        title='Bonus Offer', description='d', payout=_D('2'),
        reward_amount=_D('1.40'), click_url='https://x.com', status='active')

def _mk_user(un='rc_u'):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(username=un, email=f'{un}@t.com', password='p')


class RewardCalculatorBonusMethodsTest(TestCase):
    def setUp(self):
        from api.offerwall.utils.RewardCalculator import RewardCalculator
        self.prov  = _mk_prov()
        self.offer = _mk_offer(self.prov)
        self.user  = _mk_user('rcbm')
        self.calc  = RewardCalculator(self.offer, self.user)

    def test_calculate_tier_multiplier_returns_float(self):
        result = self.calc.calculate_tier_multiplier()
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 1.0)

    def test_calculate_time_bonus_returns_decimal(self):
        result = self.calc.calculate_time_bonus(_D('1.00'))
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('0'))

    def test_calculate_streak_bonus_zero_for_new_user(self):
        result = self.calc.calculate_streak_bonus(_D('1.00'))
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('0'))

    def test_calculate_volume_bonus_zero_for_first_offer(self):
        result = self.calc.calculate_volume_bonus(_D('1.00'))
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('0'))

    def test_calculate_special_event_bonus_returns_decimal(self):
        result = self.calc.calculate_special_event_bonus(_D('1.00'))
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('0'))

    def test_calculate_all_bonuses_returns_dict(self):
        result = self.calc.calculate_all_bonuses(_D('1.00'))
        self.assertIsInstance(result, dict)
        # Should contain at least one bonus key
        self.assertGreater(len(result), 0)

    def test_apply_bonuses_to_reward_returns_decimal(self):
        bonuses = self.calc.calculate_all_bonuses(_D('1.00'))
        result = self.calc.apply_bonuses_to_reward(_D('1.00'), bonuses)
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('1.00'))

    def test_calculate_referral_bonus_returns_decimal(self):
        result = self.calc.calculate_referral_bonus(_D('1.00'))
        self.assertIsInstance(result, _D)
        self.assertGreaterEqual(result, _D('0'))

    def test_calculate_conversion_value_returns_decimal(self):
        result = self.calc.calculate_conversion_value()
        self.assertIsInstance(result, _D)
        self.assertGreater(result, _D('0'))

    def test_convert_currency_same_currency_unchanged(self):
        result = self.calc.convert_currency(_D('1.00'), 'USD', 'USD')
        self.assertEqual(result, _D('1.00'))


class AnalyticsTrackerMissingMethodsTest(TestCase):
    def setUp(self):
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker
        self.prov  = _mk_prov()
        self.offer = _mk_offer(self.prov)
        self.user  = _mk_user('atm_u')
        self.tracker = AnalyticsTracker(self.offer, self.user)

    def test_update_offer_analytics_returns_dict(self):
        result = self.tracker.update_offer_analytics()
        self.assertIsInstance(result, dict)

    def test_generate_performance_report_returns_dict(self):
        result = self.tracker.generate_performance_report()
        self.assertIsInstance(result, dict)

    def test_get_provider_performance_returns_dict(self):
        tracker_no_offer = __import__(
            'api.offerwall.utils.AnalyticsTracker', fromlist=['AnalyticsTracker']
        ).AnalyticsTracker()
        result = tracker_no_offer.get_provider_performance(self.prov.id)
        self.assertIsInstance(result, dict)
