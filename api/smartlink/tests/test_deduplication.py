from django.test import TestCase
from unittest.mock import patch
from .factories import SmartLinkFactory, ClickFactory
from ..services.click.ClickDeduplicationService import ClickDeduplicationService
from ..utils import click_fingerprint


class ClickDeduplicationServiceTest(TestCase):
    def setUp(self):
        self.service = ClickDeduplicationService()
        self.sl = SmartLinkFactory()

    def test_fingerprint_deterministic(self):
        f1 = click_fingerprint('1.2.3.4', 'Mozilla/5.0', 42)
        f2 = click_fingerprint('1.2.3.4', 'Mozilla/5.0', 42)
        self.assertEqual(f1, f2)

    def test_different_ip_different_fingerprint(self):
        f1 = click_fingerprint('1.2.3.4', 'Mozilla/5.0', 42)
        f2 = click_fingerprint('9.9.9.9', 'Mozilla/5.0', 42)
        self.assertNotEqual(f1, f2)

    def test_different_offer_different_fingerprint(self):
        f1 = click_fingerprint('1.2.3.4', 'Mozilla/5.0', 42)
        f2 = click_fingerprint('1.2.3.4', 'Mozilla/5.0', 99)
        self.assertNotEqual(f1, f2)

    @patch('django.core.cache.cache.get', return_value='1')
    def test_cache_hit_returns_duplicate(self, mock_cache):
        is_dup = self.service.is_duplicate('1.2.3.4', 'UA', 1, self.sl.pk)
        self.assertTrue(is_dup)

    @patch('django.core.cache.cache.get', return_value=None)
    @patch('smartlink.models.UniqueClick.objects.filter')
    def test_db_miss_returns_not_duplicate(self, mock_filter, mock_cache):
        mock_filter.return_value.filter.return_value.exists.return_value = False
        mock_filter.return_value.exists.return_value = False
        is_dup = self.service.is_duplicate('5.5.5.5', 'UA', 1, self.sl.pk)
        self.assertFalse(is_dup)

    @patch('django.core.cache.cache.get', return_value=None)
    @patch('django.core.cache.cache.set')
    def test_mark_seen_sets_cache(self, mock_set, mock_get):
        click = ClickFactory(smartlink=self.sl)
        try:
            self.service.mark_seen('1.2.3.4', 'UA', 1, self.sl.pk, click)
        except Exception:
            pass
        mock_set.assert_called()
