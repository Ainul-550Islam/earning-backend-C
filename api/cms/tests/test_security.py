# api/cms/tests/test_security.py
"""Tests for security features: encryption, sanctions, fraud detection."""
from django.test import TestCase
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass


class TestEncryption(TestCase):
    def test_aes_encrypt_decrypt(self):
        from api.cms.encryption import AESCipher
        plaintext = "sensitive_account_data@paypal.com"
        encrypted = AESCipher.encrypt(plaintext)
        self.assertNotEqual(encrypted, plaintext)
        decrypted = AESCipher.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_empty_string(self):
        from api.cms.encryption import AESCipher
        result = AESCipher.encrypt('')
        self.assertEqual(result, '')

    def test_hmac_token_generate_verify(self):
        from api.cms.encryption import HMACToken
        token = HMACToken.generate('user:123', expires_in=300)
        valid, error = HMACToken.verify(token, 'user:123')
        self.assertTrue(valid)
        self.assertEqual(error, '')

    def test_hmac_token_wrong_data(self):
        from api.cms.encryption import HMACToken
        token = HMACToken.generate('user:123', expires_in=300)
        valid, error = HMACToken.verify(token, 'user:456')
        self.assertFalse(valid)

    def test_token_generator(self):
        from api.cms.encryption import TokenGenerator
        token = TokenGenerator.generate(32)
        self.assertGreater(len(token), 20)
        code = TokenGenerator.generate_referral_code(8)
        self.assertEqual(len(code), 8)

    def test_pii_mask_email(self):
        from api.cms.encryption import PIIProtection
        masked = PIIProtection.mask_account_id('user@example.com')
        self.assertIn('*', masked)
        self.assertIn('@', masked)

    def test_pii_mask_ip(self):
        from api.cms.encryption import PIIProtection
        masked = PIIProtection.mask_ip('192.168.1.100')
        self.assertIn('xxx', masked)
        self.assertNotIn('100', masked)

    def test_secure_compare_timing_safe(self):
        from api.cms.encryption import SecureCompare
        self.assertTrue(SecureCompare.strings('hello', 'hello'))
        self.assertFalse(SecureCompare.strings('hello', 'world'))


class TestSanctions(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_ban_and_check_ip(self):
        from api.cms.sanctions import FraudScorer
        test_ip = '1.2.3.4'
        FraudScorer.ban_ip(test_ip, 'Test ban', 1)
        self.assertTrue(FraudScorer.is_ip_banned(test_ip))

    def test_unban_ip(self):
        from api.cms.sanctions import FraudScorer
        test_ip = '5.6.7.8'
        FraudScorer.ban_ip(test_ip, 'Test', 1)
        FraudScorer.unban_ip(test_ip)
        self.assertFalse(FraudScorer.is_ip_banned(test_ip))

    def test_fraud_score_banned_ip(self):
        from api.cms.sanctions import FraudScorer
        test_ip = '9.10.11.12'
        FraudScorer.ban_ip(test_ip, 'Test')
        score, reasons = FraudScorer.score(1, test_ip, '1', 0.50)
        self.assertEqual(score, 100)

    def test_fraud_score_zero_payout(self):
        from api.cms.sanctions import FraudScorer
        score, reasons = FraudScorer.score(1, '8.8.8.8', '1', 0)
        self.assertGreater(score, 0)

    def test_rate_limiter_allows_under_limit(self):
        from api.cms.sanctions import RateLimiter
        allowed, remaining = RateLimiter.check('test:key:1', limit=10, window_seconds=60)
        self.assertTrue(allowed)
        self.assertLessEqual(remaining, 9)

    def test_rate_limiter_blocks_over_limit(self):
        from api.cms.sanctions import RateLimiter
        key = 'test:block:1'
        for _ in range(5):
            RateLimiter.check(key, limit=5, window_seconds=60)
        allowed, remaining = RateLimiter.check(key, limit=5, window_seconds=60)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)


class TestHelpers(TestCase):
    def test_slugify(self):
        from api.cms.helpers import slugify
        self.assertEqual(slugify('Hello World!'), 'hello-world')
        self.assertEqual(slugify('  Test 123  '), 'test-123')

    def test_truncate_text(self):
        from api.cms.helpers import truncate_text
        long_text = 'a' * 200
        result = truncate_text(long_text, max_length=100)
        self.assertEqual(len(result), 100)
        self.assertTrue(result.endswith('...'))

    def test_strip_html(self):
        from api.cms.helpers import strip_html_tags
        html = '<p>Hello <b>world</b>!</p>'
        result = strip_html_tags(html)
        self.assertEqual(result.strip(), 'Hello world !')

    def test_mask_email(self):
        from api.cms.helpers import mask_email
        masked = mask_email('user@example.com')
        self.assertIn('@', masked)
        self.assertIn('*', masked)

    def test_detect_device(self):
        from api.cms.helpers import detect_device
        self.assertEqual(detect_device('Mozilla/5.0 iPhone'), 'mobile')
        self.assertEqual(detect_device('iPad Safari'), 'tablet')
        self.assertEqual(detect_device('Mozilla/5.0 Windows'), 'desktop')

    def test_hmac_sign_verify(self):
        from api.cms.helpers import hmac_sign, hmac_verify
        sig = hmac_sign('message', 'secret')
        self.assertTrue(hmac_verify('message', sig, 'secret'))
        self.assertFalse(hmac_verify('wrong', sig, 'secret'))

    def test_chunk_list(self):
        from api.cms.helpers import chunk_list
        items = list(range(25))
        chunks = chunk_list(items, 10)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], list(range(10)))

    def test_is_tier1_country(self):
        from api.cms.helpers import is_tier1_country
        self.assertTrue(is_tier1_country('US'))
        self.assertTrue(is_tier1_country('GB'))
        self.assertFalse(is_tier1_country('BD'))

    def test_format_currency(self):
        from api.cms.helpers import format_currency
        from decimal import Decimal
        result = format_currency(Decimal('1234.56'))
        self.assertIn('1,234.56', result)
        self.assertIn('$', result)
