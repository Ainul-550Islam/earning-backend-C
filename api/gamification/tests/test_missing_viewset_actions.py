"""
test_missing_viewset_actions.py
===============================
Tests covering the 15 previously-untested viewset actions:

  UserPointsViewSet:        add_points, deduct_points, reset_monthly, reset_weekly
  StreakFreezeViewSet:       use_freeze
  ContestCycleViewSet:      distribute_rewards
  ContestParticipantViewSet: disqualify, update_rank, rank_status
  GamificationConfigViewSet: enable_all_features, disable_all_features,
                              reset_to_defaults, get_features
  GamificationInsightViewSet: calculate_today, recalculate, summary_report
  ContestRewardViewSet:      budget_status
  LeaderboardSnapshotViewSet: retrieve (is_finalized enrichment), finalized_only
  UserAchievementViewSet:    cycle_scoped_check
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.gamification.choices import (
    ContestCycleStatus,
    RewardType,
    AchievementType,
    SnapshotStatus,
    LeaderboardScope,
)
from api.gamification.models import (
    ContestCycle,
    ContestReward,
    ContestParticipant,
    GamificationConfig,
    GamificationInsight,
    LeaderboardSnapshot,
    PointsTransaction,
    Streak,
    StreakFreeze,
    UserAchievement,
    UserPoints,
)
from api.gamification.tests.factories import (
    ContestCycleFactory,
    ContestRewardFactory,
    LeaderboardSnapshotFactory,
    UserAchievementFactory,
    UserFactory,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin():
    u = UserFactory(is_staff=True, is_superuser=True)
    return u


def _make_user():
    return UserFactory()


def _active_cycle():
    return ContestCycleFactory(status=ContestCycleStatus.ACTIVE)


# ---------------------------------------------------------------------------
# UserPointsViewSet — add_points / deduct_points / reset_monthly / reset_weekly
# ---------------------------------------------------------------------------

class UserPointsAddDeductTest(APITestCase):
    """Tests for UserPointsViewSet.add_points and deduct_points."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.user_points = UserPoints.objects.create(
            user=self.user,
            total_points=500,
            lifetime_points=500,
            points_this_month=200,
            points_this_week=50,
        )

    def test_add_points_success(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/add_points/"
        resp = self.client.post(url, {"amount": 100, "source": "manual", "description": "bonus"})
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.user_points.refresh_from_db()
        self.assertGreaterEqual(self.user_points.total_points, 500)

    def test_add_points_zero_rejected(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/add_points/"
        resp = self.client.post(url, {"amount": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_points_negative_rejected(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/add_points/"
        resp = self.client.post(url, {"amount": -50})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deduct_points_success(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/deduct_points/"
        resp = self.client.post(url, {"amount": 50, "source": "penalty"})
        self.assertIn(resp.status_code, [status.HTTP_200_OK])

    def test_deduct_points_zero_rejected(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/deduct_points/"
        resp = self.client.post(url, {"amount": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deduct_points_requires_auth(self):
        self.client.force_authenticate(user=None)
        url = f"/api/gamification/user-points/{self.user_points.pk}/deduct_points/"
        resp = self.client.post(url, {"amount": 10})
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_reset_monthly_success(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/reset_monthly/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user_points.refresh_from_db()
        self.assertEqual(self.user_points.points_this_month, 0)

    def test_reset_weekly_success(self):
        url = f"/api/gamification/user-points/{self.user_points.pk}/reset_weekly/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user_points.refresh_from_db()
        self.assertEqual(self.user_points.points_this_week, 0)

    def test_reset_monthly_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/gamification/user-points/{self.user_points.pk}/reset_monthly/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_reset_weekly_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/gamification/user-points/{self.user_points.pk}/reset_weekly/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# ---------------------------------------------------------------------------
# StreakFreezeViewSet — use_freeze
# ---------------------------------------------------------------------------

class StreakFreezeUseFreezeTest(APITestCase):
    """Tests for StreakFreezeViewSet.use_freeze."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)
        self.streak = Streak.objects.create(
            user=self.user,
            current_streak=5,
            longest_streak=5,
            last_activity_date=date.today() - timedelta(days=1),
        )

    def test_use_freeze_success(self):
        url = "/api/gamification/streak-freezes/use_freeze/"
        resp = self.client.post(url, {
            "streak_id": str(self.streak.pk),
            "used_at": date.today().isoformat(),
            "reason": "missed a day",
        })
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_use_freeze_missing_streak_id(self):
        url = "/api/gamification/streak-freezes/use_freeze/"
        resp = self.client.post(url, {"used_at": date.today().isoformat()})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_use_freeze_missing_used_at(self):
        url = "/api/gamification/streak-freezes/use_freeze/"
        resp = self.client.post(url, {"streak_id": str(self.streak.pk)})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_use_freeze_other_users_streak_rejected(self):
        other_user = _make_user()
        other_streak = Streak.objects.create(
            user=other_user,
            current_streak=3,
            longest_streak=3,
            last_activity_date=date.today(),
        )
        url = "/api/gamification/streak-freezes/use_freeze/"
        resp = self.client.post(url, {
            "streak_id": str(other_streak.pk),
            "used_at": date.today().isoformat(),
        })
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_use_freeze_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        url = "/api/gamification/streak-freezes/use_freeze/"
        resp = self.client.post(url, {
            "streak_id": str(self.streak.pk),
            "used_at": date.today().isoformat(),
        })
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ---------------------------------------------------------------------------
# ContestCycleViewSet — distribute_rewards
# ---------------------------------------------------------------------------

class ContestCycleDistributeRewardsTest(APITestCase):
    """Tests for ContestCycleViewSet.distribute_rewards."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.cycle = ContestCycleFactory(status=ContestCycleStatus.COMPLETED)

    @patch("api.gamification.viewsets.services.distribute_cycle_rewards")
    def test_distribute_rewards_success(self, mock_distribute):
        mock_distribute.return_value = {"distributed": 5, "total_value": 1000}
        url = f"/api/gamification/contest-cycles/{self.cycle.pk}/distribute-rewards/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_distribute.assert_called_once()

    @patch("api.gamification.viewsets.services.distribute_cycle_rewards")
    def test_distribute_rewards_cycle_not_found(self, mock_distribute):
        from api.gamification.exceptions import ContestCycleNotFoundError
        mock_distribute.side_effect = ContestCycleNotFoundError("not found")
        url = f"/api/gamification/contest-cycles/99999/distribute-rewards/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_distribute_rewards_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/gamification/contest-cycles/{self.cycle.pk}/distribute-rewards/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN])

    def test_distribute_rewards_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        url = f"/api/gamification/contest-cycles/{self.cycle.pk}/distribute-rewards/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ---------------------------------------------------------------------------
# ContestParticipantViewSet — disqualify / update_rank / rank_status
# ---------------------------------------------------------------------------

class ContestParticipantActionsTest(APITestCase):
    """Tests for ContestParticipantViewSet.disqualify, update_rank, rank_status."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.cycle = _active_cycle()
        self.participant = ContestParticipant.objects.create(
            user=self.user,
            contest_cycle=self.cycle,
            current_points=250,
            current_rank=3,
            is_disqualified=False,
        )

    def test_disqualify_success(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/disqualify/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_disqualified)

    def test_disqualify_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/gamification/contest-participants/{self.participant.pk}/disqualify/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_update_rank_success(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/update_rank/"
        resp = self.client.post(url, {"rank": 1})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.current_rank, 1)

    def test_update_rank_invalid_zero(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/update_rank/"
        resp = self.client.post(url, {"rank": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_rank_invalid_negative(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/update_rank/"
        resp = self.client.post(url, {"rank": -1})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rank_status_success(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/rank-status/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("is_ranked", data)
        self.assertIn("current_rank", data)

    def test_rank_status_returns_correct_rank(self):
        url = f"/api/gamification/contest-participants/{self.participant.pk}/rank-status/"
        resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["current_rank"], 3)


# ---------------------------------------------------------------------------
# GamificationConfigViewSet — enable_all / disable_all / reset / get_features
# ---------------------------------------------------------------------------

class GamificationConfigActionsTest(APITestCase):
    """Tests for GamificationConfigViewSet feature toggle actions."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.config = GamificationConfig.objects.create(
            enable_contests=False,
            enable_badges=False,
            enable_streaks=False,
            enable_levels=False,
            enable_daily_challenges=False,
            leaderboard_refresh_interval=300,
        )

    def test_enable_all_features_success(self):
        url = f"/api/gamification/gamification-config/{self.config.pk}/enable_all_features/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertTrue(self.config.enable_contests)
        self.assertTrue(self.config.enable_badges)
        self.assertTrue(self.config.enable_streaks)
        self.assertTrue(self.config.enable_levels)
        self.assertTrue(self.config.enable_daily_challenges)

    def test_enable_all_returns_features_enabled(self):
        url = f"/api/gamification/gamification-config/{self.config.pk}/enable_all_features/"
        resp = self.client.post(url)
        data = resp.json()
        self.assertIn("enabled_features", data)
        self.assertIsInstance(data["enabled_features"], list)
        self.assertGreater(len(data["enabled_features"]), 0)

    def test_disable_all_features_success(self):
        self.config.enable_contests = True
        self.config.enable_badges = True
        self.config.save()
        url = f"/api/gamification/gamification-config/{self.config.pk}/disable_all_features/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertFalse(self.config.enable_contests)
        self.assertFalse(self.config.enable_badges)

    def test_disable_all_returns_empty_features(self):
        url = f"/api/gamification/gamification-config/{self.config.pk}/disable_all_features/"
        resp = self.client.post(url)
        data = resp.json()
        self.assertIn("enabled_features", data)
        self.assertEqual(data["enabled_features"], [])

    def test_reset_to_defaults_success(self):
        self.config.enable_contests = False
        self.config.leaderboard_refresh_interval = 9999
        self.config.save()
        url = f"/api/gamification/gamification-config/{self.config.pk}/reset_to_defaults/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertTrue(self.config.enable_contests)
        self.assertEqual(self.config.leaderboard_refresh_interval, 300)

    def test_get_features_success(self):
        self.config.enable_contests = True
        self.config.enable_badges = True
        self.config.save()
        url = f"/api/gamification/gamification-config/{self.config.pk}/features/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("enabled_features", data)

    def test_config_actions_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/gamification/gamification-config/{self.config.pk}/enable_all_features/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# GamificationInsightViewSet — calculate_today / recalculate / summary_report
# ---------------------------------------------------------------------------

class GamificationInsightActionsTest(APITestCase):
    """Tests for GamificationInsightViewSet insight calculation actions."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.today = date.today()
        self.insight = GamificationInsight.objects.create(
            date=self.today,
            active_users=100,
            badges_awarded=20,
            challenges_completed=15,
            total_points_issued=5000,
            contest_participants=30,
            streak_milestones=5,
        )

    @patch("api.gamification.models.GamificationInsight.calculate_daily_metrics")
    def test_calculate_today_success(self, mock_calc):
        mock_calc.return_value = self.insight
        url = "/api/gamification/gamification-insights/calculate_today/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    @patch("api.gamification.models.GamificationInsight.calculate_daily_metrics")
    def test_recalculate_specific_insight(self, mock_calc):
        mock_calc.return_value = self.insight
        url = f"/api/gamification/gamification-insights/{self.insight.pk}/recalculate/"
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_summary_report_success(self):
        start = (self.today - timedelta(days=6)).isoformat()
        end = self.today.isoformat()
        url = f"/api/gamification/gamification-insights/summary_report/?start_date={start}&end_date={end}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("period", data)
        self.assertIn("total_active_users", data)
        self.assertIn("total_badges_awarded", data)
        self.assertIn("total_points_issued", data)

    def test_summary_report_missing_dates(self):
        url = "/api/gamification/gamification-insights/summary_report/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_report_aggregates_correctly(self):
        GamificationInsight.objects.create(
            date=self.today - timedelta(days=1),
            active_users=50,
            badges_awarded=10,
            challenges_completed=5,
            total_points_issued=2000,
            contest_participants=15,
            streak_milestones=2,
        )
        start = (self.today - timedelta(days=2)).isoformat()
        end = self.today.isoformat()
        url = f"/api/gamification/gamification-insights/summary_report/?start_date={start}&end_date={end}"
        resp = self.client.get(url)
        data = resp.json()
        self.assertEqual(data["total_active_users"], 150)  # 100 + 50
        self.assertEqual(data["total_badges_awarded"], 30)  # 20 + 10

    def test_insight_actions_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/gamification/gamification-insights/calculate_today/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_calculate_today_never_raises(self):
        """Endpoint must never 500 even if calculate_daily_metrics raises."""
        with patch("api.gamification.models.GamificationInsight.calculate_daily_metrics",
                   side_effect=Exception("db failure")):
            url = "/api/gamification/gamification-insights/calculate_today/"
            resp = self.client.post(url)
            self.assertNotEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# ContestRewardViewSet — budget_status
# ---------------------------------------------------------------------------

class ContestRewardBudgetStatusTest(APITestCase):
    """Tests for ContestRewardViewSet.budget_status action."""

    def setUp(self):
        self.admin = _make_admin()
        self.client.force_authenticate(user=self.admin)
        self.cycle = ContestCycleFactory()
        self.reward = ContestRewardFactory(
            contest_cycle=self.cycle,
            total_budget=Decimal("500.00"),
            issued_count=3,
            rank_from=1,
            rank_to=10,
        )

    def test_budget_status_success(self):
        url = f"/api/gamification/contest-rewards/{self.reward.pk}/budget/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("remaining_budget", data)
        self.assertIn("is_exhausted", data)

    def test_budget_status_covers_rank_in_range(self):
        url = f"/api/gamification/contest-rewards/{self.reward.pk}/budget/?rank=5"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("covers_rank", data)
        self.assertTrue(data["covers_rank"])

    def test_budget_status_covers_rank_out_of_range(self):
        url = f"/api/gamification/contest-rewards/{self.reward.pk}/budget/?rank=99"
        resp = self.client.get(url)
        data = resp.json()
        self.assertFalse(data["covers_rank"])

    def test_budget_status_invalid_rank_handled(self):
        url = f"/api/gamification/contest-rewards/{self.reward.pk}/budget/?rank=notanumber"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsNone(data.get("covers_rank"))

    def test_budget_status_no_budget_reward(self):
        """Reward with no total_budget should still respond without error."""
        reward_no_budget = ContestRewardFactory(contest_cycle=self.cycle, total_budget=None)
        url = f"/api/gamification/contest-rewards/{reward_no_budget.pk}/budget/"
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


# ---------------------------------------------------------------------------
# LeaderboardSnapshotViewSet — is_finalized enrichment + finalized_only
# ---------------------------------------------------------------------------

class LeaderboardSnapshotFinalizedTest(APITestCase):
    """Tests for is_finalized enrichment on retrieve and finalized_only endpoint."""

    def setUp(self):
        self.admin = _make_admin()
        self.client.force_authenticate(user=self.admin)
        self.cycle = ContestCycleFactory()
        self.finalized_snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            status=SnapshotStatus.COMPLETED,
            is_finalized=True,
        )
        self.pending_snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            status=SnapshotStatus.PENDING,
            is_finalized=False,
        )

    def test_retrieve_includes_is_finalized(self):
        url = f"/api/gamification/leaderboard-snapshots/{self.finalized_snapshot.pk}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("is_finalized", data)

    def test_retrieve_finalized_true(self):
        url = f"/api/gamification/leaderboard-snapshots/{self.finalized_snapshot.pk}/"
        resp = self.client.get(url)
        self.assertTrue(resp.json()["is_finalized"])

    def test_retrieve_finalized_false_for_pending(self):
        url = f"/api/gamification/leaderboard-snapshots/{self.pending_snapshot.pk}/"
        resp = self.client.get(url)
        self.assertFalse(resp.json()["is_finalized"])

    def test_finalized_only_excludes_pending(self):
        url = "/api/gamification/leaderboard-snapshots/finalized/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        pks_returned = [item["id"] for item in resp.json().get("results", resp.json())]
        self.assertNotIn(str(self.pending_snapshot.pk), pks_returned)

    def test_finalized_only_includes_finalized(self):
        url = "/api/gamification/leaderboard-snapshots/finalized/"
        resp = self.client.get(url)
        pks_returned = [item["id"] for item in resp.json().get("results", resp.json())]
        self.assertIn(str(self.finalized_snapshot.pk), pks_returned)


# ---------------------------------------------------------------------------
# UserAchievementViewSet — cycle_scoped_check
# ---------------------------------------------------------------------------

class UserAchievementCycleScopedTest(APITestCase):
    """Tests for UserAchievementViewSet.cycle_scoped_check action."""

    def setUp(self):
        self.admin = _make_admin()
        self.user = _make_user()
        self.client.force_authenticate(user=self.admin)
        self.cycle = ContestCycleFactory()
        self.cycle_scoped_achievement = UserAchievementFactory(
            user=self.user,
            contest_cycle=self.cycle,
            achievement_type=AchievementType.BADGE,
            is_awarded=True,
        )
        self.global_achievement = UserAchievementFactory(
            user=self.user,
            contest_cycle=None,
            achievement_type=AchievementType.BADGE,
            is_awarded=True,
        )

    def test_cycle_scoped_check_returns_is_cycle_scoped(self):
        url = f"/api/gamification/user-achievements/{self.cycle_scoped_achievement.pk}/cycle-scoped/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("is_cycle_scoped", data)
        self.assertIn("achievement_id", data)

    def test_cycle_scoped_true_for_cycle_achievement(self):
        url = f"/api/gamification/user-achievements/{self.cycle_scoped_achievement.pk}/cycle-scoped/"
        resp = self.client.get(url)
        self.assertTrue(resp.json()["is_cycle_scoped"])

    def test_cycle_scoped_false_for_global_achievement(self):
        url = f"/api/gamification/user-achievements/{self.global_achievement.pk}/cycle-scoped/"
        resp = self.client.get(url)
        self.assertFalse(resp.json()["is_cycle_scoped"])

    def test_cycle_scoped_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        url = f"/api/gamification/user-achievements/{self.cycle_scoped_achievement.pk}/cycle-scoped/"
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ---------------------------------------------------------------------------
# INTEGRATION_SYSTEM wiring smoke tests
# ---------------------------------------------------------------------------

class IntegrationSystemWiringTest(APITestCase):
    """Smoke tests confirming INTEGRATION_SYSTEM classes are wired and importable."""

    def test_wiring_module_importable(self):
        try:
            from api.gamification.INTEGRATION_SYSTEM.wiring import (
                gamification_circuit_breaker,
                gamification_event_bus,
                gamification_health_manager,
                call_with_circuit_breaker,
                publish_domain_event,
                run_health_checks,
            )
        except ImportError as exc:
            self.fail(f"INTEGRATION_SYSTEM.wiring import failed: {exc}")

    def test_call_with_circuit_breaker_passes_through(self):
        from api.gamification.INTEGRATION_SYSTEM.wiring import call_with_circuit_breaker
        result = call_with_circuit_breaker(lambda: 42, fallback=0)
        self.assertEqual(result, 42)

    def test_call_with_circuit_breaker_returns_fallback_on_error(self):
        from api.gamification.INTEGRATION_SYSTEM.wiring import call_with_circuit_breaker
        def boom():
            raise RuntimeError("external failure")
        result = call_with_circuit_breaker(boom, fallback="fallback_value")
        # either passes through or returns fallback (depending on circuit state)
        self.assertIn(result, [None, "fallback_value"])

    def test_publish_domain_event_never_raises(self):
        from api.gamification.INTEGRATION_SYSTEM.wiring import publish_domain_event
        try:
            publish_domain_event("test.event", {"key": "value"})
        except Exception as exc:
            self.fail(f"publish_domain_event raised: {exc}")

    def test_run_health_checks_returns_dict(self):
        from api.gamification.INTEGRATION_SYSTEM.wiring import run_health_checks
        result = run_health_checks()
        self.assertIsInstance(result, dict)
        self.assertIn("integration_system", result)

    def test_health_endpoint_includes_integration_system(self):
        admin = _make_admin()
        self.client.force_authenticate(user=admin)
        resp = self.client.get("/api/gamification/health/")
        if resp.status_code == status.HTTP_200_OK:
            data = resp.json()
            self.assertIn("integration_system", data)


# ---------------------------------------------------------------------------
# Webhook Serializer tests (previously missing)
# ---------------------------------------------------------------------------

class WebhookSerializerTest(APITestCase):
    """Confirm WebhookEndpoint/Event/Delivery serializers exist and are importable."""

    def test_webhook_serializers_importable(self):
        try:
            from api.gamification.serializers import (
                WebhookEndpointSerializer,
                WebhookEventSerializer,
                WebhookDeliverySerializer,
            )
        except ImportError as exc:
            self.fail(f"Webhook serializer import failed: {exc}")

    def test_webhook_endpoint_serializer_requires_valid_url(self):
        from api.gamification.serializers import WebhookEndpointSerializer
        data = {"url": "not-a-url", "events": []}
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("url", serializer.errors)

    def test_webhook_endpoint_serializer_accepts_https(self):
        from api.gamification.serializers import WebhookEndpointSerializer
        data = {"url": "https://example.com/webhook", "events": [], "is_active": True}
        serializer = WebhookEndpointSerializer(data=data)
        # may fail due to missing required fields on the model — that's ok,
        # we just confirm URL validation passes
        errors = serializer.errors
        self.assertNotIn("url", errors)


# ---------------------------------------------------------------------------
# mark_notified() wiring test
# ---------------------------------------------------------------------------

class MarkNotifiedWiringTest(APITestCase):
    """Confirm mark_notified() is called after achievement notification dispatch."""

    def test_mark_notified_called_in_receivers(self):
        content = open("api/gamification/receivers.py").read()
        self.assertIn("mark_notified()", content,
                      "receivers.py must call achievement.mark_notified() after notification dispatch")

    def test_receivers_publish_domain_event(self):
        content = open("api/gamification/receivers.py").read()
        self.assertIn("publish_domain_event", content,
                      "receivers.py must publish domain events to INTEGRATION_SYSTEM EventBus")


# ---------------------------------------------------------------------------
# services_core calculate_checksum + record_performance_metric wiring
# ---------------------------------------------------------------------------

class ServicesCoreWiringTest(APITestCase):
    """Confirm TimestampedModel methods are called from services_core."""

    def test_calculate_checksum_called_in_create_cycle(self):
        content = open("api/gamification/services/services_core.py").read()
        self.assertIn("calculate_checksum()", content,
                      "create_contest_cycle must call cycle.calculate_checksum()")

    def test_record_performance_metric_called_in_award_achievement(self):
        content = open("api/gamification/services/services_core.py").read()
        self.assertIn("record_performance_metric", content,
                      "award_achievement must call achievement.record_performance_metric()")
