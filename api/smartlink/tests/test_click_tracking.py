from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import SmartLinkFactory, ClickFactory
from ..services.click.ClickTrackingService import ClickTrackingService
from ..services.click.SubIDParserService import SubIDParserService


class ClickTrackingServiceTest(TestCase):
    def setUp(self):
        self.service = ClickTrackingService()
        self.sl = SmartLinkFactory(enable_unique_click=True, enable_bot_filter=False)
        self.context = {
            'ip': '1.2.3.4',
            'user_agent': 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537.36',
            'country': 'BD',
            'region': 'Dhaka',
            'city': 'Dhaka',
            'device_type': 'mobile',
            'os': 'android',
            'browser': 'chrome',
            'referrer': 'https://google.com',
            'is_fraud': False,
            'is_bot': False,
            'fraud_score': 0,
            'sub1': 'campaign_001',
            'sub2': 'adset_002',
            'sub3': '',
            'sub4': '',
            'sub5': '',
            'final_url': 'https://offer.example.com/?sub1=campaign_001',
        }

    @patch('smartlink.services.click.ClickDeduplicationService.ClickDeduplicationService.is_duplicate', return_value=False)
    @patch('smartlink.services.click.ClickDeduplicationService.ClickDeduplicationService.mark_seen')
    def test_click_created_with_metadata(self, mock_mark, mock_dedup):
        from ..models import Click, ClickMetadata
        click = self.service.record(self.sl.pk, None, self.context)
        self.assertIsNotNone(click)
        self.assertEqual(click.country, 'BD')
        self.assertEqual(click.device_type, 'mobile')

        meta = ClickMetadata.objects.get(click=click)
        self.assertEqual(meta.sub1, 'campaign_001')
        self.assertEqual(meta.sub2, 'adset_002')

    @patch('smartlink.services.click.ClickDeduplicationService.ClickDeduplicationService.is_duplicate', return_value=True)
    def test_duplicate_click_not_unique(self, mock_dedup):
        click = self.service.record(self.sl.pk, None, self.context)
        if click:
            self.assertFalse(click.is_unique)

    def test_nonexistent_smartlink_returns_none(self):
        result = self.service.record(99999, None, self.context)
        self.assertIsNone(result)


class SubIDParserServiceTest(TestCase):
    def setUp(self):
        self.service = SubIDParserService()

    def test_parse_standard_sub_ids(self):
        context = {
            'sub1': 'camp001', 'sub2': 'adset002',
            'sub3': '', 'sub4': '', 'sub5': '',
            'query_params': {'sub1': 'camp001', 'sub2': 'adset002'},
        }
        result = self.service.parse(context)
        self.assertEqual(result['sub1'], 'camp001')
        self.assertEqual(result['sub2'], 'adset002')
        self.assertEqual(result['sub3'], '')

    def test_parse_alias_sub_ids(self):
        context = {
            'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'query_params': {'aff_sub': 'myvalue', 'aff_sub2': 'second'},
        }
        result = self.service.parse(context)
        self.assertEqual(result['sub1'], 'myvalue')
        self.assertEqual(result['sub2'], 'second')

    def test_sanitizes_dangerous_chars(self):
        context = {
            'sub1': 'valid<script>alert(1)</script>',
            'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'query_params': {},
        }
        result = self.service.parse(context)
        self.assertNotIn('<', result['sub1'])
        self.assertNotIn('>', result['sub1'])

    def test_custom_params_collected(self):
        context = {
            'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': '',
            'query_params': {'utm_source': 'google', 'utm_medium': 'cpc'},
        }
        result = self.service.parse(context)
        self.assertIn('utm_source', result['custom'])

    def test_build_url_params(self):
        sub_ids = {'sub1': 'camp1', 'sub2': 'adset1', 'sub3': '', 'sub4': '', 'sub5': ''}
        params = self.service.build_url_params(sub_ids)
        self.assertIn('sub1', params)
        self.assertIn('sub2', params)
        self.assertNotIn('sub3', params)
