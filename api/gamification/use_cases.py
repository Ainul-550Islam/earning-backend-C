"""
Gamification Use Cases — Business logic implementation for gamification features.

This module contains use case classes that encapsulate business logic for
gamification operations, providing a clean separation between business rules
and data access layers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
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
from api.gamification.services import (
    BadgeService, DailyChallengeService, StreakService, LevelUpService
)
from api.gamification.selectors import (
    BadgeSelector, UserBadgeSelector, DailyChallengeSelector,
    UserDailyChallengeSelector, StreakSelector, LevelConfigSelector,
    ContestCycleSelector, UserAchievementSelector
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import (
    PointsCalculator, BadgeHelper, StreakHelper, ChallengeHelper,
    LevelHelper, UserHelper, CacheHelper, ValidationHelper
)

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseUseCase:
    """Base class for all gamification use cases."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters."""
        pass
    
    def execute(self, **kwargs) -> Any:
        """Execute the use case."""
        raise NotImplementedError("Subclasses must implement execute method")


class BadgeUseCase(BaseUseCase):
    """Use case for badge-related operations."""
    
    def __init__(self):
        super().__init__()
        self.badge_service = BadgeService()
        self.badge_selector = BadgeSelector()
        self.user_badge_selector = UserBadgeSelector()
    
    def get_available_badges(self, user_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get available badges for user with eligibility checking."""
        try:
            self.validate_input(user_id=user_id, filters=filters)
            
            # Get user's current stats
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            
            # Get all active badges
            badges = self.badge_selector.active()
            
            # Apply filters if provided
            if filters:
                if 'rarity' in filters:
                    badges = badges.by_rarity(filters['rarity'])
                if 'criteria_type' in filters:
                    badges = badges.by_criteria_type(filters['criteria_type'])
                if 'points_min' in filters:
                    badges = badges.by_points_range(filters['points_min'], filters.get('points_max', 999999))
            
            # Check eligibility for each badge
            available_badges = []
            for badge in badges.execute():
                is_eligible = self.badge_service.check_user_badge_eligibility(
                    user_id=user_id,
                    user_points=user_stats['total_points'],
                    streak_days=user_stats['current_streak_days'],
                    achievement_count=user_stats['total_achievements'],
                    contest_wins=user_stats['contest_wins'],
                    referral_count=user_stats['referral_count']
                )
                
                if is_eligible:
                    badge_data = {
                        'id': str(badge.id),
                        'name': badge.name,
                        'description': badge.description,
                        'icon': badge.icon,
                        'rarity': badge.rarity,
                        'criteria_type': badge.criteria_type,
                        'criteria_value': badge.criteria_value,
                        'points_bonus': badge.points_bonus,
                        'is_eligible': True,
                        'progress': self._calculate_eligibility_progress(badge, user_stats)
                    }
                    available_badges.append(badge_data)
                else:
                    badge_data = {
                        'id': str(badge.id),
                        'name': badge.name,
                        'description': badge.description,
                        'icon': badge.icon,
                        'rarity': badge.rarity,
                        'criteria_type': badge.criteria_type,
                        'criteria_value': badge.criteria_value,
                        'points_bonus': badge.points_bonus,
                        'is_eligible': False,
                        'progress': self._calculate_eligibility_progress(badge, user_stats)
                    }
                    available_badges.append(badge_data)
            
            return available_badges
            
        except Exception as e:
            self.logger.error(f"Error getting available badges for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get available badges: {e}")
    
    def award_badges_to_user(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> List[UserBadge]:
        """Award eligible badges to user."""
        try:
            self.validate_input(user_id=user_id, metadata=metadata)
            
            # Get user's current stats
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            
            # Award eligible badges
            awarded_badges = self.badge_service.award_eligible_badges(
                user_id=user_id,
                user_points=user_stats['total_points'],
                streak_days=user_stats['current_streak_days'],
                achievement_count=user_stats['total_achievements'],
                contest_wins=user_stats['contest_wins'],
                referral_count=user_stats['referral_count'],
                metadata=metadata or {}
            )
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(user_id)
            
            return awarded_badges
            
        except Exception as e:
            self.logger.error(f"Error awarding badges to user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to award badges: {e}")
    
    def get_user_badge_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive badge summary for user."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get badge summary using helper
            summary = BadgeHelper.get_user_badge_summary(user_id)
            
            # Add next badge suggestions
            summary['next_badges'] = BadgeHelper.suggest_next_badges(user_id)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting badge summary for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get badge summary: {e}")
    
    def pin_badge(self, user_id: str, badge_id: str) -> UserBadge:
        """Pin a badge for user."""
        try:
            self.validate_input(user_id=user_id, badge_id=badge_id)
            
            with transaction.atomic():
                # Get user badge
                user_badge = self.user_badge_selector.for_user(user_id).by_badge(badge_id).execute().first()
                
                if not user_badge:
                    raise GamificationServiceError("User badge not found")
                
                # Update pinned status
                user_badge.is_pinned = True
                user_badge.save()
                
                # Invalidate cache
                CacheHelper.invalidate_user_cache(user_id)
                
                return user_badge
                
        except Exception as e:
            self.logger.error(f"Error pinning badge {badge_id} for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to pin badge: {e}")
    
    def unpin_badge(self, user_id: str, badge_id: str) -> UserBadge:
        """Unpin a badge for user."""
        try:
            self.validate_input(user_id=user_id, badge_id=badge_id)
            
            with transaction.atomic():
                # Get user badge
                user_badge = self.user_badge_selector.for_user(user_id).by_badge(badge_id).execute().first()
                
                if not user_badge:
                    raise GamificationServiceError("User badge not found")
                
                # Update pinned status
                user_badge.is_pinned = False
                user_badge.save()
                
                # Invalidate cache
                CacheHelper.invalidate_user_cache(user_id)
                
                return user_badge
                
        except Exception as e:
            self.logger.error(f"Error unpinning badge {badge_id} for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to unpin badge: {e}")
    
    def _calculate_eligibility_progress(self, badge: Badge, user_stats: Dict[str, Any]) -> float:
        """Calculate eligibility progress for badge."""
        if badge.criteria_type == BadgeCriteriaType.POINTS_THRESHOLD:
            return min(100.0, (user_stats['total_points'] / badge.criteria_value) * 100)
        elif badge.criteria_type == BadgeCriteriaType.STREAK_DAYS:
            return min(100.0, (user_stats['current_streak_days'] / badge.criteria_value) * 100)
        elif badge.criteria_type == BadgeCriteriaType.ACHIEVEMENT_COUNT:
            return min(100.0, (user_stats['total_achievements'] / badge.criteria_value) * 100)
        elif badge.criteria_type == BadgeCriteriaType.CONTEST_WINS:
            return min(100.0, (user_stats['contest_wins'] / badge.criteria_value) * 100)
        elif badge.criteria_type == BadgeCriteriaType.REFERRAL_COUNT:
            return min(100.0, (user_stats['referral_count'] / badge.criteria_value) * 100)
        else:
            return 0.0


class StreakUseCase(BaseUseCase):
    """Use case for streak-related operations."""
    
    def __init__(self):
        super().__init__()
        self.streak_service = StreakService()
        self.streak_selector = StreakSelector()
    
    def get_user_streak_info(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive streak information for user."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get or create user streak
            streak = self.streak_service.get_or_create_user_streak(user_id)
            
            # Get streak status
            status = StreakHelper.get_streak_status(streak)
            
            # Get milestone rewards
            milestone_rewards = StreakHelper.get_streak_milestone_rewards(streak.current_days)
            
            # Get streak statistics
            stats = self.streak_service.get_streak_statistics(user_id)
            
            return {
                'streak': {
                    'current_days': streak.current_days,
                    'longest_days': streak.longest_days,
                    'last_activity_date': streak.last_activity_date.isoformat(),
                    'is_active': streak.is_active,
                    'status': status
                },
                'milestone_rewards': milestone_rewards,
                'statistics': stats,
                'days_until_reset': StreakHelper.calculate_streak_reset_date(streak.last_activity_date).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting streak info for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get streak info: {e}")
    
    def update_user_activity(self, user_id: str, activity_date: Optional[datetime.date] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update user's streak activity."""
        try:
            self.validate_input(user_id=user_id, activity_date=activity_date, metadata=metadata)
            
            # Update activity
            streak, was_extended, days_added = self.streak_service.update_user_activity(
                user_id=user_id,
                activity_date=activity_date,
                metadata=metadata or {}
            )
            
            # Check for milestone rewards
            milestone_rewards = []
            if was_extended:
                milestone_rewards = StreakHelper.get_streak_milestone_rewards(streak.current_days)
            
            # Invalidate cache
            CacheHelper.invalidate_user_cache(user_id)
            
            return {
                'streak': {
                    'current_days': streak.current_days,
                    'longest_days': streak.longest_days,
                    'last_activity_date': streak.last_activity_date.isoformat(),
                    'is_active': streak.is_active
                },
                'was_extended': was_extended,
                'days_added': days_added,
                'milestone_rewards': milestone_rewards
            }
            
        except Exception as e:
            self.logger.error(f"Error updating activity for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to update activity: {e}")
    
    def get_streak_leaderboard(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get streak leaderboard."""
        try:
            self.validate_input(limit=limit)
            
            # Get leaderboard data
            leaderboard_data = self.streak_selector.leaderboard(limit=limit).execute()
            
            return [
                {
                    'rank': index + 1,
                    'user_id': str(streak.user.id),
                    'username': streak.user.username,
                    'current_days': streak.current_days,
                    'longest_days': streak.longest_days,
                    'last_activity_date': streak.last_activity_date.isoformat(),
                    'is_active': streak.is_active
                }
                for index, streak in enumerate(leaderboard_data)
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting streak leaderboard: {e}")
            raise GamificationServiceError(f"Failed to get streak leaderboard: {e}")
    
    def get_streak_heatmap_data(self, user_id: str, days: int = 365) -> List[Dict[str, Any]]:
        """Get streak heatmap data for user."""
        try:
            self.validate_input(user_id=user_id, days=days)
            
            # Get heatmap data
            heatmap_data = StreakHelper.calculate_streak_heatmap_data(user_id, days)
            
            return heatmap_data
            
        except Exception as e:
            self.logger.error(f"Error getting streak heatmap for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get streak heatmap: {e}")
    
    def calculate_streak_bonus(self, user_id: str) -> int:
        """Calculate streak bonus points for user."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get user streak
            streak = self.streak_service.get_or_create_user_streak(user_id)
            
            # Calculate bonus
            bonus = PointsCalculator.calculate_streak_bonus_points(streak.current_days)
            
            return bonus
            
        except Exception as e:
            self.logger.error(f"Error calculating streak bonus for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to calculate streak bonus: {e}")


class ChallengeUseCase(BaseUseCase):
    """Use case for challenge-related operations."""
    
    def __init__(self):
        super().__init__()
        self.challenge_service = DailyChallengeService()
        self.challenge_selector = DailyChallengeSelector()
        self.user_challenge_selector = UserDailyChallengeSelector()
    
    def get_available_challenges(self, user_id: str, date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """Get available challenges for user."""
        try:
            self.validate_input(user_id=user_id, date=date)
            
            # Get active challenges
            challenges = self.challenge_service.get_active_challenges(challenge_date=date)
            
            # Get user's progress for each challenge
            challenge_data = []
            for challenge in challenges:
                user_challenge = self.user_challenge_selector.for_user(user_id).for_challenge(str(challenge.id)).execute().first()
                
                data = {
                    'id': str(challenge.id),
                    'title': challenge.title,
                    'description': challenge.description,
                    'target_action': challenge.target_action,
                    'target_count': challenge.target_count,
                    'bonus_points': challenge.bonus_points,
                    'date': challenge.date.isoformat(),
                    'is_active': challenge.is_active,
                    'user_progress': {
                        'progress': user_challenge.progress if user_challenge else 0,
                        'is_completed': user_challenge.is_completed if user_challenge else False,
                        'completed_at': user_challenge.completed_at.isoformat() if user_challenge and user_challenge.completed_at else None,
                        'started_at': user_challenge.challenge.date.isoformat() if user_challenge else None
                    }
                }
                challenge_data.append(data)
            
            return challenge_data
            
        except Exception as e:
            self.logger.error(f"Error getting available challenges for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get available challenges: {e}")
    
    def start_challenge(self, user_id: str, challenge_id: str) -> Dict[str, Any]:
        """Start a challenge for user."""
        try:
            self.validate_input(user_id=user_id, challenge_id=challenge_id)
            
            # Start challenge
            user_challenge = self.challenge_service.start_user_challenge(user_id, challenge_id)
            
            # Invalidate cache
            CacheHelper.invalidate_user_cache(user_id)
            
            return {
                'user_challenge': {
                    'id': str(user_challenge.id),
                    'challenge_id': str(user_challenge.challenge.id),
                    'challenge_title': user_challenge.challenge.title,
                    'progress': user_challenge.progress,
                    'is_completed': user_challenge.is_completed,
                    'started_at': user_challenge.challenge.date.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error starting challenge {challenge_id} for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to start challenge: {e}")
    
    def update_challenge_progress(self, user_id: str, challenge_id: str, increment_amount: int = 1,
                                action_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update challenge progress for user."""
        try:
            self.validate_input(user_id=user_id, challenge_id=challenge_id, increment_amount=increment_amount)
            
            # Update progress
            user_challenge, completed = self.challenge_service.update_challenge_progress(
                user_id=user_id,
                challenge_id=challenge_id,
                increment_amount=increment_amount,
                action_metadata=action_metadata or {}
            )
            
            # Calculate bonus if completed
            bonus_points = 0
            if completed:
                bonus_points = PointsCalculator.calculate_challenge_bonus_points(
                    user_challenge.challenge.bonus_points
                )
            
            # Invalidate cache
            CacheHelper.invalidate_user_cache(user_id)
            
            return {
                'user_challenge': {
                    'id': str(user_challenge.id),
                    'challenge_id': str(user_challenge.challenge.id),
                    'challenge_title': user_challenge.challenge.title,
                    'progress': user_challenge.progress,
                    'is_completed': user_challenge.is_completed,
                    'completed_at': user_challenge.completed_at.isoformat() if user_challenge.completed_at else None,
                    'bonus_points': bonus_points
                },
                'completed': completed,
                'bonus_points': bonus_points
            }
            
        except Exception as e:
            self.logger.error(f"Error updating challenge progress {challenge_id} for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to update challenge progress: {e}")
    
    def get_challenge_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get challenge statistics for user."""
        try:
            self.validate_input(user_id=user_id, days=days)
            
            # Get statistics using helper
            stats = ChallengeHelper.get_user_challenge_stats(user_id, days)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting challenge statistics for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get challenge statistics: {e}")
    
    def get_challenge_recommendations(self, user_id: str, count: int = 5) -> List[Dict[str, Any]]:
        """Get personalized challenge recommendations for user."""
        try:
            self.validate_input(user_id=user_id, count=count)
            
            # Get user stats
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            
            # Get available challenges
            available_challenges = self.get_available_challenges(user_id)
            
            # Filter challenges user hasn't completed
            incomplete_challenges = [
                challenge for challenge in available_challenges
                if not challenge['user_progress']['is_completed']
            ]
            
            # Sort by difficulty and bonus points
            incomplete_challenges.sort(key=lambda x: (x['bonus_points'], x['target_count']))
            
            return incomplete_challenges[:count]
            
        except Exception as e:
            self.logger.error(f"Error getting challenge recommendations for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get challenge recommendations: {e}")


class LevelUseCase(BaseUseCase):
    """Use case for level-related operations."""
    
    def __init__(self):
        super().__init__()
        self.level_service = LevelUpService()
        self.level_selector = LevelConfigSelector()
    
    def get_user_level_info(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive level information for user."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get user's total points
            total_points = UserHelper.get_user_gamification_stats(user_id)['total_points']
            
            # Get current level and progress
            current_level = self.level_service.get_user_level(total_points)
            progress = self.level_service.get_level_progress(total_points)
            
            return {
                'current_level': {
                    'level_number': current_level.level_number if current_level else 0,
                    'title': current_level.title if current_level else "No Level",
                    'description': current_level.description if current_level else "",
                    'points_required': current_level.points_required if current_level else 0,
                    'points_multiplier': float(current_level.points_multiplier) if current_level else 1.0,
                    'perks': current_level.perks if current_level else {}
                },
                'progress': progress,
                'total_points': total_points
            }
            
        except Exception as e:
            self.logger.error(f"Error getting level info for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get level info: {e}")
    
    def check_level_up_eligibility(self, user_id: str) -> Dict[str, Any]:
        """Check if user is eligible for level up."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get current level info
            level_info = self.get_user_level_info(user_id)
            
            # Check if user can level up
            current_level = level_info['current_level']['level_number']
            points_to_next = level_info['progress']['points_to_next_level']
            
            can_level_up = points_to_next <= 0
            next_level = None
            
            if can_level_up:
                next_level = self.level_selector.active().by_level_range(current_level + 1, current_level + 1).execute().first()
            
            return {
                'can_level_up': can_level_up,
                'current_level': current_level,
                'points_to_next': points_to_next,
                'next_level': {
                    'level_number': next_level.level_number if next_level else None,
                    'title': next_level.title if next_level else None,
                    'points_required': next_level.points_required if next_level else None,
                    'perks': next_level.perks if next_level else None
                } if next_level else None
            }
            
        except Exception as e:
            self.logger.error(f"Error checking level up eligibility for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to check level up eligibility: {e}")
    
    def level_up_user(self, user_id: str) -> Dict[str, Any]:
        """Level up user if eligible."""
        try:
            self.validate_input(user_id=user_id)
            
            # Check eligibility
            eligibility = self.check_level_up_eligibility(user_id)
            
            if not eligibility['can_level_up']:
                raise GamificationServiceError("User is not eligible for level up")
            
            # Get current level info before level up
            old_level_info = self.get_user_level_info(user_id)
            
            # Get next level
            next_level = eligibility['next_level']
            if not next_level:
                raise GamificationServiceError("No next level available")
            
            # In a real implementation, you would:
            # 1. Create UserLevel record
            # 2. Distribute perks
            # 3. Send notifications
            # 4. Update cache
            
            # For now, return the level up result
            new_level_info = self.get_user_level_info(user_id)
            
            # Invalidate cache
            CacheHelper.invalidate_user_cache(user_id)
            
            return {
                'old_level': old_level_info['current_level'],
                'new_level': new_level_info['current_level'],
                'perks_received': next_level['perks'],
                'level_up_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error leveling up user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to level up user: {e}")
    
    def get_available_levels(self) -> List[Dict[str, Any]]:
        """Get all available levels."""
        try:
            levels = self.level_selector.active().ordered_by_level().execute()
            
            return [
                {
                    'level_number': level.level_number,
                    'title': level.title,
                    'description': level.description,
                    'points_required': level.points_required,
                    'points_multiplier': float(level.points_multiplier),
                    'perks': level.perks,
                    'badge_id': str(level.badge.id) if level.badge else None
                }
                for level in levels
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting available levels: {e}")
            raise GamificationServiceError(f"Failed to get available levels: {e}")
    
    def get_level_distribution(self) -> Dict[str, int]:
        """Get distribution of users across levels."""
        try:
            distribution = LevelHelper.get_level_distribution()
            
            return distribution
            
        except Exception as e:
            self.logger.error(f"Error getting level distribution: {e}")
            raise GamificationServiceError(f"Failed to get level distribution: {e}")


class ContestUseCase(BaseUseCase):
    """Use case for contest-related operations."""
    
    def __init__(self):
        super().__init__()
        self.contest_selector = ContestCycleSelector()
        self.achievement_selector = UserAchievementSelector()
    
    def get_active_contests(self) -> List[Dict[str, Any]]:
        """Get all active contests."""
        try:
            contests = self.contest_selector.active().execute()
            
            return [
                {
                    'id': str(contest.id),
                    'name': contest.name,
                    'description': contest.description,
                    'status': contest.status,
                    'start_time': contest.start_time.isoformat(),
                    'end_time': contest.end_time.isoformat(),
                    'points_multiplier': float(contest.points_multiplier),
                    'is_active': contest.is_active
                }
                for contest in contests
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting active contests: {e}")
            raise GamificationServiceError(f"Failed to get active contests: {e}")
    
    def get_contest_leaderboard(self, contest_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get contest leaderboard."""
        try:
            self.validate_input(contest_id=contest_id, limit=limit)
            
            # Get leaderboard data
            leaderboard = (
                self.achievement_selector
                .for_contest(contest_id)
                .awarded()
                .order_by('-points_awarded', 'rank')
                .limit_results(limit)
                .execute()
            )
            
            return [
                {
                    'rank': index + 1,
                    'user_id': str(achievement.user.id),
                    'username': achievement.user.username,
                    'points_awarded': achievement.points_awarded,
                    'rank': achievement.rank,
                    'achievement_type': achievement.achievement_type,
                    'awarded_at': achievement.awarded_at.isoformat()
                }
                for index, achievement in enumerate(leaderboard)
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting contest leaderboard for {contest_id}: {e}")
            raise GamificationServiceError(f"Failed to get contest leaderboard: {e}")
    
    def get_user_contest_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's contest participation history."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get user's contest achievements
            achievements = (
                self.achievement_selector
                .for_user(user_id)
                .awarded()
                .with_contest_details()
                .order_by('-awarded_at')
                .execute()
            )
            
            return [
                {
                    'id': str(achievement.id),
                    'contest_id': str(achievement.contest_cycle.id) if achievement.contest_cycle else None,
                    'contest_name': achievement.contest_cycle.name if achievement.contest_cycle else None,
                    'achievement_type': achievement.achievement_type,
                    'points_awarded': achievement.points_awarded,
                    'rank': achievement.rank,
                    'awarded_at': achievement.awarded_at.isoformat()
                }
                for achievement in achievements
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting contest history for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get contest history: {e}")
    
    def calculate_contest_rewards(self, contest_id: str) -> List[Dict[str, Any]]:
        """Calculate and distribute contest rewards."""
        try:
            self.validate_input(contest_id=contest_id)
            
            # Get contest leaderboard
            leaderboard = self.get_contest_leaderboard(contest_id)
            
            # Get contest rewards configuration
            from api.gamification.models import ContestReward
            rewards = ContestReward.objects.filter(contest_cycle_id=contest_id, is_active=True)
            
            calculated_rewards = []
            
            for reward in rewards:
                # Get users in reward rank range
                eligible_users = [
                    entry for entry in leaderboard
                    if reward.rank_from <= entry['rank'] <= reward.rank_to
                ]
                
                for user_entry in eligible_users:
                    calculated_rewards.append({
                        'user_id': user_entry['user_id'],
                        'username': user_entry['username'],
                        'rank': user_entry['rank'],
                        'reward_type': reward.reward_type,
                        'points_bonus': reward.points_bonus,
                        'reward_title': reward.title,
                        'reward_description': reward.description
                    })
            
            return calculated_rewards
            
        except Exception as e:
            self.logger.error(f"Error calculating contest rewards for {contest_id}: {e}")
            raise GamificationServiceError(f"Failed to calculate contest rewards: {e}")


class GamificationSummaryUseCase(BaseUseCase):
    """Use case for comprehensive gamification summaries."""
    
    def __init__(self):
        super().__init__()
        self.badge_use_case = BadgeUseCase()
        self.streak_use_case = StreakUseCase()
        self.challenge_use_case = ChallengeUseCase()
        self.level_use_case = LevelUseCase()
        self.contest_use_case = ContestUseCase()
    
    def get_user_gamification_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive gamification summary for user."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get summary from helper
            summary = UserHelper.get_user_gamification_summary(user_id)
            
            # Add additional data
            summary['badge_summary'] = self.badge_use_case.get_user_badge_summary(user_id)
            summary['streak_info'] = self.streak_use_case.get_user_streak_info(user_id)
            summary['level_info'] = self.level_use_case.get_user_level_info(user_id)
            summary['challenge_stats'] = self.challenge_use_case.get_challenge_statistics(user_id)
            summary['contest_history'] = self.contest_use_case.get_user_contest_history(user_id)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting gamification summary for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get gamification summary: {e}")
    
    def get_system_gamification_stats(self) -> Dict[str, Any]:
        """Get system-wide gamification statistics."""
        try:
            from django.db.models import Count, Sum, Avg
            
            # Badge statistics
            badge_stats = {
                'total_badges': Badge.objects.count(),
                'active_badges': Badge.objects.filter(is_active=True).count(),
                'total_user_badges': UserBadge.objects.count(),
                'awarded_badges': UserBadge.objects.count(),
            }
            
            # Challenge statistics
            challenge_stats = {
                'total_challenges': DailyChallenge.objects.count(),
                'active_challenges': DailyChallenge.objects.filter(is_active=True).count(),
                'completed_challenges': UserDailyChallenge.objects.filter(is_completed=True).count(),
                'total_user_challenges': UserDailyChallenge.objects.count(),
            }
            
            # Streak statistics
            streak_stats = {
                'total_streaks': Streak.objects.count(),
                'active_streaks': Streak.objects.filter(is_active=True).count(),
                'average_current_days': Streak.objects.aggregate(avg=Avg('current_days'))['avg'] or 0,
                'average_longest_days': Streak.objects.aggregate(avg=Avg('longest_days'))['avg'] or 0,
            }
            
            # Achievement statistics
            achievement_stats = {
                'total_achievements': UserAchievement.objects.count(),
                'awarded_achievements': UserAchievement.objects.filter(is_awarded=True).count(),
                'total_points_awarded': UserAchievement.objects.filter(is_awarded=True).aggregate(total=Sum('points_awarded'))['total'] or 0,
                'average_points_per_achievement': UserAchievement.objects.filter(is_awarded=True).aggregate(avg=Avg('points_awarded'))['avg'] or 0,
            }
            
            # User statistics
            user_stats = {
                'users_with_badges': UserBadge.objects.values('user').distinct().count(),
                'users_with_achievements': UserAchievement.objects.filter(is_awarded=True).values('user').distinct().count(),
                'users_with_streaks': Streak.objects.values('user').distinct().count(),
                'total_users': User.objects.count(),
            }
            
            return {
                'badges': badge_stats,
                'challenges': challenge_stats,
                'streaks': streak_stats,
                'achievements': achievement_stats,
                'users': user_stats,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system gamification stats: {e}")
            raise GamificationServiceError(f"Failed to get system stats: {e}")
    
    def get_leaderboard_data(self, contest_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get leaderboard data."""
        try:
            self.validate_input(limit=limit)
            
            if contest_id:
                # Contest-specific leaderboard
                leaderboard = self.contest_use_case.get_contest_leaderboard(contest_id, limit)
                contest = ContestCycle.objects.get(id=contest_id)
                
                return {
                    'type': 'contest',
                    'contest_id': contest_id,
                    'contest_name': contest.name,
                    'leaderboard': leaderboard,
                    'total_participants': len(leaderboard)
                }
            else:
                # Global leaderboard
                from django.db.models import Sum
                
                global_leaderboard = (
                    UserAchievement.objects
                    .filter(is_awarded=True)
                    .values('user_id')
                    .annotate(total_points=Sum('points_awarded'))
                    .order_by('-total_points')[:limit]
                )
                
                leaderboard_data = []
                for rank, data in enumerate(global_leaderboard, 1):
                    user = User.objects.get(id=data['user_id'])
                    leaderboard_data.append({
                        'rank': rank,
                        'user_id': str(data['user_id']),
                        'username': user.username,
                        'total_points': data['total_points']
                    })
                
                return {
                    'type': 'global',
                    'leaderboard': leaderboard_data,
                    'total_participants': len(leaderboard_data)
                }
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard data: {e}")
            raise GamificationServiceError(f"Failed to get leaderboard data: {e}")


# Use case factory for creating use cases
class UseCaseFactory:
    """Factory for creating use cases."""
    
    @staticmethod
    def create_badge_use_case() -> BadgeUseCase:
        """Create badge use case."""
        return BadgeUseCase()
    
    @staticmethod
    def create_streak_use_case() -> StreakUseCase:
        """Create streak use case."""
        return StreakUseCase()
    
    @staticmethod
    def create_challenge_use_case() -> ChallengeUseCase:
        """Create challenge use case."""
        return ChallengeUseCase()
    
    @staticmethod
    def create_level_use_case() -> LevelUseCase:
        """Create level use case."""
        return LevelUseCase()
    
    @staticmethod
    def create_contest_use_case() -> ContestUseCase:
        """Create contest use case."""
        return ContestUseCase()
    
    @staticmethod
    def create_summary_use_case() -> GamificationSummaryUseCase:
        """Create summary use case."""
        return GamificationSummaryUseCase()


# Convenience functions for common use cases
def get_user_gamification_summary(user_id: str) -> Dict[str, Any]:
    """Get user's gamification summary."""
    use_case = UseCaseFactory.create_summary_use_case()
    return use_case.get_user_gamification_summary(user_id)


def get_system_gamification_stats() -> Dict[str, Any]:
    """Get system-wide gamification statistics."""
    use_case = UseCaseFactory.create_summary_use_case()
    return use_case.get_system_gamification_stats()


def get_leaderboard_data(contest_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Get leaderboard data."""
    use_case = UseCaseFactory.create_summary_use_case()
    return use_case.get_leaderboard_data(contest_id, limit)
