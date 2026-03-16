"""
Gamification Tests — Leaderboard snapshot and generation tests.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from ..choices import ContestCycleStatus, LeaderboardScope, SnapshotStatus
from ..constants import DEFAULT_LEADERBOARD_TOP_N
from ..exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)
from ..models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
from .. import services
from .factories import (
    ContestCycleFactory,
    LeaderboardSnapshotFactory,
    ContestRewardFactory,
    UserAchievementFactory,
    UserFactory,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# ContestCycle Tests
# ---------------------------------------------------------------------------

class ContestCycleModelTest(TestCase):

    def test_create_valid_cycle(self):
        cycle = ContestCycleFactory()
        self.assertIsNotNone(cycle.id)
        self.assertEqual(cycle.status, ContestCycleStatus.DRAFT)

    def test_start_before_end_constraint(self):
        now = timezone.now()
        with self.assertRaises(ValidationError):
            ContestCycleFactory(
                start_date=now + timedelta(days=5),
                end_date=now + timedelta(days=1),
            )

    def test_is_active_property_false_when_draft(self):
        cycle = ContestCycleFactory()
        self.assertFalse(cycle.is_active)

    def test_is_active_property_true_when_active_and_in_window(self):
        now = timezone.now()
        cycle = ContestCycleFactory(
            status=ContestCycleStatus.ACTIVE,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=5),
        )
        self.assertTrue(cycle.is_active)

    def test_is_active_false_when_window_expired(self):
        now = timezone.now()
        cycle = ContestCycleFactory(
            status=ContestCycleStatus.ACTIVE,
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=1),
        )
        self.assertFalse(cycle.is_active)

    def test_duration_days(self):
        now = timezone.now()
        cycle = ContestCycleFactory(
            start_date=now,
            end_date=now + timedelta(days=7),
        )
        self.assertEqual(cycle.duration_days, 7)

    def test_invalid_points_multiplier_raises(self):
        with self.assertRaises(ValidationError):
            ContestCycleFactory(points_multiplier=Decimal("-1.00"))

    def test_only_one_active_cycle_allowed(self):
        now = timezone.now()
        ContestCycleFactory(
            status=ContestCycleStatus.ACTIVE,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=3),
        )
        with self.assertRaises(ValidationError):
            ContestCycleFactory(
                status=ContestCycleStatus.ACTIVE,
                start_date=now - timedelta(hours=1),
                end_date=now + timedelta(days=3),
            )

    def test_state_machine_valid_transition(self):
        cycle = ContestCycleFactory(status=ContestCycleStatus.DRAFT)
        cycle.transition_to(ContestCycleStatus.ACTIVE)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, ContestCycleStatus.ACTIVE)

    def test_state_machine_invalid_transition_raises(self):
        cycle = ContestCycleFactory(status=ContestCycleStatus.DRAFT)
        with self.assertRaises(ContestCycleStateError):
            cycle.transition_to(ContestCycleStatus.COMPLETED)

    def test_state_machine_terminal_state(self):
        cycle = ContestCycleFactory(status=ContestCycleStatus.ARCHIVED)
        with self.assertRaises(ContestCycleStateError):
            cycle.transition_to(ContestCycleStatus.ACTIVE)


# ---------------------------------------------------------------------------
# LeaderboardSnapshot Tests
# ---------------------------------------------------------------------------

class LeaderboardSnapshotModelTest(TestCase):

    def setUp(self):
        self.cycle = ContestCycleFactory()

    def _valid_entries(self):
        return [
            {"rank": 1, "user_id": "u1", "display_name": "Alice", "points": 500, "delta_rank": None},
            {"rank": 2, "user_id": "u2", "display_name": "Bob", "points": 300, "delta_rank": None},
        ]

    def test_finalize_sets_status_and_checksum(self):
        snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            snapshot_data=self._valid_entries(),
            status=SnapshotStatus.PENDING,
        )
        snapshot.finalize()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotStatus.FINALIZED)
        self.assertTrue(len(snapshot.checksum) == 64)
        self.assertIsNotNone(snapshot.generated_at)

    def test_finalize_idempotent(self):
        snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            snapshot_data=self._valid_entries(),
            status=SnapshotStatus.PENDING,
        )
        snapshot.finalize()
        first_checksum = snapshot.checksum
        snapshot.finalize()  # second call should be no-op
        self.assertEqual(snapshot.checksum, first_checksum)

    def test_finalize_empty_data_raises(self):
        snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            snapshot_data=[],
            status=SnapshotStatus.PENDING,
        )
        with self.assertRaises(ValidationError):
            snapshot.finalize()

    def test_mark_failed_sets_status(self):
        snapshot = LeaderboardSnapshotFactory(contest_cycle=self.cycle)
        snapshot.mark_failed("Connection timeout.")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotStatus.FAILED)
        self.assertIn("Connection timeout", snapshot.error_message)

    def test_immutability_of_finalized_snapshot(self):
        snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            snapshot_data=self._valid_entries(),
            status=SnapshotStatus.PENDING,
        )
        snapshot.finalize()
        snapshot.refresh_from_db()
        snapshot.snapshot_data = []  # attempt to clear data
        with self.assertRaises(ValidationError):
            snapshot.save()

    def test_entry_count_property(self):
        snapshot = LeaderboardSnapshotFactory(
            contest_cycle=self.cycle,
            snapshot_data=self._valid_entries(),
        )
        self.assertEqual(snapshot.entry_count, 2)

    def test_entry_count_empty(self):
        snapshot = LeaderboardSnapshotFactory(contest_cycle=self.cycle, snapshot_data=[])
        self.assertEqual(snapshot.entry_count, 0)


# ---------------------------------------------------------------------------
# ContestReward Tests
# ---------------------------------------------------------------------------

class ContestRewardModelTest(TestCase):

    def setUp(self):
        self.cycle = ContestCycleFactory()

    def test_covers_rank_within_window(self):
        reward = ContestRewardFactory(contest_cycle=self.cycle, rank_from=1, rank_to=10)
        self.assertTrue(reward.covers_rank(1))
        self.assertTrue(reward.covers_rank(5))
        self.assertTrue(reward.covers_rank(10))

    def test_covers_rank_outside_window(self):
        reward = ContestRewardFactory(contest_cycle=self.cycle, rank_from=1, rank_to=5)
        self.assertFalse(reward.covers_rank(6))
        self.assertFalse(reward.covers_rank(0))

    def test_is_exhausted_with_budget(self):
        reward = ContestRewardFactory(
            contest_cycle=self.cycle, total_budget=3, issued_count=3
        )
        self.assertTrue(reward.is_exhausted)

    def test_is_exhausted_false_when_uncapped(self):
        reward = ContestRewardFactory(contest_cycle=self.cycle, total_budget=None)
        self.assertFalse(reward.is_exhausted)

    def test_increment_issued_count(self):
        reward = ContestRewardFactory(contest_cycle=self.cycle, total_budget=5, issued_count=0)
        reward.increment_issued_count()
        reward.refresh_from_db()
        self.assertEqual(reward.issued_count, 1)

    def test_increment_raises_when_exhausted(self):
        from ..exceptions import RewardAlreadyClaimedError
        reward = ContestRewardFactory(
            contest_cycle=self.cycle, total_budget=1, issued_count=1
        )
        with self.assertRaises(RewardAlreadyClaimedError):
            reward.increment_issued_count()

    def test_rank_from_gt_rank_to_raises(self):
        with self.assertRaises(ValidationError):
            ContestRewardFactory(contest_cycle=self.cycle, rank_from=10, rank_to=5)


# ---------------------------------------------------------------------------
# UserAchievement Tests
# ---------------------------------------------------------------------------

class UserAchievementModelTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.cycle = ContestCycleFactory()

    def test_award_sets_is_awarded_and_points(self):
        achievement = UserAchievementFactory(user=self.user, contest_cycle=self.cycle)
        achievement.award(points=250, rank=3)
        achievement.refresh_from_db()
        self.assertTrue(achievement.is_awarded)
        self.assertEqual(achievement.points_awarded, 250)
        self.assertEqual(achievement.rank_at_award, 3)
        self.assertIsNotNone(achievement.awarded_at)

    def test_award_idempotent(self):
        achievement = UserAchievementFactory(user=self.user, contest_cycle=self.cycle)
        achievement.award(points=100)
        original_awarded_at = achievement.awarded_at
        achievement.award(points=999)  # second call should be a no-op
        achievement.refresh_from_db()
        self.assertEqual(achievement.awarded_at, original_awarded_at)
        self.assertEqual(achievement.points_awarded, 100)

    def test_mark_notified(self):
        achievement = UserAchievementFactory(user=self.user, contest_cycle=self.cycle)
        achievement.award(points=0)
        achievement.mark_notified()
        achievement.refresh_from_db()
        self.assertTrue(achievement.is_notified)
        self.assertIsNotNone(achievement.notified_at)

    def test_immutability_after_award(self):
        achievement = UserAchievementFactory(user=self.user, contest_cycle=self.cycle)
        achievement.award(points=100)
        achievement.refresh_from_db()
        achievement.points_awarded = 9999
        with self.assertRaises(ValidationError):
            achievement.save()


# ---------------------------------------------------------------------------
# Service Layer Tests
# ---------------------------------------------------------------------------

class AwardAchievementServiceTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.cycle = ContestCycleFactory()

    def test_award_achievement_creates_and_awards(self):
        achievement = services.award_achievement(
            user_id=self.user.pk,
            achievement_type="BADGE",
            title="Test Badge",
            points=100,
            cycle_id=self.cycle.pk,
        )
        self.assertTrue(achievement.is_awarded)
        self.assertEqual(achievement.points_awarded, 100)

    def test_award_achievement_idempotent(self):
        a1 = services.award_achievement(
            user_id=self.user.pk,
            achievement_type="BADGE",
            title="Test Badge",
            points=100,
            cycle_id=self.cycle.pk,
        )
        a2 = services.award_achievement(
            user_id=self.user.pk,
            achievement_type="BADGE",
            title="Test Badge",
            points=100,
            cycle_id=self.cycle.pk,
        )
        self.assertEqual(a1.id, a2.id)

    def test_award_achievement_invalid_user_raises(self):
        with self.assertRaises(ContestCycleNotFoundError.__class__):
            services.award_achievement(
                user_id=99999999,
                achievement_type="BADGE",
                title="Badge",
                points=0,
            )

    def test_get_user_total_points(self):
        services.award_achievement(
            user_id=self.user.pk,
            achievement_type="BADGE",
            title="B1",
            points=150,
            cycle_id=self.cycle.pk,
        )
        services.award_achievement(
            user_id=self.user.pk,
            achievement_type="MILESTONE",
            title="M1",
            points=100,
            cycle_id=self.cycle.pk,
        )
        total = services.get_user_total_points(self.user.pk, cycle_id=self.cycle.pk)
        self.assertEqual(total, 250)

    def test_batch_award_achievements(self):
        user2 = UserFactory()
        awards = [
            {"user_id": self.user.pk, "achievement_type": "BADGE", "title": "B1", "points": 50},
            {"user_id": user2.pk, "achievement_type": "BADGE", "title": "B2", "points": 75},
        ]
        result = services.batch_award_achievements(awards, cycle_id=self.cycle.pk)
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["succeeded"]), 2)
        self.assertEqual(len(result["failed"]), 0)


class LeaderboardServiceTest(TestCase):

    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.cycle = ContestCycleFactory()

    def test_generate_leaderboard_snapshot_invalid_cycle_raises(self):
        import uuid
        with self.assertRaises(ContestCycleNotFoundError):
            services.generate_leaderboard_snapshot(cycle_id=uuid.uuid4())

    def test_generate_leaderboard_snapshot_success(self):
        services.award_achievement(
            user_id=self.user1.pk, achievement_type="BADGE", title="B",
            points=300, cycle_id=self.cycle.pk,
        )
        services.award_achievement(
            user_id=self.user2.pk, achievement_type="BADGE", title="B",
            points=100, cycle_id=self.cycle.pk,
        )
        snapshot = services.generate_leaderboard_snapshot(cycle_id=self.cycle.pk)
        self.assertEqual(snapshot.status, SnapshotStatus.FINALIZED)
        self.assertGreaterEqual(snapshot.entry_count, 2)
        self.assertEqual(snapshot.snapshot_data[0]["rank"], 1)

    def test_get_user_rank_in_cycle(self):
        services.award_achievement(
            user_id=self.user1.pk, achievement_type="BADGE", title="B",
            points=500, cycle_id=self.cycle.pk,
        )
        services.award_achievement(
            user_id=self.user2.pk, achievement_type="BADGE", title="B",
            points=200, cycle_id=self.cycle.pk,
        )
        rank = services.get_user_rank_in_cycle(self.user1.pk, self.cycle.pk)
        self.assertEqual(rank, 1)
        rank2 = services.get_user_rank_in_cycle(self.user2.pk, self.cycle.pk)
        self.assertEqual(rank2, 2)

    def test_get_user_rank_none_when_no_points(self):
        rank = services.get_user_rank_in_cycle(self.user1.pk, self.cycle.pk)
        self.assertIsNone(rank)
