"""
Gamification Filters — django-filter FilterSets.
"""

from __future__ import annotations

import django_filters
from django.db import models
from django.utils import timezone

from .choices import (
    ContestCycleStatus, RewardType, AchievementType, LeaderboardScope,
    PointsTransactionSource, StreakFreezeReason, ContestParticipantStatus,
    GamificationFeature, InsightMetricType, AlertSeverity, AlertType
)
from .models import (
    ContestCycle, ContestReward, UserAchievement, UserPoints, PointsTransaction,
    StreakFreeze, ContestParticipant, GamificationConfig, GamificationInsight
)


class ContestCycleFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ContestCycleStatus.choices)
    is_featured = django_filters.BooleanFilter()
    start_date_after = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    start_date_before = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="lte")
    is_active_now = django_filters.BooleanFilter(method="filter_is_active_now")

    class Meta:
        model = ContestCycle
        fields = ["status", "is_featured"]

    def filter_is_active_now(self, queryset, name, value):
        if value is True:
            now = timezone.now()
            return queryset.filter(
                status=ContestCycleStatus.ACTIVE,
                start_date__lte=now,
                end_date__gt=now,
            )
        return queryset


class ContestRewardFilter(django_filters.FilterSet):
    reward_type = django_filters.ChoiceFilter(choices=RewardType.choices)
    is_active = django_filters.BooleanFilter()
    cycle_id = django_filters.UUIDFilter(field_name="contest_cycle_id")
    rank = django_filters.NumberFilter(method="filter_by_rank")

    class Meta:
        model = ContestReward
        fields = ["reward_type", "is_active"]

    def filter_by_rank(self, queryset, name, value):
        try:
            rank = int(value)
            if rank < 1:
                return queryset.none()
        except (TypeError, ValueError):
            return queryset.none()
        return queryset.filter(rank_from__lte=rank, rank_to__gte=rank)


class UserAchievementFilter(django_filters.FilterSet):
    achievement_type = django_filters.ChoiceFilter(choices=AchievementType.choices)
    is_awarded = django_filters.BooleanFilter()
    is_notified = django_filters.BooleanFilter()
    cycle_id = django_filters.UUIDFilter(field_name="contest_cycle_id")
    awarded_after = django_filters.DateTimeFilter(field_name="awarded_at", lookup_expr="gte")
    awarded_before = django_filters.DateTimeFilter(field_name="awarded_at", lookup_expr="lte")

    class Meta:
        model = UserAchievement
        fields = ["achievement_type", "is_awarded", "is_notified"]


class UserPointsFilter(django_filters.FilterSet):
    total_points_min = django_filters.NumberFilter(field_name="total_points", lookup_expr="gte")
    total_points_max = django_filters.NumberFilter(field_name="total_points", lookup_expr="lte")
    available_points_min = django_filters.NumberFilter(field_name="available_points", lookup_expr="gte")
    available_points_max = django_filters.NumberFilter(field_name="available_points", lookup_expr="lte")
    points_expiry_after = django_filters.DateTimeFilter(field_name="points_expiry_date", lookup_expr="gte")
    points_expiry_before = django_filters.DateTimeFilter(field_name="points_expiry_date", lookup_expr="lte")
    has_expiry_date = django_filters.BooleanFilter(method="filter_has_expiry_date")
    is_expired = django_filters.BooleanFilter(method="filter_is_expired")

    class Meta:
        model = UserPoints
        fields = ["user_id"]

    def filter_has_expiry_date(self, queryset, name, value):
        if value is True:
            return queryset.filter(points_expiry_date__isnull=False)
        elif value is False:
            return queryset.filter(points_expiry_date__isnull=True)
        return queryset

    def filter_is_expired(self, queryset, name, value):
        if value is True:
            return queryset.filter(points_expiry_date__lt=timezone.now())
        elif value is False:
            return queryset.filter(
                models.Q(points_expiry_date__gte=timezone.now()) |
                models.Q(points_expiry_date__isnull=True)
            )
        return queryset


class PointsTransactionFilter(django_filters.FilterSet):
    source = django_filters.ChoiceFilter(choices=PointsTransactionSource.choices)
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    user_id = django_filters.UUIDFilter(field_name="user_id")
    is_positive = django_filters.BooleanFilter(method="filter_is_positive")
    is_negative = django_filters.BooleanFilter(method="filter_is_negative")

    class Meta:
        model = PointsTransaction
        fields = ["source", "user_id"]

    def filter_is_positive(self, queryset, name, value):
        if value is True:
            return queryset.filter(amount__gt=0)
        elif value is False:
            return queryset.filter(amount__lt=0)
        return queryset

    def filter_is_negative(self, queryset, name, value):
        if value is True:
            return queryset.filter(amount__lt=0)
        elif value is False:
            return queryset.filter(amount__gte=0)
        return queryset


class StreakFreezeFilter(django_filters.FilterSet):
    reason = django_filters.ChoiceFilter(choices=StreakFreezeReason.choices)
    is_active = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    expires_after = django_filters.DateTimeFilter(field_name="expires_at", lookup_expr="gte")
    expires_before = django_filters.DateTimeFilter(field_name="expires_at", lookup_expr="lte")
    user_id = django_filters.UUIDFilter(field_name="user_id")
    is_expired = django_filters.BooleanFilter(method="filter_is_expired")
    duration_hours_min = django_filters.NumberFilter(method="filter_duration_hours_min")
    duration_hours_max = django_filters.NumberFilter(method="filter_duration_hours_max")

    class Meta:
        model = StreakFreeze
        fields = ["reason", "is_active", "user_id"]

    def filter_is_expired(self, queryset, name, value):
        if value is True:
            return queryset.filter(expires_at__lt=timezone.now())
        elif value is False:
            return queryset.filter(
                models.Q(expires_at__gte=timezone.now()) |
                models.Q(expires_at__isnull=True)
            )
        return queryset

    def filter_duration_hours_min(self, queryset, name, value):
        try:
            hours = int(value)
            return queryset.filter(
                models.Q(expires_at__isnull=False) &
                (models.F('expires_at') - models.F('created_at')) >= timezone.timedelta(hours=hours)
            )
        except (TypeError, ValueError):
            return queryset.none()

    def filter_duration_hours_max(self, queryset, name, value):
        try:
            hours = int(value)
            return queryset.filter(
                models.Q(expires_at__isnull=False) &
                (models.F('expires_at') - models.F('created_at')) <= timezone.timedelta(hours=hours)
            )
        except (TypeError, ValueError):
            return queryset.none()


class ContestParticipantFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ContestParticipantStatus.choices)
    contest_cycle_id = django_filters.UUIDFilter(field_name="contest_cycle_id")
    user_id = django_filters.UUIDFilter(field_name="user_id")
    joined_after = django_filters.DateTimeFilter(field_name="joined_at", lookup_expr="gte")
    joined_before = django_filters.DateTimeFilter(field_name="joined_at", lookup_expr="lte")
    is_disqualified = django_filters.BooleanFilter(method="filter_is_disqualified")
    is_active = django_filters.BooleanFilter(method="filter_is_active")
    score_min = django_filters.NumberFilter(field_name="score", lookup_expr="gte")
    score_max = django_filters.NumberFilter(field_name="score", lookup_expr="lte")

    class Meta:
        model = ContestParticipant
        fields = ["status", "contest_cycle_id", "user_id"]

    def filter_is_disqualified(self, queryset, name, value):
        if value is True:
            return queryset.filter(status=ContestParticipantStatus.DISQUALIFIED)
        elif value is False:
            return queryset.exclude(status=ContestParticipantStatus.DISQUALIFIED)
        return queryset

    def filter_is_active(self, queryset, name, value):
        if value is True:
            return queryset.filter(status=ContestParticipantStatus.ACTIVE)
        elif value is False:
            return queryset.exclude(status=ContestParticipantStatus.ACTIVE)
        return queryset


class GamificationConfigFilter(django_filters.FilterSet):
    feature = django_filters.ChoiceFilter(choices=GamificationFeature.choices)
    is_enabled = django_filters.BooleanFilter()
    tenant_id = django_filters.UUIDFilter(field_name="tenant_id")
    updated_after = django_filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_before = django_filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")
    last_synced_after = django_filters.DateTimeFilter(field_name="last_synced_at", lookup_expr="gte")
    last_synced_before = django_filters.DateTimeFilter(field_name="last_synced_at", lookup_expr="lte")
    has_synced = django_filters.BooleanFilter(method="filter_has_synced")
    needs_sync = django_filters.BooleanFilter(method="filter_needs_sync")

    class Meta:
        model = GamificationConfig
        fields = ["feature", "is_enabled", "tenant_id"]

    def filter_has_synced(self, queryset, name, value):
        if value is True:
            return queryset.filter(last_synced_at__isnull=False)
        elif value is False:
            return queryset.filter(last_synced_at__isnull=True)
        return queryset

    def filter_needs_sync(self, queryset, name, value):
        if value is True:
            # Configs that haven't been synced in the last hour
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
            return queryset.filter(
                models.Q(last_synced_at__lt=one_hour_ago) |
                models.Q(last_synced_at__isnull=True)
            )
        elif value is False:
            # Configs that have been synced in the last hour
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
            return queryset.filter(last_synced_at__gte=one_hour_ago)
        return queryset


class GamificationInsightFilter(django_filters.FilterSet):
    metric_type = django_filters.ChoiceFilter(choices=InsightMetricType.choices)
    date = django_filters.DateFilter(field_name="date")
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    value_min = django_filters.NumberFilter(field_name="value", lookup_expr="gte")
    value_max = django_filters.NumberFilter(field_name="value", lookup_expr="lte")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    has_metadata = django_filters.BooleanFilter(method="filter_has_metadata")
    tenant_id = django_filters.UUIDFilter(method="filter_tenant_id")

    class Meta:
        model = GamificationInsight
        fields = ["metric_type", "date"]

    def filter_has_metadata(self, queryset, name, value):
        if value is True:
            return queryset.filter(metadata__isnull=False).exclude(metadata={})
        elif value is False:
            return queryset.filter(
                models.Q(metadata__isnull=True) | models.Q(metadata={})
            )
        return queryset

    def filter_tenant_id(self, queryset, name, value):
        # Filter by tenant_id in metadata
        if value:
            return queryset.filter(metadata__tenant_id=value)
        return queryset
