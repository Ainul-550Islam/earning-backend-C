from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import SmartLinkFactory, OfferPoolFactory
from ..services.rotation.OfferRotationService import OfferRotationService
from ..services.rotation.CapTrackerService import CapTrackerService
from ..services.rotation.FallbackService import FallbackService
from ..services.rotation.EPCOptimizer import EPCOptimizer


class OfferRotationServiceTest(TestCase):
    def setUp(self):
        self.service = OfferRotationService()
        self.sl = SmartLinkFactory()
        self.pool = OfferPoolFactory(smartlink=self.sl)
        self.context = {'country': 'US', 'device_type': 'mobile'}

    def test_empty_pool_returns_none(self):
        result = self.service.select(self.sl, [], self.context)
        self.assertIsNone(result)

    def test_weighted_random_distribution(self):
        """Higher weight offers should be selected more often."""
        # This is probabilistic, so we run many iterations
        # With mocked entries having weight 900 vs 100
        high_weight = MagicMock()
        high_weight.weight = 900
        high_weight.priority = 0
        high_weight.offer_id = 1
        high_weight.epc_override = None
        high_weight.cap_per_day = None

        low_weight = MagicMock()
        low_weight.weight = 100
        low_weight.priority = 0
        low_weight.offer_id = 2
        low_weight.epc_override = None
        low_weight.cap_per_day = None

        with patch.object(self.service.cap_tracker, 'is_capped', return_value=False):
            with patch.object(self.service, '_log_rotation'):
                with patch.object(self.service.cap_tracker, 'increment'):
                    counts = {1: 0, 2: 0}
                    for _ in range(1000):
                        result = self.service._weighted_random([high_weight, low_weight])
                        counts[result.offer_id] += 1

        # High weight should win ~90% of the time (allow ±10% tolerance)
        high_pct = counts[1] / 1000 * 100
        self.assertGreater(high_pct, 80, f"High-weight offer only won {high_pct:.1f}%")

    def test_priority_select_returns_highest(self):
        e1 = MagicMock(priority=5, offer_id=1)
        e2 = MagicMock(priority=10, offer_id=2)
        e3 = MagicMock(priority=1, offer_id=3)
        result = self.service._priority_select([e1, e2, e3])
        self.assertEqual(result.offer_id, 2)

    @patch('django.core.cache.cache.get', return_value=5)
    @patch('django.core.cache.cache.incr')
    def test_round_robin_cycles(self, mock_incr, mock_get):
        entries = [MagicMock(offer_id=i) for i in range(3)]
        # With cache returning 5 and 3 entries: next = (5+1) % 3 = 2
        result = self.service._round_robin(self.sl, entries)
        self.assertIsNotNone(result)


class CapTrackerServiceTest(TestCase):
    def setUp(self):
        self.service = CapTrackerService()

    def test_no_cap_always_available(self):
        entry = MagicMock(cap_per_day=None, cap_per_month=None)
        self.assertFalse(self.service.is_capped(entry))

    @patch('django.core.cache.cache.get', return_value=100)
    def test_daily_cap_reached(self, mock_cache):
        entry = MagicMock(cap_per_day=100, pk=1)
        self.assertTrue(self.service.is_capped(entry))

    @patch('django.core.cache.cache.get', return_value=50)
    def test_daily_cap_not_yet_reached(self, mock_cache):
        entry = MagicMock(cap_per_day=100, pk=1)
        self.assertFalse(self.service.is_capped(entry))

    def test_apply_buffer_reduces_effective_cap(self):
        effective = self.service._apply_buffer(1000)
        self.assertLess(effective, 1000)
        self.assertGreater(effective, 990)


class FallbackServiceTest(TestCase):
    def setUp(self):
        self.service = FallbackService()

    def test_smartlink_fallback_returned(self):
        from .factories import SmartLinkFactory, SmartLinkFallbackFactory
        sl = SmartLinkFactory()
        SmartLinkFallbackFactory(smartlink=sl, url='https://myfallback.com')
        url = self.service.get_url(sl)
        self.assertEqual(url, 'https://myfallback.com')

    def test_global_fallback_when_no_fallback_set(self):
        from .factories import SmartLinkFactory
        sl = SmartLinkFactory()
        url = self.service.get_url(sl)
        self.assertTrue(url.startswith('http'))
