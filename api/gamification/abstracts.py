"""
Gamification Abstracts — Abstract base classes for gamification module.

This module provides abstract base classes that define interfaces and common
functionality for gamification components.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract Base Classes
# ---------------------------------------------------------------------------

class AbstractGamificationService(ABC):
    """Abstract base class for gamification services."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the service."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the service."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        pass


class AbstractRepository(ABC):
    """Abstract base class for repositories."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get(self, id: str) -> Optional[Any]:
        """Get an entity by ID."""
        pass
    
    @abstractmethod
    def create(self, entity: Any) -> Any:
        """Create a new entity."""
        pass
    
    @abstractmethod
    def update(self, entity: Any) -> Any:
        """Update an existing entity."""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete an entity by ID."""
        pass
    
    @abstractmethod
    def list(self, filters: Optional[Dict[str, Any]] = None, 
             limit: Optional[int] = None, offset: Optional[int] = None) -> List[Any]:
        """List entities with optional filtering and pagination."""
        pass


class AbstractValidator(ABC):
    """Abstract base class for validators."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a value."""
        pass
    
    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get validation errors."""
        pass


class AbstractEventHandler(ABC):
    """Abstract base class for event handlers."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """Check if handler can handle the event type."""
        pass
    
    @abstractmethod
    def handle(self, event: Any) -> None:
        """Handle an event."""
        pass


class AbstractPlugin(ABC):
    """Abstract base class for plugins."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._enabled = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get plugin name."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Get plugin version."""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass
    
    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set plugin enabled status."""
        self._enabled = value


# ---------------------------------------------------------------------------
# Abstract Model Classes
# ---------------------------------------------------------------------------

class AbstractGamificationModel(models.Model):
    """Abstract base class for gamification models."""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def __str__(self) -> str:
        """String representation of the model."""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        data = {}
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, datetime):
                data[field.name] = value.isoformat()
            else:
                data[field.name] = value
        return data


class AbstractUserGamificationModel(AbstractGamificationModel):
    """Abstract base class for user-related gamification models."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )
    
    class Meta:
        abstract = True
    
    @classmethod
    @abstractmethod
    def get_for_user(cls, user: User) -> 'AbstractUserGamificationModel':
        """Get instance for a specific user."""
        pass


class AbstractContestModel(AbstractGamificationModel):
    """Abstract base class for contest-related models."""
    
    contest_cycle = models.ForeignKey(
        'gamification.ContestCycle',
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )
    
    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Abstract Service Classes
# ---------------------------------------------------------------------------

class AbstractContestService(AbstractGamificationService):
    """Abstract base class for contest services."""
    
    @abstractmethod
    def create_contest(self, contest_data: Dict[str, Any]) -> Any:
        """Create a new contest."""
        pass
    
    @abstractmethod
    def activate_contest(self, contest_id: str) -> Any:
        """Activate a contest."""
        pass
    
    @abstractmethod
    def complete_contest(self, contest_id: str) -> Any:
        """Complete a contest."""
        pass
    
    @abstractmethod
    def get_active_contest(self) -> Optional[Any]:
        """Get the currently active contest."""
        pass


class AbstractAchievementService(AbstractGamificationService):
    """Abstract base class for achievement services."""
    
    @abstractmethod
    def award_achievement(self, user_id: str, achievement_data: Dict[str, Any]) -> Any:
        """Award an achievement to a user."""
        pass
    
    @abstractmethod
    def revoke_achievement(self, achievement_id: str) -> bool:
        """Revoke an achievement."""
        pass
    
    @abstractmethod
    def get_user_achievements(self, user_id: str) -> List[Any]:
        """Get all achievements for a user."""
        pass


class AbstractBadgeService(AbstractGamificationService):
    """Abstract base class for badge services."""
    
    @abstractmethod
    def create_badge(self, badge_data: Dict[str, Any]) -> Any:
        """Create a new badge."""
        pass
    
    @abstractmethod
    def award_badge(self, user_id: str, badge_id: str) -> Any:
        """Award a badge to a user."""
        pass
    
    @abstractmethod
    def get_user_badges(self, user_id: str) -> List[Any]:
        """Get all badges for a user."""
        pass


class AbstractPointsService(AbstractGamificationService):
    """Abstract base class for points services."""
    
    @abstractmethod
    def award_points(self, user_id: str, points: int, source: str) -> Dict[str, Any]:
        """Award points to a user."""
        pass
    
    @abstractmethod
    def deduct_points(self, user_id: str, points: int, reason: str) -> Dict[str, Any]:
        """Deduct points from a user."""
        pass
    
    @abstractmethod
    def get_user_points(self, user_id: str) -> int:
        """Get user's total points."""
        pass


class AbstractLeaderboardService(AbstractGamificationService):
    """Abstract base class for leaderboard services."""
    
    @abstractmethod
    def generate_leaderboard(self, contest_id: str, scope: str) -> Any:
        """Generate a leaderboard."""
        pass
    
    @abstractmethod
    def get_leaderboard(self, contest_id: str, scope: str, limit: int) -> List[Dict[str, Any]]:
        """Get leaderboard data."""
        pass
    
    @abstractmethod
    def get_user_rank(self, user_id: str, contest_id: str, scope: str) -> Optional[int]:
        """Get user's rank on leaderboard."""
        pass


class AbstractChallengeService(AbstractGamificationService):
    """Abstract base class for challenge services."""
    
    @abstractmethod
    def create_challenge(self, challenge_data: Dict[str, Any]) -> Any:
        """Create a new challenge."""
        pass
    
    @abstractmethod
    def complete_challenge(self, user_id: str, challenge_id: str) -> Any:
        """Complete a challenge for a user."""
        pass
    
    @abstractmethod
    def get_daily_challenge(self) -> Optional[Any]:
        """Get today's challenge."""
        pass


class AbstractStreakService(AbstractGamificationService):
    """Abstract base class for streak services."""
    
    @abstractmethod
    def update_streak(self, user_id: str, activity_data: Dict[str, Any]) -> Any:
        """Update user's streak."""
        pass
    
    @abstractmethod
    def reset_streak(self, user_id: str) -> Any:
        """Reset user's streak."""
        pass
    
    @abstractmethod
    def get_user_streak(self, user_id: str) -> Optional[Any]:
        """Get user's current streak."""
        pass


class AbstractLevelService(AbstractGamificationService):
    """Abstract base class for level services."""
    
    @abstractmethod
    def get_user_level(self, user_id: str) -> Optional[Any]:
        """Get user's current level."""
        pass
    
    @abstractmethod
    def check_level_up(self, user_id: str, points: int) -> Dict[str, Any]:
        """Check if user should level up."""
        pass
    
    @abstractmethod
    def get_next_level(self, user_id: str) -> Optional[Any]:
        """Get user's next level."""
        pass


# ---------------------------------------------------------------------------
# Abstract Repository Classes
# ---------------------------------------------------------------------------

class AbstractContestRepository(AbstractRepository):
    """Abstract base class for contest repositories."""
    
    @abstractmethod
    def find_active(self) -> Optional[Any]:
        """Find the active contest."""
        pass
    
    @abstractmethod
    def find_by_status(self, status: str) -> List[Any]:
        """Find contests by status."""
        pass


class AbstractUserAchievementRepository(AbstractRepository):
    """Abstract base class for user achievement repositories."""
    
    @abstractmethod
    def find_by_user(self, user_id: str) -> List[Any]:
        """Find achievements by user."""
        pass
    
    @abstractmethod
    def find_awarded(self, user_id: str) -> List[Any]:
        """Find awarded achievements by user."""
        pass


class AbstractUserBadgeRepository(AbstractRepository):
    """Abstract base class for user badge repositories."""
    
    @abstractmethod
    def find_by_user(self, user_id: str) -> List[Any]:
        """Find badges by user."""
        pass
    
    @abstractmethod
    def find_pinned(self, user_id: str) -> List[Any]:
        """Find pinned badges by user."""
        pass


# ---------------------------------------------------------------------------
# Abstract View Classes
# ---------------------------------------------------------------------------

class AbstractGamificationView(ABC):
    """Abstract base class for gamification views."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for templates."""
        pass
    
    @abstractmethod
    def dispatch(self, request, *args, **kwargs):
        """Dispatch the request."""
        pass


class AbstractGamificationAPIView(ABC):
    """Abstract base class for gamification API views."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get(self, request, *args, **kwargs):
        """Handle GET request."""
        pass
    
    @abstractmethod
    def post(self, request, *args, **kwargs):
        """Handle POST request."""
        pass
    
    @abstractmethod
    def put(self, request, *args, **kwargs):
        """Handle PUT request."""
        pass
    
    @abstractmethod
    def delete(self, request, *args, **kwargs):
        """Handle DELETE request."""
        pass


# ---------------------------------------------------------------------------
# Abstract Utility Classes
# ---------------------------------------------------------------------------

class AbstractCacheManager(ABC):
    """Abstract base class for cache managers."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """Set value in cache."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache."""
        pass


class AbstractNotificationManager(ABC):
    """Abstract base class for notification managers."""
    
    @abstractmethod
    def send_notification(self, user_id: str, notification_data: Dict[str, Any]) -> bool:
        """Send notification to user."""
        pass
    
    @abstractmethod
    def get_supported_channels(self) -> List[str]:
        """Get supported notification channels."""
        pass


class AbstractAnalyticsManager(ABC):
    """Abstract base class for analytics managers."""
    
    @abstractmethod
    def track_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Track an analytics event."""
        pass
    
    @abstractmethod
    def generate_report(self, report_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate analytics report."""
        pass


# ---------------------------------------------------------------------------
# Abstract Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AbstractEvent:
    """Abstract base class for events."""
    
    event_type: str
    timestamp: datetime = field(default_factory=lambda: timezone.now())
    data: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        pass


@dataclass
class AbstractGamificationEvent(AbstractEvent):
    """Abstract base class for gamification events."""
    
    user_id: Optional[str] = None
    source: str = "gamification"
    
    @abstractmethod
    def validate(self) -> List[str]:
        """Validate event data."""
        pass


@dataclass
class AbstractUserEvent(AbstractGamificationEvent):
    """Abstract base class for user events."""
    
    user_id: str
    
    def validate(self) -> List[str]:
        """Validate user event."""
        errors = []
        
        if not self.user_id:
            errors.append("User ID is required")
        
        return errors


@dataclass
class AbstractContestEvent(AbstractGamificationEvent):
    """Abstract base class for contest events."""
    
    contest_id: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate contest event."""
        errors = []
        
        if not self.contest_id:
            errors.append("Contest ID is required")
        
        return errors


# ---------------------------------------------------------------------------
# Abstract Configuration Classes
# ---------------------------------------------------------------------------

class AbstractConfiguration(ABC):
    """Abstract base class for configuration."""
    
    @abstractmethod
    def load(self) -> None:
        """Load configuration."""
        pass
    
    @abstractmethod
    def save(self) -> None:
        """Save configuration."""
        pass
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        pass


class AbstractGamificationConfiguration(AbstractConfiguration):
    """Abstract base class for gamification configuration."""
    
    @abstractmethod
    def get_contest_settings(self) -> Dict[str, Any]:
        """Get contest settings."""
        pass
    
    @abstractmethod
    def get_points_settings(self) -> Dict[str, Any]:
        """Get points settings."""
        pass
    
    @abstractmethod
    def get_notification_settings(self) -> Dict[str, Any]:
        """Get notification settings."""
        pass


# ---------------------------------------------------------------------------
# Abstract Factory Classes
# ---------------------------------------------------------------------------

class AbstractFactory(ABC):
    """Abstract base class for factories."""
    
    @abstractmethod
    def create(self, **kwargs) -> Any:
        """Create an instance."""
        pass


class AbstractGamificationFactory(AbstractFactory):
    """Abstract base class for gamification factories."""
    
    @abstractmethod
    def create_service(self, service_type: str, **kwargs) -> AbstractGamificationService:
        """Create a service instance."""
        pass
    
    @abstractmethod
    def create_repository(self, repository_type: str, **kwargs) -> AbstractRepository:
        """Create a repository instance."""
        pass
    
    @abstractmethod
    def create_validator(self, validator_type: str, **kwargs) -> AbstractValidator:
        """Create a validator instance."""
        pass


# ---------------------------------------------------------------------------
# Abstract Strategy Classes
# ---------------------------------------------------------------------------

class AbstractStrategy(ABC):
    """Abstract base class for strategies."""
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the strategy."""
        pass


class AbstractRewardStrategy(AbstractStrategy):
    """Abstract base class for reward strategies."""
    
    @abstractmethod
    def calculate_reward(self, rank: int, contest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate reward for a given rank."""
        pass


class AbstractNotificationStrategy(AbstractStrategy):
    """Abstract base class for notification strategies."""
    
    @abstractmethod
    def send_notification(self, user_id: str, notification_data: Dict[str, Any]) -> bool:
        """Send notification using the strategy."""
        pass


# ---------------------------------------------------------------------------
# Abstract Builder Classes
# ---------------------------------------------------------------------------

class AbstractBuilder(ABC):
    """Abstract base class for builders."""
    
    @abstractmethod
    def build(self) -> Any:
        """Build the object."""
        pass


class AbstractGamificationBuilder(AbstractBuilder):
    """Abstract base class for gamification builders."""
    
    @abstractmethod
    def set_user(self, user_id: str) -> 'AbstractGamificationBuilder':
        """Set user for the builder."""
        pass
    
    @abstractmethod
    def set_points(self, points: int) -> 'AbstractGamificationBuilder':
        """Set points for the builder."""
        pass
    
    @abstractmethod
    def set_metadata(self, metadata: Dict[str, Any]) -> 'AbstractGamificationBuilder':
        """Set metadata for the builder."""
        pass


# ---------------------------------------------------------------------------
# Abstract Observer Classes
# ---------------------------------------------------------------------------

class AbstractObserver(ABC):
    """Abstract base class for observers."""
    
    @abstractmethod
    def update(self, subject: Any, event_data: Dict[str, Any]) -> None:
        """Update observer with subject changes."""
        pass


class AbstractSubject(ABC):
    """Abstract base class for subjects."""
    
    @abstractmethod
    def attach(self, observer: AbstractObserver) -> None:
        """Attach an observer."""
        pass
    
    @abstractmethod
    def detach(self, observer: AbstractObserver) -> None:
        """Detach an observer."""
        pass
    
    @abstractmethod
    def notify(self, event_data: Dict[str, Any]) -> None:
        """Notify all observers."""
        pass


# ---------------------------------------------------------------------------
# Abstract Command Classes
# ---------------------------------------------------------------------------

class AbstractCommand(ABC):
    """Abstract base class for commands."""
    
    @abstractmethod
    def execute(self) -> Any:
        """Execute the command."""
        pass
    
    @abstractmethod
    def undo(self) -> Any:
        """Undo the command."""
        pass


class AbstractGamificationCommand(AbstractCommand):
    """Abstract base class for gamification commands."""
    
    @abstractmethod
    def validate(self) -> List[str]:
        """Validate the command."""
        pass


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def validate_abstract_implementation(cls: Type, abstract_class: Type) -> bool:
    """Validate that a class properly implements an abstract class."""
    if not issubclass(cls, abstract_class):
        return False
    
    # Check if all abstract methods are implemented
    abstract_methods = getattr(abstract_class, '__abstractmethods__', set())
    
    for method in abstract_methods:
        if not hasattr(cls, method):
            return False
    
    return True


def get_abstract_methods(cls: Type) -> List[str]:
    """Get list of abstract methods for a class."""
    return list(getattr(cls, '__abstractmethods__', set()))


# Initialize logging
logger.info("Gamification abstracts module initialized")
