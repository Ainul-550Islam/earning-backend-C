from django.test import TestCase
from unittest.mock import patch, MagicMock
from ..services.ml.SmartRotationMLEngine import SmartRotationMLEngine, ThompsonSamplingBandit
from ..services.ml.FraudMLScorer import FraudMLScorer
from ..services.antifraud.ClickQualityScore import ClickQualityScore


class ThompsonSamplingBanditTest(TestCase):
    def setUp(self):
        self.bandit = ThompsonSamplingBandit()

    def test_sample_returns_between_0_and_1(self):
        for _ in range(100):
            s = self.bandit.sample(1.0, 1.0)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)

    def test_high_alpha_tends_toward_1(self):
        samples = [self.bandit.sample(1000.0, 1.0) for _ in range(100)]
        avg = sum(samples) / len(samples)
        self.assertGreater(avg, 0.95)

    def test_high_beta_tends_toward_0(self):
        samples = [self.bandit.sample(1.0, 1000.0) for _ in range(100)]
        avg = sum(samples) / len(samples)
        self.assertLess(avg, 0.05)


class SmartRotationMLEngineTest(TestCase):
    def setUp(self):
        self.engine = SmartRotationMLEngine()

    def test_select_returns_none_for_empty_list(self):
        result = self.engine.select_offer([], {'country': 'US', 'device_type': 'mobile'})
        self.assertIsNone(result)

    def test_select_returns_single_entry_directly(self):
        entry = MagicMock()
        entry.offer_id = 1
        entry.epc_override = None
        result = self.engine.select_offer([entry], {'country': 'US', 'device_type': 'mobile'})
        self.assertEqual(result, entry)

    def test_select_returns_one_of_entries(self):
        entries = []
        for i in range(5):
            e = MagicMock()
            e.offer_id = i + 1
            e.epc_override = None
            entries.append(e)

        with patch('smartlink.services.ml.SmartRotationMLEngine.SmartRotationMLEngine._get_epc_factor', return_value=1.0):
            result = self.engine.select_offer(entries, {'country': 'US', 'device_type': 'mobile'})

        self.assertIn(result, entries)

    def test_context_key_format(self):
        key = self.engine._context_key({'country': 'BD', 'device_type': 'mobile'})
        self.assertIn('BD', key)
        self.assertIn('mob', key)

    def test_confidence_interval_structure(self):
        ci = self.engine.get_offer_confidence_interval(
            offer_id=1,
            context={'country': 'US', 'device_type': 'mobile'},
        )
        self.assertIn('lower', ci)
        self.assertIn('upper', ci)
        self.assertIn('mean', ci)
        self.assertIn('confidence', ci)
        self.assertGreaterEqual(ci['lower'], 0.0)
        self.assertLessEqual(ci['upper'], 1.0)


class FraudMLScorerTest(TestCase):
    def setUp(self):
        self.scorer = FraudMLScorer()

    def test_score_returns_float_between_0_and_1(self):
        prob, signals = self.scorer.score_click({
            'ip': '1.2.3.4',
            'user_agent': 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile',
            'country': 'US',
            'device_type': 'mobile',
            'asn': '',
            'referrer': 'https://google.com',
        })
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_headless_browser_high_score(self):
        prob, signals = self.scorer.score_click({
            'ip': '1.2.3.4',
            'user_agent': 'Mozilla/5.0 HeadlessChrome/120.0.0.0',
            'country': 'US',
            'device_type': 'desktop',
            'asn': '',
        })
        self.assertGreater(prob, 0.5)
        self.assertTrue(any('headless' in s for s in signals))

    def test_datacenter_asn_increases_score(self):
        prob_clean, _ = self.scorer.score_click({
            'ip': '1.2.3.4',
            'user_agent': 'Mozilla/5.0 (Linux; Android 13) Chrome/120',
            'asn': 'AS4134',  # China Telecom — not datacenter
            'country': 'CN', 'device_type': 'mobile',
        })
        prob_dc, signals = self.scorer.score_click({
            'ip': '52.0.0.1',
            'user_agent': 'Mozilla/5.0 (Linux; Android 13) Chrome/120',
            'asn': 'AS14618',  # Amazon AWS
            'country': 'US', 'device_type': 'mobile',
        })
        self.assertGreater(prob_dc, prob_clean)

    def test_score_to_100_conversion(self):
        score = self.scorer.score_to_100(0.75)
        self.assertEqual(score, 75)


class ClickQualityScoreTest(TestCase):
    def setUp(self):
        self.scorer = ClickQualityScore()

    def test_t1_country_gets_higher_score(self):
        t1_result = self.scorer.calculate({
            'country': 'US', 'device_type': 'mobile',
            'is_unique': True, 'referrer': 'https://google.com',
            'user_agent': 'Mozilla/5.0 Chrome/120',
            'os': 'android', 'browser': 'chrome', 'publisher_id': 0,
        })
        t3_result = self.scorer.calculate({
            'country': 'SO',  # Somalia — T3
            'device_type': 'mobile',
            'is_unique': True, 'referrer': '',
            'user_agent': 'Mozilla/5.0', 'os': 'android',
            'browser': 'chrome', 'publisher_id': 0,
        })
        self.assertGreater(t1_result['score'], t3_result['score'])

    def test_score_between_0_and_100(self):
        result = self.scorer.calculate({
            'country': 'BD', 'device_type': 'mobile',
            'is_unique': True, 'referrer': '',
            'user_agent': 'Mozilla/5.0 Chrome Mobile',
            'os': 'android', 'browser': 'chrome', 'publisher_id': 0,
        })
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 100)

    def test_tier_assignment(self):
        result = self.scorer.calculate({
            'country': 'US', 'device_type': 'mobile',
            'is_unique': True, 'referrer': 'https://facebook.com',
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile Safari',
            'os': 'ios', 'browser': 'safari', 'publisher_id': 0,
        })
        self.assertIn(result['tier'], ['premium', 'standard', 'low'])

    def test_geo_tier_classification(self):
        self.assertEqual(self.scorer._get_geo_tier('US'), 'T1')
        self.assertEqual(self.scorer._get_geo_tier('BD'), 'T2')
        self.assertEqual(self.scorer._get_geo_tier('SO'), 'T3')
