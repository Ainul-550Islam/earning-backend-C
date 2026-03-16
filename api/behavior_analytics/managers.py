# =============================================================================
# behavior_analytics/managers.py
# =============================================================================
"""
Custom QuerySet and Manager classes for behavior_analytics models.

Rules:
  - Every domain query lives here, NOT in views/services.
  - Managers never import from serializers or views.
  - All date/time operations use Django's timezone utilities.
  - Annotate heavy aggregations once and cache on the QS object.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

if TYPE_CHECKING:
    import datetime


# ---------------------------------------------------------------------------
# UserPath
# ---------------------------------------------------------------------------

class UserPathQuerySet(models.QuerySet):

    def active(self) -> "UserPathQuerySet":
        from .choices import SessionStatus
        return self.filter(status=SessionStatus.ACTIVE)

    def completed(self) -> "UserPathQuerySet":
        from .choices import SessionStatus
        return self.filter(status=SessionStatus.COMPLETED)

    def bounced(self) -> "UserPathQuerySet":
        from .choices import SessionStatus
        return self.filter(status=SessionStatus.BOUNCED)

    def for_user(self, user) -> "UserPathQuerySet":
        return self.filter(user=user)

    def for_session(self, session_id: str) -> "UserPathQuerySet":
        return self.filter(session_id=session_id)

    def in_date_range(
        self,
        start: "datetime.date",
        end: "datetime.date",
    ) -> "UserPathQuerySet":
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def with_click_count(self) -> "UserPathQuerySet":
        return self.annotate(click_count=Count("click_metrics"))

    def with_total_stay(self) -> "UserPathQuerySet":
        return self.annotate(
            total_stay_sec=Sum("stay_times__duration_seconds", default=0)
        )

    def by_device(self, device_type: str) -> "UserPathQuerySet":
        return self.filter(device_type=device_type)

    def select_full(self) -> "UserPathQuerySet":
        """Eager-load related objects for list views."""
        return self.select_related("user").prefetch_related(
            "click_metrics", "stay_times"
        )


class UserPathManager(models.Manager):
    def get_queryset(self) -> UserPathQuerySet:
        return UserPathQuerySet(self.model, using=self._db)

    def active(self) -> UserPathQuerySet:
        return self.get_queryset().active()

    def for_user(self, user) -> UserPathQuerySet:
        return self.get_queryset().for_user(user)

    def select_full(self) -> UserPathQuerySet:
        """Eager-load related objects for list views."""
        return self.get_queryset().select_full()


# ---------------------------------------------------------------------------
# ClickMetric
# ---------------------------------------------------------------------------

class ClickMetricQuerySet(models.QuerySet):

    def for_path(self, path) -> "ClickMetricQuerySet":
        return self.filter(path=path)

    def for_category(self, category: str) -> "ClickMetricQuerySet":
        return self.filter(category=category)

    def in_date_range(
        self,
        start: "datetime.datetime",
        end: "datetime.datetime",
    ) -> "ClickMetricQuerySet":
        return self.filter(clicked_at__range=(start, end))

    def for_page(self, url: str) -> "ClickMetricQuerySet":
        return self.filter(page_url=url)

    def by_day(self) -> "ClickMetricQuerySet":
        return self.annotate(day=TruncDate("clicked_at")).values("day").annotate(
            count=Count("id")
        ).order_by("day")

    def top_elements(self, limit: int = 10) -> "ClickMetricQuerySet":
        return (
            self.values("element_selector")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

    def select_full(self) -> "ClickMetricQuerySet":
        return self.select_related("path", "path__user")


class ClickMetricManager(models.Manager):
    def get_queryset(self) -> ClickMetricQuerySet:
        return ClickMetricQuerySet(self.model, using=self._db)

    def for_path(self, path) -> ClickMetricQuerySet:
        return self.get_queryset().for_path(path)

    def top_elements(self, limit: int = 10) -> ClickMetricQuerySet:
        return self.get_queryset().top_elements(limit)

    def select_full(self) -> ClickMetricQuerySet:
        """Eager-load related objects for list views."""
        return self.get_queryset().select_full()


# ---------------------------------------------------------------------------
# StayTime
# ---------------------------------------------------------------------------

class StayTimeQuerySet(models.QuerySet):

    def for_path(self, path) -> "StayTimeQuerySet":
        return self.filter(path=path)

    def active_only(self) -> "StayTimeQuerySet":
        return self.filter(is_active_time=True)

    def bounces(self) -> "StayTimeQuerySet":
        from .constants import STAY_TIME_BOUNCE_THRESHOLD
        return self.filter(duration_seconds__lt=STAY_TIME_BOUNCE_THRESHOLD)

    def non_bounces(self) -> "StayTimeQuerySet":
        from .constants import STAY_TIME_BOUNCE_THRESHOLD
        return self.filter(duration_seconds__gte=STAY_TIME_BOUNCE_THRESHOLD)

    def for_page(self, url: str) -> "StayTimeQuerySet":
        return self.filter(page_url=url)

    def aggregate_stats(self) -> dict:
        return self.aggregate(
            avg_duration=Avg("duration_seconds"),
            max_duration=Max("duration_seconds"),
            min_duration=Min("duration_seconds"),
            total_duration=Sum("duration_seconds"),
            count=Count("id"),
        )

    def in_date_range(
        self,
        start: "datetime.date",
        end: "datetime.date",
    ) -> "StayTimeQuerySet":
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)


class StayTimeManager(models.Manager):
    def get_queryset(self) -> StayTimeQuerySet:
        return StayTimeQuerySet(self.model, using=self._db)

    def for_path(self, path) -> StayTimeQuerySet:
        return self.get_queryset().for_path(path)

    def aggregate_stats(self) -> dict:
        return self.get_queryset().aggregate_stats()


# ---------------------------------------------------------------------------
# EngagementScore
# ---------------------------------------------------------------------------

class EngagementScoreQuerySet(models.QuerySet):

    def for_user(self, user) -> "EngagementScoreQuerySet":
        return self.filter(user=user)

    def for_date(self, date: "datetime.date") -> "EngagementScoreQuerySet":
        return self.filter(date=date)

    def in_date_range(
        self,
        start: "datetime.date",
        end: "datetime.date",
    ) -> "EngagementScoreQuerySet":
        return self.filter(date__gte=start, date__lte=end)

    def for_tier(self, tier: str) -> "EngagementScoreQuerySet":
        return self.filter(tier=tier)

    def high_engagement(self) -> "EngagementScoreQuerySet":
        from .constants import ENGAGEMENT_TIER_HIGH
        return self.filter(score__gte=ENGAGEMENT_TIER_HIGH)

    def aggregate_stats(self) -> dict:
        return self.aggregate(
            avg_score=Avg("score"),
            max_score=Max("score"),
            min_score=Min("score"),
            count=Count("id"),
        )

    def by_week(self) -> "EngagementScoreQuerySet":
        return (
            self.annotate(week=TruncWeek("date"))
            .values("week")
            .annotate(avg_score=Avg("score"), count=Count("id"))
            .order_by("week")
        )

    def select_full(self) -> "EngagementScoreQuerySet":
        return self.select_related("user")


class EngagementScoreManager(models.Manager):
    def get_queryset(self) -> EngagementScoreQuerySet:
        return EngagementScoreQuerySet(self.model, using=self._db)

    def for_user(self, user) -> EngagementScoreQuerySet:
        return self.get_queryset().for_user(user)

    def today(self) -> EngagementScoreQuerySet:
        return self.get_queryset().for_date(timezone.localdate())

    def high_engagement(self) -> EngagementScoreQuerySet:
        return self.get_queryset().high_engagement()

    def select_full(self) -> EngagementScoreQuerySet:
        """Eager-load related objects for list views."""
        return self.get_queryset().select_full()