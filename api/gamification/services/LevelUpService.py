"""
Level Up Service — Level progression and management functionality.

Handles level progression, point calculations, and level-up rewards.
All operations are atomic and include comprehensive validation.
"""

from __future__ import annotations
from django.db import models

import logging
from typing import Any, List, Optional, Dict, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import LevelConfig, UserBadge
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
)
from api.gamification.signals import user_leveled_up, badge_earned

logger = logging.getLogger(__name__)
User = get_user_model()


class LevelUpService:
    """
    Service class for level progression operations.
    
    Provides methods for calculating levels, checking progression,
    and managing level-up rewards.
    """
    
    @staticmethod
    def get_user_level(user_points: int) -> Optional[LevelConfig]:
        """
        Get the highest level a user has achieved based on total points.
        
        Args:
            user_points: Total points earned by the user
            
        Returns:
            LevelConfig instance or None if no level achieved
        """
        return LevelConfig.get_level_for_points(user_points)
    
    @staticmethod
    def get_level_progress(user_points: int) -> Dict[str, Any]:
        """
        Get detailed progress information toward the next level.
        
        Args:
            user_points: Total points earned by the user
            
        Returns:
            Dictionary with progress information
        """
        return LevelConfig.get_progress_to_next_level(user_points)
    
    @staticmethod
    def check_level_up(
        user_id: Any,
        old_points: int,
        new_points: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[LevelConfig], Optional[LevelConfig], bool]:
        """
        Check if a user should level up based on point changes.
        
        Args:
            user_id: User identifier
            old_points: Previous total points
            new_points: New total points
            metadata: Additional context about the point change
            
        Returns:
            Tuple of (old_level, new_level, did_level_up)
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        old_level = LevelUpService.get_user_level(old_points)
        new_level = LevelUpService.get_user_level(new_points)
        
        did_level_up = False
        
        if old_level and new_level and new_level.level_number > old_level.level_number:
            did_level_up = True
            
            # Send level-up signal
            user_leveled_up.send(
                sender=None,
                user_id=user_id,
                old_level=old_level.level_number,
                new_level=new_level.level_number,
                level_config_id=new_level.id,
            )
            
            # Award level-up badge if configured
            LevelUpService._award_level_badge(user_id, new_level.id, metadata)
            
            logger.info(
                "LevelUpService.check_level_up: user=%s leveled up from %d to %d",
                user_id,
                old_level.level_number,
                new_level.level_number,
            )
        
        return old_level, new_level, did_level_up
    
    @staticmethod
    def get_user_level_history(user_id: Any) -> Dict[str, Any]:
        """
        Get a user's level progression history.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with level history information
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        # Get all levels the user has badges for (indicating level progression)
        level_badges = UserBadge.objects.filter(
            user=user,
            metadata__awarded_via="level_up"
        ).select_related('badge').order_by('-created_at')
        
        # Get current user points (this would need to be calculated from user's achievements)
        # For now, we'll return what we can determine from badges
        current_level = None
        if level_badges.exists():
            latest_badge = level_badges.first()
            # Try to find the level config associated with this badge
            try:
                current_level = LevelConfig.objects.get(badge=latest_badge.badge)
            except LevelConfig.DoesNotExist:
                pass
        
        return {
            "current_level": current_level,
            "level_badges": list(level_badges),
            "total_levels_achieved": level_badges.count(),
            "highest_level_badge": level_badges.first() if level_badges.exists() else None,
        }
    
    @staticmethod
    def calculate_points_to_next_level(user_points: int) -> int:
        """
        Calculate points needed to reach the next level.
        
        Args:
            user_points: Current total points
            
        Returns:
            Points needed for next level (0 if at max level)
        """
        progress = LevelUpService.get_level_progress(user_points)
        
        if progress.get("is_max_level", False):
            return 0
        
        return progress.get("points_needed", 0)
    
    @staticmethod
    def calculate_level_progress_percentage(user_points: int) -> float:
        """
        Calculate progress percentage toward the next level.
        
        Args:
            user_points: Current total points
            
        Returns:
            Progress percentage (0-100)
        """
        progress = LevelUpService.get_level_progress(user_points)
        
        if progress.get("is_max_level", False):
            return 100.0
        
        return progress.get("progress_percentage", 0.0)
    
    @staticmethod
    def get_level_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get leaderboard of users by level.
        
        Args:
            limit: Maximum number of users to return
            
        Returns:
            List of user statistics dictionaries
        """
        # This is a simplified version - in practice, you'd want to calculate
        # actual user points from their achievements
        from api.gamification.models import UserAchievement
        
        # Get total points per user
        user_points = UserAchievement.objects.filter(
            is_awarded=True,
            points_awarded__gt=0
        ).values('user_id').annotate(
            total_points=models.Sum('points_awarded')
        ).order_by('-total_points')[:limit]
        
        leaderboard = []
        for user_point in user_points:
            level = LevelUpService.get_user_level(user_point['total_points'] or 0)
            progress = LevelUpService.get_level_progress(user_point['total_points'] or 0)
            
            try:
                user = User.objects.get(pk=user_point['user_id'])
                username = user.username
            except User.DoesNotExist:
                username = f"User {user_point['user_id']}"
            
            leaderboard.append({
                "user_id": user_point['user_id'],
                "username": username,
                "total_points": user_point['total_points'] or 0,
                "current_level": level.level_number if level else 0,
                "level_title": level.title if level else "No Level",
                "progress_to_next": progress.get("progress_percentage", 0),
                "is_max_level": progress.get("is_max_level", False),
            })
        
        return leaderboard
    
    @staticmethod
    def get_level_statistics(user_id: Any) -> Dict[str, Any]:
        """
        Get comprehensive level statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with level statistics
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        # Calculate user's total points from achievements
        from api.gamification.models import UserAchievement
        total_points = UserAchievement.objects.filter(
            user=user,
            is_awarded=True
        ).aggregate(
            total=models.Sum('points_awarded')
        )['total'] or 0
        
        current_level = LevelUpService.get_user_level(total_points)
        progress = LevelUpService.get_level_progress(total_points)
        
        # Get level history
        history = LevelUpService.get_user_level_history(user_id)
        
        stats = {
            "total_points": total_points,
            "current_level": current_level.level_number if current_level else 0,
            "current_level_title": current_level.title if current_level else "No Level",
            "points_to_next_level": LevelUpService.calculate_points_to_next_level(total_points),
            "progress_percentage": LevelUpService.calculate_level_progress_percentage(total_points),
            "is_max_level": progress.get("is_max_level", False),
            "level_history": history,
            "total_levels_achieved": history.get("total_levels_achieved", 0),
            "points_multiplier": current_level.points_multiplier if current_level else 1.0,
            "level_perks": current_level.perks if current_level else {},
        }
        
        return stats
    
    @staticmethod
    def get_available_levels(is_active: Optional[bool] = True) -> List[LevelConfig]:
        """
        Get available level configurations.
        
        Args:
            is_active: Filter by active status
            
        Returns:
            List of LevelConfig instances ordered by level number
        """
        queryset = LevelConfig.objects.all()
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        return list(queryset.order_by('level_number'))
    
    @staticmethod
    def create_level_config(
        level_number: int,
        points_required: int,
        title: str,
        description: str = "",
        perks: Optional[Dict[str, Any]] = None,
        points_multiplier: float = 1.0,
        badge_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LevelConfig:
        """
        Create a new level configuration.
        
        Args:
            level_number: Level number (must be unique)
            points_required: Points required to reach this level
            title: Level title
            description: Level description
            perks: Level perks configuration
            points_multiplier: Points multiplier at this level
            badge_id: Optional badge to award for reaching this level
            metadata: Additional level configuration
            
        Returns:
            Created LevelConfig instance
            
        Raises:
            GamificationServiceError: If validation fails
        """
        if not title or not title.strip():
            raise GamificationServiceError("title must be a non-empty string")
        
        if level_number < 1 or level_number > 1000:
            raise GamificationServiceError("level_number must be between 1 and 1000")
        
        if points_required < 0:
            raise GamificationServiceError("points_required must be non-negative")
        
        if points_multiplier < 0.01 or points_multiplier > 5.0:
            raise GamificationServiceError("points_multiplier must be between 0.01 and 5.0")
        
        # Check if level number already exists
        if LevelConfig.objects.filter(level_number=level_number).exists():
            raise GamificationServiceError(f"Level {level_number} already exists")
        
        # Validate points progression
        if level_number > 1:
            prev_level = LevelConfig.objects.filter(level_number=level_number - 1).first()
            if prev_level and points_required <= prev_level.points_required:
                raise GamificationServiceError(
                    f"points_required must be greater than previous level ({prev_level.points_required})"
                )
        
        with transaction.atomic():
            level_config = LevelConfig.objects.create(
                level_number=level_number,
                points_required=points_required,
                title=title.strip(),
                description=description.strip(),
                perks=perks or {},
                points_multiplier=points_multiplier,
                badge_id=badge_id,
                metadata=metadata or {},
            )
            
            logger.info(
                "LevelUpService.create_level_config: created level=%d with %d points required",
                level_number,
                points_required,
            )
            
            return level_config
    
    @staticmethod
    def update_level_config(
        level_id: Any,
        points_required: Optional[int] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        perks: Optional[Dict[str, Any]] = None,
        points_multiplier: Optional[float] = None,
        badge_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LevelConfig:
        """
        Update an existing level configuration.
        
        Args:
            level_id: Level configuration identifier
            points_required: New points required
            title: New title
            description: New description
            perks: New perks configuration
            points_multiplier: New points multiplier
            badge_id: New badge to award
            metadata: New metadata
            
        Returns:
            Updated LevelConfig instance
            
        Raises:
            GamificationServiceError: If level doesn't exist or validation fails
        """
        try:
            level_config = LevelConfig.objects.get(pk=level_id)
        except LevelConfig.DoesNotExist:
            raise GamificationServiceError(f"Level config {level_id} not found")
        
        update_fields = []
        
        if points_required is not None:
            if points_required < 0:
                raise GamificationServiceError("points_required must be non-negative")
            
            # Validate points progression
            if level_config.level_number > 1:
                prev_level = LevelConfig.objects.filter(
                    level_number=level_config.level_number - 1
                ).first()
                if prev_level and points_required <= prev_level.points_required:
                    raise GamificationServiceError(
                        f"points_required must be greater than previous level ({prev_level.points_required})"
                    )
            
            # Check next level if it exists
            next_level = LevelConfig.objects.filter(
                level_number=level_config.level_number + 1
            ).first()
            if next_level and points_required >= next_level.points_required:
                raise GamificationServiceError(
                    f"points_required must be less than next level ({next_level.points_required})"
                )
            
            level_config.points_required = points_required
            update_fields.append('points_required')
        
        if title is not None:
            if not title or not title.strip():
                raise GamificationServiceError("title must be a non-empty string")
            level_config.title = title.strip()
            update_fields.append('title')
        
        if description is not None:
            level_config.description = description.strip()
            update_fields.append('description')
        
        if perks is not None:
            level_config.perks = perks
            update_fields.append('perks')
        
        if points_multiplier is not None:
            if points_multiplier < 0.01 or points_multiplier > 5.0:
                raise GamificationServiceError("points_multiplier must be between 0.01 and 5.0")
            level_config.points_multiplier = points_multiplier
            update_fields.append('points_multiplier')
        
        if badge_id is not None:
            level_config.badge_id = badge_id
            update_fields.append('badge')
        
        if metadata is not None:
            level_config.metadata = metadata
            update_fields.append('metadata')
        
        if update_fields:
            level_config.save(update_fields=update_fields)
            
            logger.info(
                "LevelUpService.update_level_config: updated level=%d fields=%s",
                level_config.level_number,
                update_fields,
            )
        
        return level_config
    
    @staticmethod
    def _award_level_badge(
        user_id: Any,
        level_config_id: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserBadge]:
        """
        Internal method to award a level badge to a user.
        
        Args:
            user_id: User identifier
            level_config_id: Level configuration identifier
            metadata: Additional context
            
        Returns:
            Created UserBadge instance or None if no badge configured
        """
        try:
            level_config = LevelConfig.objects.get(pk=level_config_id)
        except LevelConfig.DoesNotExist:
            return None
        
        if not level_config.badge:
            return None
        
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        # Check if user already has this badge
        if UserBadge.objects.filter(user=user, badge=level_config.badge).exists():
            return None
        
        with transaction.atomic():
            user_badge = UserBadge.objects.create(
                user=user,
                badge=level_config.badge,
                metadata={
                    "awarded_via": "level_up",
                    "level": level_config.level_number,
                    "level_config_id": level_config.id,
                    **(metadata or {}),
                },
            )
            
            # Send badge earned signal
            badge_earned.send(
                sender=None,
                user_id=user_id,
                badge_id=level_config.badge.id,
                user_badge_id=user_badge.id,
            )
            
            logger.info(
                "LevelUpService._award_level_badge: awarded badge=%s to user=%s for level=%d",
                level_config.badge.id,
                user_id,
                level_config.level_number,
            )
            
            return user_badge
    
    @staticmethod
    def get_level_requirements_summary() -> Dict[str, Any]:
        """
        Get a summary of all level requirements.
        
        Returns:
            Dictionary with level requirements summary
        """
        levels = LevelUpService.get_available_levels()
        
        if not levels:
            return {"total_levels": 0, "levels": []}
        
        summary = {
            "total_levels": len(levels),
            "min_points": levels[0].points_required,
            "max_points": levels[-1].points_required,
            "levels": [],
        }
        
        for level in levels:
            summary["levels"].append({
                "level_number": level.level_number,
                "points_required": level.points_required,
                "title": level.title,
                "points_multiplier": float(level.points_multiplier),
                "has_badge": bool(level.badge),
                "badge_name": level.badge.name if level.badge else None,
                "perks_count": len(level.perks) if level.perks else 0,
            })
        
        return summary
