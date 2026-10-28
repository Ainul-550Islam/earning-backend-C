# api/cms/tests/test_new_features.py
"""Tests for new features: 2FA, API Keys, Sessions, Comments, Currency, etc."""
from django.test import TestCase
from datetime import datetime, timedelta, date
from decimal import Decimal
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
from rest_framework.test import APIClient


class TestTwoFactor(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()

    def test_setup_returns_secret_and_uri(self):
        from api.cms.two_factor import TOTPService
        secret, uri = TOTPService.setup_2fa(self.user)
        self.assertIsNotNone(secret)
        self.assertIn('otpauth://', uri)

    def test_not_enabled_initially(self):
        from api.cms.two_factor import TOTPService
        self.assertFalse(TOTPService.is_enabled(self.user))

    def test_generate_backup_codes(self):
        from api.cms.two_factor import TOTPService
        # First enable 2FA
        secret, _ = TOTPService.setup_2fa(self.user)
        # Manually set secret (bypass confirm in tests)
        from api.cms.encryption import AESCipher
        from django.core.cache import cache
        cache.set(f"cms:2fa_secret:{self.user.id}", AESCipher.encrypt(secret), 86400)
        codes = TOTPService.generate_backup_codes(self.user)
        self.assertEqual(len(codes), 8)
        for code in codes:
            self.assertEqual(len(code), 8)  # 4 hex bytes = 8 chars

    def test_verify_backup_code(self):
        from api.cms.two_factor import TOTPService
        from api.cms.encryption import AESCipher
        from django.core.cache import cache
        secret, _ = TOTPService.setup_2fa(self.user)
        cache.set(f"cms:2fa_secret:{self.user.id}", AESCipher.encrypt(secret), 86400)
        codes = TOTPService.generate_backup_codes(self.user)
        valid = TOTPService.verify_backup_code(self.user, codes[0])
        self.assertTrue(valid)
        # Can't use same code twice
        valid2 = TOTPService.verify_backup_code(self.user, codes[0])
        self.assertFalse(valid2)


class TestAPIKeys(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.user = UserFactory.create()

    def test_create_api_key(self):
        from api.cms.models_new.api_keys import APIKey
        api_key, raw_key = APIKey.create_key(self.user, 'Test Key', 'read')
        self.assertIsNotNone(api_key)
        self.assertTrue(raw_key.startswith('cms_read_'))

    def test_verify_valid_key(self):
        from api.cms.models_new.api_keys import APIKey
        _, raw_key = APIKey.create_key(self.user, 'Test', 'write')
        verified = APIKey.verify(raw_key)
        self.assertIsNotNone(verified)
        self.assertEqual(verified.user, self.user)

    def test_verify_invalid_key(self):
        from api.cms.models_new.api_keys import APIKey
        verified = APIKey.verify('cms_invalid_key_000000000000')
        self.assertIsNone(verified)

    def test_revoke_key(self):
        from api.cms.models_new.api_keys import APIKey
        api_key, raw_key = APIKey.create_key(self.user, 'Revoke Test', 'read')
        api_key.revoke()
        verified = APIKey.verify(raw_key)
        self.assertIsNone(verified)

    def test_scope_enforcement(self):
        from api.cms.models_new.api_keys import APIKey
        _, raw_key = APIKey.create_key(self.user, 'Read Key', 'read')
        # Read key should not satisfy write requirement
        verified = APIKey.verify(raw_key, required_scope='write')
        self.assertIsNone(verified)

    def test_max_10_keys(self):
        from api.cms.models_new.api_keys import APIKey
        for i in range(10):
            APIKey.create_key(self.user, f'Key {i}', 'read')
        self.assertEqual(APIKey.objects.filter(user=self.user, is_active=True).count(), 10)


class TestSessions(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.user = UserFactory.create()

    def test_create_session(self):
        from api.cms.models_new.sessions import UserSession
        session = UserSession.objects.create(
            user=self.user, session_key='test_session_key',
            ip_address='1.2.3.4', device_type='desktop',
        )
        self.assertTrue(session.is_active)

    def test_revoke_session(self):
        from api.cms.models_new.sessions import UserSession
        session = UserSession.objects.create(
            user=self.user, session_key='rev_session',
            ip_address='1.2.3.4',
        )
        session.revoke()
        session.refresh_from_db()
        self.assertFalse(session.is_active)

    def test_revoke_all(self):
        from api.cms.models_new.sessions import UserSession
        for i in range(3):
            UserSession.objects.create(
                user=self.user, session_key=f'session_{i}',
                ip_address='1.2.3.4',
            )
        UserSession.revoke_all_for_user(self.user)
        active = UserSession.objects.filter(user=self.user, is_active=True).count()
        self.assertEqual(active, 0)


class TestComments(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()

    def test_create_comment(self):
        from api.cms.models_new.comments import Comment
        comment = Comment.objects.create(
            content_type='blog_post', object_id=1,
            user=self.user, body='Test comment', status='approved'
        )
        self.assertEqual(comment.author_display, self.user.username)
        self.assertFalse(comment.is_reply)

    def test_threaded_reply(self):
        from api.cms.models_new.comments import Comment
        parent = Comment.objects.create(
            content_type='blog_post', object_id=1,
            user=self.user, body='Parent', status='approved'
        )
        reply = Comment.objects.create(
            content_type='blog_post', object_id=1,
            user=self.user, body='Reply', status='approved',
            parent=parent, depth=1,
        )
        self.assertTrue(reply.is_reply)
        self.assertEqual(reply.parent, parent)
        replies = parent.get_replies()
        self.assertEqual(replies.count(), 1)


class TestCurrency(TestCase):
    def test_convert_usd_to_bdt(self):
        from api.cms.currency import CurrencyService
        usd = Decimal('1.00')
        bdt = CurrencyService.convert(usd, 'BDT')
        self.assertGreater(float(bdt), 50)  # BDT rate should be > 50

    def test_format_currency(self):
        from api.cms.currency import CurrencyService
        from decimal import Decimal
        formatted = CurrencyService.format(Decimal('10.00'), 'USD')
        self.assertIn('$', formatted)
        self.assertIn('10', formatted)

    def test_country_to_currency(self):
        from api.cms.currency import COUNTRY_CURRENCY
        self.assertEqual(COUNTRY_CURRENCY.get('US'), 'USD')
        self.assertEqual(COUNTRY_CURRENCY.get('BD'), 'BDT')
        self.assertEqual(COUNTRY_CURRENCY.get('IN'), 'INR')

    def test_supported_currencies_list(self):
        from api.cms.currency import CurrencyService
        currencies = CurrencyService.get_supported_currencies()
        self.assertGreater(len(currencies), 20)
        codes = [c['code'] for c in currencies]
        self.assertIn('USD', codes)
        self.assertIn('BDT', codes)


class TestLandingPages(TestCase):
    def test_create_landing_page(self):
        from api.cms.models_new.landing_pages import LandingPage
        page = LandingPage.objects.create(
            name='Free Robux Page', slug='free-robux',
            niche='roblox', headline='Get Free Robux!',
            cta_text='Get It Now',
        )
        self.assertEqual(page.niche, 'roblox')
        self.assertEqual(page.conversion_rate, 0.0)
        self.assertEqual(page.ctr, 0.0)

    def test_conversion_rate_calculation(self):
        from api.cms.models_new.landing_pages import LandingPage
        page = LandingPage(
            name='Test', slug='test-page', niche='minecraft',
            headline='Test', views=100, clicks=20, conversions=5,
        )
        self.assertEqual(page.conversion_rate, 5.0)
        self.assertEqual(page.ctr, 20.0)

    def test_gaming_niches_defined(self):
        from api.cms.models_new.landing_pages import GAMING_NICHES
        niches = [n[0] for n in GAMING_NICHES]
        self.assertIn('minecraft', niches)
        self.assertIn('roblox', niches)
        self.assertIn('fortnite', niches)
        self.assertIn('gta_v', niches)
