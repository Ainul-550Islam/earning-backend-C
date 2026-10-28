"""
Streak Service — Streak maintenance and reward functionality.

Handles streak tracking, maintenance, and reward distribution.
All operations are atomic and include comprehensive validation.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, List, Optional, Dict, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import Streak, StreakReward, UserBadge
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
)
from api.gamification.signals import streak_updated

logger = logging.getLogger(__name__)
User = get_user_model()


class StreakService:
    """
    Service class for streak operations.
    
    Provides methods for tracking user streaks, updating activity,
    and managing streak rewards.
    """
    
    @staticmethod
    def get_or_create_user_streak(user_id: Any) -> Streak:
        """
        Get or create a streak for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Streak instance for the user
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        streak, created = Streak.objects.get_or_create(
            user=user,
            defaults={
                "current_days": 0,
                "longest_days": 0,
                "is_active": True,
                "metadata": {"created_via": "service_call"},
            }
        )
        
        if created:
            logger.info(
                "StreakService.get_or_create_user_streak: created new streak for user=%s",
                user_id,
            )
        
        return streak
    
    @staticmethod
    def update_user_activity(
        user_id: Any,
        activity_date: Optional[date] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Streak, bool, int]:
        """
        Update a user's streak based on activity.
        
        Args:
            user_id: User identifier
            activity_date: Date of activity (defaults to today)
            metadata: Additional context about the activity
            
        Returns:
            Tuple of (Streak instance, was_extended, days_added)
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        if activity_date is None:
            activity_date = date.today()
        
        # Validate activity date
        if activity_date > date.today():
            raise GamificationServiceError("Activity date cannot be in the future")
        
        with transaction.atomic():
            streak = StreakService.get_or_create_user_streak(user_id)
            
            # Store previous state
            previous_days = streak.current_days
            previous_active = streak.is_active
            
            # Update the streak
            was_extended, days_added = streak.update_activity()
            
            # Update metadata
            if metadata:
                current_metadata = streak.metadata or {}
                current_metadata.update({
                    "last_activity": {
                        "date": activity_date.isoformat(),
                        "metadata": metadata,
                        "was_extended": was_extended,
                        "days_added": days_added,
                    },
                    "last_updated": timezone.now().isoformat(),
                })
                streak.metadata = current_metadata
                streak.save(update_fields=['metadata', 'updated_at'])
            
            # Send streak updated signal if there was a change
            if previous_days != streak.current_days or previous_active != streak.is_active:
                streak_updated.send(
                    sender=None,
                    user_id=user_id,
                    streak_days=streak.current_days,
                    was_extended=was_extended,
                )
            
            logger.info(
                "StreakService.update_user_activity: user=%s streak=%d days (extended=%s, added=%d)",
                user_id,
                streak.current_days,
                was_extended,
                days_added,
            )
            
            return streak, was_extended, days_added
    
    @staticmethod
    def reset_user_streak(user_id: Any, reason: Optional[str] = None) -> Streak:
        """
        Reset a user's streak to 0.
        
        Args:
            user_id: User identifier
            reason: Reason for resetting the streak
            
        Returns:
            Updated Streak instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        with transaction.atomic():
            streak = StreakService.get_or_create_user_streak(user_id)
            
            # Store previous state
            previous_days = streak.current_days
            
            # Reset the streak
            streak.reset_streak()
            
            # Update metadata
            current_metadata = streak.metadata or {}
            current_metadata.update({
                "reset_info": {
                    "reason": reason or "manual_reset",
                    "previous_days": previous_days,
                    "reset_date": date.today().isoformat(),
                },
                "last_updated": timezone.now().isoformat(),
            })
            streak.metadata = current_metadata
            streak.save(update_fields=['metadata', 'updated_at'])
            
            # Send streak updated signal
            streak_updated.send(
                sender=None,
                user_id=user_id,
                streak_days=streak.current_days,
                was_extended=False,
            )
            
            logger.info(
                "StreakService.reset_user_streak: reset streak for user=%s (reason=%s, previous_days=%d)",
                user_id,
                reason or "manual_reset",
                previous_days,
            )
            
            return streak
    
    @staticmethod
    def check_streak_rewards(user_id: Any, streak_days: Optional[int] = None) -> List[StreakReward]:
        """
        Check which streak rewards a user is eligible for.
        
        Args:
            user_id: User identifier
            streak_days: Specific streak days to check (uses current streak if None)
            
        Returns:
            List of eligible StreakReward instances
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        if streak_days is None:
            streak = StreakService.get_or_create_user_streak(user_id)
            streak_days = streak.current_days
        
        # Get rewards user has already received (via badges)
        received_reward_ids = []
        user_badges = UserBadge.objects.filter(user=user).select_related('badge')
        for ub in user_badges:
            # Check if this badge was awarded via streak milestone
            if ub.metadata.get("awarded_via") == "streak_milestone":
                received_reward_ids.extend(
                    StreakReward.objects.filter(badge=ub.badge).values_list('id', flat=True)
                )
        
        # Find eligible rewards
        eligible_rewards = StreakReward.objects.filter(
            is_active=True,
            streak_days__lte=streak_days
        ).exclude(id__in=received_reward_ids)
        
        return list(eligible_rewards.order_by('-streak_days'))
    
    @staticmethod
    def award_streak_rewards(user_id: Any, streak_days: Optional[int] = None) -> List[UserBadge]:
        """
        Award all eligible streak rewards to a user.
        
        Args:
            user_id: User identifier
            streak_days: Specific streak days to check (uses current streak if None)
            
        Returns:
            List of awarded UserBadge instances
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        eligible_rewards = StreakService.check_streak_rewards(user_id, streak_days)
        awarded_badges = []
        
        with transaction.atomic():
            for reward in eligible_rewards:
                try:
                    if reward.badge:
                        # Check if user already has this badge
                        if UserBadge.objects.filter(
                            user_id=user_id,
                            badge=reward.badge
                        ).exists():
                            continue  # Already awarded
                        
                        user_badge = UserBadge.objects.create(
                            user_id=user_id,
                            badge=reward.badge,
                            metadata={
                                "awarded_via": "streak_milestone",
                                "streak_days": reward.streak_days,
                                "reward_id": reward.id,
                                "points_bonus": reward.points_bonus,
                            },
                        )
                        awarded_badges.append(user_badge)
                        
                        logger.info(
                            "StreakService.award_streak_rewards: awarded badge=%s to user=%s for %d-day streak",
                            reward.badge.id,
                            user_id,
                            reward.streak_days,
                        )
                
                except Exception as exc:
                    logger.warning(
                        "Failed to award streak reward=%s to user=%s: %s",
                        reward.id,
                        user_id,
                        exc,
                    )
                    continue
        
        return awarded_badges
    
    @staticmethod
    def get_streak_leaderboard(limit: int = 10, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get streak leaderboard.
        
        Args:
            limit: Maximum number of users to return
            active_only: Only include users with active streaks
            
        Returns:
            List of user statistics dictionaries
        """
        queryset = Streak.objects.all()
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        streaks = queryset.select_related('user').order_by('-current_days', '-longest_days')[:limit]
        
        leaderboard = []
        for streak in streaks:
            leaderboard.append({
                "user_id": streak.user_id,
                "username": streak.user.username,
                "current_days": streak.current_days,
                "longest_days": streak.longest_days,
                "last_activity_date": streak.last_activity_date,
                "days_until_reset": streak.days_until_reset,
                "is_expired": streak.is_expired,
            })
        
        return leaderboard
    
    @staticmethod
    def get_streak_statistics(user_id: Any) -> Dict[str, Any]:
        """
        Get comprehensive streak statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with streak statistics
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        streak = StreakService.get_or_create_user_streak(user_id)
        
        # Calculate additional statistics
        total_days = (date.today() - (streak.last_activity_date or date.today())).days + 1
        
        stats = {
            "current_days": streak.current_days,
            "longest_days": streak.longest_days,
            "is_active": streak.is_active,
            "last_activity_date": streak.last_activity_date,
            "days_until_reset": streak.days_until_reset,
            "is_expired": streak.is_expired,
            "total_tracked_days": total_days,
            "current_streak_percentage": (streak.current_days / streak.longest_days * 100) if streak.longest_days > 0 else 0,
            "available_rewards": StreakService.check_streak_rewards(user_id, streak.current_days),
            "metadata": streak.metadata,
        }
        
        return stats
    
    @staticmethod
    def get_users_with_expiring_streaks(grace_period_days: int = 1) -> List[Streak]:
        """
        Get users whose streaks will expire soon.
        
        Args:
            grace_period_days: Number of days before expiration to include
            
        Returns:
            List of Streak instances that will expire soon
        """
        cutoff_date = date.today() - timedelta(days=grace_period_days)
        
        expiring_streaks = Streak.objects.filter(
            is_active=True,
            last_activity_date__lte=cutoff_date,
            last_activity_date__gte=date.today() - timedelta(days=2)  # Only recent activity
        ).select_related('user')
        
        return list(expiring_streaks)
    
    @staticmethod
    def cleanup_expired_streaks() -> int:
        """
        Clean up streaks that have been expired for more than 30 days.
        
        Returns:
            Number of streaks cleaned up
        """
        cutoff_date = date.today() - timedelta(days=30)
        
        with transaction.atomic():
            count = Streak.objects.filter(
                is_active=False,
                last_activity_date__lt=cutoff_date
            ).update(is_active=False)
        
        logger.info(
            "StreakService.cleanup_expired_streaks: cleaned up %d expired streaks",
            count,
        )
        
        return count
    
    @staticmethod
    def get_streak_milestones(user_id: Any) -> List[Dict[str, Any]]:
        """
        Get streak milestone information for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of milestone dictionaries
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        streak = StreakService.get_or_create_user_streak(user_id)
        
        # Get all streak rewards as milestones
        all_rewards = StreakReward.objects.filter(is_active=True).order_by('streak_days')
        
        milestones = []
        for reward in all_rewards:
            # Check if user has received this reward
            received = UserBadge.objects.filter(
                user=user,
                badge=reward.badge,
                metadata__awarded_via="streak_milestone"
            ).exists() if reward.badge else False
            
            milestones.append({
                "streak_days": reward.streak_days,
                "title": reward.title,
                "description": reward.description,
                "points_bonus": reward.points_bonus,
                "badge_id": reward.badge_id if reward.badge else None,
                "badge_name": reward.badge.name if reward.badge else None,
                "received": received,
                "achieved": streak.current_days >= reward.streak_days,
                "progress_percentage": min(100.0, (streak.current_days / reward.streak_days * 100)) if reward.streak_days > 0 else 0,
            })
        
        return milestones
