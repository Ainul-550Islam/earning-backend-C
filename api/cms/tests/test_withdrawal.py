# api/cms/tests/test_withdrawal.py
"""Tests for Withdrawal and Payout system."""
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
from decimal import Decimal


class TestWithdrawalService(TestCase):
    def setUp(self):
        from api.cms.factories import (
            UserFactory, VirtualCurrencyFactory,
            UserVirtualBalanceFactory, UserProfileFactory
        )
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()
        self.vc = VirtualCurrencyFactory.create(usd_ratio=100)
        self.balance = UserVirtualBalanceFactory.create(
            user=self.user, currency=self.vc, balance=2000
        )
        self.profile = UserProfileFactory.create(user=self.user)

    def test_request_withdrawal_success(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        result = WithdrawalService.request_withdrawal(
            user=self.user, method='paypal',
            account_id='user@paypal.com',
            coins_amount=Decimal('1000'),
        )
        self.assertTrue(result['success'])
        self.assertGreater(result['net_usd'], 0)
        self.assertEqual(result['method'], 'paypal')

    def test_request_withdrawal_insufficient_balance(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        result = WithdrawalService.request_withdrawal(
            user=self.user, method='paypal',
            account_id='user@paypal.com',
            coins_amount=Decimal('999999'),
        )
        self.assertFalse(result['success'])
        self.assertIn('balance', result['error'].lower())

    def test_usdt_minimum_25_usd(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        # 1 coin = $0.01 → need 2500 coins for $25 USDT minimum
        result = WithdrawalService.request_withdrawal(
            user=self.user, method='usdt',
            account_id='TRXaddress123',
            coins_amount=Decimal('100'),  # Only $1 — below $25 min
        )
        self.assertFalse(result['success'])
        self.assertIn('25', result['error'])  # mentions $25 minimum

    def test_get_withdrawal_history(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        history = WithdrawalService.get_history(self.user)
        self.assertIsInstance(history, list)

    def test_fee_calculation(self):
        from api.cms.logic import calculate_withdrawal_fee
        fee, net = calculate_withdrawal_fee(Decimal('100.00'), Decimal('0.02'))
        self.assertEqual(fee, Decimal('2.0000'))
        self.assertEqual(net, Decimal('98.0000'))

    def test_add_payout_method(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        result = WithdrawalService.add_method(
            self.user, 'payoneer', 'payoneer@user.com'
        )
        self.assertTrue(result['success'])

    def test_get_user_methods(self):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        WithdrawalService.add_method(self.user, 'paypal', 'user@paypal.com')
        methods = WithdrawalService.get_user_methods(self.user)
        self.assertGreater(len(methods), 0)


class TestUserProfile(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.user = UserFactory.create()

    def test_get_or_create_profile(self):
        from api.cms.services_new.WithdrawalService import UserProfileService
        profile = UserProfileService.get_or_create(self.user)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.user, self.user)

    def test_calculate_user_level(self):
        from api.cms.logic import calculate_user_level
        self.assertEqual(calculate_user_level(0), 1)
        self.assertEqual(calculate_user_level(10), 2)
        self.assertEqual(calculate_user_level(100), 4)
        self.assertEqual(calculate_user_level(1000), 7)
