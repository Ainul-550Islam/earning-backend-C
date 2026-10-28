# api/cms/tests/test_leaderboard.py
"""Tests for Leaderboard and Streak systems."""
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


class TestLeaderboardService(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()

    def test_update_score_creates_entry(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.update_score(self.user, Decimal('10.00'), 'earnings', 'weekly')
        self.assertTrue(result)

    def test_get_top_returns_list(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        LeaderboardService.update_score(self.user, Decimal('5.00'), 'earnings', 'weekly')
        LeaderboardService.refresh_ranks('weekly', 'earnings')
        top = LeaderboardService.get_top('weekly', 'earnings', 10)
        self.assertIsInstance(top, list)

    def test_get_user_rank_not_found(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        rank = LeaderboardService.get_user_rank(self.user, 'weekly', 'earnings')
        self.assertIn('rank', rank)

    def test_refresh_ranks_bulk_update(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        from api.cms.factories import UserFactory
        users = [UserFactory.create() for _ in range(5)]
        for i, u in enumerate(users):
            LeaderboardService.update_score(u, Decimal(str((i+1)*10)), 'earnings', 'weekly')
        count = LeaderboardService.refresh_ranks('weekly', 'earnings')
        self.assertGreaterEqual(count, 5)


class TestStreakService(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()

    def test_first_earn_starts_streak(self):
        from api.cms.services_new.LeaderboardService import StreakService
        result = StreakService.record_earn(self.user)
        self.assertEqual(result['current_streak'], 1)

    def test_same_day_earn_no_duplicate(self):
        from api.cms.services_new.LeaderboardService import StreakService
        StreakService.record_earn(self.user)
        result2 = StreakService.record_earn(self.user)
        self.assertEqual(result2['current_streak'], 1)

    def test_streak_multiplier_calculated(self):
        from api.cms.logic import calculate_streak_multiplier
        multiplier = calculate_streak_multiplier(10)
        self.assertGreater(multiplier, Decimal('1.0'))
        self.assertLessEqual(multiplier, Decimal('2.0'))

    def test_get_streak_info_new_user(self):
        from api.cms.services_new.LeaderboardService import StreakService
        info = StreakService.get_streak_info(self.user)
        self.assertEqual(info['current_streak'], 0)
        self.assertEqual(info['multiplier'], 1.0)
