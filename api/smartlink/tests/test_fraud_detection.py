from django.test import TestCase
from unittest.mock import patch
from ..services.click.ClickFraudService import ClickFraudService
from ..services.click.BotDetectionService import BotDetectionService


class BotDetectionTest(TestCase):
    def setUp(self):
        self.service = BotDetectionService()

    def test_googlebot_detected(self):
        ua = 'Googlebot/2.1 (+http://www.google.com/bot.html)'
        is_bot, bot_type = self.service.detect('1.2.3.4', ua)
        self.assertTrue(is_bot)
        self.assertIn('googlebot', bot_type)

    def test_curl_detected(self):
        ua = 'curl/7.68.0'
        is_bot, bot_type = self.service.detect('1.2.3.4', ua)
        self.assertTrue(is_bot)

    def test_python_requests_detected(self):
        ua = 'python-requests/2.28.0'
        is_bot, bot_type = self.service.detect('1.2.3.4', ua)
        self.assertTrue(is_bot)

    def test_headless_chrome_detected(self):
        ua = 'Mozilla/5.0 HeadlessChrome/120.0.0.0'
        is_bot, bot_type = self.service.detect('1.2.3.4', ua)
        self.assertTrue(is_bot)
        self.assertIn('headless', bot_type)

    def test_real_mobile_ua_not_bot(self):
        ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36'
        is_bot, bot_type = self.service.detect('1.2.3.4', ua)
        self.assertFalse(is_bot)

    def test_empty_ua_is_bot(self):
        is_bot, bot_type = self.service.detect('1.2.3.4', '')
        self.assertTrue(is_bot)
        self.assertEqual(bot_type, 'empty_ua')


class ClickFraudServiceTest(TestCase):
    def setUp(self):
        self.service = ClickFraudService()

    def test_valid_click_low_score(self):
        ua = 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537.36'
        score, signals = self.service.score('1.2.3.4', ua, {'country': 'US', 'asn': 'AS4134'})
        self.assertLess(score, 60)

    def test_headless_browser_high_score(self):
        ua = 'Mozilla/5.0 HeadlessChrome/120'
        score, signals = self.service.score('1.2.3.4', ua, {'country': 'US', 'asn': ''})
        self.assertGreater(score, 40)

    def test_empty_ua_adds_score(self):
        score, signals = self.service.score('1.2.3.4', '', {'country': 'US', 'asn': ''})
        self.assertGreater(score, 0)

    @patch('django.core.cache.cache.get', return_value='1')
    def test_known_bad_ip_blocked(self, mock_cache):
        ua = 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537.36'
        score, signals = self.service.score('1.2.3.4', ua, {'country': 'US', 'asn': ''})
        self.assertGreater(score, 30)
