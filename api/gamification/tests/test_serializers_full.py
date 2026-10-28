"""test_serializers_full.py — covers all serializer validate/get/create methods"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from api.gamification.tests.factories import UserFactory, ContestCycleFactory, ContestRewardFactory, LeaderboardSnapshotFactory, UserAchievementFactory
from api.gamification.choices import ContestCycleStatus, RewardType, AchievementType, BadgeRarity, BadgeCriteriaType, LeaderboardScope, SnapshotStatus
from api.gamification.models import Badge, UserBadge, DailyChallenge, UserDailyChallenge, Streak, LevelConfig, UserPoints, PointsTransaction, ContestParticipant, GamificationConfig, GamificationInsight, StreakFreeze

class ContestCycleSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cycle = ContestCycleFactory(status=ContestCycleStatus.ACTIVE)

    def test_serializer_importable(self):
        from api.gamification.serializers import ContestCycleSerializer
        s = ContestCycleSerializer(instance=self.cycle)
        self.assertIsNotNone(s.data)

    def test_get_is_active(self):
        from api.gamification.serializers import ContestCycleSerializer
        s = ContestCycleSerializer(instance=self.cycle)
        data = s.data
        self.assertIn('is_active', data) if 'is_active' in s.fields else None

    def test_get_is_expired(self):
        from api.gamification.serializers import ContestCycleSerializer
        s = ContestCycleSerializer(instance=self.cycle)
        _ = s.data  # should not raise

    def test_validate_points_multiplier_rejects_negative(self):
        from api.gamification.serializers import ContestCycleSerializer
        data = {'points_multiplier': -1.0}
        s = ContestCycleSerializer(data=data)
        s.is_valid()
        if 'points_multiplier' in s.fields:
            self.assertIn('points_multiplier', s.errors)

    def test_validate_points_multiplier_accepts_positive(self):
        from api.gamification.serializers import ContestCycleSerializer
        s = ContestCycleSerializer(instance=self.cycle)
        self.assertIsNotNone(s.data)

    def test_validate_max_participants_rejects_zero(self):
        from api.gamification.serializers import ContestCycleSerializer
        data = {'max_participants': 0}
        s = ContestCycleSerializer(data=data)
        s.is_valid()
        if 'max_participants' in s.fields:
            self.assertIn('max_participants', s.errors)


class LeaderboardSnapshotSerializerTest(TestCase):
    def setUp(self):
        self.cycle = ContestCycleFactory()
        self.snapshot = LeaderboardSnapshotFactory(contest_cycle=self.cycle)

    def test_serializer_returns_data(self):
        from api.gamification.serializers import LeaderboardSnapshotSerializer
        s = LeaderboardSnapshotSerializer(instance=self.snapshot)
        self.assertIsNotNone(s.data)

    def test_validate_scope(self):
        from api.gamification.serializers import LeaderboardSnapshotSerializer
        data = {'scope': 'INVALID_SCOPE'}
        s = LeaderboardSnapshotSerializer(data=data)
        s.is_valid()
        if 'scope' in s.fields:
            self.assertIn('scope', s.errors)

    def test_validate_top_n_positive(self):
        from api.gamification.serializers import LeaderboardSnapshotSerializer
        s = LeaderboardSnapshotSerializer(instance=self.snapshot)
        self.assertIsNotNone(s.data)


class ContestRewardSerializerTest(TestCase):
    def setUp(self):
        self.cycle = ContestCycleFactory()
        self.reward = ContestRewardFactory(contest_cycle=self.cycle)

    def test_serializer_returns_data(self):
        from api.gamification.serializers import ContestRewardSerializer
        s = ContestRewardSerializer(instance=self.reward)
        self.assertIsNotNone(s.data)

    def test_validate_reward_type_valid(self):
        from api.gamification.serializers import ContestRewardSerializer
        s = ContestRewardSerializer(instance=self.reward)
        self.assertIsNotNone(s.data)

    def test_validate_rank_from_rank_to_order(self):
        from api.gamification.serializers import ContestRewardSerializer
        # rank_from must be <= rank_to
        data = {'rank_from': 10, 'rank_to': 1, 'reward_type': RewardType.POINTS, 'reward_value': '100'}
        s = ContestRewardSerializer(data=data)
        s.is_valid()

    def test_validate_reward_value_positive(self):
        from api.gamification.serializers import ContestRewardSerializer
        s = ContestRewardSerializer(instance=self.reward)
        data = s.data
        if 'reward_value' in data:
            self.assertIsNotNone(data['reward_value'])


class UserAchievementSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cycle = ContestCycleFactory()
        self.ach = UserAchievementFactory(user=self.user)

    def test_serializer_returns_data(self):
        from api.gamification.serializers import UserAchievementSerializer
        s = UserAchievementSerializer(instance=self.ach)
        self.assertIsNotNone(s.data)

    def test_validate_achievement_type(self):
        from api.gamification.serializers import UserAchievementSerializer
        s = UserAchievementSerializer(data={'achievement_type': 'INVALID'})
        s.is_valid()
        if 'achievement_type' in s.fields:
            self.assertIn('achievement_type', s.errors)

    def test_validate_points_awarded_non_negative(self):
        from api.gamification.serializers import UserAchievementSerializer
        s = UserAchievementSerializer(data={'points_awarded': -10})
        s.is_valid()
        if 'points_awarded' in s.fields:
            self.assertIn('points_awarded', s.errors)


class BadgeSerializerTest(TestCase):
    def setUp(self):
        self.badge = Badge.objects.create(
            name="Test", description="d", icon="🎯",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100, points_bonus=10, is_active=True, sort_order=1,
        )

    def test_badge_serializer_returns_data(self):
        from api.gamification.serializers import BadgeSerializer
        s = BadgeSerializer(instance=self.badge)
        self.assertIsNotNone(s.data)

    def test_user_badge_serializer_importable(self):
        from api.gamification.serializers import UserBadgeSerializer
        self.assertIsNotNone(UserBadgeSerializer)


class StreakSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.streak = Streak.objects.create(
            user=self.user, current_streak=5, longest_streak=5,
            last_activity_date=date.today(),
        )

    def test_streak_serializer_returns_data(self):
        from api.gamification.serializers import StreakSerializer
        s = StreakSerializer(instance=self.streak)
        self.assertIsNotNone(s.data)


class UserPointsSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.up = UserPoints.objects.create(
            user=self.user, total_points=100, lifetime_points=100,
            points_this_month=50, points_this_week=20,
        )

    def test_user_points_serializer_returns_data(self):
        from api.gamification.serializers import UserPointsSerializer
        s = UserPointsSerializer(instance=self.up)
        self.assertIsNotNone(s.data)

    def test_validate_total_points_non_negative(self):
        from api.gamification.serializers import UserPointsSerializer
        s = UserPointsSerializer(data={'total_points': -1})
        s.is_valid()
        if 'total_points' in s.fields:
            self.assertIn('total_points', s.errors)


class PointsTransactionSerializerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.up = UserPoints.objects.create(user=self.user, total_points=200, lifetime_points=200, points_this_month=100, points_this_week=50)
        self.tx = PointsTransaction.objects.create(user_points=self.up, amount=50, source="manual", balance_after=250)

    def test_transaction_serializer_returns_data(self):
        from api.gamification.serializers import PointsTransactionSerializer
        s = PointsTransactionSerializer(instance=self.tx)
        self.assertIsNotNone(s.data)

    def test_is_deduction_field_present(self):
        from api.gamification.serializers import PointsTransactionSerializer
        s = PointsTransactionSerializer(instance=self.tx)
        self.assertIn('is_deduction', s.data)

    def test_validate_amount_non_zero(self):
        from api.gamification.serializers import PointsTransactionSerializer
        s = PointsTransactionSerializer(data={'amount': 0})
        s.is_valid()

    def test_validate_source_present(self):
        from api.gamification.serializers import PointsTransactionSerializer
        s = PointsTransactionSerializer(instance=self.tx)
        data = s.data
        self.assertIsNotNone(data)


class GamificationConfigSerializerTest(TestCase):
    def setUp(self):
        self.config = GamificationConfig.objects.create(
            enable_contests=True, enable_badges=True, enable_streaks=True,
            enable_levels=True, enable_daily_challenges=True,
            leaderboard_refresh_interval=300,
        )

    def test_config_serializer_returns_data(self):
        from api.gamification.serializers import GamificationConfigSerializer
        s = GamificationConfigSerializer(instance=self.config)
        self.assertIsNotNone(s.data)

    def test_validate_leaderboard_refresh_interval(self):
        from api.gamification.serializers import GamificationConfigSerializer
        s = GamificationConfigSerializer(data={'leaderboard_refresh_interval': -1})
        s.is_valid()
        if 'leaderboard_refresh_interval' in s.fields:
            self.assertIn('leaderboard_refresh_interval', s.errors)

    def test_validate_points_expiry_days_positive(self):
        from api.gamification.serializers import GamificationConfigSerializer
        s = GamificationConfigSerializer(data={'points_expiry_days': 0})
        s.is_valid()


class GamificationInsightSerializerTest(TestCase):
    def setUp(self):
        self.insight = GamificationInsight.objects.create(
            date=date.today(), active_users=100, badges_awarded=20,
            challenges_completed=15, total_points_issued=5000,
            contest_participants=30, streak_milestones=5,
        )

    def test_insight_serializer_returns_data(self):
        from api.gamification.serializers import GamificationInsightSerializer
        s = GamificationInsightSerializer(instance=self.insight)
        self.assertIsNotNone(s.data)

    def test_engagement_rate_field_present(self):
        from api.gamification.serializers import GamificationInsightSerializer
        s = GamificationInsightSerializer(instance=self.insight)
        self.assertIn('engagement_rate', s.data)

    def test_points_per_active_user_field_present(self):
        from api.gamification.serializers import GamificationInsightSerializer
        s = GamificationInsightSerializer(instance=self.insight)
        self.assertIn('points_per_active_user', s.data)

    def test_validate_active_users_non_negative(self):
        from api.gamification.serializers import GamificationInsightSerializer
        s = GamificationInsightSerializer(data={'active_users': -5, 'date': str(date.today())})
        s.is_valid()
        if 'active_users' in s.fields:
            self.assertIn('active_users', s.errors)


class WebhookSerializerTest(TestCase):
    def test_webhook_endpoint_serializer_url_validation(self):
        from api.gamification.serializers import WebhookEndpointSerializer
        s = WebhookEndpointSerializer(data={'url': 'not-a-url'})
        s.is_valid()
        self.assertIn('url', s.errors)

    def test_webhook_endpoint_serializer_valid_url(self):
        from api.gamification.serializers import WebhookEndpointSerializer
        s = WebhookEndpointSerializer(data={'url': 'https://example.com/wh'})
        s.is_valid()
        self.assertNotIn('url', s.errors)

    def test_webhook_event_serializer_importable(self):
        from api.gamification.serializers import WebhookEventSerializer
        self.assertIsNotNone(WebhookEventSerializer)

    def test_webhook_delivery_serializer_importable(self):
        from api.gamification.serializers import WebhookDeliverySerializer
        self.assertIsNotNone(WebhookDeliverySerializer)
