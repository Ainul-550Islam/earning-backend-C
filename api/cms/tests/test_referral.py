# api/cms/tests/test_referral.py
"""Tests for Referral System."""
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
from unittest.mock import patch


class TestReferralService(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory, VirtualCurrencyFactory
        self.referrer = UserFactory.create(username='referrer')
        self.referred = UserFactory.create(username='referred')
        self.vc = VirtualCurrencyFactory.create(usd_ratio=100)

    def test_get_or_create_code(self):
        from api.cms.services_new.ReferralService import ReferralService
        code = ReferralService.get_or_create_code(self.referrer)
        self.assertIsNotNone(code)
        self.assertEqual(len(code), 8)
        # Same user always gets same code
        code2 = ReferralService.get_or_create_code(self.referrer)
        self.assertEqual(code, code2)

    def test_apply_valid_code(self):
        from api.cms.services_new.ReferralService import ReferralService
        code = ReferralService.get_or_create_code(self.referrer)
        result = ReferralService.apply_referral(self.referred, code)
        self.assertTrue(result['success'])
        self.assertEqual(result['referrer_username'], 'referrer')

    def test_apply_invalid_code(self):
        from api.cms.services_new.ReferralService import ReferralService
        result = ReferralService.apply_referral(self.referred, 'INVALIDXXX')
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'invalid_code')

    def test_self_referral_blocked(self):
        from api.cms.services_new.ReferralService import ReferralService
        code = ReferralService.get_or_create_code(self.referrer)
        result = ReferralService.apply_referral(self.referrer, code)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'self_referral')

    def test_double_referral_blocked(self):
        from api.cms.services_new.ReferralService import ReferralService
        from api.cms.factories import UserFactory
        third_user = UserFactory.create(username='third')
        code = ReferralService.get_or_create_code(self.referrer)
        ReferralService.apply_referral(self.referred, code)
        code2 = ReferralService.get_or_create_code(third_user)
        result = ReferralService.apply_referral(self.referred, code2)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'already_referred')

    def test_calculate_referral_bonus(self):
        from api.cms.logic import calculate_referral_bonus
        bonus = calculate_referral_bonus(Decimal('10.00'), Decimal('0.05'))
        self.assertEqual(bonus, Decimal('0.5000'))

    def test_referral_stats_empty(self):
        from api.cms.services_new.ReferralService import ReferralService
        stats = ReferralService.get_referral_stats(self.referrer)
        self.assertIn('referral_code', stats)
        self.assertEqual(stats['total_referrals'], 0)
        self.assertEqual(stats['total_bonus_usd'], 0.0)
        self.assertEqual(stats['bonus_rate_pct'], 5.0)


class TestReferralEarning(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory, VirtualCurrencyFactory
        self.referrer = UserFactory.create(username='ref_earner')
        self.referred = UserFactory.create(username='ref_new')
        self.vc = VirtualCurrencyFactory.create(usd_ratio=100)
        from api.cms.services_new.ReferralService import ReferralService
        code = ReferralService.get_or_create_code(self.referrer)
        ReferralService.apply_referral(self.referred, code)

    def test_award_referral_bonus(self):
        from api.cms.services_new.ReferralService import ReferralService
        import uuid
        lead_id = f"TEST_{uuid.uuid4().hex[:8]}"
        bonus = ReferralService.award_referral_bonus(
            self.referred, Decimal('1.00'), lead_id=lead_id
        )
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus, Decimal('0.0500'))

    def test_dedup_same_lead_id(self):
        from api.cms.services_new.ReferralService import ReferralService
        import uuid
        lead_id = f"DEDUP_{uuid.uuid4().hex[:8]}"
        bonus1 = ReferralService.award_referral_bonus(
            self.referred, Decimal('1.00'), lead_id=lead_id
        )
        bonus2 = ReferralService.award_referral_bonus(
            self.referred, Decimal('1.00'), lead_id=lead_id
        )
        self.assertIsNotNone(bonus1)
        self.assertIsNone(bonus2)
