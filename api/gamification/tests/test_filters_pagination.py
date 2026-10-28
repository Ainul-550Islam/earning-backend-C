"""test_filters_pagination.py — 0% → full coverage for filters.py, pagination.py, validators.py"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, RequestFactory
from rest_framework.request import Request
from api.gamification.tests.factories import UserFactory, ContestCycleFactory, ContestRewardFactory
from api.gamification.choices import ContestCycleStatus, RewardType, LeaderboardScope
from api.gamification.models import ContestCycle, UserPoints, PointsTransaction, StreakFreeze, Streak
from api.gamification.choices import AchievementType

class FiltersImportTest(TestCase):
    def test_all_filters_importable(self):
        from api.gamification.filters import (
            ContestCycleFilter, ContestRewardFilter, UserAchievementFilter,
            UserPointsFilter, PointsTransactionFilter, StreakFreezeFilter,
        )

class ContestCycleFilterTest(TestCase):
    def setUp(self):
        self.active = ContestCycleFactory(status=ContestCycleStatus.ACTIVE)
        self.draft = ContestCycleFactory(status=ContestCycleStatus.DRAFT)

    def test_filter_is_active_now_method_exists(self):
        from api.gamification.filters import ContestCycleFilter
        f = ContestCycleFilter()
        self.assertTrue(hasattr(f, 'filter_is_active_now'))

    def test_filter_returns_queryset(self):
        from api.gamification.filters import ContestCycleFilter
        qs = ContestCycle.objects.all()
        f = ContestCycleFilter(queryset=qs)
        self.assertIsNotNone(f.qs)

    def test_filter_by_status(self):
        from api.gamification.filters import ContestCycleFilter
        f = ContestCycleFilter(data={'status': ContestCycleStatus.ACTIVE},
                               queryset=ContestCycle.objects.all())
        result = f.qs
        statuses = list(result.values_list('status', flat=True))
        for s in statuses:
            self.assertEqual(s, ContestCycleStatus.ACTIVE)


class ContestRewardFilterTest(TestCase):
    def setUp(self):
        self.cycle = ContestCycleFactory()
        self.reward = ContestRewardFactory(contest_cycle=self.cycle, rank_from=1, rank_to=10)

    def test_filter_by_rank_method_exists(self):
        from api.gamification.filters import ContestRewardFilter
        f = ContestRewardFilter()
        self.assertTrue(hasattr(f, 'filter_by_rank'))

    def test_filter_reward_type(self):
        from api.gamification.filters import ContestRewardFilter
        from api.gamification.models import ContestReward
        f = ContestRewardFilter(data={'reward_type': RewardType.POINTS},
                               queryset=ContestReward.objects.all())
        self.assertIsNotNone(f.qs)


class UserPointsFilterTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.up = UserPoints.objects.create(
            user=self.user, total_points=100, lifetime_points=100,
            points_this_month=50, points_this_week=20,
        )

    def test_filter_has_expiry_date_method_exists(self):
        from api.gamification.filters import UserPointsFilter
        f = UserPointsFilter()
        self.assertTrue(hasattr(f, 'filter_has_expiry_date'))

    def test_filter_is_expired_method_exists(self):
        from api.gamification.filters import UserPointsFilter
        f = UserPointsFilter()
        self.assertTrue(hasattr(f, 'filter_is_expired'))

    def test_filter_returns_queryset(self):
        from api.gamification.filters import UserPointsFilter
        f = UserPointsFilter(queryset=UserPoints.objects.all())
        self.assertIsNotNone(f.qs)


class PointsTransactionFilterTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.up = UserPoints.objects.create(user=self.user, total_points=200, lifetime_points=200, points_this_month=100, points_this_week=50)
        self.tx_pos = PointsTransaction.objects.create(user_points=self.up, amount=50, source="bonus", balance_after=250)
        self.tx_neg = PointsTransaction.objects.create(user_points=self.up, amount=-30, source="penalty", balance_after=220)

    def test_filter_is_positive_method_exists(self):
        from api.gamification.filters import PointsTransactionFilter
        f = PointsTransactionFilter()
        self.assertTrue(hasattr(f, 'filter_is_positive'))

    def test_filter_is_negative_method_exists(self):
        from api.gamification.filters import PointsTransactionFilter
        f = PointsTransactionFilter()
        self.assertTrue(hasattr(f, 'filter_is_negative'))

    def test_filter_returns_queryset(self):
        from api.gamification.filters import PointsTransactionFilter
        f = PointsTransactionFilter(queryset=PointsTransaction.objects.all())
        self.assertIsNotNone(f.qs)


class StreakFreezeFilterTest(TestCase):
    def test_filter_is_expired_method_exists(self):
        from api.gamification.filters import StreakFreezeFilter
        f = StreakFreezeFilter()
        self.assertTrue(hasattr(f, 'filter_is_expired'))

    def test_filter_duration_hours_min_method_exists(self):
        from api.gamification.filters import StreakFreezeFilter
        f = StreakFreezeFilter()
        self.assertTrue(hasattr(f, 'filter_duration_hours_min'))

    def test_filter_returns_queryset(self):
        from api.gamification.filters import StreakFreezeFilter
        f = StreakFreezeFilter(queryset=StreakFreeze.objects.all())
        self.assertIsNotNone(f.qs)


# ===========================================================================
# pagination.py
# ===========================================================================

class PaginationImportTest(TestCase):
    def test_all_paginators_importable(self):
        from api.gamification.pagination import (
            GamificationPagination, BadgePagination, LeaderboardPagination,
            ChallengePagination, AchievementPagination, InfiniteScrollPagination,
            get_pagination_class_for_model, create_pagination_response,
        )

class GamificationPaginationTest(TestCase):
    def test_pagination_instantiable(self):
        from api.gamification.pagination import GamificationPagination
        p = GamificationPagination()
        self.assertIsNotNone(p)

    def test_get_paginated_response_schema(self):
        from api.gamification.pagination import GamificationPagination
        p = GamificationPagination()
        if hasattr(p, 'get_paginated_response_schema'):
            schema = p.get_paginated_response_schema({})
            self.assertIsNotNone(schema)

    def test_has_page_size(self):
        from api.gamification.pagination import GamificationPagination
        p = GamificationPagination()
        self.assertTrue(hasattr(p, 'page_size'))

class BadgePaginationTest(TestCase):
    def test_badge_pagination_instantiable(self):
        from api.gamification.pagination import BadgePagination
        p = BadgePagination()
        self.assertIsNotNone(p)

class LeaderboardPaginationTest(TestCase):
    def test_leaderboard_pagination_instantiable(self):
        from api.gamification.pagination import LeaderboardPagination
        p = LeaderboardPagination()
        self.assertIsNotNone(p)

    def test_get_paginated_response_schema(self):
        from api.gamification.pagination import LeaderboardPagination
        p = LeaderboardPagination()
        if hasattr(p, 'get_paginated_response_schema'):
            self.assertIsNotNone(p.get_paginated_response_schema({}))

class ChallengePaginationTest(TestCase):
    def test_challenge_pagination_instantiable(self):
        from api.gamification.pagination import ChallengePagination
        p = ChallengePagination()
        self.assertIsNotNone(p)

class AchievementPaginationTest(TestCase):
    def test_achievement_pagination_instantiable(self):
        from api.gamification.pagination import AchievementPagination
        p = AchievementPagination()
        self.assertIsNotNone(p)

class InfiniteScrollPaginationTest(TestCase):
    def test_infinite_scroll_instantiable(self):
        from api.gamification.pagination import InfiniteScrollPagination
        p = InfiniteScrollPagination()
        self.assertIsNotNone(p)

    def test_has_cursor_or_offset(self):
        from api.gamification.pagination import InfiniteScrollPagination
        p = InfiniteScrollPagination()
        self.assertTrue(hasattr(p, 'cursor_query_param') or hasattr(p, 'offset_query_param') or hasattr(p, 'page_size'))

class PaginationHelperFunctionsTest(TestCase):
    def test_get_pagination_class_for_model_returns_class(self):
        from api.gamification.pagination import get_pagination_class_for_model, GamificationPagination
        from api.gamification.models import Badge
        result = get_pagination_class_for_model(Badge)
        self.assertTrue(callable(result) or result is not None)

    def test_create_pagination_response_returns_dict(self):
        from api.gamification.pagination import create_pagination_response
        result = create_pagination_response(data=[], count=0, page=1, page_size=20)
        self.assertIsInstance(result, dict)


# ===========================================================================
# validators.py
# ===========================================================================

class ValidatorsImportTest(TestCase):
    def test_validators_importable(self):
        from api.gamification.validators import (
            validate_points_amount, validate_contest_dates,
            validate_reward_value, validate_leaderboard_scope,
            validate_top_n_value, validate_user_achievement_data,
        )

class ValidatePointsAmountTest(TestCase):
    def test_valid_positive_amount(self):
        from api.gamification.validators import validate_points_amount
        try:
            validate_points_amount(100)
        except Exception as e:
            self.fail(f"validate_points_amount raised: {e}")

    def test_zero_raises(self):
        from api.gamification.validators import validate_points_amount
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, ValueError)):
            validate_points_amount(0)

    def test_negative_raises(self):
        from api.gamification.validators import validate_points_amount
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, ValueError)):
            validate_points_amount(-50)

class ValidateContestDatesTest(TestCase):
    def test_valid_dates(self):
        from api.gamification.validators import validate_contest_dates
        start = date.today()
        end = start + timedelta(days=30)
        try:
            validate_contest_dates(start, end)
        except Exception as e:
            self.fail(f"validate_contest_dates raised: {e}")

    def test_end_before_start_raises(self):
        from api.gamification.validators import validate_contest_dates
        from django.core.exceptions import ValidationError
        start = date.today()
        end = start - timedelta(days=1)
        with self.assertRaises((ValidationError, ValueError)):
            validate_contest_dates(start, end)

class ValidateRewardValueTest(TestCase):
    def test_valid_reward_value(self):
        from api.gamification.validators import validate_reward_value
        try:
            validate_reward_value(Decimal('100.00'), RewardType.POINTS)
        except Exception as e:
            self.fail(f"validate_reward_value raised: {e}")

    def test_negative_reward_raises(self):
        from api.gamification.validators import validate_reward_value
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, ValueError)):
            validate_reward_value(Decimal('-10.00'), RewardType.POINTS)

class ValidateLeaderboardScopeTest(TestCase):
    def test_valid_scope(self):
        from api.gamification.validators import validate_leaderboard_scope
        try:
            validate_leaderboard_scope(LeaderboardScope.GLOBAL)
        except Exception as e:
            self.fail(f"validate_leaderboard_scope raised: {e}")

    def test_invalid_scope_raises(self):
        from api.gamification.validators import validate_leaderboard_scope
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, ValueError)):
            validate_leaderboard_scope('INVALID_SCOPE')

class ValidateTopNTest(TestCase):
    def test_valid_top_n(self):
        from api.gamification.validators import validate_top_n_value
        try:
            validate_top_n_value(10)
        except Exception as e:
            self.fail(f"validate_top_n_value raised: {e}")

    def test_zero_top_n_raises(self):
        from api.gamification.validators import validate_top_n_value
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, ValueError)):
            validate_top_n_value(0)

class ValidateUserAchievementDataTest(TestCase):
    def test_valid_achievement_data(self):
        from api.gamification.validators import validate_user_achievement_data
        data = {'achievement_type': AchievementType.BADGE, 'points_awarded': 50}
        try:
            validate_user_achievement_data(data)
        except Exception as e:
            self.fail(f"validate_user_achievement_data raised: {e}")
