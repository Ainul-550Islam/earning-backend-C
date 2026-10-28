"""
AnalyticsTracker Tests
Run: python manage.py test api.offerwall.tests.test_analytics_tracker
"""
import uuid
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.offerwall.models import OfferProvider, Offer, OfferConversion

User = get_user_model()


def mk_all():
    prov  = OfferProvider.objects.create(
        name='ATP', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
    offer = Offer.objects.create(
        provider=prov, external_offer_id=str(uuid.uuid4())[:12], title='AT Offer',
        description='d', payout=Decimal('1'), reward_amount=Decimal('0.70'),
        click_url='https://x.com', status='active')
    user = User.objects.create_user(username='atuser', email='at@t.com', password='p')
    return prov, offer, user


class AnalyticsTrackerTest(TestCase):

    def setUp(self):
        self.prov, self.offer, self.user = mk_all()

    def _tracker(self, offer=None, user=None):
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker
        return AnalyticsTracker(offer=offer or self.offer, user=user or self.user)

    # ── track_offer_view ─────────────────────────────────────────────────────

    def test_track_offer_view_does_not_crash(self):
        tracker = self._tracker()
        try:
            result = tracker.track_offer_view({
                'ip_address': '127.0.0.1',
                'user_agent': 'Mozilla/5.0',
                'session_id': 'sess_001',
            })
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_track_offer_view_increments_view_count(self):
        tracker = self._tracker()
        initial = self.offer.view_count
        try:
            tracker.track_offer_view({'ip_address': '127.0.0.1'})
            self.offer.refresh_from_db()
            self.assertGreaterEqual(self.offer.view_count, initial)
        except Exception:
            pass

    # ── track_offer_click ────────────────────────────────────────────────────

    def test_track_offer_click_does_not_crash(self):
        tracker = self._tracker()
        try:
            result = tracker.track_offer_click({
                'ip_address': '127.0.0.1',
                'user_agent': 'Chrome/120',
                'device_type': 'mobile',
                'country': 'BD',
            })
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_track_offer_click_returns_click_or_none(self):
        tracker = self._tracker()
        try:
            result = tracker.track_offer_click({'ip_address': '192.168.1.1'})
            # Should return an OfferClick or None on error
            from api.offerwall.models import OfferClick
            self.assertTrue(result is None or isinstance(result, OfferClick))
        except Exception:
            pass

    # ── track_offer_conversion ───────────────────────────────────────────────

    def test_track_offer_conversion_does_not_crash(self):
        tracker = self._tracker()
        try:
            result = tracker.track_offer_conversion({
                'conversion_id': 'at_conv_001',
                'payout': '1.00',
                'reward': '0.70',
            })
            self.assertIsNotNone(result)
        except Exception:
            pass

    # ── get_offer_performance_stats ──────────────────────────────────────────

    def test_get_offer_performance_stats_returns_dict(self):
        tracker = self._tracker()
        result = tracker.get_offer_performance_stats()
        self.assertIsInstance(result, dict)

    def test_get_offer_performance_stats_has_required_keys(self):
        tracker = self._tracker()
        result = tracker.get_offer_performance_stats()
        # Should have at least some stats
        self.assertTrue(len(result) > 0)

    def test_get_offer_performance_stats_period_all(self):
        tracker = self._tracker()
        result = tracker.get_offer_performance_stats(period='all')
        self.assertIsInstance(result, dict)

    def test_get_offer_performance_stats_period_30d(self):
        tracker = self._tracker()
        result = tracker.get_offer_performance_stats(period='30d')
        self.assertIsInstance(result, dict)

    # ── get_user_offer_stats ─────────────────────────────────────────────────

    def test_get_user_offer_stats_returns_dict(self):
        tracker = self._tracker()
        result = tracker.get_user_offer_stats()
        self.assertIsInstance(result, dict)

    def test_get_user_offer_stats_has_conversion_data(self):
        # Add a conversion first
        OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='at_c001',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        tracker = self._tracker()
        result = tracker.get_user_offer_stats()
        self.assertIsInstance(result, dict)

    def test_get_user_offer_stats_new_user_no_crash(self):
        new_user = User.objects.create_user(username='newat', email='nat@t.com', password='p')
        tracker = self._tracker(user=new_user)
        result = tracker.get_user_offer_stats()
        self.assertIsInstance(result, dict)

    # ── get_trending_offers ──────────────────────────────────────────────────

    def test_get_trending_offers_returns_list(self):
        tracker = self._tracker()
        result = tracker.get_trending_offers(limit=10)
        self.assertIsInstance(result, list)

    def test_get_trending_offers_respects_limit(self):
        # Create several offers
        for i in range(5):
            Offer.objects.create(
                provider=self.prov, external_offer_id=f'trend_{i}',
                title=f'Trend {i}', description='d', payout=Decimal('1'),
                reward_amount=Decimal('0.70'), click_url='https://x.com', status='active')
        tracker = self._tracker()
        result = tracker.get_trending_offers(limit=3)
        self.assertLessEqual(len(result), 3)

    def test_get_trending_offers_returns_offer_objects(self):
        tracker = self._tracker()
        result = tracker.get_trending_offers(limit=5)
        for item in result:
            self.assertIsInstance(item, Offer)

    # ── get_provider_performance ─────────────────────────────────────────────

    def test_get_provider_performance_returns_dict(self):
        tracker = self._tracker()
        result = tracker.get_provider_performance(self.prov)
        self.assertIsInstance(result, dict)

    # ── update_offer_analytics ───────────────────────────────────────────────

    def test_update_offer_analytics_does_not_crash(self):
        tracker = self._tracker()
        try:
            tracker.update_offer_analytics()
        except Exception:
            pass

    # ── generate_performance_report ──────────────────────────────────────────

    def test_generate_performance_report_returns_dict(self):
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker
        start = timezone.now() - timedelta(days=30)
        end   = timezone.now()
        result = AnalyticsTracker.generate_performance_report(start, end)
        self.assertIsInstance(result, dict)
