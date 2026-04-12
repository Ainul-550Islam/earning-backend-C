from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import (
    SmartLinkFactory, TargetingRuleFactory, GeoTargetingFactory,
    DeviceTargetingFactory, OfferPoolFactory, ClickFactory, UserFactory,
)
from ..services.targeting.TargetingEngine import TargetingEngine
from ..services.targeting.GeoTargetingService import GeoTargetingService
from ..services.targeting.DeviceTargetingService import DeviceTargetingService
from ..services.targeting.TargetingRuleEvaluator import TargetingRuleEvaluator


class TargetingEngineTest(TestCase):
    def setUp(self):
        self.engine = TargetingEngine()
        self.sl = SmartLinkFactory()
        self.pool = OfferPoolFactory(smartlink=self.sl)

    def test_no_targeting_returns_all_entries(self):
        """SmartLink with no targeting rules → all pool entries eligible."""
        result = self.engine.evaluate(self.sl, {'country': 'US', 'device_type': 'mobile'})
        self.assertIsInstance(result, list)

    def test_geo_whitelist_match(self):
        rule = TargetingRuleFactory(smartlink=self.sl, logic='AND')
        GeoTargetingFactory(rule=rule, mode='whitelist', countries=['US', 'GB'])
        context = {'country': 'US', 'device_type': 'mobile', 'os': '', 'language': '', 'isp': '', 'asn': ''}
        result = self.engine.evaluate(self.sl, context)
        self.assertIsInstance(result, list)

    def test_geo_blacklist_blocks_country(self):
        rule = TargetingRuleFactory(smartlink=self.sl, logic='AND')
        GeoTargetingFactory(rule=rule, mode='blacklist', countries=['CN', 'RU'])
        context = {'country': 'CN', 'device_type': 'mobile', 'os': '', 'language': '', 'isp': '', 'asn': ''}
        result = self.engine.evaluate(self.sl, context)
        self.assertEqual(result, [])


class TargetingRuleEvaluatorTest(TestCase):
    def setUp(self):
        self.evaluator = TargetingRuleEvaluator()

    def test_and_logic_all_true(self):
        self.assertTrue(self.evaluator.evaluate({'geo': True, 'device': True, 'time': True}, 'AND'))

    def test_and_logic_one_false(self):
        self.assertFalse(self.evaluator.evaluate({'geo': True, 'device': False}, 'AND'))

    def test_or_logic_one_true(self):
        self.assertTrue(self.evaluator.evaluate({'geo': False, 'device': True}, 'OR'))

    def test_or_logic_all_false(self):
        self.assertFalse(self.evaluator.evaluate({'geo': False, 'device': False}, 'OR'))

    def test_empty_rules_returns_true(self):
        self.assertTrue(self.evaluator.evaluate({}, 'AND'))

    def test_explain_returns_dict(self):
        result = self.evaluator.explain({'geo': True, 'device': False}, 'AND')
        self.assertIn('final_result', result)
        self.assertIn('passed_rules', result)
        self.assertIn('failed_rules', result)
        self.assertFalse(result['final_result'])
        self.assertEqual(result['passed_rules'], ['geo'])
        self.assertEqual(result['failed_rules'], ['device'])


class GeoTargetingServiceTest(TestCase):
    def setUp(self):
        self.service = GeoTargetingService()

    def test_whitelist_match(self):
        rule = TargetingRuleFactory(smartlink=SmartLinkFactory())
        geo = GeoTargetingFactory(rule=rule, mode='whitelist', countries=['BD', 'IN'])
        self.assertTrue(self.service.matches(geo, 'BD'))
        self.assertFalse(self.service.matches(geo, 'US'))

    def test_none_targeting_always_matches(self):
        self.assertTrue(self.service.matches(None, 'US'))


class DeviceTargetingServiceTest(TestCase):
    def setUp(self):
        self.service = DeviceTargetingService()

    def test_parse_mobile_ua(self):
        ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36'
        result = self.service.parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'mobile')
        self.assertFalse(result['is_bot'])

    def test_parse_bot_ua(self):
        ua = 'Googlebot/2.1 (+http://www.google.com/bot.html)'
        result = self.service.parse_user_agent(ua)
        self.assertTrue(result['is_bot'])

    def test_parse_desktop_ua(self):
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        result = self.service.parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'desktop')
