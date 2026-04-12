from django.test import TestCase
from unittest.mock import MagicMock
from .factories import SmartLinkFactory
from ..services.redirect.URLBuilderService import URLBuilderService
from ..utils import build_tracking_url


class URLBuilderServiceTest(TestCase):
    def setUp(self):
        self.service = URLBuilderService()
        self.sl = SmartLinkFactory()

    def _make_offer(self, url='https://offer.example.com/lp'):
        offer = MagicMock()
        offer.pk = 42
        offer.url = url
        offer.tracking_url = url
        return offer

    def test_build_appends_sub_ids(self):
        offer = self._make_offer()
        context = {
            'sub1': 'campaign_001', 'sub2': 'adset_002',
            'sub3': '', 'sub4': '', 'sub5': '',
            'country': 'US', 'device_type': 'mobile',
            'custom_params': {},
        }
        url = self.service.build(offer, self.sl, context)
        self.assertIn('sub1=campaign_001', url)
        self.assertIn('sub2=adset_002', url)

    def test_build_appends_sl_id(self):
        offer = self._make_offer()
        context = {
            'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'country': 'BD', 'device_type': 'mobile', 'custom_params': {},
        }
        url = self.service.build(offer, self.sl, context)
        self.assertIn(f'sl_id={self.sl.slug}', url)

    def test_build_appends_geo(self):
        offer = self._make_offer()
        context = {
            'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'country': 'BD', 'device_type': 'mobile', 'custom_params': {},
        }
        url = self.service.build(offer, self.sl, context)
        self.assertIn('geo=BD', url)

    def test_existing_params_preserved(self):
        offer = self._make_offer('https://offer.example.com/lp?existing=value')
        context = {
            'sub1': 'test', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'country': 'US', 'device_type': 'desktop', 'custom_params': {},
        }
        url = self.service.build(offer, self.sl, context)
        self.assertIn('existing=value', url)
        self.assertIn('sub1=test', url)


class BuildTrackingURLTest(TestCase):
    def test_appends_params_to_clean_url(self):
        url = build_tracking_url('https://example.com/', {'sub1': 'abc', 'sub2': 'def'})
        self.assertIn('sub1=abc', url)
        self.assertIn('sub2=def', url)

    def test_appends_params_to_url_with_existing_query(self):
        url = build_tracking_url('https://example.com/?foo=bar', {'sub1': 'abc'})
        self.assertIn('foo=bar', url)
        self.assertIn('sub1=abc', url)

    def test_none_values_not_appended(self):
        url = build_tracking_url('https://example.com/', {'sub1': 'abc', 'sub2': None})
        self.assertIn('sub1=abc', url)
        self.assertNotIn('sub2', url)
