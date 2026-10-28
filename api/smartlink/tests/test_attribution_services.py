"""
Tests for attribution and revenue services:
  ClickAttributionService, RevenueAttributionService,
  OfferScoreService, ConversionFunnelService.
"""
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
import datetime

from .factories import SmartLinkFactory, UserFactory, ClickFactory


# ─── ClickAttributionService ──────────────────────────────────────────────────

class ClickAttributionServiceTest(TestCase):
    def setUp(self):
        from ..services.click.ClickAttributionService import ClickAttributionService
        from offer_inventory.models import Offer
        self.svc = ClickAttributionService()
        self.sl = SmartLinkFactory()
        # Create real Offer objects to satisfy FK constraints
        self.offer1 = Offer.objects.create(name='Test Offer 1')
        self.offer2 = Offer.objects.create(name='Test Offer 2')
        self.offer3 = Offer.objects.create(name='Test Offer 3')
        self.offer4 = Offer.objects.create(name='Test Offer 4')
        self.offer5 = Offer.objects.create(name='Test Offer 5')

    def test_attribute_by_sub1_click_id(self):
        click = ClickFactory(
            smartlink=self.sl,
            offer_id=self.offer1.pk,
            is_converted=False,
            payout=0,
        )
        result = self.svc.attribute(
            offer_id=self.offer1.pk,
            sub1=str(click.pk),
            payout=2.50,
        )
        self.assertEqual(result, click)
        click.refresh_from_db()
        self.assertTrue(click.is_converted)

    def test_attribute_by_ip_fallback(self):
        click = ClickFactory(
            smartlink=self.sl,
            offer_id=self.offer2.pk,
            ip='5.5.5.5',
            is_converted=False,
            is_fraud=False,
            is_bot=False,
        )
        result = self.svc.attribute(
            offer_id=self.offer2.pk,
            sub1='',
            ip='5.5.5.5',
            payout=1.00,
        )
        self.assertEqual(result, click)

    def test_attribute_returns_none_when_no_match(self):
        result = self.svc.attribute(
            offer_id=9999,
            sub1='nonexistent_sub1',
            ip='1.2.3.4',
        )
        self.assertIsNone(result)

    def test_attribute_skips_already_converted_click(self):
        click = ClickFactory(
            smartlink=self.sl,
            offer_id=self.offer3.pk,
            is_converted=True,
        )
        result = self.svc.attribute(
            offer_id=self.offer3.pk,
            sub1=str(click.pk),
            payout=5.00,
        )
        self.assertIsNone(result)

    def test_attribute_updates_smartlink_totals(self):
        from ..models import SmartLink
        click = ClickFactory(
            smartlink=self.sl,
            offer_id=self.offer4.pk,
            is_converted=False,
        )
        self.svc.attribute(
            offer_id=self.offer4.pk,
            sub1=str(click.pk),
            payout=3.00,
        )
        self.sl.refresh_from_db()
        self.assertEqual(self.sl.total_conversions, 1)

    def test_mark_converted_adds_payout_to_click(self):
        click = ClickFactory(smartlink=self.sl, payout=0)
        self.svc._mark_converted(click, 7.50)
        click.refresh_from_db()
        self.assertTrue(click.is_converted)
        self.assertGreater(click.payout, 0)

    def test_find_by_ip_respects_24h_window(self):
        old_click = ClickFactory(
            smartlink=self.sl,
            offer_id=self.offer5.pk,
            ip='9.9.9.9',
            is_converted=False,
            is_fraud=False,
            is_bot=False,
        )
        # Force the click to be old
        from ..models import Click
        Click.objects.filter(pk=old_click.pk).update(
            created_at=timezone.now() - datetime.timedelta(hours=25)
        )
        result = self.svc._find_by_ip('9.9.9.9', offer_id=self.offer5.pk)
        self.assertIsNone(result)

    def test_find_by_ip_skips_fraud_clicks(self):
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='Fraud Skip Offer')
        ClickFactory(
            smartlink=self.sl,
            offer_id=offer.pk,
            ip='8.8.8.8',
            is_converted=False,
            is_fraud=True,
        )
        result = self.svc._find_by_ip('8.8.8.8', offer_id=offer.pk)
        self.assertIsNone(result)

    def test_find_by_sub1_handles_non_numeric_sub1(self):
        result = self.svc._find_by_sub1('not_a_number', offer_id=self.offer1.pk)
        self.assertIsNone(result)


# ─── RevenueAttributionService ────────────────────────────────────────────────

class RevenueAttributionServiceTest(TestCase):
    def setUp(self):
        from ..services.analytics.RevenueAttributionService import RevenueAttributionService
        self.svc = RevenueAttributionService()
        self.publisher = UserFactory()
        self.sl = SmartLinkFactory(publisher=self.publisher)

    def test_get_smartlink_revenue_empty(self):
        result = self.svc.get_smartlink_revenue(self.sl, days=30)
        self.assertEqual(result['revenue'], 0.0)
        self.assertEqual(result['conversions'], 0)

    def test_get_smartlink_revenue_with_conversions(self):
        ClickFactory(
            smartlink=self.sl,
            is_converted=True,
            payout=Decimal('5.00'),
        )
        ClickFactory(
            smartlink=self.sl,
            is_converted=True,
            payout=Decimal('3.00'),
        )
        ClickFactory(
            smartlink=self.sl,
            is_converted=False,  # not converted — should not count
            payout=Decimal('0.00'),
        )
        result = self.svc.get_smartlink_revenue(self.sl, days=30)
        self.assertAlmostEqual(result['revenue'], 8.0, places=2)
        self.assertEqual(result['conversions'], 2)

    def test_get_publisher_revenue_sums_across_smartlinks(self):
        sl2 = SmartLinkFactory(publisher=self.publisher)
        ClickFactory(smartlink=self.sl, is_converted=True, payout=Decimal('4.00'))
        ClickFactory(smartlink=sl2, is_converted=True, payout=Decimal('6.00'))
        result = self.svc.get_publisher_revenue(self.publisher, days=30)
        self.assertAlmostEqual(result['revenue'], 10.0, places=2)
        self.assertEqual(result['conversions'], 2)

    def test_get_publisher_revenue_ignores_other_publishers(self):
        other_publisher = UserFactory()
        other_sl = SmartLinkFactory(publisher=other_publisher)
        ClickFactory(smartlink=other_sl, is_converted=True, payout=Decimal('100.00'))
        result = self.svc.get_publisher_revenue(self.publisher, days=30)
        self.assertEqual(result['revenue'], 0.0)

    def test_get_revenue_by_offer_groups_correctly(self):
        from offer_inventory.models import Offer
        o1 = Offer.objects.create(name='Offer 1')
        o2 = Offer.objects.create(name='Offer 2')
        ClickFactory(smartlink=self.sl, offer_id=o1.pk, is_converted=True, payout=Decimal('3.00'))
        ClickFactory(smartlink=self.sl, offer_id=o1.pk, is_converted=True, payout=Decimal('3.00'))
        ClickFactory(smartlink=self.sl, offer_id=o2.pk, is_converted=True, payout=Decimal('5.00'))
        rows = self.svc.get_revenue_by_offer(self.sl, days=30)
        offer_ids = [r['offer_id'] for r in rows]
        self.assertIn(o1.pk, offer_ids)
        self.assertIn(o2.pk, offer_ids)

    def test_get_revenue_by_country_returns_sorted_list(self):
        ClickFactory(
            smartlink=self.sl, country='US', is_converted=True,
            payout=Decimal('10.00'),
        )
        ClickFactory(
            smartlink=self.sl, country='BD', is_converted=True,
            payout=Decimal('2.00'),
        )
        rows = self.svc.get_revenue_by_country(self.sl, days=30)
        self.assertGreaterEqual(len(rows), 1)
        # First row should have highest revenue
        self.assertEqual(rows[0]['country'], 'US')


# ─── OfferScoreService ────────────────────────────────────────────────────────

class OfferScoreServiceTest(TestCase):
    def setUp(self):
        from ..services.rotation.OfferScoreService import OfferScoreService
        from offer_inventory.models import Offer
        self.svc = OfferScoreService()
        self.offer1 = Offer.objects.create(name='Score Offer 1')
        self.offer2 = Offer.objects.create(name='Score Offer 2')

    def test_get_score_returns_zero_when_not_in_db(self):
        with patch('django.core.cache.cache.get', return_value=None):
            score = self.svc.get_score(offer_id=99999, country='US', device_type='mobile')
        self.assertEqual(score, 0.0)

    def test_get_score_returns_cached_value(self):
        with patch('django.core.cache.cache.get', return_value={'score': 7.5, 'epc': 0.25, 'clicks': 100}):
            score = self.svc.get_score(offer_id=self.offer1.pk, country='US', device_type='mobile')
        self.assertEqual(score, 7.5)

    def test_get_score_reads_from_db_when_cache_miss(self):
        from ..models.offer_pool import OfferScoreCache
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='GB Desktop Offer')
        OfferScoreCache.objects.create(
            offer_id=offer.pk,
            country='GB',
            device_type='desktop',
            epc=Decimal('0.40'),
            conversion_rate=Decimal('0.04'),
            total_clicks=500,
            total_conversions=20,
            score=8.94,
        )
        with patch('django.core.cache.cache.get', return_value=None):
            with patch('django.core.cache.cache.set'):
                score = self.svc.get_score(offer_id=offer.pk, country='GB', device_type='desktop')
        self.assertAlmostEqual(score, 8.94, places=1)

    def test_update_score_creates_record(self):
        from ..models.offer_pool import OfferScoreCache
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='Score Test Offer')
        with patch('django.core.cache.cache.set'):
            with patch('django.core.cache.cache.delete'):
                self.svc.update_score(
                    offer_id=offer.pk,
                    country='US',
                    device_type='mobile',
                    clicks=100,
                    conversions=5,
                    revenue=15.00,
                )
        self.assertTrue(
            OfferScoreCache.objects.filter(
                offer_id=offer.pk, country='US', device_type='mobile'
            ).exists()
        )

    def test_update_score_epc_calculated_correctly(self):
        from ..models.offer_pool import OfferScoreCache
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='EPC Test Offer')
        with patch('django.core.cache.cache.set'):
            with patch('django.core.cache.cache.delete'):
                self.svc.update_score(
                    offer_id=offer.pk,
                    country='BD',
                    device_type='mobile',
                    clicks=200,
                    conversions=10,
                    revenue=20.00,
                )
        cache_obj = OfferScoreCache.objects.get(
            offer_id=offer.pk, country='BD', device_type='mobile'
        )
        self.assertAlmostEqual(float(cache_obj.epc), 0.10, places=2)

    def test_get_top_offers_returns_list(self):
        from ..models.offer_pool import OfferScoreCache
        from ..constants import EPC_MIN_CLICKS_FOR_SCORE
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='Top Offer')
        OfferScoreCache.objects.create(
            offer_id=offer.pk, country='US', device_type='mobile',
            epc=0.50, conversion_rate=0.05,
            total_clicks=EPC_MIN_CLICKS_FOR_SCORE + 10,
            total_conversions=5, score=11.18,
        )
        results = self.svc.get_top_offers(country='US', device_type='mobile', limit=5)
        self.assertIsInstance(results, list)


# ─── ConversionFunnelService ──────────────────────────────────────────────────

class ConversionFunnelServiceTest(TestCase):
    def setUp(self):
        from ..services.conversion.ConversionFunnelService import ConversionFunnelService
        self.svc = ConversionFunnelService()
        self.sl = SmartLinkFactory()

    def _make_clicks(self, **flags):
        """Helper to batch-create clicks with specific flags."""
        count = flags.pop('count', 1)
        for _ in range(count):
            ClickFactory(smartlink=self.sl, **flags)

    def test_funnel_structure_all_zeros(self):
        result = self.svc.get_funnel(self.sl, days=7)
        self.assertIn('steps', result)
        self.assertIn('period_days', result)
        self.assertEqual(result['period_days'], 7)
        for step in result['steps']:
            for key in ('step', 'name', 'count', 'rate'):
                self.assertIn(key, step)

    def test_funnel_total_click_count(self):
        self._make_clicks(is_unique=True, is_fraud=False, is_bot=False, count=10)
        self._make_clicks(is_unique=False, is_fraud=False, is_bot=False, count=5)
        result = self.svc.get_funnel(self.sl, days=7)
        total_step = next(s for s in result['steps'] if s['step'] == 1)
        self.assertEqual(total_step['count'], 15)

    def test_funnel_unique_click_count(self):
        self._make_clicks(is_unique=True, is_fraud=False, is_bot=False, count=8)
        self._make_clicks(is_unique=False, is_fraud=False, is_bot=False, count=4)
        result = self.svc.get_funnel(self.sl, days=7)
        unique_step = next(s for s in result['steps'] if s['step'] == 2)
        self.assertEqual(unique_step['count'], 8)

    def test_funnel_first_step_rate_always_100(self):
        self._make_clicks(is_unique=True, count=5)
        result = self.svc.get_funnel(self.sl, days=7)
        first_step = next(s for s in result['steps'] if s['step'] == 1)
        self.assertEqual(first_step['rate'], 100.0)

    def test_funnel_conversion_count(self):
        self._make_clicks(
            is_unique=True, is_fraud=False, is_bot=False,
            is_converted=True, count=3,
        )
        self._make_clicks(
            is_unique=True, is_fraud=False, is_bot=False,
            is_converted=False, count=7,
        )
        result = self.svc.get_funnel(self.sl, days=7)
        conv_step = next(s for s in result['steps'] if 'Conversion' in s['name'])
        self.assertEqual(conv_step['count'], 3)

    def test_funnel_excludes_fraud_from_conversions(self):
        """Fraudulent clicks must never appear in conversion step."""
        self._make_clicks(
            is_unique=True, is_fraud=True, is_bot=False,
            is_converted=True, count=5,
        )
        result = self.svc.get_funnel(self.sl, days=7)
        conv_step = next(s for s in result['steps'] if 'Conversion' in s['name'])
        self.assertEqual(conv_step['count'], 0)

    def test_funnel_empty_when_no_clicks(self):
        result = self.svc.get_funnel(self.sl, days=7)
        total_step = next(s for s in result['steps'] if s['step'] == 1)
        self.assertEqual(total_step['count'], 0)
        self.assertEqual(total_step['rate'], 100.0)
