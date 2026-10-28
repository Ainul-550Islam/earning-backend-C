"""
Gamification Schemas — Data schemas and validation schemas for gamification module.

This module provides comprehensive schema definitions for gamification data
structures, API request/response schemas, and validation schemas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum
import json

from django.contrib.auth import get_user_model
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError
from api.gamification.choices import (
    ContestCycleStatus, RewardType, AchievementType, LeaderboardScope,
    SnapshotStatus, BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ChallengeStatus, StreakStatus, LevelPerkType
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Schema Classes
# ---------------------------------------------------------------------------

@dataclass
class BaseSchema:
    """Base schema class with common functionality."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [item.to_dict() if hasattr(item, 'to_dict') else item for item in value]
            else:
                result[key] = value
        return result
    
    def to_json(self) -> str:
        """Convert schema to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseSchema':
        """Create schema from dictionary."""
        # This would need to be implemented in subclasses
        raise NotImplementedError
    
    def validate(self) -> List[str]:
        """Validate schema data."""
        errors = []
        # Basic validation - override in subclasses
        return errors


# ---------------------------------------------------------------------------
# Contest Schemas
# ---------------------------------------------------------------------------

@dataclass
class ContestCycleSchema(BaseSchema):
    """Schema for contest cycle data."""
    
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    status: str = ContestCycleStatus.DRAFT
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_featured: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate contest cycle data."""
        errors = []
        
        if not self.name:
            errors.append("Name is required")
        
        if not self.start_date:
            errors.append("Start date is required")
        
        if not self.end_date:
            errors.append("End date is required")
        
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            errors.append("Start date must be before end date")
        
        if self.status not in [choice.value for choice in ContestCycleStatus]:
            errors.append("Invalid status")
        
        return errors


@dataclass
class ContestRewardSchema(BaseSchema):
    """Schema for contest reward data."""
    
    id: Optional[str] = None
    contest_cycle_id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    reward_type: str = RewardType.POINTS
    rank_from: int = 1
    rank_to: int = 1
    points_value: Optional[int] = None
    badge_id: Optional[str] = None
    total_budget: Optional[int] = None
    issued_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate contest reward data."""
        errors = []
        
        if not self.title:
            errors.append("Title is required")
        
        if not self.contest_cycle_id:
            errors.append("Contest cycle ID is required")
        
        if self.rank_from < 1:
            errors.append("Rank from must be at least 1")
        
        if self.rank_to < 1:
            errors.append("Rank to must be at least 1")
        
        if self.rank_from > self.rank_to:
            errors.append("Rank from cannot be greater than rank to")
        
        if self.reward_type not in [choice.value for choice in RewardType]:
            errors.append("Invalid reward type")
        
        if self.reward_type == RewardType.POINTS and not self.points_value:
            errors.append("Points value is required for points rewards")
        
        if self.reward_type == RewardType.BADGE and not self.badge_id:
            errors.append("Badge ID is required for badge rewards")
        
        return errors


# ---------------------------------------------------------------------------
# Achievement Schemas
# ---------------------------------------------------------------------------

@dataclass
class UserAchievementSchema(BaseSchema):
    """Schema for user achievement data."""
    
    id: Optional[str] = None
    user_id: Optional[str] = None
    contest_cycle_id: Optional[str] = None
    contest_reward_id: Optional[str] = None
    achievement_type: str = AchievementType.CONTEST_PARTICIPATION
    points_awarded: int = 0
    is_awarded: bool = False
    is_notified: bool = False
    awarded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate user achievement data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if not self.contest_cycle_id:
            errors.append("Contest cycle ID is required")
        
        if self.achievement_type not in [choice.value for choice in AchievementType]:
            errors.append("Invalid achievement type")
        
        if self.points_awarded < 0:
            errors.append("Points awarded cannot be negative")
        
        return errors


# ---------------------------------------------------------------------------
# Leaderboard Schemas
# ---------------------------------------------------------------------------

@dataclass
class LeaderboardSnapshotSchema(BaseSchema):
    """Schema for leaderboard snapshot data."""
    
    id: Optional[str] = None
    contest_cycle_id: Optional[str] = None
    scope: str = LeaderboardScope.GLOBAL
    status: str = SnapshotStatus.PENDING
    entry_count: int = 0
    generated_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate leaderboard snapshot data."""
        errors = []
        
        if not self.contest_cycle_id:
            errors.append("Contest cycle ID is required")
        
        if self.scope not in [choice.value for choice in LeaderboardScope]:
            errors.append("Invalid scope")
        
        if self.status not in [choice.value for choice in SnapshotStatus]:
            errors.append("Invalid status")
        
        return errors


@dataclass
class LeaderboardEntrySchema(BaseSchema):
    """Schema for leaderboard entry data."""
    
    user_id: str
    username: str
    rank: int
    points: int
    achievements_count: int
    badges_count: int
    streak_days: int
    level: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate leaderboard entry data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if not self.username:
            errors.append("Username is required")
        
        if self.rank < 1:
            errors.append("Rank must be at least 1")
        
        if self.points < 0:
            errors.append("Points cannot be negative")
        
        return errors


# ---------------------------------------------------------------------------
# Badge Schemas
# ---------------------------------------------------------------------------

@dataclass
class BadgeSchema(BaseSchema):
    """Schema for badge data."""
    
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    image_url: Optional[str] = None
    rarity: str = BadgeRarity.COMMON
    criteria_type: str = BadgeCriteriaType.POINTS_THRESHOLD
    criteria_value: Optional[int] = None
    is_active: bool = True
    is_pinnable: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate badge data."""
        errors = []
        
        if not self.name:
            errors.append("Name is required")
        
        if self.rarity not in [choice.value for choice in BadgeRarity]:
            errors.append("Invalid rarity")
        
        if self.criteria_type not in [choice.value for choice in BadgeCriteriaType]:
            errors.append("Invalid criteria type")
        
        if self.criteria_type == BadgeCriteriaType.POINTS_THRESHOLD and not self.criteria_value:
            errors.append("Criteria value is required for points threshold criteria")
        
        return errors


@dataclass
class UserBadgeSchema(BaseSchema):
    """Schema for user badge data."""
    
    id: Optional[str] = None
    user_id: Optional[str] = None
    badge_id: Optional[str] = None
    is_pinned: bool = False
    earned_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate user badge data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if not self.badge_id:
            errors.append("Badge ID is required")
        
        return errors


# ---------------------------------------------------------------------------
# Challenge Schemas
# ---------------------------------------------------------------------------

@dataclass
class DailyChallengeSchema(BaseSchema):
    """Schema for daily challenge data."""
    
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    action: str = ChallengeAction.LOGIN
    target_value: int = 1
    points_reward: int = 0
    badge_id: Optional[str] = None
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate daily challenge data."""
        errors = []
        
        if not self.title:
            errors.append("Title is required")
        
        if self.action not in [choice.value for choice in ChallengeAction]:
            errors.append("Invalid action")
        
        if self.target_value < 1:
            errors.append("Target value must be at least 1")
        
        if self.points_reward < 0:
            errors.append("Points reward cannot be negative")
        
        return errors


@dataclass
class UserDailyChallengeSchema(BaseSchema):
    """Schema for user daily challenge data."""
    
    id: Optional[str] = None
    user_id: Optional[str] = None
    challenge_id: Optional[str] = None
    current_progress: int = 0
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    points_awarded: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate user daily challenge data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if not self.challenge_id:
            errors.append("Challenge ID is required")
        
        if self.current_progress < 0:
            errors.append("Current progress cannot be negative")
        
        return errors


# ---------------------------------------------------------------------------
# Streak Schemas
# ---------------------------------------------------------------------------

@dataclass
class StreakSchema(BaseSchema):
    """Schema for streak data."""
    
    id: Optional[str] = None
    user_id: Optional[str] = None
    current_days: int = 0
    longest_days: int = 0
    is_active: bool = True
    last_activity_date: Optional[datetime] = None
    reset_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate streak data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if self.current_days < 0:
            errors.append("Current days cannot be negative")
        
        if self.longest_days < 0:
            errors.append("Longest days cannot be negative")
        
        if self.longest_days < self.current_days:
            errors.append("Longest days cannot be less than current days")
        
        return errors


@dataclass
class StreakRewardSchema(BaseSchema):
    """Schema for streak reward data."""
    
    id: Optional[str] = None
    streak_days: int = 0
    points_reward: int = 0
    badge_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate streak reward data."""
        errors = []
        
        if self.streak_days < 1:
            errors.append("Streak days must be at least 1")
        
        if self.points_reward < 0:
            errors.append("Points reward cannot be negative")
        
        return errors


# ---------------------------------------------------------------------------
# Level Schemas
# ---------------------------------------------------------------------------

@dataclass
class LevelConfigSchema(BaseSchema):
    """Schema for level configuration data."""
    
    id: Optional[str] = None
    level_number: int = 1
    name: str = ""
    description: Optional[str] = None
    points_required: int = 0
    badge_id: Optional[str] = None
    perks: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate level configuration data."""
        errors = []
        
        if not self.name:
            errors.append("Name is required")
        
        if self.level_number < 1:
            errors.append("Level number must be at least 1")
        
        if self.points_required < 0:
            errors.append("Points required cannot be negative")
        
        for perk in self.perks:
            if perk not in [choice.value for choice in LevelPerkType]:
                errors.append(f"Invalid perk type: {perk}")
        
        return errors


# ---------------------------------------------------------------------------
# API Request/Response Schemas
# ---------------------------------------------------------------------------

@dataclass
class APIResponseSchema(BaseSchema):
    """Schema for API responses."""
    
    success: bool = True
    data: Optional[Any] = None
    message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: timezone.now())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate API response."""
        errors = []
        
        if not isinstance(self.success, bool):
            errors.append("Success must be a boolean")
        
        if not isinstance(self.errors, list):
            errors.append("Errors must be a list")
        
        if not isinstance(self.warnings, list):
            errors.append("Warnings must be a list")
        
        return errors


@dataclass
class PaginationSchema(BaseSchema):
    """Schema for pagination data."""
    
    page: int = 1
    per_page: int = 20
    total: int = 0
    pages: int = 0
    has_next: bool = False
    has_prev: bool = False
    
    def validate(self) -> List[str]:
        """Validate pagination data."""
        errors = []
        
        if self.page < 1:
            errors.append("Page must be at least 1")
        
        if self.per_page < 1:
            errors.append("Per page must be at least 1")
        
        if self.per_page > 100:
            errors.append("Per page cannot exceed 100")
        
        if self.total < 0:
            errors.append("Total cannot be negative")
        
        return errors


@dataclass
class LeaderboardResponseSchema(BaseSchema):
    """Schema for leaderboard API response."""
    
    pagination: PaginationSchema = field(default_factory=PaginationSchema)
    entries: List[LeaderboardEntrySchema] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate leaderboard response."""
        errors = []
        
        pagination_errors = self.pagination.validate()
        errors.extend(pagination_errors)
        
        for i, entry in enumerate(self.entries):
            entry_errors = entry.validate()
            for error in entry_errors:
                errors.append(f"Entry {i}: {error}")
        
        return errors


# ---------------------------------------------------------------------------
# User Profile Schemas
# ---------------------------------------------------------------------------

@dataclass
class UserProfileSchema(BaseSchema):
    """Schema for user gamification profile."""
    
    user_id: str
    username: str
    total_points: int = 0
    current_level: int = 1
    next_level_points: int = 0
    badges_count: int = 0
    achievements_count: int = 0
    streak_days: int = 0
    streak_active: bool = False
    rank: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate user profile data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if not self.username:
            errors.append("Username is required")
        
        if self.total_points < 0:
            errors.append("Total points cannot be negative")
        
        if self.current_level < 1:
            errors.append("Current level must be at least 1")
        
        if self.next_level_points < 0:
            errors.append("Next level points cannot be negative")
        
        if self.streak_days < 0:
            errors.append("Streak days cannot be negative")
        
        return errors


@dataclass
class UserStatsSchema(BaseSchema):
    """Schema for user statistics."""
    
    user_id: str
    period: str = "all_time"  # all_time, monthly, weekly, daily
    points_earned: int = 0
    achievements_completed: int = 0
    badges_earned: int = 0
    challenges_completed: int = 0
    contests_participated: int = 0
    average_rank: Optional[float] = None
    best_rank: Optional[int] = None
    current_streak: int = 0
    longest_streak: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate user statistics data."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        if self.period not in ["all_time", "monthly", "weekly", "daily"]:
            errors.append("Invalid period")
        
        if self.points_earned < 0:
            errors.append("Points earned cannot be negative")
        
        if self.achievements_completed < 0:
            errors.append("Achievements completed cannot be negative")
        
        if self.badges_earned < 0:
            errors.append("Badges earned cannot be negative")
        
        if self.challenges_completed < 0:
            errors.append("Challenges completed cannot be negative")
        
        if self.contests_participated < 0:
            errors.append("Contests participated cannot be negative")
        
        if self.average_rank is not None and self.average_rank < 1:
            errors.append("Average rank must be at least 1")
        
        if self.best_rank is not None and self.best_rank < 1:
            errors.append("Best rank must be at least 1")
        
        if self.current_streak < 0:
            errors.append("Current streak cannot be negative")
        
        if self.longest_streak < 0:
            errors.append("Longest streak cannot be negative")
        
        return errors


# ---------------------------------------------------------------------------
# Schema Registry
# ---------------------------------------------------------------------------

class SchemaRegistry:
    """Registry for managing schemas."""
    
    def __init__(self):
        self.schemas: Dict[str, Type[BaseSchema]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_schema(self, name: str, schema_class: Type[BaseSchema]) -> None:
        """Register a schema class."""
        self.schemas[name] = schema_class
        self.logger.info(f"Registered schema: {name}")
    
    def get_schema(self, name: str) -> Optional[Type[BaseSchema]]:
        """Get a schema class by name."""
        return self.schemas.get(name)
    
    def create_schema(self, name: str, data: Dict[str, Any]) -> BaseSchema:
        """Create a schema instance from data."""
        schema_class = self.get_schema(name)
        if not schema_class:
            raise ValueError(f"Schema not found: {name}")
        
        return schema_class.from_dict(data)
    
    def list_schemas(self) -> List[str]:
        """List all registered schemas."""
        return list(self.schemas.keys())
    
    def clear_schemas(self) -> None:
        """Clear all schemas."""
        self.schemas.clear()
        self.logger.info("Cleared all schemas")


# Global schema registry
schema_registry = SchemaRegistry()


# Initialize default schemas
def initialize_default_schemas() -> None:
    """Initialize default schemas."""
    try:
        # Register schema classes
        schema_registry.register_schema('contest_cycle', ContestCycleSchema)
        schema_registry.register_schema('contest_reward', ContestRewardSchema)
        schema_registry.register_schema('user_achievement', UserAchievementSchema)
        schema_registry.register_schema('leaderboard_snapshot', LeaderboardSnapshotSchema)
        schema_registry.register_schema('leaderboard_entry', LeaderboardEntrySchema)
        schema_registry.register_schema('badge', BadgeSchema)
        schema_registry.register_schema('user_badge', UserBadgeSchema)
        schema_registry.register_schema('daily_challenge', DailyChallengeSchema)
        schema_registry.register_schema('user_daily_challenge', UserDailyChallengeSchema)
        schema_registry.register_schema('streak', StreakSchema)
        schema_registry.register_schema('streak_reward', StreakRewardSchema)
        schema_registry.register_schema('level_config', LevelConfigSchema)
        schema_registry.register_schema('api_response', APIResponseSchema)
        schema_registry.register_schema('pagination', PaginationSchema)
        schema_registry.register_schema('leaderboard_response', LeaderboardResponseSchema)
        schema_registry.register_schema('user_profile', UserProfileSchema)
        schema_registry.register_schema('user_stats', UserStatsSchema)
        
        logger.info("Initialized default schemas")
        
    except Exception as e:
        logger.error(f"Error initializing default schemas: {e}")


# Schema utilities
def validate_schema(schema_name: str, data: Dict[str, Any]) -> List[str]:
    """Validate data against a schema."""
    schema = schema_registry.create_schema(schema_name, data)
    return schema.validate()


def create_schema(schema_name: str, data: Dict[str, Any]) -> BaseSchema:
    """Create a schema instance."""
    return schema_registry.create_schema(schema_name, data)


def create_api_response(success: bool = True, data: Optional[Any] = None,
                      message: Optional[str] = None, errors: Optional[List[str]] = None,
                      warnings: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> APIResponseSchema:
    """Create an API response schema."""
    return APIResponseSchema(
        success=success,
        data=data,
        message=message,
        errors=errors or [],
        warnings=warnings or [],
        metadata=metadata or {}
    )


# Initialize on module import
try:
    initialize_default_schemas()
    logger.info("Gamification schemas module initialized")
except Exception as e:
    logger.error(f"Error initializing schemas module: {e}")
