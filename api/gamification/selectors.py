"""
Gamification Selectors — Data selection logic for gamification queries.

This module provides selector classes for complex data selection and filtering
operations in the gamification system, following the Selector pattern.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, F, Func, Value, Case, When
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, LeaderboardSnapshot,
    ContestReward, UserAchievement, WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction, ChallengeStatus,
    StreakStatus, ContestCycleStatus, LeaderboardScope, SnapshotStatus,
    RewardType, AchievementType, WebhookStatus, WebhookEventType
)

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseSelector:
    """Base selector class with common functionality."""
    
    def __init__(self):
        self.queryset = None
        self.filters = {}
        self.exclusions = {}
        self.ordering = []
        self.limit = None
        self.offset = None
    
    def filter(self, **kwargs) -> 'BaseSelector':
        """Add filters to the selector."""
        self.filters.update(kwargs)
        return self
    
    def exclude(self, **kwargs) -> 'BaseSelector':
        """Add exclusions to the selector."""
        self.exclusions.update(kwargs)
        return self
    
    def order_by(self, *fields) -> 'BaseSelector':
        """Set ordering for the selector."""
        self.ordering = list(fields)
        return self
    
    def limit_results(self, limit: int) -> 'BaseSelector':
        """Set limit for results."""
        self.limit = limit
        return self
    
    def offset_results(self, offset: int) -> 'BaseSelector':
        """Set offset for results."""
        self.offset = offset
        return self
    
    def apply_filters(self, queryset):
        """Apply filters to queryset."""
        if self.filters:
            queryset = queryset.filter(**self.filters)
        
        if self.exclusions:
            queryset = queryset.exclude(**self.exclusions)
        
        return queryset
    
    def apply_ordering(self, queryset):
        """Apply ordering to queryset."""
        if self.ordering:
            queryset = queryset.order_by(*self.ordering)
        
        return queryset
    
    def apply_pagination(self, queryset):
        """Apply pagination to queryset."""
        if self.offset:
            queryset = queryset.offset(self.offset)
        
        if self.limit:
            queryset = queryset.limit(self.limit)
        
        return queryset
    
    def execute(self):
        """Execute the selector query."""
        if self.queryset is None:
            raise ValueError("Queryset not set")
        
        queryset = self.apply_filters(self.queryset)
        queryset = self.apply_ordering(queryset)
        queryset = self.apply_pagination(queryset)
        
        return queryset


class BadgeSelector(BaseSelector):
    """Selector for Badge model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = Badge.objects.all()
    
    def active(self) -> 'BadgeSelector':
        """Filter active badges."""
        return self.filter(is_active=True)
    
    def by_rarity(self, rarity: str) -> 'BadgeSelector':
        """Filter by rarity."""
        return self.filter(rarity=rarity)
    
    def by_criteria_type(self, criteria_type: str) -> 'BadgeSelector':
        """Filter by criteria type."""
        return self.filter(criteria_type=criteria_type)
    
    def by_points_range(self, min_points: int, max_points: int) -> 'BadgeSelector':
        """Filter by points bonus range."""
        return self.filter(points_bonus__gte=min_points, points_bonus__lte=max_points)
    
    def by_user_eligibility(self, user_points: int, streak_days: int = 0,
                           achievement_count: int = 0, contest_wins: int = 0,
                           referral_count: int = 0) -> 'BadgeSelector':
        """Filter badges user is eligible for."""
        eligibility_conditions = Q()
        
        # Points threshold criteria
        eligibility_conditions |= Q(
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value__lte=user_points
        )
        
        # Streak days criteria
        eligibility_conditions |= Q(
            criteria_type=BadgeCriteriaType.STREAK_DAYS,
            criteria_value__lte=streak_days
        )
        
        # Achievement count criteria
        eligibility_conditions |= Q(
            criteria_type=BadgeCriteriaType.ACHIEVEMENT_COUNT,
            criteria_value__lte=achievement_count
        )
        
        # Contest wins criteria
        eligibility_conditions |= Q(
            criteria_type=BadgeCriteriaType.CONTEST_WINS,
            criteria_value__lte=contest_wins
        )
        
        # Referral count criteria
        eligibility_conditions |= Q(
            criteria_type=BadgeCriteriaType.REFERRAL_COUNT,
            criteria_value__lte=referral_count
        )
        
        return self.filter(eligibility_conditions).active()
    
    def with_user_count(self) -> 'BadgeSelector':
        """Annotate with user count."""
        self.queryset = self.queryset.annotate(
            user_count=models.Count('userbadge', distinct=True)
        )
        return self
    
    def with_award_rate(self) -> 'BadgeSelector':
        """Annotate with award rate."""
        total_users = User.objects.count()
        if total_users == 0:
            return self.annotate(award_rate=models.Value(0.0))
        
        self.queryset = self.queryset.annotate(
            user_count=models.Count('userbadge', distinct=True)
        ).annotate(
            award_rate=models.ExpressionWrapper(
                models.F('user_count') * 100.0 / total_users,
                output_field=models.FloatField()
            )
        )
        return self
    
    def popular(self) -> 'BadgeSelector':
        """Get popular badges (most awarded)."""
        return self.with_user_count().order_by('-user_count')
    
    def recently_created(self, days: int = 30) -> 'BadgeSelector':
        """Get recently created badges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def annotate(self, **annotations) -> 'BadgeSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class UserBadgeSelector(BaseSelector):
    """Selector for UserBadge model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = UserBadge.objects.all()
    
    def for_user(self, user_id: str) -> 'UserBadgeSelector':
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def pinned(self) -> 'UserBadgeSelector':
        """Filter pinned badges."""
        return self.filter(is_pinned=True)
    
    def by_badge(self, badge_id: str) -> 'UserBadgeSelector':
        """Filter by badge."""
        return self.filter(badge_id=badge_id)
    
    def by_rarity(self, rarity: str) -> 'UserBadgeSelector':
        """Filter by badge rarity."""
        return self.filter(badge__rarity=rarity)
    
    def recently_earned(self, days: int = 30) -> 'UserBadgeSelector':
        """Filter recently earned badges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(earned_at__gte=since)
    
    def with_badge_details(self) -> 'UserBadgeSelector':
        """Select related badge details."""
        self.queryset = self.queryset.select_related('badge')
        return self
    
    def with_user_details(self) -> 'UserBadgeSelector':
        """Select related user details."""
        self.queryset = self.queryset.select_related('user')
        return self
    
    def for_user_with_details(self, user_id: str) -> 'UserBadgeSelector':
        """Get user badges with all details."""
        return self.for_user(user_id).with_badge_details()
    
    def count_by_rarity(self) -> 'UserBadgeSelector':
        """Count badges by rarity."""
        self.queryset = self.queryset.values('badge__rarity').annotate(
            count=models.Count('id')
        ).order_by('-count')
        return self
    
    def annotate(self, **annotations) -> 'UserBadgeSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class DailyChallengeSelector(BaseSelector):
    """Selector for DailyChallenge model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = DailyChallenge.objects.all()
    
    def active(self) -> 'DailyChallengeSelector':
        """Filter active challenges."""
        return self.filter(is_active=True)
    
    def for_date(self, challenge_date: datetime.date) -> 'DailyChallengeSelector':
        """Filter by specific date."""
        return self.filter(date=challenge_date)
    
    def for_date_range(self, start_date: datetime.date, end_date: datetime.date) -> 'DailyChallengeSelector':
        """Filter by date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)
    
    def by_action(self, action: str) -> 'DailyChallengeSelector':
        """Filter by action type."""
        return self.filter(target_action=action)
    
    def by_points_range(self, min_points: int, max_points: int) -> 'DailyChallengeSelector':
        """Filter by points bonus range."""
        return self.filter(bonus_points__gte=min_points, bonus_points__lte=max_points)
    
    def recent(self, days: int = 7) -> 'DailyChallengeSelector':
        """Get recent challenges."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=since)
    
    def upcoming(self, days: int = 7) -> 'DailyChallengeSelector':
        """Get upcoming challenges."""
        until = timezone.now().date() + timedelta(days=days)
        return self.filter(date__gt=timezone.now().date(), date__lte=until)
    
    def with_completion_stats(self) -> 'DailyChallengeSelector':
        """Annotate with completion statistics."""
        self.queryset = self.queryset.annotate(
            total_participants=models.Count('userdailychallenge', distinct=True),
            completed_count=models.Count(
                'userdailychallenge',
                filter=models.Q(userdailychallenge__is_completed=True)
            ),
            completion_rate=models.ExpressionWrapper(
                models.F('completed_count') * 100.0 / models.F('total_participants'),
                output_field=models.FloatField()
            )
        )
        return self
    
    def popular(self) -> 'DailyChallengeSelector':
        """Get most popular challenges (by participation)."""
        return self.with_completion_stats().order_by('-total_participants')
    
    def annotate(self, **annotations) -> 'DailyChallengeSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class UserDailyChallengeSelector(BaseSelector):
    """Selector for UserDailyChallenge model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = UserDailyChallenge.objects.all()
    
    def for_user(self, user_id: str) -> 'UserDailyChallengeSelector':
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def for_challenge(self, challenge_id: str) -> 'UserDailyChallengeSelector':
        """Filter by challenge."""
        return self.filter(challenge_id=challenge_id)
    
    def completed(self) -> 'UserDailyChallengeSelector':
        """Filter completed challenges."""
        return self.filter(is_completed=True)
    
    def in_progress(self) -> 'UserDailyChallengeSelector':
        """Filter challenges in progress."""
        return self.filter(is_completed=False)
    
    def for_date(self, challenge_date: datetime.date) -> 'UserDailyChallengeSelector':
        """Filter by challenge date."""
        return self.filter(challenge__date=challenge_date)
    
    def for_date_range(self, start_date: datetime.date, end_date: datetime.date) -> 'UserDailyChallengeSelector':
        """Filter by date range."""
        return self.filter(challenge__date__gte=start_date, challenge__date__lte=end_date)
    
    def by_action(self, action: str) -> 'UserDailyChallengeSelector':
        """Filter by action type."""
        return self.filter(challenge__target_action=action)
    
    def with_challenge_details(self) -> 'UserDailyChallengeSelector':
        """Select related challenge details."""
        self.queryset = self.queryset.select_related('challenge')
        return self
    
    def with_user_details(self) -> 'UserDailyChallengeSelector':
        """Select related user details."""
        self.queryset = self.queryset.select_related('user')
        return self
    
    def recently_completed(self, days: int = 7) -> 'UserDailyChallengeSelector':
        """Filter recently completed challenges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(is_completed=True, completed_at__gte=since)
    
    def with_progress_percentage(self) -> 'UserDailyChallengeSelector':
        """Annotate with progress percentage."""
        self.queryset = self.queryset.annotate(
            progress_percentage=models.ExpressionWrapper(
                models.F('progress') * 100.0 / models.F('challenge__target_count'),
                output_field=models.FloatField()
            )
        )
        return self
    
    def for_user_with_details(self, user_id: str) -> 'UserDailyChallengeSelector':
        """Get user challenges with all details."""
        return self.for_user(user_id).with_challenge_details()
    
    def annotate(self, **annotations) -> 'UserDailyChallengeSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class StreakSelector(BaseSelector):
    """Selector for Streak model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = Streak.objects.all()
    
    def for_user(self, user_id: str) -> 'StreakSelector':
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def active(self) -> 'StreakSelector':
        """Filter active streaks."""
        return self.filter(is_active=True)
    
    def inactive(self) -> 'StreakSelector':
        """Filter inactive streaks."""
        return self.filter(is_active=False)
    
    def with_current_days(self, min_days: int) -> 'StreakSelector':
        """Filter by minimum current days."""
        return self.filter(current_days__gte=min_days)
    
    def with_longest_days(self, min_days: int) -> 'StreakSelector':
        """Filter by minimum longest days."""
        return self.filter(longest_days__gte=min_days)
    
    def recently_active(self, days: int = 7) -> 'StreakSelector':
        """Filter streaks with recent activity."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(last_activity_date__gte=since)
    
    def expiring_soon(self, days: int = 1) -> 'StreakSelector':
        """Filter streaks that will expire soon."""
        threshold_date = timezone.now().date() - timedelta(days=days)
        return self.filter(
            is_active=True,
            last_activity_date__lte=threshold_date
        )
    
    def with_user_details(self) -> 'StreakSelector':
        """Select related user details."""
        self.queryset = self.queryset.select_related('user')
        return self
    
    def with_activity_stats(self) -> 'StreakSelector':
        """Annotate with activity statistics."""
        self.queryset = self.queryset.annotate(
            days_until_reset=models.ExpressionWrapper(
                models.F('last_activity_date') + timedelta(days=1) - timezone.now().date(),
                output_field=models.IntegerField()
            ),
            is_expired=models.Case(
                When(
                    last_activity_date__lt=timezone.now().date() - timedelta(days=1),
                    then=models.Value(True)
                ),
                default=models.Value(False),
                output_field=models.BooleanField()
            )
        )
        return self
    
    def leaderboard(self, limit: int = 100) -> 'StreakSelector':
        """Get streak leaderboard."""
        return self.active().with_user_details().order_by('-current_days', '-longest_days').limit_results(limit)
    
    def by_activity_range(self, start_date: datetime.date, end_date: datetime.date) -> 'StreakSelector':
        """Filter streaks with activity in date range."""
        return self.filter(
            last_activity_date__gte=start_date,
            last_activity_date__lte=end_date
        )
    
    def annotate(self, **annotations) -> 'StreakSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class LevelConfigSelector(BaseSelector):
    """Selector for LevelConfig model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = LevelConfig.objects.all()
    
    def active(self) -> 'LevelConfigSelector':
        """Filter active levels."""
        return self.filter(is_active=True)
    
    def by_level_range(self, min_level: int, max_level: int) -> 'LevelConfigSelector':
        """Filter by level range."""
        return self.filter(level_number__gte=min_level, level_number__lte=max_level)
    
    def by_points_range(self, min_points: int, max_points: int) -> 'LevelConfigSelector':
        """Filter by points required range."""
        return self.filter(points_required__gte=min_points, points_required__lte=max_points)
    
    def with_badge(self) -> 'LevelConfigSelector':
        """Filter levels that have associated badges."""
        return self.filter(badge__isnull=False)
    
    def without_badge(self) -> 'LevelConfigSelector':
        """Filter levels without associated badges."""
        return self.filter(badge__isnull=True)
    
    def with_user_count(self) -> 'LevelConfigSelector':
        """Annotate with user count at this level."""
        self.queryset = self.queryset.annotate(
            user_count=models.Count(
                'userachievement',
                filter=models.Q(userachievement__points_awarded__gte=models.F('points_required'))
            )
        )
        return self
    
    def ordered_by_level(self) -> 'LevelConfigSelector':
        """Order by level number."""
        return self.order_by('level_number')
    
    def max_level(self) -> 'LevelConfigSelector':
        """Get maximum level."""
        return self.active().order_by('-level_number').limit_results(1)
    
    def for_points(self, points: int) -> 'LevelConfigSelector':
        """Get level for given points."""
        return self.active().filter(points_required__lte=points).order_by('-level_number')
    
    def annotate(self, **annotations) -> 'LevelConfigSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class ContestCycleSelector(BaseSelector):
    """Selector for ContestCycle model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = ContestCycle.objects.all()
    
    def by_status(self, status: str) -> 'ContestCycleSelector':
        """Filter by status."""
        return self.filter(status=status)
    
    def active(self) -> 'ContestCycleSelector':
        """Filter active contests."""
        return self.filter(status=ContestCycleStatus.ACTIVE)
    
    def completed(self) -> 'ContestCycleSelector':
        """Filter completed contests."""
        return self.filter(status=ContestCycleStatus.COMPLETED)
    
    def upcoming(self) -> 'ContestCycleSelector':
        """Filter upcoming contests."""
        return self.filter(
            status=ContestCycleStatus.SCHEDULED,
            start_time__gt=timezone.now()
        )
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> 'ContestCycleSelector':
        """Filter contests within date range."""
        return self.filter(
            start_time__gte=start_date,
            end_time__lte=end_date
        )
    
    def current(self) -> 'ContestCycleSelector':
        """Get current contest (active or most recent)."""
        return self.filter(
            models.Q(status=ContestCycleStatus.ACTIVE) |
            models.Q(status=ContestCycleStatus.COMPLETED)
        ).order_by('-start_time').limit_results(1)
    
    def with_participant_count(self) -> 'ContestCycleSelector':
        """Annotate with participant count."""
        self.queryset = self.queryset.annotate(
            participant_count=models.Count('userachievement__user', distinct=True)
        )
        return self
    
    def with_total_points_awarded(self) -> 'ContestCycleSelector':
        """Annotate with total points awarded."""
        self.queryset = self.queryset.annotate(
            total_points_awarded=models.Sum('userachievement__points_awarded')
        )
        return self
    
    def with_completion_stats(self) -> 'ContestCycleSelector':
        """Annotate with completion statistics."""
        self.queryset = self.queryset.annotate(
            participant_count=models.Count('userachievement__user', distinct=True),
            total_points_awarded=models.Sum('userachievement__points_awarded'),
            average_points=models.Avg('userachievement__points_awarded')
        )
        return self
    
    def recent(self, days: int = 30) -> 'ContestCycleSelector':
        """Get recent contests."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(start_time__gte=since)
    
    def annotate(self, **annotations) -> 'ContestCycleSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class UserAchievementSelector(BaseSelector):
    """Selector for UserAchievement model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = UserAchievement.objects.all()
    
    def for_user(self, user_id: str) -> 'UserAchievementSelector':
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def for_contest(self, contest_id: str) -> 'UserAchievementSelector':
        """Filter by contest."""
        return self.filter(contest_cycle_id=contest_id)
    
    def awarded(self) -> 'UserAchievementSelector':
        """Filter awarded achievements."""
        return self.filter(is_awarded=True)
    
    def pending(self) -> 'UserAchievementSelector':
        """Filter pending achievements."""
        return self.filter(is_awarded=False)
    
    def by_type(self, achievement_type: str) -> 'UserAchievementSelector':
        """Filter by achievement type."""
        return self.filter(achievement_type=achievement_type)
    
    def by_points_range(self, min_points: int, max_points: int) -> 'UserAchievementSelector':
        """Filter by points range."""
        return self.filter(points_awarded__gte=min_points, points_awarded__lte=max_points)
    
    def by_rank_range(self, min_rank: int, max_rank: int) -> 'UserAchievementSelector':
        """Filter by rank range."""
        return self.filter(rank__gte=min_rank, rank__lte=max_rank)
    
    def recently_awarded(self, days: int = 30) -> 'UserAchievementSelector':
        """Filter recently awarded achievements."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(is_awarded=True, awarded_at__gte=since)
    
    def with_contest_details(self) -> 'UserAchievementSelector':
        """Select related contest details."""
        self.queryset = self.queryset.select_related('contest_cycle')
        return self
    
    def with_user_details(self) -> 'UserAchievementSelector':
        """Select related user details."""
        self.queryset = self.queryset.select_related('user')
        return self
    
    def leaderboard(self, contest_id: Optional[str] = None, limit: int = 100) -> 'UserAchievementSelector':
        """Get achievement leaderboard."""
        queryset = self.awarded()
        
        if contest_id:
            queryset = queryset.for_contest(contest_id)
        
        return queryset.with_user_details().order_by('-points_awarded', 'rank').limit_results(limit)
    
    def for_user_with_details(self, user_id: str) -> 'UserAchievementSelector':
        """Get user achievements with all details."""
        return self.for_user(user_id).with_contest_details().order_by('-awarded_at')
    
    def with_total_points(self) -> 'UserAchievementSelector':
        """Annotate with total points for user."""
        self.queryset = self.queryset.values('user_id').annotate(
            total_points=models.Sum('points_awarded'),
            achievement_count=models.Count('id')
        ).order_by('-total_points')
        return self
    
    def annotate(self, **annotations) -> 'UserAchievementSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class WebhookEndpointSelector(BaseSelector):
    """Selector for WebhookEndpoint model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = WebhookEndpoint.objects.all()
    
    def active(self) -> 'WebhookEndpointSelector':
        """Filter active endpoints."""
        return self.filter(is_active=True)
    
    def inactive(self) -> 'WebhookEndpointSelector':
        """Filter inactive endpoints."""
        return self.filter(is_active=False)
    
    def by_event_type(self, event_type: str) -> 'WebhookEndpointSelector':
        """Filter by event type."""
        return self.filter(event_types__contains=[event_type])
    
    def with_delivery_stats(self) -> 'WebhookEndpointSelector':
        """Annotate with delivery statistics."""
        self.queryset = self.queryset.annotate(
            total_deliveries=models.Count('webhookdelivery'),
            successful_deliveries=models.Count(
                'webhookdelivery',
                filter=models.Q(webhookdelivery__status=WebhookStatus.SUCCESS)
            ),
            failed_deliveries=models.Count(
                'webhookdelivery',
                filter=models.Q(webhookdelivery__status=WebhookStatus.FAILED)
            )
        ).annotate(
            success_rate=models.ExpressionWrapper(
                models.F('successful_deliveries') * 100.0 / models.F('total_deliveries'),
                output_field=models.FloatField()
            )
        )
        return self
    
    def recent_deliveries(self, hours: int = 24) -> 'WebhookEndpointSelector':
        """Filter endpoints with recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            webhookdelivery__created_at__gte=since
        ).distinct()
    
    def annotate(self, **annotations) -> 'WebhookEndpointSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class WebhookEventSelector(BaseSelector):
    """Selector for WebhookEvent model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = WebhookEvent.objects.all()
    
    def by_type(self, event_type: str) -> 'WebhookEventSelector':
        """Filter by event type."""
        return self.filter(event_type=event_type)
    
    def for_user(self, user_id: str) -> 'WebhookEventSelector':
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def recent(self, hours: int = 24) -> 'WebhookEventSelector':
        """Filter recent events."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> 'WebhookEventSelector':
        """Filter events within date range."""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def with_delivery_count(self) -> 'WebhookEventSelector':
        """Annotate with delivery count."""
        self.queryset = self.queryset.annotate(
            delivery_count=models.Count('webhookdelivery')
        )
        return self
    
    def undelivered(self) -> 'WebhookEventSelector':
        """Filter events that haven't been delivered."""
        return self.filter(webhookdelivery__isnull=True)
    
    def annotate(self, **annotations) -> 'WebhookEventSelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


class WebhookDeliverySelector(BaseSelector):
    """Selector for WebhookDelivery model queries."""
    
    def __init__(self):
        super().__init__()
        self.queryset = WebhookDelivery.objects.all()
    
    def by_status(self, status: str) -> 'WebhookDeliverySelector':
        """Filter by status."""
        return self.filter(status=status)
    
    def successful(self) -> 'WebhookDeliverySelector':
        """Filter successful deliveries."""
        return self.filter(status=WebhookStatus.SUCCESS)
    
    def failed(self) -> 'WebhookDeliverySelector':
        """Filter failed deliveries."""
        return self.filter(status=WebhookStatus.FAILED)
    
    def retrying(self) -> 'WebhookDeliverySelector':
        """Filter deliveries pending retry."""
        return self.filter(status=WebhookStatus.RETRY)
    
    def pending(self) -> 'WebhookDeliverySelector':
        """Filter pending deliveries."""
        return self.filter(status=WebhookStatus.PENDING)
    
    def for_webhook(self, webhook_id: str) -> 'WebhookDeliverySelector':
        """Filter by webhook."""
        return self.filter(webhook_id=webhook_id)
    
    def for_event(self, event_id: str) -> 'WebhookDeliverySelector':
        """Filter by event."""
        return self.filter(event_id=event_id)
    
    def recent(self, hours: int = 24) -> 'WebhookDeliverySelector':
        """Filter recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def with_details(self) -> 'WebhookDeliverySelector':
        """Select related details."""
        self.queryset = self.queryset.select_related('webhook', 'event')
        return self
    
    def by_attempt_count(self, min_attempts: int, max_attempts: Optional[int] = None) -> 'WebhookDeliverySelector':
        """Filter by attempt count."""
        queryset = self.filter(attempts__gte=min_attempts)
        
        if max_attempts is not None:
            queryset = queryset.filter(attempts__lte=max_attempts)
        
        return queryset
    
    def scheduled_for_retry(self) -> 'WebhookDeliverySelector':
        """Filter deliveries scheduled for retry."""
        return self.filter(
            status=WebhookStatus.RETRY,
            scheduled_at__lte=timezone.now()
        )
    
    def annotate(self, **annotations) -> 'WebhookDeliverySelector':
        """Add annotations to queryset."""
        self.queryset = self.queryset.annotate(**annotations)
        return self


# Composite selectors for complex queries
class GamificationCompositeSelector:
    """Composite selector for complex gamification queries."""
    
    def __init__(self):
        self.badge_selector = BadgeSelector()
        self.user_badge_selector = UserBadgeSelector()
        self.challenge_selector = DailyChallengeSelector()
        self.user_challenge_selector = UserDailyChallengeSelector()
        self.streak_selector = StreakSelector()
        self.level_selector = LevelConfigSelector()
        self.contest_selector = ContestCycleSelector()
        self.achievement_selector = UserAchievementSelector()
    
    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user summary."""
        # User badges
        user_badges = (
            self.user_badge_selector
            .for_user(user_id)
            .with_badge_details()
            .execute()
        )
        
        # User achievements
        user_achievements = (
            self.achievement_selector
            .for_user(user_id)
            .awarded()
            .with_contest_details()
            .execute()
        )
        
        # User streak
        user_streak = (
            self.streak_selector
            .for_user(user_id)
            .first()
            .execute()
        )
        
        # User challenges
        user_challenges = (
            self.user_challenge_selector
            .for_user(user_id)
            .with_challenge_details()
            .recent(days=7)
            .execute()
        )
        
        return {
            'badges': user_badges,
            'achievements': user_achievements,
            'streak': user_streak,
            'recent_challenges': user_challenges,
            'total_badges': len(user_badges),
            'total_achievements': len(user_achievements),
            'current_streak': user_streak.current_days if user_streak else 0,
        }
    
    def get_leaderboard_data(self, contest_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leaderboard data."""
        leaderboard = (
            self.achievement_selector
            .leaderboard(contest_id=contest_id, limit=limit)
            .execute()
        )
        
        return [
            {
                'rank': index + 1,
                'user_id': str(achievement.user.id),
                'username': achievement.user.username,
                'points_awarded': achievement.points_awarded,
                'achievement_type': achievement.achievement_type,
                'contest_name': achievement.contest_cycle.name if achievement.contest_cycle else None,
            }
            for index, achievement in enumerate(leaderboard)
        ]
    
    def get_popular_content(self, days: int = 30) -> Dict[str, Any]:
        """Get popular content statistics."""
        # Popular badges
        popular_badges = (
            self.badge_selector
            .with_user_count()
            .recent(days=days)
            .popular()
            .limit_results(10)
            .execute()
        )
        
        # Popular challenges
        popular_challenges = (
            self.challenge_selector
            .with_completion_stats()
            .recent(days=days)
            .popular()
            .limit_results(10)
            .execute()
        )
        
        return {
            'popular_badges': popular_badges,
            'popular_challenges': popular_challenges,
            'period_days': days,
        }


# Utility functions for creating selectors
def create_badge_selector() -> BadgeSelector:
    """Create a new badge selector."""
    return BadgeSelector()


def create_user_badge_selector() -> UserBadgeSelector:
    """Create a new user badge selector."""
    return UserBadgeSelector()


def create_challenge_selector() -> DailyChallengeSelector:
    """Create a new challenge selector."""
    return DailyChallengeSelector()


def create_achievement_selector() -> UserAchievementSelector:
    """Create a new achievement selector."""
    return UserAchievementSelector()


def create_composite_selector() -> GamificationCompositeSelector:
    """Create a new composite selector."""
    return GamificationCompositeSelector()


# Selector factory for dynamic selector creation
class SelectorFactory:
    """Factory for creating selectors dynamically."""
    
    @staticmethod
    def create_selector(model_name: str) -> BaseSelector:
        """Create selector for given model name."""
        selector_mapping = {
            'badge': BadgeSelector,
            'userbadge': UserBadgeSelector,
            'dailychallenge': DailyChallengeSelector,
            'userdailychallenge': UserDailyChallengeSelector,
            'streak': StreakSelector,
            'levelconfig': LevelConfigSelector,
            'contestcycle': ContestCycleSelector,
            'userachievement': UserAchievementSelector,
            'webhookendpoint': WebhookEndpointSelector,
            'webhookevent': WebhookEventSelector,
            'webhookdelivery': WebhookDeliverySelector,
        }
        
        selector_class = selector_mapping.get(model_name.lower())
        if not selector_class:
            raise ValueError(f"Unknown model: {model_name}")
        
        return selector_class()
    
    @staticmethod
    def create_user_summary_selector(user_id: str) -> GamificationCompositeSelector:
        """Create selector for user summary."""
        composite = GamificationCompositeSelector()
        return composite.get_user_summary(user_id)
    
    @staticmethod
    def create_leaderboard_selector(contest_id: Optional[str] = None, limit: int = 100) -> GamificationCompositeSelector:
        """Create selector for leaderboard."""
        composite = GamificationCompositeSelector()
        return composite.get_leaderboard_data(contest_id, limit)
