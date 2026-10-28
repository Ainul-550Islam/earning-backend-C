"""
Daily Challenge Service — Daily challenge generation, tracking, and completion.

Handles creation of daily challenges, progress tracking, and completion logic.
All operations are atomic and include comprehensive validation.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, List, Optional, Dict, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import DailyChallenge, UserDailyChallenge
from api.gamification.choices import ChallengeAction
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
    DuplicateAchievementError,
)
from api.gamification.signals import daily_challenge_completed

logger = logging.getLogger(__name__)
User = get_user_model()


class DailyChallengeService:
    """
    Service class for daily challenge operations.
    
    Provides methods for creating challenges, tracking progress,
    and managing challenge completion.
    """
    
    @staticmethod
    def create_daily_challenge(
        title: str,
        description: str,
        target_action: str,
        target_count: int,
        bonus_points: int,
        challenge_date: Optional[date] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DailyChallenge:
        """
        Create a new daily challenge.
        
        Args:
            title: Challenge title
            description: Challenge description
            target_action: Type of action that counts toward the challenge
            target_count: Number of actions required to complete
            bonus_points: Points awarded for completion
            challenge_date: Date for the challenge (defaults to today)
            metadata: Additional challenge configuration
            
        Returns:
            Created DailyChallenge instance
            
        Raises:
            GamificationServiceError: If validation fails
        """
        if not title or not title.strip():
            raise GamificationServiceError("title must be a non-empty string")
        
        if target_action not in ChallengeAction.values:
            raise GamificationServiceError(
                f"Invalid target_action '{target_action}'. Valid choices: {ChallengeAction.values}"
            )
        
        if target_count < 1 or target_count > 1000:
            raise GamificationServiceError("target_count must be between 1 and 1000")
        
        if bonus_points < 0 or bonus_points > 10000:
            raise GamificationServiceError("bonus_points must be between 0 and 10000")
        
        if challenge_date is None:
            challenge_date = date.today()
        
        # Check if challenge already exists for this date and action
        if DailyChallenge.objects.filter(
            date=challenge_date,
            target_action=target_action
        ).exists():
            raise GamificationServiceError(
                f"Challenge already exists for date={challenge_date} and action={target_action}"
            )
        
        with transaction.atomic():
            challenge = DailyChallenge.objects.create(
                title=title.strip(),
                description=description.strip(),
                target_action=target_action,
                target_count=target_count,
                bonus_points=bonus_points,
                date=challenge_date,
                metadata=metadata or {},
            )
            
            logger.info(
                "DailyChallengeService.create_daily_challenge: created challenge=%s for date=%s",
                challenge.id,
                challenge_date,
            )
            
            return challenge
    
    @staticmethod
    def get_active_challenges(
        challenge_date: Optional[date] = None,
        target_action: Optional[str] = None,
    ) -> List[DailyChallenge]:
        """
        Get active daily challenges for a specific date.
        
        Args:
            challenge_date: Date to get challenges for (defaults to today)
            target_action: Filter by specific action type
            
        Returns:
            List of active DailyChallenge instances
        """
        queryset = DailyChallenge.objects.filter(is_active=True)
        if challenge_date is not None:
            queryset = queryset.filter(date=challenge_date)
        elif DailyChallenge.objects.filter(date__isnull=False).exists():
            # Only filter by date if some challenges have dates
            challenge_date = date.today()
            queryset = queryset.filter(date=challenge_date)
        # If all challenges have date=None, return all active ones
        
        if target_action is not None:
            queryset = queryset.filter(target_action=target_action)
        
        return list(queryset.order_by('target_action'))
    
    @staticmethod
    def get_user_challenge_progress(
        user_id: Any,
        challenge_id: Optional[Any] = None,
        challenge_date: Optional[date] = None,
    ) -> List[UserDailyChallenge]:
        """
        Get a user's progress on daily challenges.
        
        Args:
            user_id: User identifier
            challenge_id: Specific challenge to get progress for
            challenge_date: Get progress for all challenges on this date
            
        Returns:
            List of UserDailyChallenge instances
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        queryset = UserDailyChallenge.objects.filter(user=user)
        
        if challenge_id is not None:
            queryset = queryset.filter(challenge_id=challenge_id)
        elif challenge_date is not None:
            queryset = queryset.filter(challenge__date=challenge_date)
        
        return list(queryset.select_related('challenge').order_by('-created_at'))
    
    @staticmethod
    def start_user_challenge(
        user_id: Any,
        challenge_id: Any,
    ) -> UserDailyChallenge:
        """
        Start a user's progress on a daily challenge.
        
        Args:
            user_id: User identifier
            challenge_id: Challenge identifier
            
        Returns:
            Created UserDailyChallenge instance
            
        Raises:
            UserNotFoundError: If user doesn't exist
            GamificationServiceError: If challenge doesn't exist or is inactive
            DuplicateAchievementError: If user already started this challenge
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        try:
            challenge = DailyChallenge.objects.get(pk=challenge_id, is_active=True)
        except DailyChallenge.DoesNotExist:
            raise GamificationServiceError(f"Active challenge {challenge_id} not found")
        
        # Check if user already has this challenge
        if UserDailyChallenge.objects.filter(user=user, challenge=challenge).exists():
            raise DuplicateAchievementError(
                f"User {user_id} already has challenge {challenge_id}"
            )
        
        with transaction.atomic():
            user_challenge = UserDailyChallenge.objects.create(
                user=user,
                challenge=challenge,
                progress=0,
                metadata={"started_via": "service_call"},
            )
            
            logger.info(
                "DailyChallengeService.start_user_challenge: user=%s started challenge=%s",
                user_id,
                challenge_id,
            )
            
            return user_challenge
    
    @staticmethod
    def update_challenge_progress(
        user_id: Any,
        challenge_id: Any,
        increment_amount: int = 1,
        action_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[UserDailyChallenge, bool]:
        """
        Update a user's progress on a daily challenge.
        
        Args:
            user_id: User identifier
            challenge_id: Challenge identifier
            increment_amount: Amount to increment progress by
            action_metadata: Additional context about the action
            
        Returns:
            Tuple of (updated UserDailyChallenge instance, was_completed)
            
        Raises:
            UserNotFoundError: If user doesn't exist
            GamificationServiceError: If challenge doesn't exist or user hasn't started it
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        try:
            user_challenge = UserDailyChallenge.objects.get(
                user=user,
                challenge_id=challenge_id
            )
        except UserDailyChallenge.DoesNotExist:
            raise GamificationServiceError(
                f"User {user_id} hasn't started challenge {challenge_id}"
            )
        
        if increment_amount <= 0:
            raise GamificationServiceError("increment_amount must be positive")
        
        with transaction.atomic():
            was_completed = user_challenge.is_completed
            completed_now = user_challenge.increment_progress(increment_amount)
            
            # Update metadata
            if action_metadata:
                current_metadata = user_challenge.metadata or {}
                current_metadata.update({
                    "last_action": action_metadata,
                    "last_increment": increment_amount,
                    "last_updated": timezone.now().isoformat(),
                })
                user_challenge.metadata = current_metadata
                user_challenge.save(update_fields=['metadata', 'updated_at'])
            
            # If just completed, send completion signal
            if completed_now and not was_completed:
                daily_challenge_completed.send(
                    sender=None,
                    user_id=user_id,
                    challenge_id=challenge_id,
                    user_challenge_id=user_challenge.id,
                )
                
                logger.info(
                    "DailyChallengeService.update_challenge_progress: user=%s completed challenge=%s",
                    user_id,
                    challenge_id,
                )
            
            return user_challenge, completed_now
    
    @staticmethod
    def auto_start_active_challenges(user_id: Any) -> List[UserDailyChallenge]:
        """
        Automatically start all active challenges for a user for today.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of created UserDailyChallenge instances
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        active_challenges = DailyChallengeService.get_active_challenges()
        started_challenges = []
        
        with transaction.atomic():
            for challenge in active_challenges:
                # Check if user already has this challenge
                if not UserDailyChallenge.objects.filter(
                    user=user,
                    challenge=challenge
                ).exists():
                    user_challenge = UserDailyChallenge.objects.create(
                        user=user,
                        challenge=challenge,
                        progress=0,
                        metadata={"started_via": "auto_start"},
                    )
                    started_challenges.append(user_challenge)
        
        logger.info(
            "DailyChallengeService.auto_start_active_challenges: started %d challenges for user=%s",
            len(started_challenges),
            user_id,
        )
        
        return started_challenges
    
    @staticmethod
    def get_challenge_statistics(
        user_id: Any,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get comprehensive challenge statistics for a user.
        
        Args:
            user_id: User identifier
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with challenge statistics
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        start_date = date.today() - timedelta(days=days)
        
        user_challenges = UserDailyChallenge.objects.filter(
            user=user,
            created_at__date__gte=start_date
        ).select_related('challenge')
        
        total_challenges = user_challenges.count()
        completed_challenges = user_challenges.filter(completed_at__isnull=False).count()
        
        stats = {
            "period_days": days,
            "total_challenges": total_challenges,
            "completed_challenges": completed_challenges,
            "completion_rate": (completed_challenges / total_challenges * 100) if total_challenges > 0 else 0,
            "total_bonus_points": sum(
                uc.challenge.bonus_points 
                for uc in user_challenges.filter(completed_at__isnull=False)
            ),
            "by_action_type": {},
            "daily_completion": {},
            "recent_challenges": user_challenges.order_by('-created_at')[:5],
        }
        
        # Count by action type
        for uc in user_challenges:
            action_type = uc.challenge.target_action
            if action_type not in stats["by_action_type"]:
                stats["by_action_type"][action_type] = {"total": 0, "completed": 0}
            stats["by_action_type"][action_type]["total"] += 1
            if uc.is_completed:
                stats["by_action_type"][action_type]["completed"] += 1
        
        # Daily completion breakdown
        for uc in user_challenges:
            day = uc.created_at.date().isoformat()
            if day not in stats["daily_completion"]:
                stats["daily_completion"][day] = {"total": 0, "completed": 0}
            stats["daily_completion"][day]["total"] += 1
            if uc.is_completed:
                stats["daily_completion"][day]["completed"] += 1
        
        return stats
    
    @staticmethod
    def get_leaderboard(
        challenge_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard for daily challenges on a specific date.
        
        Args:
            challenge_date: Date to get leaderboard for (defaults to today)
            limit: Maximum number of users to return
            
        Returns:
            List of user statistics dictionaries
        """
        if challenge_date is None:
            challenge_date = date.today()
        
        # Get all user challenges for this date
        user_challenges = UserDailyChallenge.objects.filter(
            challenge__date=challenge_date,
            completed_at__isnull=False
        ).select_related('user', 'challenge')
        
        # Aggregate by user
        user_stats = {}
        for uc in user_challenges:
            user_id = uc.user_id
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "user_id": user_id,
                    "username": uc.user.username,
                    "completed_challenges": 0,
                    "total_bonus_points": 0,
                    "completed_at": uc.completed_at,
                }
            
            user_stats[user_id]["completed_challenges"] += 1
            user_stats[user_id]["total_bonus_points"] += uc.challenge.bonus_points
            
            # Keep the latest completion time
            if uc.completed_at > user_stats[user_id]["completed_at"]:
                user_stats[user_id]["completed_at"] = uc.completed_at
        
        # Sort by completed challenges, then bonus points, then completion time
        leaderboard = sorted(
            user_stats.values(),
            key=lambda x: (-x["completed_challenges"], -x["total_bonus_points"], x["completed_at"])
        )
        
        return leaderboard[:limit]
    
    @staticmethod
    def deactivate_expired_challenges() -> int:
        """
        Deactivate challenges that are older than 7 days.
        
        Returns:
            Number of challenges deactivated
        """
        cutoff_date = date.today() - timedelta(days=7)
        
        with transaction.atomic():
            count = DailyChallenge.objects.filter(
                date__lt=cutoff_date,
                is_active=True
            ).update(is_active=False)
        
        logger.info(
            "DailyChallengeService.deactivate_expired_challenges: deactivated %d challenges",
            count,
        )
        
        return count
