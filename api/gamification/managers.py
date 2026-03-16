"""
Gamification Managers — Custom QuerySet and Manager classes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import models
from django.db.models import QuerySet, Sum, F
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ContestCycle
# ---------------------------------------------------------------------------

class ContestCycleQuerySet(models.QuerySet):

    def active(self) -> "ContestCycleQuerySet":
        """Cycles in ACTIVE status AND within their date window."""
        from .choices import ContestCycleStatus
        now = timezone.now()
        return self.filter(
            status=ContestCycleStatus.ACTIVE,
            start_date__lte=now,
            end_date__gt=now,
        )

    def draft(self) -> "ContestCycleQuerySet":
        from .choices import ContestCycleStatus
        return self.filter(status=ContestCycleStatus.DRAFT)

    def completed(self) -> "ContestCycleQuerySet":
        from .choices import ContestCycleStatus
        return self.filter(status=ContestCycleStatus.COMPLETED)

    def archived(self) -> "ContestCycleQuerySet":
        from .choices import ContestCycleStatus
        return self.filter(status=ContestCycleStatus.ARCHIVED)

    def featured(self) -> "ContestCycleQuerySet":
        return self.filter(is_featured=True)

    def upcoming(self) -> "ContestCycleQuerySet":
        """DRAFT cycles whose start_date is in the future."""
        from .choices import ContestCycleStatus
        return self.filter(
            status=ContestCycleStatus.DRAFT,
            start_date__gt=timezone.now(),
        )

    def expired(self) -> "ContestCycleQuerySet":
        """Cycles whose end_date has passed, regardless of status."""
        return self.filter(end_date__lte=timezone.now())


class ContestCycleManager(models.Manager):
    def get_queryset(self) -> ContestCycleQuerySet:
        return ContestCycleQuerySet(self.model, using=self._db)

    def get_current(self) -> Optional[Any]:
        """
        Return the single currently ACTIVE cycle, or None.

        Logs a warning if multiple active cycles are found (data integrity issue).
        """
        qs = self.get_queryset().active()
        count = qs.count()
        if count == 0:
            return None
        if count > 1:
            logger.warning(
                "ContestCycleManager.get_current: found %d active cycles; "
                "returning most recently started.",
                count,
            )
        return qs.order_by("-start_date").first()

    def active(self) -> ContestCycleQuerySet:
        return self.get_queryset().active()

    def draft(self) -> ContestCycleQuerySet:
        return self.get_queryset().draft()

    def completed(self) -> ContestCycleQuerySet:
        return self.get_queryset().completed()

    def featured(self) -> ContestCycleQuerySet:
        return self.get_queryset().featured()


# ---------------------------------------------------------------------------
# LeaderboardSnapshot
# ---------------------------------------------------------------------------

class LeaderboardSnapshotQuerySet(models.QuerySet):

    def finalized(self) -> "LeaderboardSnapshotQuerySet":
        from .choices import SnapshotStatus
        return self.filter(status=SnapshotStatus.FINALIZED)

    def pending(self) -> "LeaderboardSnapshotQuerySet":
        from .choices import SnapshotStatus
        return self.filter(status=SnapshotStatus.PENDING)

    def failed(self) -> "LeaderboardSnapshotQuerySet":
        from .choices import SnapshotStatus
        return self.filter(status=SnapshotStatus.FAILED)

    def for_cycle(self, cycle_id: Any) -> "LeaderboardSnapshotQuerySet":
        if cycle_id is None:
            raise ValueError("cycle_id must not be None.")
        return self.filter(contest_cycle_id=cycle_id)

    def global_scope(self) -> "LeaderboardSnapshotQuerySet":
        from .choices import LeaderboardScope
        return self.filter(scope=LeaderboardScope.GLOBAL)

    def latest_finalized_for_cycle(self, cycle_id: Any) -> Optional[Any]:
        """Return the most recently finalized snapshot for a cycle, or None."""
        from .choices import SnapshotStatus
        return (
            self.filter(contest_cycle_id=cycle_id, status=SnapshotStatus.FINALIZED)
            .order_by("-generated_at")
            .first()
        )


class LeaderboardSnapshotManager(models.Manager):
    def get_queryset(self) -> LeaderboardSnapshotQuerySet:
        return LeaderboardSnapshotQuerySet(self.model, using=self._db)

    def finalized(self) -> LeaderboardSnapshotQuerySet:
        return self.get_queryset().finalized()

    def for_cycle(self, cycle_id: Any) -> LeaderboardSnapshotQuerySet:
        return self.get_queryset().for_cycle(cycle_id)


# ---------------------------------------------------------------------------
# ContestReward
# ---------------------------------------------------------------------------

class ContestRewardQuerySet(models.QuerySet):

    def active(self) -> "ContestRewardQuerySet":
        return self.filter(is_active=True)

    def for_cycle(self, cycle_id: Any) -> "ContestRewardQuerySet":
        if cycle_id is None:
            raise ValueError("cycle_id must not be None.")
        return self.filter(contest_cycle_id=cycle_id)

    def covering_rank(self, rank: int) -> "ContestRewardQuerySet":
        """Return rewards whose rank window includes *rank*."""
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"rank must be a positive integer, got {rank!r}.")
        return self.filter(rank_from__lte=rank, rank_to__gte=rank)

    def with_remaining_budget(self) -> "ContestRewardQuerySet":
        """Rewards that still have budget left (includes uncapped rewards)."""
        return self.filter(
            models.Q(total_budget__isnull=True) |
            models.Q(issued_count__lt=F("total_budget"))
        )

    def by_reward_type(self, reward_type: str) -> "ContestRewardQuerySet":
        return self.filter(reward_type=reward_type)


class ContestRewardManager(models.Manager):
    def get_queryset(self) -> ContestRewardQuerySet:
        return ContestRewardQuerySet(self.model, using=self._db)

    def active(self) -> ContestRewardQuerySet:
        return self.get_queryset().active()

    def for_cycle(self, cycle_id: Any) -> ContestRewardQuerySet:
        return self.get_queryset().for_cycle(cycle_id)

    def available_for_rank(self, cycle_id: Any, rank: int) -> ContestRewardQuerySet:
        """
        Return active, non-exhausted rewards for *cycle_id* that cover *rank*.
        """
        if cycle_id is None:
            raise ValueError("cycle_id must not be None.")
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"rank must be a positive integer, got {rank!r}.")
        return (
            self.get_queryset()
            .for_cycle(cycle_id)
            .active()
            .covering_rank(rank)
            .with_remaining_budget()
        )


# ---------------------------------------------------------------------------
# UserAchievement
# ---------------------------------------------------------------------------

class UserAchievementQuerySet(models.QuerySet):

    def awarded(self) -> "UserAchievementQuerySet":
        return self.filter(is_awarded=True)

    def pending(self) -> "UserAchievementQuerySet":
        return self.filter(is_awarded=False)

    def with_related(self) -> UserAchievementQuerySet:
        return self.get_queryset().with_related()

    def unnotified(self) -> "UserAchievementQuerySet":
        return self.filter(is_awarded=True, is_notified=False)

    def for_user(self, user_id: Any) -> "UserAchievementQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(user_id=user_id)

    def for_cycle(self, cycle_id: Any) -> "UserAchievementQuerySet":
        if cycle_id is None:
            raise ValueError("cycle_id must not be None.")
        return self.filter(contest_cycle_id=cycle_id)

    def of_type(self, achievement_type: str) -> "UserAchievementQuerySet":
        if not achievement_type:
            raise ValueError("achievement_type must not be empty.")
        return self.filter(achievement_type=achievement_type)

    def total_points(self) -> int:
        """Aggregate sum of points_awarded for this queryset. Returns 0 on empty."""
        result = self.awarded().aggregate(total=Sum("points_awarded"))
        return result.get("total") or 0

    def with_related(self) -> "UserAchievementQuerySet":
        """Pre-fetch commonly joined relations for display."""
        return self.select_related("user", "contest_cycle", "contest_reward")


class UserAchievementManager(models.Manager):
    def get_queryset(self) -> UserAchievementQuerySet:
        return UserAchievementQuerySet(self.model, using=self._db)

    def awarded(self) -> UserAchievementQuerySet:
        return self.get_queryset().awarded()

    def for_user(self, user_id: Any) -> UserAchievementQuerySet:
        return self.get_queryset().for_user(user_id)

    def for_user_in_cycle(self, user_id: Any, cycle_id: Any) -> UserAchievementQuerySet:
        return self.get_queryset().for_user(user_id).for_cycle(cycle_id)

    def with_related(self) -> UserAchievementQuerySet:
        return self.get_queryset().with_related()

    def unnotified(self) -> UserAchievementQuerySet:
        return self.get_queryset().unnotified()
