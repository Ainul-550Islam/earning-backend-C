"""
Badge Service — Badge checking and awarding functionality.

Handles badge eligibility checking, awarding, and management operations.
All operations are atomic and include comprehensive validation.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import Badge, UserBadge, Streak
from api.gamification.choices import BadgeCriteriaType
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
    DuplicateAchievementError,
)
from api.gamification.signals import badge_earned

logger = logging.getLogger(__name__)
User = get_user_model()


class BadgeService:
    """
    Service class for badge-related operations.
    
    Provides methods for checking badge eligibility, awarding badges,
    and managing user badge collections.
    """
    
    @staticmethod
    def check_user_badge_eligibility(
        user_id: Any,
        user_points: int = 0,
        streak_days: int = 0,
        achievement_count: int = 0,
        contest_wins: int = 0,
        referral_count: int = 0,
    ) -> List[Badge]:
        """
        Check which badges a user is eligible for based on their stats.
        
        Args:
            user_id: User identifier
            user_points: Total points earned by user
            streak_days: Current streak days
            achievement_count: Number of achievements earned
            contest_wins: Number of contest wins
            referral_count: Number of successful referrals
            
        Returns:
            List of Badge objects the user is eligible for but hasn't earned yet
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        # Get badges user already has
        earned_badge_ids = UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
        
        # Find eligible badges
        eligible_badges = []
        
        # Points-based badges
        points_badges = Badge.objects.filter(
            is_active=True,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value__lte=user_points
        ).exclude(id__in=earned_badge_ids)
        
        for badge in points_badges:
            if badge.is_unlocked_by_user(user_points=user_points, streak_days=streak_days):
                eligible_badges.append(badge)
        
        # Streak-based badges
        streak_badges = Badge.objects.filter(
            is_active=True,
            criteria_type=BadgeCriteriaType.STREAK_DAYS,
            criteria_value__lte=streak_days
        ).exclude(id__in=earned_badge_ids)
        
        for badge in streak_badges:
            if badge.is_unlocked_by_user(user_points=user_points, streak_days=streak_days):
                eligible_badges.append(badge)
        
        # Achievement count badges
        achievement_badges = Badge.objects.filter(
            is_active=True,
            criteria_type=BadgeCriteriaType.ACHIEVEMENT_COUNT,
            criteria_value__lte=achievement_count
        ).exclude(id__in=earned_badge_ids)
        
        eligible_badges.extend(achievement_badges)
        
        # Contest win badges
        contest_badges = Badge.objects.filter(
            is_active=True,
            criteria_type=BadgeCriteriaType.CONTEST_WINS,
            criteria_value__lte=contest_wins
        ).exclude(id__in=earned_badge_ids)
        
        eligible_badges.extend(contest_badges)
        
        # Referral badges
        referral_badges = Badge.objects.filter(
            is_active=True,
            criteria_type=BadgeCriteriaType.REFERRAL_COUNT,
            criteria_value__lte=referral_count
        ).exclude(id__in=earned_badge_ids)
        
        eligible_badges.extend(referral_badges)
        
        # Remove duplicates and sort by rarity and name
        unique_badges = list({badge.id: badge for badge in eligible_badges}.values())
        unique_badges.sort(key=lambda b: (b.rarity, b.name))
        
        logger.info(
            "BadgeService.check_user_badge_eligibility: user=%s found %d eligible badges",
            user_id,
            len(unique_badges)
        )
        
        return unique_badges
    
    @staticmethod
    def award_badge_to_user(
        user_id: Any,
        badge_id: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserBadge:
        """
        Award a specific badge to a user.
        
        Args:
            user_id: User identifier
            badge_id: Badge identifier
            metadata: Additional context data about how the badge was earned
            
        Returns:
            Created UserBadge instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
            GamificationServiceError: If badge doesn't exist or is inactive
            DuplicateAchievementError: If user already has this badge
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        try:
            badge = Badge.objects.get(pk=badge_id, is_active=True)
        except Badge.DoesNotExist:
            raise GamificationServiceError(f"Active badge {badge_id} not found")
        
        # Check if user already has this badge
        if UserBadge.objects.filter(user=user, badge=badge).exists():
            raise DuplicateAchievementError(
                f"User {user_id} already has badge {badge_id}"
            )
        
        with transaction.atomic():
            user_badge = UserBadge.objects.create(
                user=user,
                badge=badge,
                metadata=metadata or {},
            )
            
            # Send badge earned signal
            badge_earned.send(
                sender=None,
                user_id=user_id,
                badge_id=badge_id,
                user_badge_id=user_badge.id,
            )
            
            logger.info(
                "BadgeService.award_badge_to_user: awarded badge=%s to user=%s",
                badge_id,
                user_id,
            )
            
            return user_badge
    
    @staticmethod
    def award_eligible_badges(
        user_id: Any,
        user_points: int = 0,
        streak_days: int = 0,
        achievement_count: int = 0,
        contest_wins: int = 0,
        referral_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[UserBadge]:
        """
        Award all eligible badges to a user in a single transaction.
        
        Args:
            user_id: User identifier
            user_points: Total points earned by user
            streak_days: Current streak days
            achievement_count: Number of achievements earned
            contest_wins: Number of contest wins
            referral_count: Number of successful referrals
            metadata: Additional context data about how badges were earned
            
        Returns:
            List of created UserBadge instances
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=user_id,
            user_points=user_points,
            streak_days=streak_days,
            achievement_count=achievement_count,
            contest_wins=contest_wins,
            referral_count=referral_count,
        )
        
        awarded_badges = []
        
        with transaction.atomic():
            for badge in eligible_badges:
                try:
                    badge_metadata = {
                        **(metadata or {}),
                        "awarded_via": "bulk_eligibility_check",
                        "user_points": user_points,
                        "streak_days": streak_days,
                    }
                    
                    user_badge = BadgeService.award_badge_to_user(
                        user_id=user_id,
                        badge_id=badge.id,
                        metadata=badge_metadata,
                    )
                    awarded_badges.append(user_badge)
                    
                except DuplicateAchievementError:
                    # Skip if already earned (shouldn't happen with eligibility check)
                    continue
                except Exception as exc:
                    logger.warning(
                        "Failed to award badge=%s to user=%s: %s",
                        badge.id,
                        user_id,
                        exc,
                    )
                    continue
        
        logger.info(
            "BadgeService.award_eligible_badges: awarded %d badges to user=%s",
            len(awarded_badges),
            user_id,
        )
        
        return awarded_badges
    
    @staticmethod
    def get_user_badges(
        user_id: Any,
        is_pinned: Optional[bool] = None,
        rarity: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[UserBadge]:
        """
        Get badges for a user with optional filtering.
        
        Args:
            user_id: User identifier
            is_pinned: Filter by pinned status (None for all)
            rarity: Filter by badge rarity (None for all)
            limit: Maximum number of badges to return
            
        Returns:
            List of UserBadge instances ordered by earned_at (newest first)
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        queryset = UserBadge.objects.filter(user=user)
        
        if is_pinned is not None:
            queryset = queryset.filter(is_pinned=is_pinned)
        
        if rarity is not None:
            queryset = queryset.filter(badge__rarity=rarity)
        
        queryset = queryset.select_related('badge').order_by('-earned_at')
        
        if limit is not None:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    @staticmethod
    def pin_user_badge(user_id: Any, user_badge_id: Any) -> UserBadge:
        """
        Pin a user's badge for display priority.
        
        Args:
            user_id: User identifier
            user_badge_id: UserBadge identifier
            
        Returns:
            Updated UserBadge instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
            GamificationServiceError: If user_badge doesn't exist or doesn't belong to user
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        try:
            user_badge = UserBadge.objects.get(pk=user_badge_id, user=user)
        except UserBadge.DoesNotExist:
            raise GamificationServiceError(
                f"UserBadge {user_badge_id} not found for user {user_id}"
            )
        
        user_badge.is_pinned = True
        user_badge.save(update_fields=['is_pinned', 'updated_at'])
        
        logger.info(
            "BadgeService.pin_user_badge: pinned badge=%s for user=%s",
            user_badge_id,
            user_id,
        )
        
        return user_badge
    
    @staticmethod
    def unpin_user_badge(user_id: Any, user_badge_id: Any) -> UserBadge:
        """
        Unpin a user's badge.
        
        Args:
            user_id: User identifier
            user_badge_id: UserBadge identifier
            
        Returns:
            Updated UserBadge instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
            GamificationServiceError: If user_badge doesn't exist or doesn't belong to user
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        try:
            user_badge = UserBadge.objects.get(pk=user_badge_id, user=user)
        except UserBadge.DoesNotExist:
            raise GamificationServiceError(
                f"UserBadge {user_badge_id} not found for user {user_id}"
            )
        
        user_badge.is_pinned = False
        user_badge.save(update_fields=['is_pinned', 'updated_at'])
        
        logger.info(
            "BadgeService.unpin_user_badge: unpinned badge=%s for user=%s",
            user_badge_id,
            user_id,
        )
        
        return user_badge
    
    @staticmethod
    def get_badge_statistics(user_id: Any) -> Dict[str, Any]:
        """
        Get comprehensive badge statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with badge statistics
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        except (ValueError, TypeError):
            raise UserNotFoundError(f"User {user_id} not found")
        
        badges = UserBadge.objects.filter(user=user).select_related('badge')
        
        stats = {
            "total_badges": badges.count(),
            "pinned_badges": badges.filter(is_pinned=True).count(),
            "by_rarity": {},
            "by_criteria_type": {},
            "recent_badges": badges.order_by('-earned_at')[:5],
            "points_from_badges": sum(badge.badge.points_bonus for badge in badges),
        }
        
        # Count by rarity
        for badge in badges:
            rarity = badge.badge.rarity
            stats["by_rarity"][rarity] = stats["by_rarity"].get(rarity, 0) + 1
        
        # Count by criteria type
        for badge in badges:
            criteria_type = badge.badge.criteria_type
            stats["by_criteria_type"][criteria_type] = stats["by_criteria_type"].get(criteria_type, 0) + 1
        
        return stats
    
    @staticmethod
    def get_available_badges(
        is_active: Optional[bool] = True,
        rarity: Optional[str] = None,
        criteria_type: Optional[str] = None,
    ) -> List[Badge]:
        """
        Get available badges with optional filtering.
        
        Args:
            is_active: Filter by active status
            rarity: Filter by rarity
            criteria_type: Filter by criteria type
            
        Returns:
            List of Badge instances ordered by sort_order and name
        """
        queryset = Badge.objects.all()
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        if rarity is not None:
            queryset = queryset.filter(rarity=rarity)
        
        if criteria_type is not None:
            queryset = queryset.filter(criteria_type=criteria_type)
        
        return list(queryset.order_by('sort_order', 'name'))
