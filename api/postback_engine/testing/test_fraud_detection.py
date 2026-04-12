"""testing/test_fraud_detection.py — Fraud detection tests."""
from django.test import TestCase

class TestBotDetector(TestCase):
    def setUp(self):
        from api.postback_engine.fraud_detection.bot_detector import BotDetector
        self.detector = BotDetector()

    def test_googlebot_detected(self):
        is_bot, score = self.detector.check_user_agent("Googlebot/2.1 (+http://www.google.com/bot.html)")
        self.assertTrue(is_bot)
        self.assertGreaterEqual(score, 90)

    def test_curl_detected(self):
        is_bot, score = self.detector.check_user_agent("curl/7.64.0")
        self.assertTrue(is_bot)

    def test_empty_ua_is_bot(self):
        is_bot, score = self.detector.check_user_agent("")
        self.assertTrue(is_bot)
        self.assertGreaterEqual(score, 80)

    def test_real_chrome_not_bot(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
        is_bot, score = self.detector.check_user_agent(ua)
        self.assertFalse(is_bot)

    def test_timing_under_3s_is_fraud(self):
        is_fraud, score = self.detector.check_timing(2)
        self.assertTrue(is_fraud)
        self.assertGreaterEqual(score, 90)

    def test_timing_over_30s_is_clean(self):
        is_fraud, score = self.detector.check_timing(60)
        self.assertFalse(is_fraud)
        self.assertEqual(score, 0.0)

class TestVelocityThresholds(TestCase):
    def test_threshold_is_5(self):
        import api.postback_engine.fraud_detection.velocity_checker as vc
        self.assertEqual(vc._IP_CONVERSIONS_PER_MINUTE, 5)

    def test_hash_is_consistent(self):
        from api.postback_engine.fraud_detection.velocity_checker import VelocityChecker
        checker = VelocityChecker()
        self.assertEqual(checker._hash("1.2.3.4"), checker._hash("1.2.3.4"))
        self.assertNotEqual(checker._hash("1.2.3.4"), checker._hash("5.6.7.8"))
