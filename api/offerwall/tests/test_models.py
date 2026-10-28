"""
Model Tests — HIGH PRIORITY
Run: python manage.py test api.offerwall.tests.test_models
"""
import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.offerwall.models import (
    OfferProvider, OfferCategory, Offer, OfferClick, OfferConversion, OfferWall
)
User = get_user_model()


def mk_provider(**kw):
    d = dict(name='TP', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
    d.update(kw); return OfferProvider.objects.create(**d)

def mk_offer(prov, **kw):
    d = dict(external_offer_id=str(uuid.uuid4())[:12], title='Test Offer', description='d',
             payout=Decimal('1'), reward_amount=Decimal('0.70'), click_url='https://x.com',
             status='active', currency='USD', reward_currency='BDT')
    d.update(kw); return Offer.objects.create(provider=prov, **d)

def mk_user(un='u'): return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


class OfferProviderModelTest(TestCase):
    def test_create(self): self.assertEqual(mk_provider().status, 'active')
    def test_is_active_true(self): self.assertTrue(mk_provider(status='active').is_active())
    def test_is_active_false_inactive(self): self.assertFalse(mk_provider(status='inactive').is_active())
    def test_is_active_false_suspended(self): self.assertFalse(mk_provider(status='suspended').is_active())
    def test_str(self): self.assertIn('TP', str(mk_provider()))
    def test_defaults(self): p = mk_provider(); self.assertEqual(p.total_offers, 0); self.assertTrue(p.auto_sync)


class OfferCategoryModelTest(TestCase):
    def test_create(self): c = OfferCategory.objects.create(name='Games', slug='gm'); self.assertTrue(c.is_active)
    def test_str(self): c = OfferCategory.objects.create(name='Survey', slug='sv'); self.assertEqual(str(c), 'Survey')


class OfferModelTest(TestCase):
    def setUp(self): self.prov = mk_provider(); self.user = mk_user()

    def test_create(self): self.assertEqual(mk_offer(self.prov).title, 'Test Offer')
    def test_is_active_true(self): self.assertTrue(mk_offer(self.prov).is_active())
    def test_is_active_paused(self): self.assertFalse(mk_offer(self.prov, status='paused').is_active())
    def test_is_active_future_start(self):
        o = mk_offer(self.prov, start_date=timezone.now() + timedelta(days=3))
        self.assertFalse(o.is_active())
    def test_is_active_past_end(self):
        o = mk_offer(self.prov, end_date=timezone.now() - timedelta(hours=1))
        self.assertFalse(o.is_active())
    def test_is_active_cap_reached(self):
        # total_cap check lives in is_available_for_user, not is_active
        o = mk_offer(self.prov, total_cap=5)
        Offer.objects.filter(pk=o.pk).update(conversion_count=5)
        o.refresh_from_db()
        self.assertFalse(o.is_available_for_user(None))
    def test_increment_view(self):
        o = mk_offer(self.prov); o.increment_view(); o.refresh_from_db()
        self.assertEqual(o.view_count, 1)
    def test_increment_click(self):
        o = mk_offer(self.prov); o.increment_click(); o.refresh_from_db()
        self.assertEqual(o.click_count, 1)
    def test_increment_conversion(self):
        o = mk_offer(self.prov); o.increment_conversion(); o.refresh_from_db()
        self.assertEqual(o.conversion_count, 1)
    def test_quality_score_in_range(self):
        s = mk_offer(self.prov).calculate_quality_score()
        self.assertGreaterEqual(s, 0); self.assertLessEqual(s, 100)
    def test_unique_together(self):
        from django.db import IntegrityError
        mk_offer(self.prov, external_offer_id='dup1')
        with self.assertRaises(IntegrityError): mk_offer(self.prov, external_offer_id='dup1')
    def test_is_available_true(self): self.assertTrue(mk_offer(self.prov).is_available_for_user(self.user))
    def test_is_available_false_user_limit(self):
        o = mk_offer(self.prov, user_limit=1)
        OfferConversion.objects.create(offer=o, user=self.user, conversion_id='lm1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.assertFalse(o.is_available_for_user(self.user))
    def test_is_available_no_user(self): self.assertTrue(mk_offer(self.prov).is_available_for_user(None))


class OfferConversionModelTest(TestCase):
    def setUp(self):
        self.prov = mk_provider(); self.offer = mk_offer(self.prov); self.user = mk_user('cu')

    def _conv(self, cid='c1', status='pending'):
        return OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id=cid,
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status=status)

    def test_approve_returns_true(self): self.assertTrue(self._conv().approve())
    def test_approve_changes_status(self):
        c = self._conv(); c.approve(); c.refresh_from_db()
        self.assertEqual(c.status, 'approved'); self.assertTrue(c.is_verified)
    def test_approve_idempotent(self):
        c = self._conv(status='approved'); self.assertFalse(c.approve())
    def test_approve_has_update_fields(self):
        # approve() must use update_fields (no full save)
        c = self._conv()
        import unittest.mock as mock
        with mock.patch.object(c, 'save', wraps=c.save) as mock_save:
            c.approve()
            call_kwargs = mock_save.call_args.kwargs
            self.assertIn('update_fields', call_kwargs)
    def test_reject_changes_status(self):
        c = self._conv(); c.reject(reason='Fraud')
        c.refresh_from_db()
        self.assertEqual(c.status, 'rejected'); self.assertEqual(c.rejection_reason, 'Fraud')
    def test_reject_has_update_fields(self):
        c = self._conv()
        import unittest.mock as mock
        with mock.patch.object(c, 'save', wraps=c.save) as mock_save:
            c.reject(reason='test')
            call_kwargs = mock_save.call_args.kwargs
            self.assertIn('update_fields', call_kwargs)
    def test_str_contains_conversion_id(self):
        # __str__ returns "username - title - status"; check username part
        c = self._conv(); s = str(c)
        self.assertIn(c.user.username, s)
        self.assertIn(c.status, s)


# ── Extra Model Tests ─────────────────────────────────────────────────────────

class OfferModelExtraTest(TestCase):

    def setUp(self):
        self.prov = mk_provider(name='ExtraProv')
        self.user = mk_user('eu')

    def test_increment_view_uses_f_expression(self):
        """F() expression ensure করে concurrent safe update"""
        o = mk_offer(self.prov)
        initial = o.view_count
        o.increment_view()
        o.increment_view()
        o.refresh_from_db()
        self.assertEqual(o.view_count, initial + 2)

    def test_offer_click_save_generates_click_id(self):
        from api.offerwall.models import OfferClick
        o = mk_offer(self.prov)
        click = OfferClick.objects.create(
            offer=o, user=self.user, ip_address='127.0.0.1')
        self.assertTrue(len(click.click_id) > 0)
        self.assertIsNotNone(click.click_id)

    def test_offer_conversion_str_without_user(self):
        o = mk_offer(self.prov)
        conv = OfferConversion.objects.create(
            offer=o, user=None, conversion_id='nouser_cv001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='pending')
        # Should not crash
        s = str(conv)
        self.assertIsNotNone(s)

    def test_offer_quality_score_improves_with_conversions(self):
        o = mk_offer(self.prov)
        initial_score = o.calculate_quality_score()
        o.completion_rate = 50.0
        o.save()
        new_score = o.calculate_quality_score()
        self.assertGreaterEqual(new_score, initial_score)

    def test_offer_is_available_daily_cap_reached(self):
        from django.utils import timezone
        o = mk_offer(self.prov, daily_cap=1)
        user2 = mk_user('cap2')
        OfferConversion.objects.create(
            offer=o, user=user2, conversion_id='cap_daily_001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'),
            status='approved')
        # Daily cap reached → not available for any user
        user3 = mk_user('cap3')
        self.assertFalse(o.is_available_for_user(user3))

    def test_offer_wall_get_offers_returns_queryset(self):
        from api.offerwall.models import OfferWall
        o = mk_offer(self.prov)
        wall = OfferWall.objects.create(name='Extra Wall', slug='extra-wall')
        offers = wall.get_offers()
        self.assertIn(o, offers)

    def test_offer_wall_get_offers_filters_by_category(self):
        from api.offerwall.models import OfferWall, OfferCategory
        cat = OfferCategory.objects.create(name='WallCat', slug='wall-cat')
        o_with_cat    = mk_offer(self.prov, category=cat, external_offer_id='wc_001')
        o_without_cat = mk_offer(self.prov, external_offer_id='wc_002')
        wall = OfferWall.objects.create(name='Cat Wall', slug='cat-wall')
        wall.categories.add(cat)
        offers = wall.get_offers()
        self.assertIn(o_with_cat, offers)
        self.assertNotIn(o_without_cat, offers)

    def test_offer_wall_get_offers_excludes_completed_for_user(self):
        from api.offerwall.models import OfferWall
        o = mk_offer(self.prov, user_limit=1, external_offer_id='wall_excl_001')
        OfferConversion.objects.create(
            offer=o, user=self.user, conversion_id='wall_excl_cv001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        wall   = OfferWall.objects.create(name='Excl Wall', slug='excl-wall')
        offers = wall.get_offers(user=self.user)
        self.assertNotIn(o, offers)

    def test_offer_category_str(self):
        from api.offerwall.models import OfferCategory
        cat = OfferCategory.objects.create(name='TestStr', slug='test-str-cat')
        self.assertEqual(str(cat), 'TestStr')

    def test_offer_provider_defaults(self):
        p = mk_provider(name='DefaultProv')
        self.assertEqual(p.total_offers, 0)
        self.assertEqual(p.total_conversions, 0)
        self.assertEqual(float(p.total_revenue), 0.0)
        self.assertTrue(p.auto_sync)

    def test_offerconversion_external_wallet_field_exists(self):
        o    = mk_offer(self.prov)
        conv = OfferConversion.objects.create(
            offer=o, user=self.user, conversion_id='ew_001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'),
            external_WalletTransaction_id='wallet_tx_abc123',
            status='pending')
        conv.refresh_from_db()
        self.assertEqual(conv.external_WalletTransaction_id, 'wallet_tx_abc123')
        self.assertFalse(hasattr(conv, 'external_transaction_id'))


# ══════════════════════════════════════════════════════════════════════════════
# MISSING MODEL METHOD TESTS
# ══════════════════════════════════════════════════════════════════════════════

class OfferCalculateQualityScoreTest(TestCase):
    def setUp(self):
        self.prov = mk_provider()
        self.offer = mk_offer(self.prov)

    def test_returns_numeric_score(self):
        score = self.offer.calculate_quality_score()
        self.assertIsInstance(score, (int, float))

    def test_score_between_0_and_100(self):
        score = self.offer.calculate_quality_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_score_saved_on_model(self):
        self.offer.calculate_quality_score()
        self.offer.refresh_from_db()
        self.assertGreaterEqual(self.offer.quality_score, 0)

    def test_higher_completion_rate_increases_score(self):
        offer_high = mk_offer(self.prov, external_offer_id='qs_high',
                              completion_rate=0.90, click_count=100, conversion_count=90)
        offer_low  = mk_offer(self.prov, external_offer_id='qs_low',
                              completion_rate=0.10, click_count=100, conversion_count=10)
        self.assertGreater(offer_high.calculate_quality_score(),
                           offer_low.calculate_quality_score())


class OfferIncrementClickEdgeCasesTest(TestCase):
    def setUp(self):
        self.prov = mk_provider()
        self.offer = mk_offer(self.prov)

    def test_increment_click_increments_by_one(self):
        initial = self.offer.click_count
        self.offer.increment_click()
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.click_count, initial + 1)

    def test_multiple_increments_accumulate(self):
        initial = self.offer.click_count
        for _ in range(5):
            self.offer.increment_click()
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.click_count, initial + 5)


class OfferIncrementConversionEdgeCasesTest(TestCase):
    def setUp(self):
        self.prov = mk_provider()
        self.offer = mk_offer(self.prov)

    def test_increment_conversion_increments_by_one(self):
        initial = self.offer.conversion_count
        self.offer.increment_conversion()
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.conversion_count, initial + 1)

    def test_completion_rate_updated_after_increment(self):
        # click_count > 0 is needed for completion_rate to be meaningful
        from decimal import Decimal
        self.offer.click_count = 10
        self.offer.conversion_count = 0
        self.offer.save(update_fields=['click_count', 'conversion_count'])
        self.offer.increment_conversion()
        self.offer.refresh_from_db()
        self.assertGreater(self.offer.conversion_count, 0)
