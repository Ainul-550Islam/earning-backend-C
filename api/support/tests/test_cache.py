# api/support/tests/test_cache.py
"""Tests for caching module."""
from django.test import TestCase
from django.core.cache import cache


class CacheTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_get_ticket_stats_returns_dict(self):
        from api.support.cache import get_ticket_stats
        stats = get_ticket_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('total', stats)

    def test_get_support_settings(self):
        from api.support.cache import get_settings
        obj = get_settings()
        self.assertIsNotNone(obj)

    def test_invalidate_stats(self):
        from api.support.cache import get_ticket_stats, invalidate_stats
        stats = get_ticket_stats()
        invalidate_stats()
        stats2 = get_ticket_stats()
        self.assertIsInstance(stats2, dict)

    def test_invalidate_settings(self):
        from api.support.cache import get_settings, invalidate_settings
        get_settings()
        invalidate_settings()
        obj = get_settings()
        self.assertIsNotNone(obj)

    def test_cache_manager_warm_up(self):
        from api.support.caching import cache_manager
        results = cache_manager.warm_up()
        self.assertIsInstance(results, dict)

    def test_cache_manager_flush_all(self):
        from api.support.caching import cache_manager
        cache_manager.flush_all()  # Should not raise

    def test_invalidate_user_tickets(self):
        from api.support.cache import invalidate_user_tickets
        invalidate_user_tickets(999)  # Should not raise