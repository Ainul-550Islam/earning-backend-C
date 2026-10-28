# api/cms/tests/test_cpalead.py
"""Tests for CPAlead core integration."""
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
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestCPALeadPostback(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from api.cms.models_new.cpalead import OfferWallConfig
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='testuser', password='pass', email='t@t.com'
        )
        # Create CPALeadConfig so handle_postback can find config
        from api.cms.models_new.extras import CPALeadConfig
        from django.core.cache import cache
        cache.clear()  # clear cached config
        self.config, _ = CPALeadConfig.objects.get_or_create(
            name='Test Config',
            defaults={
                'is_active': True,
                'api_key': 'test_key',
                'publisher_id': 'test_pub',
                'website_id': 'test_site',
            }
        )

    def test_postback_requires_subid(self):
        from api.cms.services_new.CPALeadService import CPALeadService
        success, msg = CPALeadService.handle_postback({
            'payout': '0.50', 'lead_id': 'abc123', 'password': ''
        })
        self.assertFalse(success)
        self.assertIn('subid', msg)

    def test_postback_requires_lead_id(self):
        from api.cms.services_new.CPALeadService import CPALeadService
        success, msg = CPALeadService.handle_postback({
            'subid': '1', 'payout': '0.50', 'password': ''
        })
        self.assertFalse(success)

    def test_postback_invalid_payout(self):
        from api.cms.services_new.CPALeadService import CPALeadService
        success, msg = CPALeadService.handle_postback({
            'subid': str(self.user.id), 'payout': 'notanumber',
            'lead_id': 'abc123', 'password': ''
        })
        self.assertFalse(success)

    def test_postback_dedup(self):
        """Same lead_id twice should succeed first, skip second."""
        from api.cms.services_new.CPALeadService import CPALeadService
        from api.cms.models_new.cpalead import ConversionLog
        lead_id = 'UNIQUE_LEAD_001'
        ConversionLog.objects.create(
            subid=str(self.user.id), lead_id=lead_id,
            payout_usd=Decimal('0.50'), status='approved',
            raw_postback_data={},
        )
        success, msg = CPALeadService.handle_postback({
            'subid': str(self.user.id), 'payout': '0.50',
            'lead_id': lead_id, 'password': '',
        })
        self.assertTrue(success)
        self.assertIn('duplicate', msg)

    def test_resolve_user_by_id(self):
        from api.cms.services_new.CPALeadService import CPALeadService
        user = CPALeadService._resolve_user(str(self.user.id))
        self.assertEqual(user, self.user)

    def test_resolve_user_not_found(self):
        from api.cms.services_new.CPALeadService import CPALeadService
        user = CPALeadService._resolve_user('99999')
        self.assertIsNone(user)


class TestVirtualCurrency(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory, VirtualCurrencyFactory
        self.user = UserFactory.create()
        self.vc = VirtualCurrencyFactory.create(usd_ratio=100)

    def test_usd_to_virtual_conversion(self):
        coins = self.vc.usd_to_virtual(Decimal('1.00'))
        self.assertEqual(coins, Decimal('100'))

    def test_virtual_to_usd_conversion(self):
        usd = self.vc.virtual_to_usd(Decimal('100'))
        self.assertEqual(usd, Decimal('1.0000'))

    def test_add_coins_to_balance(self):
        from api.cms.models_new.cpalead import UserVirtualBalance
        balance = UserVirtualBalance.objects.create(
            user=self.user, currency=self.vc, balance=Decimal('0')
        )
        result = balance.add_coins(Decimal('500'))
        self.assertTrue(result)
        balance.refresh_from_db()
        self.assertEqual(balance.balance, Decimal('500'))

    def test_spend_coins(self):
        from api.cms.models_new.cpalead import UserVirtualBalance
        balance = UserVirtualBalance.objects.create(
            user=self.user, currency=self.vc, balance=Decimal('100')
        )
        result = balance.spend_coins(Decimal('50'))
        self.assertTrue(result)
        balance.refresh_from_db()
        self.assertEqual(balance.balance, Decimal('50'))

    def test_spend_more_than_balance_fails(self):
        from api.cms.models_new.cpalead import UserVirtualBalance
        balance = UserVirtualBalance.objects.create(
            user=self.user, currency=self.vc, balance=Decimal('10')
        )
        result = balance.spend_coins(Decimal('100'))
        self.assertFalse(result)
        balance.refresh_from_db()
        self.assertEqual(balance.balance, Decimal('10'))


class TestContentLocker(TestCase):
    def setUp(self):
        from api.cms.factories import ContentLockerFactory, UserFactory
        self.user = UserFactory.create()
        self.locker = ContentLockerFactory.create(unlock_mode='24h', zero_hours_mode=False)
        self.zero_locker = ContentLockerFactory.create(zero_hours_mode=True)

    def test_locker_is_locked_for_new_user(self):
        locked = self.locker.is_locked_for_user(user=self.user)
        self.assertTrue(locked)

    def test_zero_hours_locker_always_locked(self):
        locked = self.zero_locker.is_locked_for_user(user=self.user)
        self.assertTrue(locked)

    def test_record_view_increments_counter(self):
        initial = self.locker.total_views
        self.locker.record_view()
        self.locker.refresh_from_db()
        self.assertEqual(self.locker.total_views, initial + 1)


class TestEarningCapService(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(
            username='capuser', password='pass'
        )

    def test_can_earn_no_config(self):
        from api.cms.services_new.CPALeadService import EarningCapService
        can, remaining = EarningCapService.can_earn(self.user, Decimal('1.0'), None)
        self.assertTrue(can)

    def test_today_earnings_starts_at_zero(self):
        from api.cms.services_new.CPALeadService import EarningCapService
        earned = EarningCapService.get_today_earnings(self.user)
        self.assertEqual(earned, Decimal('0'))
