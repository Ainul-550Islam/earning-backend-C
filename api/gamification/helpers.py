"""
Gamification Helpers — Utility functions for gamification operations.

This module provides helper functions for common gamification tasks,
calculations, and data transformations.
"""

from __future__ import annotations
from datetime import date

import hashlib
import json
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Sum, Count, Avg, Max, Min
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    StreakStatus, ContestCycleStatus
)
from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class PointsCalculator:
    """Helper class for points calculations."""
    
    @staticmethod
    def calculate_level_points(level: int, base_points: int = 100, multiplier: float = 1.2) -> int:
        """Calculate points required for a given level."""
        return int(base_points * (multiplier ** (level - 1)))
    
    @staticmethod
    def calculate_streak_bonus_points(streak_days: int, base_bonus: int = 10) -> int:
        """Calculate bonus points for streak days."""
        if streak_days <= 0:
            return 0
        
        # Exponential growth with diminishing returns
        bonus = base_bonus * math.log(streak_days + 1)
        return int(bonus)
    
    @staticmethod
    def calculate_challenge_bonus_points(
        challenge_points: int,
        completion_time_minutes: Optional[int] = None,
        target_time_minutes: int = 60
    ) -> int:
        """Calculate bonus points for challenge completion."""
        base_bonus = challenge_points
        
        if completion_time_minutes is None:
            return base_bonus
        
        # Time bonus (faster completion = more points)
        if completion_time_minutes < target_time_minutes:
            time_ratio = completion_time_minutes / target_time_minutes
            time_bonus = int(base_bonus * (1 - time_ratio) * 0.5)  # Up to 50% bonus
            return base_bonus + time_bonus
        
        return base_bonus
    
    @staticmethod
    def calculate_contest_multiplier_points(
        base_points: int,
        contest_multiplier: float,
        rank: Optional[int] = None
    ) -> int:
        """Calculate points with contest multiplier and rank bonus."""
        points = int(base_points * contest_multiplier)
        
        # Rank bonus (top ranks get extra points)
        if rank:
            if rank == 1:
                points = int(points * 1.5)  # 50% bonus for 1st place
            elif rank <= 3:
                points = int(points * 1.2)  # 20% bonus for top 3
            elif rank <= 10:
                points = int(points * 1.1)  # 10% bonus for top 10
        
        return points
    
    @staticmethod
    def calculate_decay_points(
        original_points: int,
        days_since_activity: int,
        decay_rate: float = 0.1,
        max_decay_days: int = 30
    ) -> int:
        """Calculate points after decay."""
        if days_since_activity <= 0:
            return original_points
        
        # Apply exponential decay
        decay_days = min(days_since_activity, max_decay_days)
        decay_factor = math.exp(-decay_rate * decay_days)
        
        return int(original_points * decay_factor)


class BadgeHelper:
    """Helper class for badge operations."""
    
    @staticmethod
    def get_badge_rarity_weight(rarity: str) -> float:
        """Get weight for badge rarity."""
        rarity_weights = {
            BadgeRarity.COMMON: 1.0,
            BadgeRarity.RARE: 2.0,
            BadgeRarity.EPIC: 3.0,
            BadgeRarity.LEGENDARY: 5.0,
        }
        return rarity_weights.get(rarity, 1.0)
    
    @staticmethod
    def calculate_badge_score(badge: Badge, user_points: int) -> float:
        """Calculate badge score for ranking."""
        rarity_weight = BadgeHelper.get_badge_rarity_weight(badge.rarity)
        points_ratio = min(user_points / max(badge.criteria_value, 1), 2.0)
        
        return rarity_weight * points_ratio * badge.points_bonus
    
    @staticmethod
    def get_user_badge_summary(user_id: str) -> Dict[str, Any]:
        """Get comprehensive badge summary for user."""
        user_badges = UserBadge.objects.filter(user_id=user_id).select_related('badge')
        
        # Basic counts
        total_badges = user_badges.count()
        pinned_badges = user_badges.filter(is_pinned=True).count()
        
        # Rarity distribution
        rarity_distribution = {}
        total_points = 0
        
        for user_badge in user_badges:
            rarity = user_badge.badge.rarity or 'unknown'
            rarity_distribution[rarity] = rarity_distribution.get(rarity, 0) + 1
            total_points += user_badge.badge.points_bonus
        
        # Recent badges
        recent_badges = user_badges.order_by('-earned_at')[:5]
        
        return {
            'total_badges': total_badges,
            'pinned_badges': pinned_badges,
            'total_points': total_points,
            'rarity_distribution': rarity_distribution,
            'recent_badges': [
                {
                    'id': str(badge.id),
                    'name': badge.badge.name,
                    'icon': badge.badge.icon,
                    'earned_at': badge.earned_at.isoformat(),
                }
                for badge in recent_badges
            ]
        }
    
    @staticmethod
    def suggest_next_badges(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Suggest next badges user can earn."""
        # Get user's current stats
        user_stats = UserHelper.get_user_gamification_stats(user_id)
        
        # Get eligible badges
        from api.gamification.services import BadgeService
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=user_id,
            user_points=user_stats['total_points'],
            streak_days=user_stats['current_streak_days'],
            achievement_count=user_stats['total_achievements'],
            contest_wins=user_stats['contest_wins'],
            referral_count=user_stats['referral_count']
        )
        
        # Sort by score and return top suggestions
        suggestions = []
        for badge in eligible_badges[:limit]:
            score = BadgeHelper.calculate_badge_score(badge, user_stats['total_points'])
            suggestions.append({
                'id': str(badge.id),
                'name': badge.name,
                'description': badge.description,
                'icon': badge.icon,
                'rarity': badge.rarity,
                'points_bonus': badge.points_bonus,
                'score': score,
                'progress': min(user_stats['total_points'] / max(badge.criteria_value, 1), 1.0) * 100
            })
        
        return sorted(suggestions, key=lambda x: x['score'], reverse=True)


class StreakHelper:
    """Helper class for streak operations."""
    
    @staticmethod
    def calculate_streak_reset_date(last_activity_date: date, grace_period_days: int = 1) -> date:
        """Calculate when streak will reset."""
        return last_activity_date + timedelta(days=grace_period_days + 1)
    
    @staticmethod
    def get_streak_status(streak: Streak) -> str:
        """Get current streak status."""
        if not streak.is_active:
            return StreakStatus.INACTIVE
        
        today = timezone.now().date()
        reset_date = StreakHelper.calculate_streak_reset_date(streak.last_activity_date)
        
        if today > reset_date:
            return StreakStatus.EXPIRED
        elif today == reset_date:
            return StreakStatus.EXPIRING_TODAY
        elif today == streak.last_activity_date:
            return StreakStatus.ACTIVE_TODAY
        else:
            return StreakStatus.ACTIVE
    
    @staticmethod
    def get_streak_milestone_rewards(streak_days: int) -> List[Dict[str, Any]]:
        """Get milestone rewards for streak days."""
        from api.gamification.models import StreakReward
        
        rewards = StreakReward.objects.filter(
            streak_days__lte=streak_days,
            is_active=True
        ).order_by('-streak_days')
        
        return [
            {
                'streak_days': reward.streak_days,
                'title': reward.title,
                'description': reward.description,
                'points_bonus': reward.points_bonus,
                'badge_id': str(reward.badge.id) if reward.badge else None,
            }
            for reward in rewards
        ]
    
    @staticmethod
    def calculate_streak_heatmap_data(user_id: str, days: int = 365) -> List[Dict[str, Any]]:
        """Calculate streak heatmap data."""
        from api.gamification.models import StreakActivity
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        activities = StreakActivity.objects.filter(
            user_id=user_id,
            activity_date__gte=start_date,
            activity_date__lte=end_date
        ).order_by('activity_date')
        
        # Create heatmap data
        heatmap_data = []
        activity_dates = {activity.activity_date for activity in activities}
        
        current_date = start_date
        while current_date <= end_date:
            has_activity = current_date in activity_dates
            
            heatmap_data.append({
                'date': current_date.isoformat(),
                'has_activity': has_activity,
                'intensity': 4 if has_activity else 0,  # Simplified intensity
            })
            
            current_date += timedelta(days=1)
        
        return heatmap_data


class ChallengeHelper:
    """Helper class for challenge operations."""
    
    @staticmethod
    def get_challenge_difficulty(target_count: int, action_type: str) -> str:
        """Determine challenge difficulty."""
        difficulty_thresholds = {
            ChallengeAction.LOGIN: {'easy': 1, 'medium': 7, 'hard': 30},
            ChallengeAction.POST: {'easy': 1, 'medium': 5, 'hard': 20},
            ChallengeAction.COMMENT: {'easy': 3, 'medium': 10, 'hard': 50},
            ChallengeAction.LIKE: {'easy': 5, 'medium': 25, 'hard': 100},
            ChallengeAction.SHARE: {'easy': 1, 'medium': 3, 'hard': 10},
        }
        
        thresholds = difficulty_thresholds.get(action_type, {'easy': 1, 'medium': 5, 'hard': 20})
        
        if target_count <= thresholds['easy']:
            return 'easy'
        elif target_count <= thresholds['medium']:
            return 'medium'
        else:
            return 'hard'
    
    @staticmethod
    def calculate_challenge_completion_rate(challenge: DailyChallenge) -> float:
        """Calculate completion rate for a challenge."""
        total_participants = UserDailyChallenge.objects.filter(challenge=challenge).count()
        completed_participants = UserDailyChallenge.objects.filter(
            challenge=challenge,
            is_completed=True
        ).count()
        
        if total_participants == 0:
            return 0.0
        
        return (completed_participants / total_participants) * 100
    
    @staticmethod
    def get_user_challenge_stats(user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get user's challenge statistics."""
        since_date = timezone.now().date() - timedelta(days=days)
        
        user_challenges = UserDailyChallenge.objects.filter(
            user_id=user_id,
            challenge__date__gte=since_date
        ).select_related('challenge')
        
        total_challenges = user_challenges.count()
        completed_challenges = user_challenges.filter(is_completed=True).count()
        
        # Action type distribution
        action_distribution = {}
        total_bonus_points = 0
        
        for user_challenge in user_challenges:
            action = user_challenge.challenge.target_action or 'unknown'
            action_distribution[action] = action_distribution.get(action, 0) + 1
            
            if user_challenge.is_completed:
                total_bonus_points += user_challenge.challenge.bonus_points
        
        return {
            'total_challenges': total_challenges,
            'completed_challenges': completed_challenges,
            'completion_rate': (completed_challenges / total_challenges * 100) if total_challenges > 0 else 0,
            'total_bonus_points': total_bonus_points,
            'action_distribution': action_distribution,
        }


class LevelHelper:
    """Helper class for level operations."""
    
    @staticmethod
    def get_level_for_points(points: int) -> Optional[LevelConfig]:
        """Get level configuration for given points."""
        return LevelConfig.objects.filter(
            points_required__lte=points,
            is_active=True
        ).order_by('-level_number').first()
    
    @staticmethod
    def calculate_level_progress(points: int) -> Dict[str, Any]:
        """Calculate level progress."""
        current_level = LevelHelper.get_level_for_points(points)
        
        if not current_level:
            return {
                'current_level': 0,
                'points_to_next_level': 0,
                'progress_percentage': 0,
                'points_in_current_level': points,
            }
        
        # Get next level
        next_level = LevelConfig.objects.filter(
            level_number=current_level.level_number + 1,
            is_active=True
        ).first()
        
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
        }
    
    @staticmethod
    def get_level_distribution() -> Dict[str, int]:
        """Get distribution of users across levels."""
        from django.db.models import Count
        
        # Get all users with their total points
        user_points = (
            UserAchievement.objects
            .filter(is_awarded=True)
            .values('user_id')
            .annotate(total_points=Sum('points_awarded'))
        )
        
        level_distribution = {}
        
        for user_data in user_points:
            points = user_data['total_points'] or 0
            level = LevelHelper.get_level_for_points(points)
            level_number = level.level_number if level else 0
            
            level_distribution[level_number] = level_distribution.get(level_number, 0) + 1
        
        return level_distribution


class UserHelper:
    """Helper class for user operations."""
    
    @staticmethod
    def get_user_gamification_stats(user_id: str) -> Dict[str, Any]:
        """Get comprehensive gamification statistics for user."""
        # Basic counts
        total_badges = UserBadge.objects.filter(user_id=user_id).count()
        total_achievements = UserAchievement.objects.filter(
            user_id=user_id,
            is_awarded=True
        ).count()
        
        # Points
        total_points = UserAchievement.objects.filter(
            user_id=user_id,
            is_awarded=True
        ).aggregate(total=Sum('points_awarded'))['total'] or 0
        
        # Streak
        streak = Streak.objects.filter(user_id=user_id).first()
        current_streak_days = streak.current_days if streak else 0
        longest_streak_days = streak.longest_days if streak else 0
        
        # Level
        level_progress = LevelHelper.calculate_level_progress(total_points)
        
        # Recent activity
        recent_achievements = UserAchievement.objects.filter(
            user_id=user_id,
            is_awarded=True
        ).order_by('-awarded_at')[:5]
        
        # Contest wins
        contest_wins = UserAchievement.objects.filter(
            user_id=user_id,
            is_awarded=True,
            rank__lte=3  # Top 3 positions
        ).count()
        
        return {
            'total_badges': total_badges,
            'total_achievements': total_achievements,
            'total_points': total_points,
            'current_streak_days': current_streak_days,
            'longest_streak_days': longest_streak_days,
            'current_level': level_progress.get('current_level', 0),
            'level_progress': level_progress,
            'contest_wins': contest_wins,
            'referral_count': 0,  # Would need to implement referral tracking
            'recent_achievements': [
                {
                    'id': str(achievement.id),
                    'points_awarded': achievement.points_awarded,
                    'rank': achievement.rank,
                    'awarded_at': achievement.awarded_at.isoformat(),
                }
                for achievement in recent_achievements
            ]
        }
    
    @staticmethod
    def get_user_ranking(user_id: str, scope: str = 'global') -> Dict[str, Any]:
        """Get user's ranking in different scopes."""
        from django.db.models import F, Window, RowNumber
        
        # Global ranking by points
        global_ranking = (
            UserAchievement.objects
            .filter(is_awarded=True)
            .values('user_id')
            .annotate(total_points=Sum('points_awarded'))
            .order_by('-total_points')
        )
        
        # Find user's rank
        user_rank = None
        for rank, data in enumerate(global_ranking, 1):
            if str(data['user_id']) == user_id:
                user_rank = rank
                break
        
        return {
            'global_rank': user_rank,
            'total_users': global_ranking.count(),
            'percentile': (user_rank / global_ranking.count() * 100) if user_rank else None,
        }


class CacheHelper:
    """Helper class for cache operations."""
    
    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """Generate cache key."""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def cache_user_stats(user_id: str, stats: Dict[str, Any], timeout: int = 300) -> None:
        """Cache user statistics."""
        cache_key = CacheHelper.get_cache_key('user_stats', user_id)
        cache.set(cache_key, stats, timeout)
    
    @staticmethod
    def get_cached_user_stats(user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user statistics."""
        cache_key = CacheHelper.get_cache_key('user_stats', user_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_leaderboard(scope: str, data: List[Dict[str, Any]], timeout: int = 600) -> None:
        """Cache leaderboard data."""
        cache_key = CacheHelper.get_cache_key('leaderboard', scope)
        cache.set(cache_key, data, timeout)
    
    @staticmethod
    def get_cached_leaderboard(scope: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached leaderboard data."""
        cache_key = CacheHelper.get_cache_key('leaderboard', scope)
        return cache.get(cache_key)
    
    @staticmethod
    def invalidate_user_cache(user_id: str) -> None:
        """Invalidate user-related cache entries."""
        cache_keys = [
            CacheHelper.get_cache_key('user_stats', user_id),
            CacheHelper.get_cache_key('user_badges', user_id),
            CacheHelper.get_cache_key('user_achievements', user_id),
            CacheHelper.get_cache_key('user_level', user_id),
        ]
        
        cache.delete_many(cache_keys)


class ValidationHelper:
    """Helper class for validation operations."""
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """Validate user ID format."""
        try:
            from uuid import UUID
            UUID(user_id)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_points_range(points: int, min_points: int = 0, max_points: int = 1000000) -> bool:
        """Validate points range."""
        return min_points <= points <= max_points
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> bool:
        """Validate date range."""
        return start_date <= end_date
    
    @staticmethod
    def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize metadata dictionary."""
        if not isinstance(metadata, dict):
            return {}
        
        # Remove potentially sensitive keys
        sensitive_keys = ['password', 'token', 'secret', 'key']
        
        sanitized = {}
        for key, value in metadata.items():
            if key.lower() not in sensitive_keys:
                # Convert complex objects to JSON-serializable format
                try:
                    json.dumps(value)  # Test if serializable
                    sanitized[key] = value
                except (TypeError, ValueError):
                    sanitized[key] = str(value)
        
        return sanitized


class DataHelper:
    """Helper class for data transformations."""
    
    @staticmethod
    def serialize_datetime(dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()
    
    @staticmethod
    def deserialize_datetime(dt_str: str) -> datetime:
        """Deserialize datetime from ISO format."""
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    
    @staticmethod
    def flatten_nested_dict(data: Dict[str, Any], separator: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary."""
        def _flatten(obj, parent_key=''):
            items = []
            for k, v in obj.items():
                new_key = f"{parent_key}{separator}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(_flatten(v, new_key).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        
        return _flatten(data)
    
    @staticmethod
    def calculate_percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index % 1)
    
    @staticmethod
    def generate_checksum(data: Dict[str, Any]) -> str:
        """Generate checksum for data integrity."""
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_str.encode()).hexdigest()


class NotificationHelper:
    """Helper class for notification operations."""
    
    @staticmethod
    def format_badge_earned_message(badge_name: str, points_bonus: int) -> str:
        """Format badge earned notification message."""
        return f"🎉 Congratulations! You've earned the '{badge_name}' badge and {points_bonus} points!"
    
    @staticmethod
    def format_streak_milestone_message(days: int, bonus_points: int) -> str:
        """Format streak milestone notification message."""
        return f"🔥 Amazing! You've maintained a {days}-day streak and earned {bonus_points} bonus points!"
    
    @staticmethod
    def format_level_up_message(new_level: int, level_title: str) -> str:
        """Format level up notification message."""
        return f"⬆️ Level Up! You've reached Level {new_level}: {level_title}"
    
    @staticmethod
    def format_challenge_completed_message(challenge_title: str, bonus_points: int) -> str:
        """Format challenge completed notification message."""
        return f"✅ Challenge Complete! You've completed '{challenge_title}' and earned {bonus_points} bonus points!"
    
    @staticmethod
    def get_notification_priority(event_type: str) -> str:
        """Get notification priority for event type."""
        priority_mapping = {
            'badge_earned': 'medium',
            'streak_milestone': 'high',
            'level_up': 'high',
            'challenge_completed': 'low',
            'achievement_awarded': 'medium',
        }
        return priority_mapping.get(event_type, 'low')


# Utility functions for common operations
def get_user_gamification_summary(user_id: str) -> Dict[str, Any]:
    """Get comprehensive gamification summary for user."""
    user_stats = UserHelper.get_user_gamification_stats(user_id)
    badge_summary = BadgeHelper.get_user_badge_summary(user_id)
    challenge_stats = ChallengeHelper.get_user_challenge_stats(user_id)
    
    return {
        'user_stats': user_stats,
        'badge_summary': badge_summary,
        'challenge_stats': challenge_stats,
        'next_badges': BadgeHelper.suggest_next_badges(user_id),
        'ranking': UserHelper.get_user_ranking(user_id),
    }


def calculate_global_leaderboard(limit: int = 100) -> List[Dict[str, Any]]:
    """Calculate global leaderboard."""
    leaderboard_data = (
        UserAchievement.objects
        .filter(is_awarded=True)
        .values('user_id')
        .annotate(
            total_points=Sum('points_awarded'),
            achievement_count=Count('id')
        )
        .order_by('-total_points')[:limit]
    )
    
    # Add user information
    result = []
    for rank, data in enumerate(leaderboard_data, 1):
        result.append({
            'rank': rank,
            'user_id': data['user_id'],
            'total_points': data['total_points'],
            'achievement_count': data['achievement_count'],
        })
    
    return result


def invalidate_user_caches(user_id: str) -> None:
    """Invalidate all cache entries for user."""
    CacheHelper.invalidate_user_cache(user_id)
    
    # Also invalidate leaderboard cache
    cache.delete('leaderboard:global')
    cache.delete('leaderboard:weekly')
    cache.delete('leaderboard:monthly')


def validate_gamification_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize gamification data."""
    validated_data = {}
    
    # Validate user_id
    if 'user_id' in data:
        if ValidationHelper.validate_user_id(data['user_id']):
            validated_data['user_id'] = data['user_id']
        else:
            raise ValueError("Invalid user_id format")
    
    # Validate points
    if 'points' in data:
        points = int(data['points'])
        if ValidationHelper.validate_points_range(points):
            validated_data['points'] = points
        else:
            raise ValueError("Points value out of valid range")
    
    # Sanitize metadata
    if 'metadata' in data:
        validated_data['metadata'] = ValidationHelper.sanitize_metadata(data['metadata'])
    
    return validated_data
