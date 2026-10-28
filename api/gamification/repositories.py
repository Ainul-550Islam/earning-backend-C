"""
Gamification Repositories — Data access layer for gamification system.

This module provides repository classes that encapsulate data access logic
for gamification models, following the Repository pattern for clean
separation of concerns and testability.
"""

from __future__ import annotations
from django.db.models import BooleanField
from django.db.models import ExpressionWrapper
from django.db.models import FloatField
from django.db.models import IntegerField

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Q, F, Func, Value, Case, When, Sum, Count, Avg, Max, Min
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
from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository class with common functionality."""
    
    def __init__(self, model_class: type):
        self.model_class = model_class
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache_timeout = 300  # 5 minutes default cache timeout
    
    def get_by_id(self, id: str) -> Optional[models.Model]:
        """Get model instance by ID."""
        try:
            return self.model_class.objects.get(id=id)
        except self.model_class.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting {self.model_class.__name__} by ID {id}: {e}")
            raise GamificationServiceError(f"Failed to get {self.model_class.__name__}: {e}")
    
    def get_by_ids(self, ids: List[str]) -> List[models.Model]:
        """Get model instances by list of IDs."""
        try:
            return list(self.model_class.objects.filter(id__in=ids))
        except Exception as e:
            self.logger.error(f"Error getting {self.model_class.__name__} by IDs {ids}: {e}")
            raise GamificationServiceError(f"Failed to get {self.model_class.__name__}s: {e}")
    
    def create(self, **kwargs) -> models.Model:
        """Create new model instance."""
        try:
            return self.model_class.objects.create(**kwargs)
        except Exception as e:
            self.logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise GamificationServiceError(f"Failed to create {self.model_class.__name__}: {e}")
    
    def update(self, id: str, **kwargs) -> Optional[models.Model]:
        """Update model instance by ID."""
        try:
            instance = self.get_by_id(id)
            if instance:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
                instance.save()
                return instance
            return None
        except Exception as e:
            self.logger.error(f"Error updating {self.model_class.__name__} {id}: {e}")
            raise GamificationServiceError(f"Failed to update {self.model_class.__name__}: {e}")
    
    def delete(self, id: str) -> bool:
        """Delete model instance by ID."""
        try:
            instance = self.get_by_id(id)
            if instance:
                instance.delete()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            raise GamificationServiceError(f"Failed to delete {self.model_class.__name__}: {e}")
    
    def exists(self, **kwargs) -> bool:
        """Check if instance exists with given criteria."""
        try:
            return self.model_class.objects.filter(**kwargs).exists()
        except Exception as e:
            self.logger.error(f"Error checking {self.model_class.__name__} existence: {e}")
            raise GamificationServiceError(f"Failed to check {self.model_class.__name__} existence: {e}")
    
    def count(self, **kwargs) -> int:
        """Count instances with given criteria."""
        try:
            return self.model_class.objects.filter(**kwargs).count()
        except Exception as e:
            self.logger.error(f"Error counting {self.model_class.__name__}s: {e}")
            raise GamificationServiceError(f"Failed to count {self.model_class.__name__}s: {e}")
    
    def get_queryset(self):
        """Get base queryset."""
        return self.model_class.objects.all()
    
    def filter(self, **kwargs) -> models.QuerySet:
        """Filter instances."""
        return self.get_queryset().filter(**kwargs)
    
    def exclude(self, **kwargs) -> models.QuerySet:
        """Exclude instances."""
        return self.get_queryset().exclude(**kwargs)
    
    def all(self) -> models.QuerySet:
        """Get all instances."""
        return self.get_queryset()
    
    def bulk_create(self, instances: List[models.Model]) -> List[models.Model]:
        """Bulk create instances."""
        try:
            return self.model_class.objects.bulk_create(instances)
        except Exception as e:
            self.logger.error(f"Error bulk creating {self.model_class.__name__}s: {e}")
            raise GamificationServiceError(f"Failed to bulk create {self.model_class.__name__}s: {e}")
    
    def bulk_update(self, instances: List[models.Model], fields: List[str]) -> int:
        """Bulk update instances."""
        try:
            return self.model_class.objects.bulk_update(instances, fields)
        except Exception as e:
            self.logger.error(f"Error bulk updating {self.model_class.__name__}s: {e}")
            raise GamificationServiceError(f"Failed to bulk update {self.model_class.__name__}s: {e}")
    
    def bulk_delete(self, ids: List[str]) -> int:
        """Bulk delete instances by IDs."""
        try:
            return self.model_class.objects.filter(id__in=ids).delete()[0]
        except Exception as e:
            self.logger.error(f"Error bulk deleting {self.model_class.__name__}s: {e}")
            raise GamificationServiceError(f"Failed to bulk delete {self.model_class.__name__}s: {e}")


class BadgeRepository(BaseRepository):
    """Repository for Badge model."""
    
    def __init__(self):
        super().__init__(Badge)
    
    def get_active_badges(self) -> models.QuerySet:
        """Get active badges."""
        return self.filter(is_active=True)
    
    def get_by_rarity(self, rarity: str) -> models.QuerySet:
        """Get badges by rarity."""
        return self.filter(rarity=rarity)
    
    def get_by_criteria_type(self, criteria_type: str) -> models.QuerySet:
        """Get badges by criteria type."""
        return self.filter(criteria_type=criteria_type)
    
    def get_by_points_range(self, min_points: int, max_points: int) -> models.QuerySet:
        """Get badges by points bonus range."""
        return self.filter(points_bonus__gte=min_points, points_bonus__lte=max_points)
    
    def get_eligible_badges_for_user(self, user_points: int, streak_days: int = 0,
                                   achievement_count: int = 0, contest_wins: int = 0,
                                   referral_count: int = 0) -> models.QuerySet:
        """Get badges user is eligible for."""
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
        
        return self.filter(eligibility_conditions, is_active=True)
    
    def get_with_user_count(self) -> models.QuerySet:
        """Get badges with user count annotation."""
        return self.get_queryset().annotate(
            user_count=Count('userbadge', distinct=True)
        )
    
    def get_with_award_rate(self) -> models.QuerySet:
        """Get badges with award rate annotation."""
        total_users = User.objects.count()
        if total_users == 0:
            return self.annotate(award_rate=Value(0.0))
        
        return self.get_queryset().annotate(
            user_count=Count('userbadge', distinct=True)
        ).annotate(
            award_rate=ExpressionWrapper(
                F('user_count') * 100.0 / total_users,
                output_field=FloatField()
            )
        )
    
    def get_popular_badges(self, limit: int = 10) -> models.QuerySet:
        """Get most popular badges."""
        return self.get_with_user_count().order_by('-user_count')[:limit]
    
    def get_recently_created(self, days: int = 30) -> models.QuerySet:
        """Get recently created badges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)


class UserBadgeRepository(BaseRepository):
    """Repository for UserBadge model."""
    
    def __init__(self):
        super().__init__(UserBadge)
    
    def get_for_user(self, user_id: str) -> models.QuerySet:
        """Get badges for specific user."""
        return self.filter(user_id=user_id)
    
    def get_pinned_badges(self, user_id: str) -> models.QuerySet:
        """Get pinned badges for user."""
        return self.filter(user_id=user_id, is_pinned=True)
    
    def get_by_badge(self, badge_id: str) -> models.QuerySet:
        """Get user badges by badge ID."""
        return self.filter(badge_id=badge_id)
    
    def get_by_rarity(self, user_id: str, rarity: str) -> models.QuerySet:
        """Get user badges by rarity."""
        return self.filter(user_id=user_id, badge__rarity=rarity)
    
    def get_recently_earned(self, user_id: str, days: int = 30) -> models.QuerySet:
        """Get recently earned badges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(user_id=user_id, earned_at__gte=since)
    
    def get_with_badge_details(self, user_id: str) -> models.QuerySet:
        """Get user badges with badge details."""
        return self.get_for_user(user_id).select_related('badge')
    
    def get_user_badge_count(self, user_id: str) -> int:
        """Get total badge count for user."""
        return self.count(user_id=user_id)
    
    def get_user_badge_count_by_rarity(self, user_id: str) -> Dict[str, int]:
        """Get badge count by rarity for user."""
        return dict(
            self.get_for_user(user_id)
            .values('badge__rarity')
            .annotate(count=Count('id'))
            .values_list('badge__rarity', 'count')
        )
    
    def check_user_has_badge(self, user_id: str, badge_id: str) -> bool:
        """Check if user has specific badge."""
        return self.exists(user_id=user_id, badge_id=badge_id)
    
    def get_user_badges_with_progress(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user badges with eligibility progress."""
        user_badges = self.get_with_badge_details(user_id)
        
        result = []
        for user_badge in user_badges:
            result.append({
                'id': str(user_badge.id),
                'badge_id': str(user_badge.badge.id),
                'badge_name': user_badge.badge.name,
                'badge_description': user_badge.badge.description,
                'badge_icon': user_badge.badge.icon,
                'badge_rarity': user_badge.badge.rarity,
                'badge_points_bonus': user_badge.badge.points_bonus,
                'is_pinned': user_badge.is_pinned,
                'earned_at': user_badge.earned_at.isoformat(),
                'metadata': user_badge.metadata or {}
            })
        
        return result


class DailyChallengeRepository(BaseRepository):
    """Repository for DailyChallenge model."""
    
    def __init__(self):
        super().__init__(DailyChallenge)
    
    def get_active_challenges(self) -> models.QuerySet:
        """Get active challenges."""
        return self.filter(is_active=True)
    
    def get_for_date(self, challenge_date: datetime.date) -> models.QuerySet:
        """Get challenges for specific date."""
        return self.filter(date=challenge_date)
    
    def get_for_date_range(self, start_date: datetime.date, end_date: datetime.date) -> models.QuerySet:
        """Get challenges within date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)
    
    def get_by_action(self, action: str) -> models.QuerySet:
        """Get challenges by action type."""
        return self.filter(target_action=action)
    
    def get_by_points_range(self, min_points: int, max_points: int) -> models.QuerySet:
        """Get challenges by points bonus range."""
        return self.filter(bonus_points__gte=min_points, bonus_points__lte=max_points)
    
    def get_recent_challenges(self, days: int = 7) -> models.QuerySet:
        """Get recent challenges."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=since)
    
    def get_upcoming_challenges(self, days: int = 7) -> models.QuerySet:
        """Get upcoming challenges."""
        until = timezone.now().date() + timedelta(days=days)
        return self.filter(date__gt=timezone.now().date(), date__lte=until)
    
    def get_with_completion_stats(self) -> models.QuerySet:
        """Get challenges with completion statistics."""
        return self.get_queryset().annotate(
            total_participants=Count('userdailychallenge', distinct=True),
            completed_count=Count(
                'userdailychallenge',
                filter=Q(userdailychallenge__is_completed=True)
            ),
            completion_rate=ExpressionWrapper(
                F('completed_count') * 100.0 / F('total_participants'),
                output_field=FloatField()
            )
        )
    
    def get_popular_challenges(self, limit: int = 10) -> models.QuerySet:
        """Get most popular challenges."""
        return self.get_with_completion_stats().order_by('-total_participants')[:limit]


class UserDailyChallengeRepository(BaseRepository):
    """Repository for UserDailyChallenge model."""
    
    def __init__(self):
        super().__init__(UserDailyChallenge)
    
    def get_for_user(self, user_id: str) -> models.QuerySet:
        """Get challenges for specific user."""
        return self.filter(user_id=user_id)
    
    def get_for_challenge(self, challenge_id: str) -> models.QuerySet:
        """Get user challenges by challenge ID."""
        return self.filter(challenge_id=challenge_id)
    
    def get_completed_challenges(self, user_id: str) -> models.QuerySet:
        """Get completed challenges for user."""
        return self.filter(user_id=user_id, is_completed=True)
    
    def get_in_progress_challenges(self, user_id: str) -> models.QuerySet:
        """Get in-progress challenges for user."""
        return self.filter(user_id=user_id, is_completed=False)
    
    def get_for_date(self, user_id: str, challenge_date: datetime.date) -> models.QuerySet:
        """Get user challenges for specific date."""
        return self.filter(user_id=user_id, challenge__date=challenge_date)
    
    def get_for_date_range(self, user_id: str, start_date: datetime.date, end_date: datetime.date) -> models.QuerySet:
        """Get user challenges within date range."""
        return self.filter(
            user_id=user_id,
            challenge__date__gte=start_date,
            challenge__date__lte=end_date
        )
    
    def get_by_action(self, user_id: str, action: str) -> models.QuerySet:
        """Get user challenges by action type."""
        return self.filter(user_id=user_id, challenge__target_action=action)
    
    def get_with_challenge_details(self, user_id: str) -> models.QuerySet:
        """Get user challenges with challenge details."""
        return self.get_for_user(user_id).select_related('challenge')
    
    def get_recently_completed(self, user_id: str, days: int = 7) -> models.QuerySet:
        """Get recently completed challenges."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(user_id=user_id, is_completed=True, completed_at__gte=since)
    
    def get_user_challenge_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get challenge statistics for user."""
        since = timezone.now().date() - timedelta(days=days)
        
        user_challenges = self.get_for_date_range(user_id, since, timezone.now().date())
        
        total_challenges = user_challenges.count()
        completed_challenges = user_challenges.filter(is_completed=True).count()
        
        # Action type distribution
        action_distribution = dict(
            user_challenges.values('challenge__target_action')
            .annotate(count=Count('id'))
            .values_list('challenge__target_action', 'count')
        )
        
        # Total bonus points
        total_bonus_points = (
            user_challenges.filter(is_completed=True)
            .aggregate(total=Sum('challenge__bonus_points'))['total'] or 0
        )
        
        return {
            'total_challenges': total_challenges,
            'completed_challenges': completed_challenges,
            'completion_rate': (completed_challenges / total_challenges * 100) if total_challenges > 0 else 0,
            'total_bonus_points': total_bonus_points,
            'action_distribution': action_distribution,
        }


class StreakRepository(BaseRepository):
    """Repository for Streak model."""
    
    def __init__(self):
        super().__init__(Streak)
    
    def get_for_user(self, user_id: str) -> Optional[Streak]:
        """Get streak for specific user."""
        return self.filter(user_id=user_id).first()
    
    def get_active_streaks(self) -> models.QuerySet:
        """Get active streaks."""
        return self.filter(is_active=True)
    
    def get_inactive_streaks(self) -> models.QuerySet:
        """Get inactive streaks."""
        return self.filter(is_active=False)
    
    def get_by_current_days(self, min_days: int) -> models.QuerySet:
        """Get streaks with minimum current days."""
        return self.filter(current_days__gte=min_days)
    
    def get_by_longest_days(self, min_days: int) -> models.QuerySet:
        """Get streaks with minimum longest days."""
        return self.filter(longest_days__gte=min_days)
    
    def get_recently_active(self, days: int = 7) -> models.QuerySet:
        """Get streaks with recent activity."""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(last_activity_date__gte=since)
    
    def get_expiring_soon(self, days: int = 1) -> models.QuerySet:
        """Get streaks that will expire soon."""
        threshold_date = timezone.now().date() - timedelta(days=days)
        return self.filter(is_active=True, last_activity_date__lte=threshold_date)
    
    def get_with_user_details(self) -> models.QuerySet:
        """Get streaks with user details."""
        return self.get_queryset().select_related('user')
    
    def get_with_activity_stats(self) -> models.QuerySet:
        """Get streaks with activity statistics."""
        return self.get_queryset().annotate(
            days_until_reset=ExpressionWrapper(
                F('last_activity_date') + timedelta(days=1) - timezone.now().date(),
                output_field=IntegerField()
            ),
            is_expired=Case(
                When(
                    last_activity_date__lt=timezone.now().date() - timedelta(days=1),
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )
    
    def get_leaderboard(self, limit: int = 100) -> models.QuerySet:
        """Get streak leaderboard."""
        return (
            self.get_active_streaks()
            .with_user_details()
            .order_by('-current_days', '-longest_days')[:limit]
        )
    
    def create_or_update_streak(self, user_id: str, current_days: int, longest_days: int,
                             last_activity_date: datetime.date, is_active: bool = True) -> Streak:
        """Create or update user streak."""
        streak = self.get_for_user(user_id)
        
        if streak:
            streak.current_days = current_days
            streak.longest_days = max(longest_days, streak.longest_days)
            streak.last_activity_date = last_activity_date
            streak.is_active = is_active
            streak.save()
            return streak
        else:
            return self.create(
                user_id=user_id,
                current_days=current_days,
                longest_days=longest_days,
                last_activity_date=last_activity_date,
                is_active=is_active
            )


class LevelConfigRepository(BaseRepository):
    """Repository for LevelConfig model."""
    
    def __init__(self):
        super().__init__(LevelConfig)
    
    def get_active_levels(self) -> models.QuerySet:
        """Get active levels."""
        return self.filter(is_active=True)
    
    def get_by_level_range(self, min_level: int, max_level: int) -> models.QuerySet:
        """Get levels within range."""
        return self.filter(level_number__gte=min_level, level_number__lte=max_level)
    
    def get_by_points_range(self, min_points: int, max_points: int) -> models.QuerySet:
        """Get levels by points required range."""
        return self.filter(points_required__gte=min_points, points_required__lte=max_points)
    
    def get_with_badge(self) -> models.QuerySet:
        """Get levels that have associated badges."""
        return self.filter(badge__isnull=False)
    
    def get_without_badge(self) -> models.QuerySet:
        """Get levels without associated badges."""
        return self.filter(badge__isnull=True)
    
    def get_with_user_count(self) -> models.QuerySet:
        """Get levels with user count annotation."""
        return self.get_queryset().annotate(
            user_count=Count(
                'userachievement',
                filter=Q(userachievement__points_awarded__gte=F('points_required'))
            )
        )
    
    def get_for_points(self, points: int) -> Optional[LevelConfig]:
        """Get level for given points."""
        return (
            self.get_active_levels()
            .filter(points_required__lte=points)
            .order_by('-level_number')
            .first()
        )
    
    def get_max_level(self) -> Optional[LevelConfig]:
        """Get maximum active level."""
        return self.get_active_levels().order_by('-level_number').first()
    
    def get_level_progress(self, points: int) -> Dict[str, Any]:
        """Get level progress for given points."""
        current_level = self.get_for_points(points)
        
        if not current_level:
            return {
                'current_level': 0,
                'points_to_next_level': 0,
                'progress_percentage': 0,
                'points_in_current_level': points,
                'is_max_level': True,
            }
        
        # Get next level
        next_level = (
            self.get_active_levels()
            .filter(level_number=current_level.level_number + 1)
            .first()
        )
        
        if not next_level:
            return {
                'current_level': current_level.level_number,
                'points_to_next_level': 0,
                'progress_percentage': 100,
                'points_in_current_level': points - current_level.points_required,
                'is_max_level': True,
            }
        
        points_in_current_level = points - current_level.points_required
        points_to_next_level = next_level.points_required - points
        points_needed_for_next_level = next_level.points_required - current_level.points_required
        
        progress_percentage = (points_in_current_level / points_needed_for_next_level) * 100
        
        return {
            'current_level': current_level.level_number,
            'current_level_title': current_level.title,
            'points_to_next_level': max(0, points_to_next_level),
            'progress_percentage': min(100, progress_percentage),
            'points_in_current_level': points_in_current_level,
            'points_needed_for_next_level': points_needed_for_next_level,
            'next_level_title': next_level.title,
            'points_multiplier': current_level.points_multiplier,
            'is_max_level': False,
        }


class ContestCycleRepository(BaseRepository):
    """Repository for ContestCycle model."""
    
    def __init__(self):
        super().__init__(ContestCycle)
    
    def get_by_status(self, status: str) -> models.QuerySet:
        """Get contests by status."""
        return self.filter(status=status)
    
    def get_active_contests(self) -> models.QuerySet:
        """Get active contests."""
        return self.filter(status=ContestCycleStatus.ACTIVE)
    
    def get_completed_contests(self) -> models.QuerySet:
        """Get completed contests."""
        return self.filter(status=ContestCycleStatus.COMPLETED)
    
    def get_upcoming_contests(self) -> models.QuerySet:
        """Get upcoming contests."""
        return self.filter(
            status=ContestCycleStatus.SCHEDULED,
            start_time__gt=timezone.now()
        )
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> models.QuerySet:
        """Get contests within date range."""
        return self.filter(
            start_time__gte=start_date,
            end_time__lte=end_date
        )
    
    def get_current_contest(self) -> Optional[ContestCycle]:
        """Get current contest."""
        return (
            self.filter(
                Q(status=ContestCycleStatus.ACTIVE) |
                Q(status=ContestCycleStatus.COMPLETED)
            )
            .order_by('-start_time')
            .first()
        )
    
    def get_with_participant_count(self) -> models.QuerySet:
        """Get contests with participant count."""
        return self.get_queryset().annotate(
            participant_count=Count('userachievement__user', distinct=True)
        )
    
    def get_with_total_points_awarded(self) -> models.QuerySet:
        """Get contests with total points awarded."""
        return self.get_queryset().annotate(
            total_points_awarded=Sum('userachievement__points_awarded')
        )
    
    def get_with_completion_stats(self) -> models.QuerySet:
        """Get contests with completion statistics."""
        return self.get_queryset().annotate(
            participant_count=Count('userachievement__user', distinct=True),
            total_points_awarded=Sum('userachievement__points_awarded'),
            average_points=Avg('userachievement__points_awarded')
        )
    
    def get_recent_contests(self, days: int = 30) -> models.QuerySet:
        """Get recent contests."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(start_time__gte=since)


class UserAchievementRepository(BaseRepository):
    """Repository for UserAchievement model."""
    
    def __init__(self):
        super().__init__(UserAchievement)
    
    def get_for_user(self, user_id: str) -> models.QuerySet:
        """Get achievements for specific user."""
        return self.filter(user_id=user_id)
    
    def get_for_contest(self, contest_id: str) -> models.QuerySet:
        """Get achievements for specific contest."""
        return self.filter(contest_cycle_id=contest_id)
    
    def get_awarded_achievements(self) -> models.QuerySet:
        """Get awarded achievements."""
        return self.filter(is_awarded=True)
    
    def get_pending_achievements(self) -> models.QuerySet:
        """Get pending achievements."""
        return self.filter(is_awarded=False)
    
    def get_by_type(self, achievement_type: str) -> models.QuerySet:
        """Get achievements by type."""
        return self.filter(achievement_type=achievement_type)
    
    def get_by_points_range(self, min_points: int, max_points: int) -> models.QuerySet:
        """Get achievements by points range."""
        return self.filter(points_awarded__gte=min_points, points_awarded__lte=max_points)
    
    def get_by_rank_range(self, min_rank: int, max_rank: int) -> models.QuerySet:
        """Get achievements by rank range."""
        return self.filter(rank__gte=min_rank, rank__lte=max_rank)
    
    def get_recently_awarded(self, days: int = 30) -> models.QuerySet:
        """Get recently awarded achievements."""
        since = timezone.now() - timedelta(days=days)
        return self.filter(is_awarded=True, awarded_at__gte=since)
    
    def get_with_contest_details(self) -> models.QuerySet:
        """Get achievements with contest details."""
        return self.get_queryset().select_related('contest_cycle')
    
    def get_with_user_details(self) -> models.QuerySet:
        """Get achievements with user details."""
        return self.get_queryset().select_related('user')
    
    def get_leaderboard(self, contest_id: Optional[str] = None, limit: int = 100) -> models.QuerySet:
        """Get achievement leaderboard."""
        queryset = self.get_awarded_achievements()
        
        if contest_id:
            queryset = queryset.for_contest(contest_id)
        
        return queryset.with_user_details().order_by('-points_awarded', 'rank')[:limit]
    
    def get_user_total_points(self, user_id: str) -> int:
        """Get total points for user."""
        result = (
            self.get_for_user(user_id)
            .get_awarded_achievements()
            .aggregate(total=Sum('points_awarded'))
        )
        return result['total'] or 0
    
    def get_user_achievement_count(self, user_id: str) -> int:
        """Get achievement count for user."""
        return self.get_for_user(user_id).get_awarded_achievements().count()
    
    def get_user_ranking_data(self, user_id: str) -> Dict[str, Any]:
        """Get user's ranking data."""
        total_points = self.get_user_total_points(user_id)
        achievement_count = self.get_user_achievement_count(user_id)
        
        # Get global ranking
        global_ranking = (
            self.get_awarded_achievements()
            .values('user_id')
            .annotate(total_points=Sum('points_awarded'))
            .order_by('-total_points')
        )
        
        user_rank = None
        for rank, data in enumerate(global_ranking, 1):
            if str(data['user_id']) == user_id:
                user_rank = rank
                break
        
        return {
            'total_points': total_points,
            'achievement_count': achievement_count,
            'global_rank': user_rank,
            'total_users': global_ranking.count(),
            'percentile': (user_rank / global_ranking.count() * 100) if user_rank else None,
        }


class WebhookEndpointRepository(BaseRepository):
    """Repository for WebhookEndpoint model."""
    
    def __init__(self):
        super().__init__(WebhookEndpoint)
    
    def get_active_endpoints(self) -> models.QuerySet:
        """Get active endpoints."""
        return self.filter(is_active=True)
    
    def get_inactive_endpoints(self) -> models.QuerySet:
        """Get inactive endpoints."""
        return self.filter(is_active=False)
    
    def get_by_event_type(self, event_type: str) -> models.QuerySet:
        """Get endpoints that handle specific event type."""
        return self.filter(event_types__contains=[event_type])
    
    def get_with_delivery_stats(self) -> models.QuerySet:
        """Get endpoints with delivery statistics."""
        return self.get_queryset().annotate(
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
            success_rate=ExpressionWrapper(
                F('successful_deliveries') * 100.0 / F('total_deliveries'),
                output_field=FloatField()
            )
        )
    
    def get_recent_deliveries(self, hours: int = 24) -> models.QuerySet:
        """Get endpoints with recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            webhookdelivery__created_at__gte=since
        ).distinct()


class WebhookEventRepository(BaseRepository):
    """Repository for WebhookEvent model."""
    
    def __init__(self):
        super().__init__(WebhookEvent)
    
    def get_by_type(self, event_type: str) -> models.QuerySet:
        """Get events by type."""
        return self.filter(event_type=event_type)
    
    def get_for_user(self, user_id: str) -> models.QuerySet:
        """Get events for specific user."""
        return self.filter(user_id=user_id)
    
    def get_recent_events(self, hours: int = 24) -> models.QuerySet:
        """Get recent events."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> models.QuerySet:
        """Get events within date range."""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def get_with_delivery_count(self) -> models.QuerySet:
        """Get events with delivery count."""
        return self.get_queryset().annotate(
            delivery_count=Count('webhookdelivery')
        )
    
    def get_undelivered_events(self) -> models.QuerySet:
        """Get events that haven't been delivered."""
        return self.filter(webhookdelivery__isnull=True)


class WebhookDeliveryRepository(BaseRepository):
    """Repository for WebhookDelivery model."""
    
    def __init__(self):
        super().__init__(WebhookDelivery)
    
    def get_by_status(self, status: str) -> models.QuerySet:
        """Get deliveries by status."""
        return self.filter(status=status)
    
    def get_successful_deliveries(self) -> models.QuerySet:
        """Get successful deliveries."""
        return self.filter(status=WebhookStatus.SUCCESS)
    
    def get_failed_deliveries(self) -> models.QuerySet:
        """Get failed deliveries."""
        return self.filter(status=WebhookStatus.FAILED)
    
    def get_retrying_deliveries(self) -> models.QuerySet:
        """Get deliveries pending retry."""
        return self.filter(status=WebhookStatus.RETRY)
    
    def get_pending_deliveries(self) -> models.QuerySet:
        """Get pending deliveries."""
        return self.filter(status=WebhookStatus.PENDING)
    
    def get_for_webhook(self, webhook_id: str) -> models.QuerySet:
        """Get deliveries for specific webhook."""
        return self.filter(webhook_id=webhook_id)
    
    def get_for_event(self, event_id: str) -> models.QuerySet:
        """Get deliveries for specific event."""
        return self.filter(event_id=event_id)
    
    def get_recent_deliveries(self, hours: int = 24) -> models.QuerySet:
        """Get recent deliveries."""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def get_with_details(self) -> models.QuerySet:
        """Get deliveries with related details."""
        return self.get_queryset().select_related('webhook', 'event')
    
    def get_by_attempt_count(self, min_attempts: int, max_attempts: Optional[int] = None) -> models.QuerySet:
        """Get deliveries by attempt count."""
        queryset = self.filter(attempts__gte=min_attempts)
        
        if max_attempts is not None:
            queryset = queryset.filter(attempts__lte=max_attempts)
        
        return queryset
    
    def get_scheduled_for_retry(self) -> models.QuerySet:
        """Get deliveries scheduled for retry."""
        return self.filter(
            status=WebhookStatus.RETRY,
            scheduled_at__lte=timezone.now()
        )
    
    def get_failed_deliveries_for_retry(self, max_attempts: int = 3) -> models.QuerySet:
        """Get failed deliveries that can be retried."""
        return self.get_failed_deliveries().filter(
            attempts__lt=max_attempts
        )


# Repository factory for creating repositories
class RepositoryFactory:
    """Factory for creating repositories."""
    
    @staticmethod
    def create_badge_repository() -> BadgeRepository:
        """Create badge repository."""
        return BadgeRepository()
    
    @staticmethod
    def create_user_badge_repository() -> UserBadgeRepository:
        """Create user badge repository."""
        return UserBadgeRepository()
    
    @staticmethod
    def create_challenge_repository() -> DailyChallengeRepository:
        """Create challenge repository."""
        return DailyChallengeRepository()
    
    @staticmethod
    def create_user_challenge_repository() -> UserDailyChallengeRepository:
        """Create user challenge repository."""
        return UserDailyChallengeRepository()
    
    @staticmethod
    def create_streak_repository() -> StreakRepository:
        """Create streak repository."""
        return StreakRepository()
    
    @staticmethod
    def create_level_repository() -> LevelConfigRepository:
        """Create level repository."""
        return LevelConfigRepository()
    
    @staticmethod
    def create_contest_repository() -> ContestCycleRepository:
        """Create contest repository."""
        return ContestCycleRepository()
    
    @staticmethod
    def create_achievement_repository() -> UserAchievementRepository:
        """Create achievement repository."""
        return UserAchievementRepository()
    
    @staticmethod
    def create_webhook_endpoint_repository() -> WebhookEndpointRepository:
        """Create webhook endpoint repository."""
        return WebhookEndpointRepository()
    
    @staticmethod
    def create_webhook_event_repository() -> WebhookEventRepository:
        """Create webhook event repository."""
        return WebhookEventRepository()
    
    @staticmethod
    def create_webhook_delivery_repository() -> WebhookDeliveryRepository:
        """Create webhook delivery repository."""
        return WebhookDeliveryRepository()


# Cached repository wrapper for performance optimization
class CachedRepository:
    """Repository wrapper with caching functionality."""
    
    def __init__(self, repository: BaseRepository, cache_timeout: int = 300):
        self.repository = repository
        self.cache_timeout = cache_timeout
    
    def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key for method call."""
        key_parts = [f"{self.repository.model_class.__name__}_{method}"]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return "_".join(key_parts)
    
    def get_by_id(self, id: str) -> Optional[models.Model]:
        """Get by ID with caching."""
        cache_key = self._get_cache_key("get_by_id", id)
        result = cache.get(cache_key)
        
        if result is None:
            result = self.repository.get_by_id(id)
            cache.set(cache_key, result, self.cache_timeout)
        
        return result
    
    def get_queryset(self):
        """Get queryset (not cached)."""
        return self.repository.get_queryset()
    
    def invalidate_cache(self, pattern: str = None):
        """Invalidate cache entries."""
        if pattern:
            # Delete cache entries matching pattern
            keys = cache.keys(f"*{pattern}*")
            cache.delete_many(keys)
        else:
            # Delete all cache entries for this repository
            keys = cache.keys(f"{self.repository.model_class.__name__}_*")
            cache.delete_many(keys)


# Convenience functions for common repository operations
def get_user_badges_with_details(user_id: str) -> List[Dict[str, Any]]:
    """Get user badges with full details."""
    repo = RepositoryFactory.create_user_badge_repository()
    return repo.get_user_badges_with_progress(user_id)


def get_user_challenge_stats(user_id: str, days: int = 30) -> Dict[str, Any]:
    """Get user challenge statistics."""
    repo = RepositoryFactory.create_user_challenge_repository()
    return repo.get_user_challenge_stats(user_id, days)


def get_user_achievement_summary(user_id: str) -> Dict[str, Any]:
    """Get user achievement summary."""
    repo = RepositoryFactory.create_achievement_repository()
    return repo.get_user_ranking_data(user_id)


def get_active_contests_with_stats() -> List[Dict[str, Any]]:
    """Get active contests with statistics."""
    repo = RepositoryFactory.create_contest_repository()
    contests = repo.get_active_contests().with_completion_stats()
    
    return [
        {
            'id': str(contest.id),
            'name': contest.name,
            'description': contest.description,
            'status': contest.status,
            'start_time': contest.start_time.isoformat(),
            'end_time': contest.end_time.isoformat(),
            'points_multiplier': float(contest.points_multiplier),
            'participant_count': contest.participant_count,
            'total_points_awarded': contest.total_points_awarded or 0,
            'average_points': float(contest.average_points or 0),
        }
        for contest in contests
    ]
