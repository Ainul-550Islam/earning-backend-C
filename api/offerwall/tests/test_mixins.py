"""
Mixin Tests — OfferFilterMixin, OfferSortMixin, CacheMixin, RateLimitMixin, ResponseMixin
Run: python manage.py test api.offerwall.tests.test_mixins
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.response import Response
from rest_framework.views import APIView
from api.offerwall.models import OfferProvider, OfferCategory, Offer, OfferConversion

User = get_user_model()
rf   = RequestFactory()


def mk_prov(**kw):
    d = dict(name='MixProv', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
    d.update(kw); return OfferProvider.objects.create(**d)

def mk_cat(slug=None):
    s = slug or f'mix-{uuid.uuid4().hex[:6]}'
    import uuid as _uu; return OfferCategory.objects.create(name=f'MixCat_{_uu.uuid4().hex[:6]}', slug=s, is_active=True)

def mk_offer(prov, **kw):
    d = dict(external_offer_id=str(uuid.uuid4())[:12], title='Mix Offer', description='d',
             payout=Decimal('1'), reward_amount=Decimal('0.70'),
             click_url='https://x.com', status='active',
             platform='android', countries=['BD'], offer_type='app_install',
             difficulty='easy', currency='USD', reward_currency='BDT')
    d.update(kw); return Offer.objects.create(provider=prov, **d)

def mk_user(un='mxu'):
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


# ── OfferFilterMixin ──────────────────────────────────────────────────────────

class OfferFilterMixinTest(TestCase):

    def setUp(self):
        from api.offerwall.mixins import OfferFilterMixin
        self.prov  = mk_prov()
        self.cat   = mk_cat()
        self.mixin = OfferFilterMixin()

    def qs(self): return Offer.objects.all()

    def test_filter_by_status_active(self):
        mk_offer(self.prov, status='active')
        mk_offer(self.prov, status='paused')
        result = self.mixin.filter_by_status(self.qs(), 'active')
        for o in result: self.assertEqual(o.status, 'active')

    def test_filter_by_status_paused(self):
        mk_offer(self.prov, status='paused')
        result = self.mixin.filter_by_status(self.qs(), 'paused')
        for o in result: self.assertEqual(o.status, 'paused')

    def test_filter_by_platform_android(self):
        mk_offer(self.prov, platform='android')
        mk_offer(self.prov, platform='ios')
        result = self.mixin.filter_by_platform(self.qs(), 'android')
        platforms = [o.platform for o in result]
        self.assertIn('android', platforms)
        self.assertNotIn('ios', platforms)

    def test_filter_by_platform_all_includes_all_platform_offers(self):
        mk_offer(self.prov, platform='all', external_offer_id='all_plat_001')
        result = self.mixin.filter_by_platform(self.qs(), 'android')
        platforms = [o.platform for o in result]
        # 'all' platform offers should show up for any platform filter
        self.assertIn('all', platforms)

    def test_filter_by_country_includes_offer(self):
        mk_offer(self.prov, countries=['BD', 'IN'], external_offer_id='country_001')
        result = self.mixin.filter_by_country(self.qs(), 'BD')
        country_lists = [o.countries for o in result]
        found = any('BD' in cl for cl in country_lists if cl)
        self.assertTrue(found)

    def test_filter_by_country_excludes_excluded_country(self):
        mk_offer(self.prov, countries=['BD'], excluded_countries=['US'],
                 external_offer_id='excl_001')
        result = self.mixin.filter_by_country(self.qs(), 'US')
        for o in result:
            self.assertNotIn('US', o.excluded_countries or [])

    def test_filter_by_category(self):
        cat2 = mk_cat()
        mk_offer(self.prov, category=self.cat, external_offer_id='cat_f001')
        mk_offer(self.prov, category=cat2, external_offer_id='cat_f002')
        result = self.mixin.filter_by_category(self.qs(), self.cat.id)
        for o in result:
            self.assertEqual(o.category_id, self.cat.id)

    def test_filter_by_offer_type(self):
        mk_offer(self.prov, offer_type='survey', external_offer_id='type_srv')
        mk_offer(self.prov, offer_type='app_install', external_offer_id='type_app')
        result = self.mixin.filter_by_offer_type(self.qs(), 'survey')
        for o in result: self.assertEqual(o.offer_type, 'survey')

    def test_filter_by_payout_range_min(self):
        mk_offer(self.prov, payout=Decimal('0.50'), external_offer_id='pay_low')
        mk_offer(self.prov, payout=Decimal('2.00'), external_offer_id='pay_high')
        result = self.mixin.filter_by_payout_range(self.qs(), min_payout='1.00', max_payout=None)
        for o in result: self.assertGreaterEqual(float(o.payout), 1.00)

    def test_filter_by_payout_range_max(self):
        mk_offer(self.prov, payout=Decimal('0.50'), external_offer_id='pay_low2')
        mk_offer(self.prov, payout=Decimal('5.00'), external_offer_id='pay_high2')
        result = self.mixin.filter_by_payout_range(self.qs(), min_payout=None, max_payout='1.00')
        for o in result: self.assertLessEqual(float(o.payout), 1.00)

    def test_filter_featured_true(self):
        mk_offer(self.prov, is_featured=True,  external_offer_id='feat_t')
        mk_offer(self.prov, is_featured=False, external_offer_id='feat_f')
        result = self.mixin.filter_featured(self.qs(), True)
        for o in result: self.assertTrue(o.is_featured)

    def test_filter_featured_false(self):
        mk_offer(self.prov, is_featured=True,  external_offer_id='nfeat_t')
        mk_offer(self.prov, is_featured=False, external_offer_id='nfeat_f')
        result = self.mixin.filter_featured(self.qs(), False)
        for o in result: self.assertFalse(o.is_featured)

    def test_filter_available_for_user_excludes_completed(self):
        user = mk_user()
        offer = mk_offer(self.prov, user_limit=1, external_offer_id='avl_excl')
        OfferConversion.objects.create(
            offer=offer, user=user, conversion_id='mix_cv1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        result = self.mixin.filter_available_for_user(self.qs(), user)
        ids = [o.id for o in result]
        self.assertNotIn(offer.id, ids)


# ── OfferSortMixin ────────────────────────────────────────────────────────────

class OfferSortMixinTest(TestCase):

    def setUp(self):
        from api.offerwall.mixins import OfferSortMixin
        self.prov  = mk_prov(name='SortProv')
        self.mixin = OfferSortMixin()
        mk_offer(self.prov, payout=Decimal('1.00'), external_offer_id='sort_001')
        mk_offer(self.prov, payout=Decimal('3.00'), external_offer_id='sort_002')
        mk_offer(self.prov, payout=Decimal('2.00'), external_offer_id='sort_003')

    def qs(self): return Offer.objects.filter(provider=self.prov)

    def test_sort_by_payout_descending(self):
        result = list(self.mixin.sort_offers(self.qs(), 'payout'))
        payouts = [float(o.payout) for o in result]
        self.assertEqual(payouts, sorted(payouts, reverse=True))

    def test_sort_by_payout_ascending(self):
        result = list(self.mixin.sort_offers(self.qs(), 'payout_asc'))
        payouts = [float(o.payout) for o in result]
        self.assertEqual(payouts, sorted(payouts))

    def test_sort_by_quality_score(self):
        result = list(self.mixin.sort_offers(self.qs(), 'quality_score'))
        scores = [o.quality_score for o in result]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_sort_by_newest(self):
        result = list(self.mixin.sort_offers(self.qs(), 'newest'))
        dates = [o.created_at for o in result]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_sort_by_oldest(self):
        result = list(self.mixin.sort_offers(self.qs(), 'oldest'))
        dates = [o.created_at for o in result]
        self.assertEqual(dates, sorted(dates))

    def test_unknown_sort_falls_back_to_quality(self):
        result = list(self.mixin.sort_offers(self.qs(), 'nonexistent_sort'))
        self.assertEqual(len(result), 3)

    def test_sort_by_completion_rate(self):
        result = list(self.mixin.sort_offers(self.qs(), 'completion_rate'))
        rates = [o.completion_rate for o in result]
        self.assertEqual(rates, sorted(rates, reverse=True))


# ── CacheMixin ────────────────────────────────────────────────────────────────

class CacheMixinTest(TestCase):

    def setUp(self):
        from api.offerwall.mixins import CacheMixin
        self.mixin = CacheMixin()

    def test_set_and_get_cached_data(self):
        key  = 'test_cache_key_mix_001'
        data = {'offers': [1, 2, 3], 'total': 3}
        self.mixin.set_cached_data(key, data, timeout=60)
        result = self.mixin.get_cached_data(key)
        self.assertEqual(result, data)

    def test_get_missing_key_returns_default(self):
        result = self.mixin.get_cached_data('nonexistent_key_xyz', default='fallback')
        self.assertEqual(result, 'fallback')

    def test_get_missing_key_returns_none_by_default(self):
        result = self.mixin.get_cached_data('missing_key_abc_123')
        self.assertIsNone(result)

    def test_delete_cached_data(self):
        key = 'delete_test_key_001'
        self.mixin.set_cached_data(key, 'some_value', timeout=60)
        self.mixin.delete_cached_data(key)
        result = self.mixin.get_cached_data(key)
        self.assertIsNone(result)

    def test_get_cache_key_template(self):
        key = self.mixin.get_cache_key('offers:{0}:detail', 'abc123')
        self.assertEqual(key, 'offers:abc123:detail')

    def test_set_returns_true_on_success(self):
        result = self.mixin.set_cached_data('cache_set_test', 'val', timeout=60)
        self.assertTrue(result)


# ── RateLimitMixin ────────────────────────────────────────────────────────────

class RateLimitMixinTest(TestCase):

    def setUp(self):
        from api.offerwall.mixins import RateLimitMixin
        self.mixin = RateLimitMixin()
        self.user  = mk_user('rluser')

    def test_check_rate_limit_under_limit_allowed(self):
        result = self.mixin.check_rate_limit(self.user, 'test_action_rl', limit=10, period=3600)
        self.assertTrue(result)

    def test_check_rate_limit_over_limit_blocked(self):
        # Hit limit 5 times
        for _ in range(5):
            self.mixin.check_rate_limit(self.user, 'test_over_limit', limit=5, period=3600)
        # 6th should be blocked
        result = self.mixin.check_rate_limit(self.user, 'test_over_limit', limit=5, period=3600)
        self.assertFalse(result)

    def test_different_actions_have_separate_limits(self):
        for _ in range(3):
            self.mixin.check_rate_limit(self.user, 'action_alpha', limit=3, period=3600)
        # action_beta should still be allowed
        result = self.mixin.check_rate_limit(self.user, 'action_beta', limit=3, period=3600)
        self.assertTrue(result)

    def test_get_rate_limit_status_returns_dict(self):
        self.mixin.check_rate_limit(self.user, 'status_test', limit=10, period=3600)
        status = self.mixin.get_rate_limit_status(self.user, 'status_test')
        self.assertIsInstance(status, dict)
        self.assertIn('current', status)


# ── ResponseMixin ─────────────────────────────────────────────────────────────

class ResponseMixinTest(TestCase):

    def setUp(self):
        from api.offerwall.mixins import ResponseMixin
        self.mixin = ResponseMixin()

    def test_success_response_has_success_true(self):
        r = self.mixin.success_response({'key': 'value'})
        self.assertIsInstance(r, Response)
        self.assertTrue(r.data['success'])

    def test_success_response_has_data(self):
        r = self.mixin.success_response({'offers': [1, 2, 3]})
        self.assertEqual(r.data['data'], {'offers': [1, 2, 3]})

    def test_success_response_with_message(self):
        r = self.mixin.success_response({'id': 1}, message='Created!')
        self.assertEqual(r.data['message'], 'Created!')

    def test_error_response_has_success_false(self):
        r = self.mixin.error_response('Something went wrong')
        self.assertFalse(r.data['success'])

    def test_error_response_has_message(self):
        r = self.mixin.error_response('Offer not found')
        self.assertEqual(r.data['message'], 'Offer not found')

    def test_error_response_with_code(self):
        r = self.mixin.error_response('Rate limited', code='RATE_LIMIT_EXCEEDED')
        self.assertEqual(r.data.get('error_code'), 'RATE_LIMIT_EXCEEDED')

    def test_error_response_default_status_400(self):
        r = self.mixin.error_response('Bad input')
        self.assertEqual(r.status_code, 400)

    def test_success_response_default_status_200(self):
        r = self.mixin.success_response({'ok': True})
        self.assertEqual(r.status_code, 200)
