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


# ---------------------------------------------------------------------------
# UserPoints Managers
# ---------------------------------------------------------------------------

class UserPointsQuerySet(models.QuerySet):
    """Custom QuerySet for UserPoints model."""

    def with_high_points(self, min_points: int = 1000) -> "UserPointsQuerySet":
        """Users with points above threshold."""
        return self.filter(total_points__gte=min_points)

    def active_this_month(self) -> "UserPointsQuerySet":
        """Users who earned points this month."""
        from django.utils import timezone
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(points_this_month__gt=0, updated_at__gte=current_month)

    def active_this_week(self) -> "UserPointsQuerySet":
        """Users who earned points this week."""
        from django.utils import timezone
        week_start = timezone.now() - timezone.timedelta(days=timezone.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(points_this_week__gt=0, updated_at__gte=week_start)

    def by_rank_range(self, min_rank: int, max_rank: int) -> "UserPointsQuerySet":
        """Users within rank range."""
        return self.filter(monthly_rank__gte=min_rank, monthly_rank__lte=max_rank)

    def top_earners(self, limit: int = 100) -> "UserPointsQuerySet":
        """Top points earners."""
        return self.order_by("-total_points")[:limit]

    def zero_balance(self) -> "UserPointsQuerySet":
        """Users with zero points."""
        return self.filter(total_points=0)


class UserPointsManager(models.Manager):
    """Custom manager for UserPoints model."""

    def get_queryset(self) -> UserPointsQuerySet:
        return UserPointsQuerySet(self.model, using=self._db)

    def with_high_points(self, min_points: int = 1000) -> UserPointsQuerySet:
        return self.get_queryset().with_high_points(min_points)

    def active_this_month(self) -> UserPointsQuerySet:
        return self.get_queryset().active_this_month()

    def active_this_week(self) -> UserPointsQuerySet:
        return self.get_queryset().active_this_week()

    def by_rank_range(self, min_rank: int, max_rank: int) -> UserPointsQuerySet:
        return self.get_queryset().by_rank_range(min_rank, max_rank)

    def top_earners(self, limit: int = 100) -> UserPointsQuerySet:
        return self.get_queryset().top_earners(limit)

    def zero_balance(self) -> UserPointsQuerySet:
        return self.get_queryset().zero_balance()


# ---------------------------------------------------------------------------
# PointsTransaction Managers
# ---------------------------------------------------------------------------

class PointsTransactionQuerySet(models.QuerySet):
    """Custom QuerySet for PointsTransaction model."""

    def earnings(self) -> "PointsTransactionQuerySet":
        """Positive transactions (points earned)."""
        return self.filter(amount__gt=0)

    def deductions(self) -> "PointsTransactionQuerySet":
        """Negative transactions (points deducted)."""
        return self.filter(amount__lt=0)

    def by_source(self, source: str) -> "PointsTransactionQuerySet":
        """Transactions by source."""
        return self.filter(source=source)

    def recent(self, days: int = 30) -> "PointsTransactionQuerySet":
        """Recent transactions within days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def for_user(self, user_id: Any) -> "PointsTransactionQuerySet":
        """Transactions for specific user."""
        return self.filter(user_id=user_id)

    def high_value(self, min_amount: int = 1000) -> "PointsTransactionQuerySet":
        """High value transactions."""
        return self.filter(amount__gte=min_amount)

    def by_date_range(self, start_date, end_date) -> "PointsTransactionQuerySet":
        """Transactions within date range."""
        return self.filter(created_at__date__range=[start_date, end_date])


class PointsTransactionManager(models.Manager):
    """Custom manager for PointsTransaction model."""

    def get_queryset(self) -> PointsTransactionQuerySet:
        return PointsTransactionQuerySet(self.model, using=self._db)

    def earnings(self) -> PointsTransactionQuerySet:
        return self.get_queryset().earnings()

    def deductions(self) -> PointsTransactionQuerySet:
        return self.get_queryset().deductions()

    def by_source(self, source: str) -> PointsTransactionQuerySet:
        return self.get_queryset().by_source(source)

    def recent(self, days: int = 30) -> PointsTransactionQuerySet:
        return self.get_queryset().recent(days)

    def for_user(self, user_id: Any) -> PointsTransactionQuerySet:
        return self.get_queryset().for_user(user_id)

    def high_value(self, min_amount: int = 1000) -> PointsTransactionQuerySet:
        return self.get_queryset().high_value(min_amount)

    def by_date_range(self, start_date, end_date) -> PointsTransactionQuerySet:
        return self.get_queryset().by_date_range(start_date, end_date)


# ---------------------------------------------------------------------------
# StreakFreeze Managers
# ---------------------------------------------------------------------------

class StreakFreezeQuerySet(models.QuerySet):
    """Custom QuerySet for StreakFreeze model."""

    def recent(self, days: int = 30) -> "StreakFreezeQuerySet":
        """Recent streak freezes within days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def for_user(self, user_id: Any) -> "StreakFreezeQuerySet":
        """Freezes for specific user."""
        return self.filter(user_id=user_id)

    def by_reason(self, reason: str) -> "StreakFreezeQuerySet":
        """Freezes by reason."""
        return self.filter(reason=reason)

    def by_date(self, date) -> "StreakFreezeQuerySet":
        """Freezes used on specific date."""
        return self.filter(used_at=date)

    def this_month(self) -> "StreakFreezeQuerySet":
        """Freezes used this month."""
        from django.utils import timezone
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(used_at__gte=current_month)


class StreakFreezeManager(models.Manager):
    """Custom manager for StreakFreeze model."""

    def get_queryset(self) -> StreakFreezeQuerySet:
        return StreakFreezeQuerySet(self.model, using=self._db)

    def recent(self, days: int = 30) -> StreakFreezeQuerySet:
        return self.get_queryset().recent(days)

    def for_user(self, user_id: Any) -> StreakFreezeQuerySet:
        return self.get_queryset().for_user(user_id)

    def by_reason(self, reason: str) -> StreakFreezeQuerySet:
        return self.get_queryset().by_reason(reason)

    def by_date(self, date) -> StreakFreezeQuerySet:
        return self.get_queryset().by_date(date)

    def this_month(self) -> StreakFreezeQuerySet:
        return self.get_queryset().this_month()


# ---------------------------------------------------------------------------
# ContestParticipant Managers
# ---------------------------------------------------------------------------

class ContestParticipantQuerySet(models.QuerySet):
    """Custom QuerySet for ContestParticipant model."""

    def active(self) -> "ContestParticipantQuerySet":
        """Active (not disqualified) participants."""
        return self.filter(is_disqualified=False)

    def disqualified(self) -> "ContestParticipantQuerySet":
        """Disqualified participants."""
        return self.filter(is_disqualified=True)

    def ranked(self) -> "ContestParticipantQuerySet":
        """Participants with ranks."""
        return self.filter(current_rank__isnull=False)

    def by_contest(self, contest_id: Any) -> "ContestParticipantQuerySet":
        """Participants in specific contest."""
        return self.filter(contest_cycle_id=contest_id)

    def by_user(self, user_id: Any) -> "ContestParticipantQuerySet":
        """Participations by specific user."""
        return self.filter(user_id=user_id)

    def top_performers(self, limit: int = 100) -> "ContestParticipantQuerySet":
        """Top performers by points."""
        return self.filter(is_disqualified=False).order_by("-current_points")[:limit]

    def with_points(self, min_points: int = 1) -> "ContestParticipantQuerySet":
        """Participants with minimum points."""
        return self.filter(current_points__gte=min_points)


class ContestParticipantManager(models.Manager):
    """Custom manager for ContestParticipant model."""

    def get_queryset(self) -> ContestParticipantQuerySet:
        return ContestParticipantQuerySet(self.model, using=self._db)

    def active(self) -> ContestParticipantQuerySet:
        return self.get_queryset().active()

    def disqualified(self) -> ContestParticipantQuerySet:
        return self.get_queryset().disqualified()

    def ranked(self) -> ContestParticipantQuerySet:
        return self.get_queryset().ranked()

    def by_contest(self, contest_id: Any) -> ContestParticipantQuerySet:
        return self.get_queryset().by_contest(contest_id)

    def by_user(self, user_id: Any) -> ContestParticipantQuerySet:
        return self.get_queryset().by_user(user_id)

    def top_performers(self, limit: int = 100) -> ContestParticipantQuerySet:
        return self.get_queryset().top_performers(limit)

    def with_points(self, min_points: int = 1) -> ContestParticipantQuerySet:
        return self.get_queryset().with_points(min_points)


# ---------------------------------------------------------------------------
# GamificationConfig Managers
# ---------------------------------------------------------------------------

class GamificationConfigQuerySet(models.QuerySet):
    """Custom QuerySet for GamificationConfig model."""

    def with_feature_enabled(self, feature: str) -> "GamificationConfigQuerySet":
        """Configs with specific feature enabled."""
        feature_field = f"enable_{feature}"
        return self.filter(**{feature_field: True})

    def by_tenant(self, tenant_id: Any) -> "GamificationConfigQuerySet":
        """Config for specific tenant."""
        return self.filter(tenant_id=tenant_id)

    def with_all_features_enabled(self) -> "GamificationConfigQuerySet":
        """Configs with all features enabled."""
        return self.filter(
            enable_contests=True,
            enable_badges=True,
            enable_streaks=True,
            enable_levels=True,
            enable_daily_challenges=True
        )

    def with_points_expiry(self) -> "GamificationConfigQuerySet":
        """Configs with points expiry enabled."""
        return self.filter(points_expiry_days__isnull=False)


class GamificationConfigManager(models.Manager):
    """Custom manager for GamificationConfig model."""

    def get_queryset(self) -> GamificationConfigQuerySet:
        return GamificationConfigQuerySet(self.model, using=self._db)

    def with_feature_enabled(self, feature: str) -> GamificationConfigQuerySet:
        return self.get_queryset().with_feature_enabled(feature)

    def by_tenant(self, tenant_id: Any) -> GamificationConfigQuerySet:
        return self.get_queryset().by_tenant(tenant_id)

    def with_all_features_enabled(self) -> GamificationConfigQuerySet:
        return self.get_queryset().with_all_features_enabled()

    def with_points_expiry(self) -> GamificationConfigQuerySet:
        return self.get_queryset().with_points_expiry()


# ---------------------------------------------------------------------------
# GamificationInsight Managers
# ---------------------------------------------------------------------------

class GamificationInsightQuerySet(models.QuerySet):
    """Custom QuerySet for GamificationInsight model."""

    def by_date_range(self, start_date, end_date) -> "GamificationInsightQuerySet":
        """Insights within date range."""
        return self.filter(date__range=[start_date, end_date])

    def recent(self, days: int = 30) -> "GamificationInsightQuerySet":
        """Recent insights within days."""
        from django.utils import timezone
        cutoff = timezone.now().date() - timezone.timedelta(days=days)
        return self.filter(date__gte=cutoff)

    def high_engagement(self, min_rate: float = 0.5) -> "GamificationInsightQuerySet":
        """Days with high engagement rate."""
        return self.filter(engagement_rate__gte=min_rate)

    def with_activity(self, min_users: int = 1) -> "GamificationInsightQuerySet":
        """Days with minimum active users."""
        return self.filter(active_users__gte=min_users)

    def by_year(self, year: int) -> "GamificationInsightQuerySet":
        """Insights for specific year."""
        return self.filter(date__year=year)

    def by_month(self, year: int, month: int) -> "GamificationInsightQuerySet":
        """Insights for specific year/month."""
        return self.filter(date__year=year, date__month=month)


class GamificationInsightManager(models.Manager):
    """Custom manager for GamificationInsight model."""

    def get_queryset(self) -> GamificationInsightQuerySet:
        return GamificationInsightQuerySet(self.model, using=self._db)

    def by_date_range(self, start_date, end_date) -> GamificationInsightQuerySet:
        return self.get_queryset().by_date_range(start_date, end_date)

    def recent(self, days: int = 30) -> GamificationInsightQuerySet:
        return self.get_queryset().recent(days)

    def high_engagement(self, min_rate: float = 0.5) -> GamificationInsightQuerySet:
        return self.get_queryset().high_engagement(min_rate)

    def with_activity(self, min_users: int = 1) -> GamificationInsightQuerySet:
        return self.get_queryset().with_activity(min_users)

    def by_year(self, year: int) -> GamificationInsightQuerySet:
        return self.get_queryset().by_year(year)

    def by_month(self, year: int, month: int) -> GamificationInsightQuerySet:
        return self.get_queryset().by_month(year, month)
