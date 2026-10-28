"""
Gamification QuerySets — Custom query managers for optimized data access.

This module provides specialized QuerySet classes for gamification models
with optimized queries, filtering, and aggregation methods.
"""

from __future__ import annotations
from django.db.models import When

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from django.db.models import QuerySet

from django.db import models
from django.db.models import Count, Q, F, Sum, Avg, Max, Min, Prefetch
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, StreakReward, LevelConfig, ContestCycle, LeaderboardSnapshot,
    ContestReward, UserAchievement, WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction, ChallengeStatus,
    StreakStatus, ContestCycleStatus, LeaderboardScope, SnapshotStatus,
    RewardType, AchievementType, WebhookStatus, WebhookEventType
)

logger = logging.getLogger(__name__)


class BadgeQuerySet(models.QuerySet):
    """Custom QuerySet for Badge model."""
    
    def active(self) -> QuerySet['Badge']:
        """Filter active badges."""
        return self.filter(is_active=True)
    
    def by_rarity(self, rarity: str) -> QuerySet['Badge']:
        """Filter by rarity."""
        return self.filter(rarity=rarity)
    
    def by_criteria_type(self, criteria_type: str) -> QuerySet['Badge']:
        """Filter by criteria type."""
        return self.filter(criteria_type=criteria_type)
    
    def with_user_count(self) -> QuerySet['Badge']:
        """Annotate with user count."""
        return self.annotate(
            user_count=Count('userbadge', distinct=True)
        )
    
    def with_award_rate(self) -> QuerySet['Badge']:
        """Annotate with award rate (percentage of eligible users who have earned it)."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        total_users = User.objects.count()
        if total_users == 0:
            return self.annotate(award_rate=models.Value(0.0))
        
        return self.annotate(
            user_count=Count('userbadge', distinct=True)
        ).annotate(
            award_rate=models.ExpressionWrapper(
                models.F('user_count') * 100.0 / total_users,
                output_field=models.FloatField()
            )
        )
    
    def searchable(self) -> QuerySet['Badge']:
        """Filter badges that can be searched."""
        return self.active().filter(
            Q(name__icontains='') |
            Q(description__icontains='')
        )
    
    def by_points_range(self, min_points: int, max_points: int) -> QuerySet['Badge']:
        """Filter by points bonus range."""
        return self.filter(
            points_bonus__gte=min_points,
            points_bonus__lte=max_points
        )
    
    def ordered_by_popularity(self) -> QuerySet['Badge']:
        """Order by popularity (most awarded first)."""
        return self.with_user_count().order_by('-user_count', 'sort_order')
    
    def for_user_eligibility(self, user_points: int, streak_days: int = 0, 
                           achievement_count: int = 0, contest_wins: int = 0,
                           referral_count: int = 0) -> QuerySet['Badge']:
        """Get badges user is eligible for."""
        queryset = self.active()
        
        # Filter by criteria
        queryset = queryset.filter(
            Q(criteria_type=BadgeCriteriaType.POINTS_THRESHOLD, criteria_value__lte=user_points) |
            Q(criteria_type=BadgeCriteriaType.STREAK_DAYS, criteria_value__lte=streak_days) |
            Q(criteria_type=BadgeCriteriaType.ACHIEVEMENT_COUNT, criteria_value__lte=achievement_count) |
            Q(criteria_type=BadgeCriteriaType.CONTEST_WINS, criteria_value__lte=contest_wins) |
            Q(criteria_type=BadgeCriteriaType.REFERRAL_COUNT, criteria_value__lte=referral_count)
        )
        
        return queryset.distinct()


class UserBadgeQuerySet(models.QuerySet):
    """Custom QuerySet for UserBadge model."""
    
    def for_user(self, user_id: str) -> QuerySet['UserBadge']:
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def pinned(self) -> QuerySet['UserBadge']:
        """Filter pinned badges."""
        return self.filter(is_pinned=True)
    
    def by_badge(self, badge_id: str) -> QuerySet['UserBadge']:
        """Filter by badge."""
        return self.filter(badge_id=badge_id)
    
    def by_rarity(self, rarity: str) -> QuerySet['UserBadge']:
        """Filter by badge rarity."""
        return self.filter(badge__rarity=rarity)
    
    def recently_earned(self, days: int = 30) -> QuerySet['UserBadge']:
        """Filter recently earned badges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(earned_at__gte=since)
    
    def with_badge_details(self) -> QuerySet['UserBadge']:
        """Select related badge details."""
        return self.select_related('badge')
    
    def with_user_details(self) -> QuerySet['UserBadge']:
        """Select related user details."""
        return self.select_related('user')
    
    def for_user_with_details(self, user_id: str) -> QuerySet['UserBadge']:
        """Get user badges with all details."""
        return self.for_user(user_id).with_badge_details().order_by('-earned_at')
    
    def count_by_rarity(self) -> QuerySet['UserBadge']:
        """Count badges by rarity."""
        return self.values('badge__rarity').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def count_by_criteria_type(self) -> QuerySet['UserBadge']:
        """Count badges by criteria type."""
        return self.values('badge__criteria_type').annotate(
            count=Count('id')
        ).order_by('-count')


class DailyChallengeQuerySet(models.QuerySet):
    """Custom QuerySet for DailyChallenge model."""
    
    def active(self) -> QuerySet['DailyChallenge']:
        """Filter active challenges."""
        return self.filter(is_active=True)
    
    def for_date(self, challenge_date: date) -> QuerySet['DailyChallenge']:
        """Filter by specific date."""
        return self.filter(date=challenge_date)
    
    def for_date_range(self, start_date: date, end_date: date) -> QuerySet['DailyChallenge']:
        """Filter by date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)
    
    def by_action(self, action: str) -> QuerySet['DailyChallenge']:
        """Filter by action type."""
        return self.filter(target_action=action)
    
    def by_points_range(self, min_points: int, max_points: int) -> QuerySet['DailyChallenge']:
        """Filter by points bonus range."""
        return self.filter(
            bonus_points__gte=min_points,
            bonus_points__lte=max_points
        )
    
    def recent(self, days: int = 7) -> QuerySet['DailyChallenge']:
        """Get recent challenges."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=since)
    
    def upcoming(self, days: int = 7) -> QuerySet['DailyChallenge']:
        """Get upcoming challenges."""
        until = timezone.now().date() + timedelta(days=days)
        return self.filter(date__gt=timezone.now().date(), date__lte=until)
    
    def with_completion_stats(self) -> QuerySet['DailyChallenge']:
        """Annotate with completion statistics."""
        return self.annotate(
            total_participants=Count('userdailychallenge', distinct=True),
            completed_count=Count('userdailychallenge', filter=Q(userdailychallenge__is_completed=True)),
            completion_rate=models.ExpressionWrapper(
                models.F('completed_count') * 100.0 / models.F('total_participants'),
                output_field=models.FloatField()
            )
        )
    
    def popular(self) -> QuerySet['DailyChallenge']:
        """Get most popular challenges (by participation)."""
        return self.with_completion_stats().order_by('-total_participants')


class UserDailyChallengeQuerySet(models.QuerySet):
    """Custom QuerySet for UserDailyChallenge model."""
    
    def for_user(self, user_id: str) -> QuerySet['UserDailyChallenge']:
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def for_challenge(self, challenge_id: str) -> QuerySet['UserDailyChallenge']:
        """Filter by challenge."""
        return self.filter(challenge_id=challenge_id)
    
    def completed(self) -> QuerySet['UserDailyChallenge']:
        """Filter completed challenges."""
        return self.filter(is_completed=True)
    
    def in_progress(self) -> QuerySet['UserDailyChallenge']:
        """Filter challenges in progress."""
        return self.filter(is_completed=False)
    
    def for_date(self, challenge_date: date) -> QuerySet['UserDailyChallenge']:
        """Filter by challenge date."""
        return self.filter(challenge__date=challenge_date)
    
    def for_date_range(self, start_date: date, end_date: date) -> QuerySet['UserDailyChallenge']:
        """Filter by date range."""
        return self.filter(challenge__date__gte=start_date, challenge__date__lte=end_date)
    
    def by_action(self, action: str) -> QuerySet['UserDailyChallenge']:
        """Filter by action type."""
        return self.filter(challenge__target_action=action)
    
    def with_challenge_details(self) -> QuerySet['UserDailyChallenge']:
        """Select related challenge details."""
        return self.select_related('challenge')
    
    def with_user_details(self) -> QuerySet['UserDailyChallenge']:
        """Select related user details."""
        return self.select_related('user')
    
    def recently_completed(self, days: int = 7) -> QuerySet['UserDailyChallenge']:
        """Filter recently completed challenges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(is_completed=True, completed_at__gte=since)
    
    def with_progress_percentage(self) -> QuerySet['UserDailyChallenge']:
        """Annotate with progress percentage."""
        return self.annotate(
            progress_percentage=models.ExpressionWrapper(
                models.F('progress') * 100.0 / models.F('challenge__target_count'),
                output_field=models.FloatField()
            )
        )
    
    def for_user_with_details(self, user_id: str) -> QuerySet['UserDailyChallenge']:
        """Get user challenges with all details."""
        return self.for_user(user_id).with_challenge_details().order_by('-challenge__date')


class StreakQuerySet(models.QuerySet):
    """Custom QuerySet for Streak model."""
    
    def for_user(self, user_id: str) -> QuerySet['Streak']:
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def active(self) -> QuerySet['Streak']:
        """Filter active streaks."""
        return self.filter(is_active=True)
    
    def inactive(self) -> QuerySet['Streak']:
        """Filter inactive streaks."""
        return self.filter(is_active=False)
    
    def with_current_days(self, min_days: int) -> QuerySet['Streak']:
        """Filter by minimum current days."""
        return self.filter(current_days__gte=min_days)
    
    def with_longest_days(self, min_days: int) -> QuerySet['Streak']:
        """Filter by minimum longest days."""
        return self.filter(longest_days__gte=min_days)
    
    def recently_active(self, days: int = 7) -> QuerySet['Streak']:
        """Filter streaks with recent activity."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(last_activity_date__gte=since)
    
    def expiring_soon(self, days: int = 1) -> QuerySet['Streak']:
        """Filter streaks that will expire soon."""
        threshold_date = timezone.now().date() - timedelta(days=days)
        return self.filter(
            is_active=True,
            last_activity_date__lte=threshold_date
        )
    
    def with_user_details(self) -> QuerySet['Streak']:
        """Select related user details."""
        return self.select_related('user')
    
    def with_activity_stats(self) -> QuerySet['Streak']:
        """Annotate with activity statistics."""
        return self.annotate(
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
    
    def leaderboard(self, limit: int = 100) -> QuerySet['Streak']:
        """Get streak leaderboard."""
        return self.active().with_user_details().order_by('-current_days', '-longest_days')[:limit]
    
    def by_activity_range(self, start_date: date, end_date: date) -> QuerySet['Streak']:
        """Filter streaks with activity in date range."""
        return self.filter(
            last_activity_date__gte=start_date,
            last_activity_date__lte=end_date
        )


class LevelConfigQuerySet(models.QuerySet):
    """Custom QuerySet for LevelConfig model."""
    
    def active(self) -> QuerySet['LevelConfig']:
        """Filter active levels."""
        return self.filter(is_active=True)
    
    def by_level_range(self, min_level: int, max_level: int) -> QuerySet['LevelConfig']:
        """Filter by level range."""
        return self.filter(level_number__gte=min_level, level_number__lte=max_level)
    
    def by_points_range(self, min_points: int, max_points: int) -> QuerySet['LevelConfig']:
        """Filter by points required range."""
        return self.filter(
            points_required__gte=min_points,
            points_required__lte=max_points
        )
    
    def with_badge(self) -> QuerySet['LevelConfig']:
        """Filter levels that have associated badges."""
        return self.filter(badge__isnull=False)
    
    def without_badge(self) -> QuerySet['LevelConfig']:
        """Filter levels without associated badges."""
        return self.filter(badge__isnull=True)
    
    def with_user_count(self) -> QuerySet['LevelConfig']:
        """Annotate with user count at this level."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        return self.annotate(
            user_count=Count(
                'userachievement',
                filter=Q(userachievement__points_awarded__gte=F('points_required'))
            )
        )
    
    def ordered_by_level(self) -> QuerySet['LevelConfig']:
        """Order by level number."""
        return self.order_by('level_number')
    
    def max_level(self) -> QuerySet['LevelConfig']:
        """Get maximum level."""
        return self.active().order_by('-level_number').first()
    
    def for_points(self, points: int) -> QuerySet['LevelConfig']:
        """Get level for given points."""
        return self.active().filter(points_required__lte=points).order_by('-level_number')


class ContestCycleQuerySet(models.QuerySet):
    """Custom QuerySet for ContestCycle model."""
    
    def by_status(self, status: str) -> QuerySet['ContestCycle']:
        """Filter by status."""
        return self.filter(status=status)
    
    def active(self) -> QuerySet['ContestCycle']:
        """Filter active contests."""
        return self.filter(status=ContestCycleStatus.ACTIVE)
    
    def completed(self) -> QuerySet['ContestCycle']:
        """Filter completed contests."""
        return self.filter(status=ContestCycleStatus.COMPLETED)
    
    def upcoming(self) -> QuerySet['ContestCycle']:
        """Filter upcoming contests."""
        return self.filter(
            status=ContestCycleStatus.SCHEDULED,
            start_time__gt=timezone.now()
        )
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet['ContestCycle']:
        """Filter contests within date range."""
        return self.filter(
            start_time__gte=start_date,
            end_time__lte=end_date
        )
    
    def current(self) -> QuerySet['ContestCycle']:
        """Get current contest (active or most recent)."""
        return self.filter(
            Q(status=ContestCycleStatus.ACTIVE) |
            Q(status=ContestCycleStatus.COMPLETED)
        ).order_by('-start_time').first()
    
    def with_participant_count(self) -> QuerySet['ContestCycle']:
        """Annotate with participant count."""
        return self.annotate(
            participant_count=Count('userachievement__user', distinct=True)
        )
    
    def with_total_points_awarded(self) -> QuerySet['ContestCycle']:
        """Annotate with total points awarded."""
        return self.annotate(
            total_points_awarded=Sum('userachievement__points_awarded')
        )
    
    def with_completion_stats(self) -> QuerySet['ContestCycle']:
        """Annotate with completion statistics."""
        return self.annotate(
            participant_count=Count('userachievement__user', distinct=True),
            total_points_awarded=Sum('userachievement__points_awarded'),
            average_points=Avg('userachievement__points_awarded')
        )
    
    def recent(self, days: int = 30) -> QuerySet['ContestCycle']:
        """Get recent contests."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(start_time__gte=since)


class LeaderboardSnapshotQuerySet(models.QuerySet):
    """Custom QuerySet for LeaderboardSnapshot model."""
    
    def for_contest(self, contest_id: str) -> QuerySet['LeaderboardSnapshot']:
        """Filter by contest."""
        return self.filter(contest_cycle_id=contest_id)
    
    def by_scope(self, scope: str) -> QuerySet['LeaderboardSnapshot']:
        """Filter by scope."""
        return self.filter(scope=scope)
    
    def by_status(self, status: str) -> QuerySet['LeaderboardSnapshot']:
        """Filter by status."""
        return self.filter(status=status)
    
    def finalized(self) -> QuerySet['LeaderboardSnapshot']:
        """Filter finalized snapshots."""
        return self.filter(status=SnapshotStatus.FINALIZED)
    
    def recent(self, days: int = 7) -> QuerySet['LeaderboardSnapshot']:
        """Filter recent snapshots."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def with_contest_details(self) -> QuerySet['LeaderboardSnapshot']:
        """Select related contest details."""
        return self.select_related('contest_cycle')
    
    def with_entry_count(self) -> QuerySet['LeaderboardSnapshot']:
        """Annotate with entry count."""
        return self.annotate(
            entry_count=models.Func(
                models.F('snapshot_data'),
                function='json_array_length',
                output_field=models.IntegerField()
            )
        )
    
    def latest_for_contest(self, contest_id: str) -> QuerySet['LeaderboardSnapshot']:
        """Get latest snapshot for contest."""
        return self.for_contest(contest_id).order_by('-created_at').first()
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet['LeaderboardSnapshot']:
        """Filter snapshots within date range."""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )


class UserAchievementQuerySet(models.QuerySet):
    """Custom QuerySet for UserAchievement model."""
    
    def for_user(self, user_id: str) -> QuerySet['UserAchievement']:
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def for_contest(self, contest_id: str) -> QuerySet['UserAchievement']:
        """Filter by contest."""
        return self.filter(contest_cycle_id=contest_id)
    
    def awarded(self) -> QuerySet['UserAchievement']:
        """Filter awarded achievements."""
        return self.filter(is_awarded=True)
    
    def pending(self) -> QuerySet['UserAchievement']:
        """Filter pending achievements."""
        return self.filter(is_awarded=False)
    
    def by_type(self, achievement_type: str) -> QuerySet['UserAchievement']:
        """Filter by achievement type."""
        return self.filter(achievement_type=achievement_type)
    
    def by_points_range(self, min_points: int, max_points: int) -> QuerySet['UserAchievement']:
        """Filter by points range."""
        return self.filter(
            points_awarded__gte=min_points,
            points_awarded__lte=max_points
        )
    
    def by_rank_range(self, min_rank: int, max_rank: int) -> QuerySet['UserAchievement']:
        """Filter by rank range."""
        return self.filter(
            rank__gte=min_rank,
            rank__lte=max_rank
        )
    
    def recently_awarded(self, days: int = 30) -> QuerySet['UserAchievement']:
        """Filter recently awarded achievements."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(is_awarded=True, awarded_at__gte=since)
    
    def with_contest_details(self) -> QuerySet['UserAchievement']:
        """Select related contest details."""
        return self.select_related('contest_cycle')
    
    def with_user_details(self) -> QuerySet['UserAchievement']:
        """Select related user details."""
        return self.select_related('user')
    
    def leaderboard(self, contest_id: Optional[str] = None, limit: int = 100) -> QuerySet['UserAchievement']:
        """Get achievement leaderboard."""
        queryset = self.awarded()
        
        if contest_id:
            queryset = queryset.for_contest(contest_id)
        
        return queryset.with_user_details().order_by('-points_awarded', 'rank')[:limit]
    
    def for_user_with_details(self, user_id: str) -> QuerySet['UserAchievement']:
        """Get user achievements with all details."""
        return self.for_user(user_id).with_contest_details().order_by('-awarded_at')
    
    def with_total_points(self) -> QuerySet['UserAchievement']:
        """Annotate with total points for user."""
        return self.values('user_id').annotate(
            total_points=Sum('points_awarded'),
            achievement_count=Count('id')
        ).order_by('-total_points')


class WebhookEndpointQuerySet(models.QuerySet):
    """Custom QuerySet for WebhookEndpoint model."""
    
    def active(self) -> QuerySet['WebhookEndpoint']:
        """Filter active endpoints."""
        return self.filter(is_active=True)
    
    def inactive(self) -> QuerySet['WebhookEndpoint']:
        """Filter inactive endpoints."""
        return self.filter(is_active=False)
    
    def by_event_type(self, event_type: str) -> QuerySet['WebhookEndpoint']:
        """Filter by event type."""
        return self.filter(event_types__contains=[event_type])
    
    def with_delivery_stats(self) -> QuerySet['WebhookEndpoint']:
        """Annotate with delivery statistics."""
        return self.annotate(
            total_deliveries=Count('webhookdelivery'),
            successful_deliveries=Count(
                'webhookdelivery',
                filter=Q(webhookdelivery__status=WebhookStatus.SUCCESS)
            ),
            failed_deliveries=Count(
                'webhookdelivery',
                filter=Q(webhookdelivery__status=WebhookStatus.FAILED)
            )
        ).annotate(
            success_rate=models.ExpressionWrapper(
                models.F('successful_deliveries') * 100.0 / models.F('total_deliveries'),
                output_field=models.FloatField()
            )
        )
    
    def recent_deliveries(self, hours: int = 24) -> QuerySet['WebhookEndpoint']:
        """Filter endpoints with recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            webhookdelivery__created_at__gte=since
        ).distinct()


class WebhookEventQuerySet(models.QuerySet):
    """Custom QuerySet for WebhookEvent model."""
    
    def by_type(self, event_type: str) -> QuerySet['WebhookEvent']:
        """Filter by event type."""
        return self.filter(event_type=event_type)
    
    def for_user(self, user_id: str) -> QuerySet['WebhookEvent']:
        """Filter by user."""
        return self.filter(user_id=user_id)
    
    def recent(self, hours: int = 24) -> QuerySet['WebhookEvent']:
        """Filter recent events."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet['WebhookEvent']:
        """Filter events within date range."""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def with_delivery_count(self) -> QuerySet['WebhookEvent']:
        """Annotate with delivery count."""
        return self.annotate(
            delivery_count=Count('webhookdelivery')
        )
    
    def undelivered(self) -> QuerySet['WebhookEvent']:
        """Filter events that haven't been delivered."""
        return self.filter(webhookdelivery__isnull=True)


class WebhookDeliveryQuerySet(models.QuerySet):
    """Custom QuerySet for WebhookDelivery model."""
    
    def by_status(self, status: str) -> QuerySet['WebhookDelivery']:
        """Filter by status."""
        return self.filter(status=status)
    
    def successful(self) -> QuerySet['WebhookDelivery']:
        """Filter successful deliveries."""
        return self.filter(status=WebhookStatus.SUCCESS)
    
    def failed(self) -> QuerySet['WebhookDelivery']:
        """Filter failed deliveries."""
        return self.filter(status=WebhookStatus.FAILED)
    
    def retrying(self) -> QuerySet['WebhookDelivery']:
        """Filter deliveries pending retry."""
        return self.filter(status=WebhookStatus.RETRY)
    
    def pending(self) -> QuerySet['WebhookDelivery']:
        """Filter pending deliveries."""
        return self.filter(status=WebhookStatus.PENDING)
    
    def for_webhook(self, webhook_id: str) -> QuerySet['WebhookDelivery']:
        """Filter by webhook."""
        return self.filter(webhook_id=webhook_id)
    
    def for_event(self, event_id: str) -> QuerySet['WebhookDelivery']:
        """Filter by event."""
        return self.filter(event_id=event_id)
    
    def recent(self, hours: int = 24) -> QuerySet['WebhookDelivery']:
        """Filter recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def with_details(self) -> QuerySet['WebhookDelivery']:
        """Select related details."""
        return self.select_related('webhook', 'event')
    
    def by_attempt_count(self, min_attempts: int, max_attempts: Optional[int] = None) -> QuerySet['WebhookDelivery']:
        """Filter by attempt count."""
        queryset = self.filter(attempts__gte=min_attempts)
        if max_attempts is not None:
            queryset = queryset.filter(attempts__lte=max_attempts)
        return queryset
    
    def scheduled_for_retry(self) -> QuerySet['WebhookDelivery']:
        """Filter deliveries scheduled for retry."""
        return self.filter(
            status=WebhookStatus.RETRY,
            scheduled_at__lte=timezone.now()
        )


# Custom managers using the querysets
class BadgeManager(models.Manager):
    """Custom manager for Badge model."""
    
    def get_queryset(self) -> BadgeQuerySet:
        return BadgeQuerySet(self.model, using=self._db)
    
    def active(self) -> BadgeQuerySet:
        return self.get_queryset().active()
    
    def by_rarity(self, rarity: str) -> BadgeQuerySet:
        return self.get_queryset().by_rarity(rarity)
    
    def with_user_count(self) -> BadgeQuerySet:
        return self.get_queryset().with_user_count()
    
    def for_user_eligibility(self, user_points: int, streak_days: int = 0,
                           achievement_count: int = 0, contest_wins: int = 0,
                           referral_count: int = 0) -> BadgeQuerySet:
        return self.get_queryset().for_user_eligibility(
            user_points, streak_days, achievement_count, contest_wins, referral_count
        )


class UserBadgeManager(models.Manager):
    """Custom manager for UserBadge model."""
    
    def get_queryset(self) -> UserBadgeQuerySet:
        return UserBadgeQuerySet(self.model, using=self._db)
    
    def for_user(self, user_id: str) -> UserBadgeQuerySet:
        return self.get_queryset().for_user(user_id)
    
    def pinned(self) -> UserBadgeQuerySet:
        return self.get_queryset().pinned()
    
    def recently_earned(self, days: int = 30) -> UserBadgeQuerySet:
        return self.get_queryset().recently_earned(days)


class DailyChallengeManager(models.Manager):
    """Custom manager for DailyChallenge model."""
    
    def get_queryset(self) -> DailyChallengeQuerySet:
        return DailyChallengeQuerySet(self.model, using=self._db)
    
    def active(self) -> DailyChallengeQuerySet:
        return self.get_queryset().active()
    
    def for_date(self, challenge_date: date) -> DailyChallengeQuerySet:
        return self.get_queryset().for_date(challenge_date)
    
    def recent(self, days: int = 7) -> DailyChallengeQuerySet:
        return self.get_queryset().recent(days)


class UserDailyChallengeManager(models.Manager):
    """Custom manager for UserDailyChallenge model."""
    
    def get_queryset(self) -> UserDailyChallengeQuerySet:
        return UserDailyChallengeQuerySet(self.model, using=self._db)
    
    def for_user(self, user_id: str) -> UserDailyChallengeQuerySet:
        return self.get_queryset().for_user(user_id)
    
    def completed(self) -> UserDailyChallengeQuerySet:
        return self.get_queryset().completed()
    
    def for_user_with_details(self, user_id: str) -> UserDailyChallengeQuerySet:
        return self.get_queryset().for_user_with_details(user_id)


class StreakManager(models.Manager):
    """Custom manager for Streak model."""
    
    def get_queryset(self) -> StreakQuerySet:
        return StreakQuerySet(self.model, using=self._db)
    
    def active(self) -> StreakQuerySet:
        return self.get_queryset().active()
    
    def expiring_soon(self, days: int = 1) -> StreakQuerySet:
        return self.get_queryset().expiring_soon(days)
    
    def leaderboard(self, limit: int = 100) -> StreakQuerySet:
        return self.get_queryset().leaderboard(limit)


class LevelConfigManager(models.Manager):
    """Custom manager for LevelConfig model."""
    
    def get_queryset(self) -> LevelConfigQuerySet:
        return LevelConfigQuerySet(self.model, using=self._db)
    
    def active(self) -> LevelConfigQuerySet:
        return self.get_queryset().active()
    
    def for_points(self, points: int) -> LevelConfigQuerySet:
        return self.get_queryset().for_points(points)
    
    def max_level(self) -> LevelConfigQuerySet:
        return self.get_queryset().max_level()


class ContestCycleManager(models.Manager):
    """Custom manager for ContestCycle model."""
    
    def get_queryset(self) -> ContestCycleQuerySet:
        return ContestCycleQuerySet(self.model, using=self._db)
    
    def active(self) -> ContestCycleQuerySet:
        return self.get_queryset().active()
    
    def completed(self) -> ContestCycleQuerySet:
        return self.get_queryset().completed()
    
    def current(self) -> ContestCycleQuerySet:
        return self.get_queryset().current()


class UserAchievementManager(models.Manager):
    """Custom manager for UserAchievement model."""
    
    def get_queryset(self) -> UserAchievementQuerySet:
        return UserAchievementQuerySet(self.model, using=self._db)
    
    def for_user(self, user_id: str) -> UserAchievementQuerySet:
        return self.get_queryset().for_user(user_id)
    
    def awarded(self) -> UserAchievementQuerySet:
        return self.get_queryset().awarded()
    
    def leaderboard(self, contest_id: Optional[str] = None, limit: int = 100) -> UserAchievementQuerySet:
        return self.get_queryset().leaderboard(contest_id, limit)


class WebhookEndpointManager(models.Manager):
    """Custom manager for WebhookEndpoint model."""
    
    def get_queryset(self) -> WebhookEndpointQuerySet:
        return WebhookEndpointQuerySet(self.model, using=self._db)
    
    def active(self) -> WebhookEndpointQuerySet:
        return self.get_queryset().active()
    
    def with_delivery_stats(self) -> WebhookEndpointQuerySet:
        return self.get_queryset().with_delivery_stats()


class WebhookDeliveryManager(models.Manager):
    """Custom manager for WebhookDelivery model."""
    
    def get_queryset(self) -> WebhookDeliveryQuerySet:
        return WebhookDeliveryQuerySet(self.model, using=self._db)
    
    def successful(self) -> WebhookDeliveryQuerySet:
        return self.get_queryset().successful()
    
    def failed(self) -> WebhookDeliveryQuerySet:
        return self.get_queryset().failed()
    
    def scheduled_for_retry(self) -> WebhookDeliveryQuerySet:
        return self.get_queryset().scheduled_for_retry()
