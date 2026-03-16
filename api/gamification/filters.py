"""
Gamification Filters — django-filter FilterSets.
"""

from __future__ import annotations

import django_filters
from django.utils import timezone

from .choices import ContestCycleStatus, RewardType, AchievementType, LeaderboardScope
from .models import ContestCycle, ContestReward, UserAchievement


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
