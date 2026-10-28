"""
Gamification Events — Event handling system for gamification module.

This module provides a comprehensive event system for handling gamification
events, including event dispatching, handling, and processing.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union, Callable
from functools import wraps
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Enumeration of gamification event types."""
    
    # Contest events
    CONTEST_CREATED = "contest_created"
    CONTEST_UPDATED = "contest_updated"
    CONTEST_ACTIVATED = "contest_activated"
    CONTEST_COMPLETED = "contest_completed"
    CONTEST_ARCHIVED = "contest_archived"
    
    # Achievement events
    ACHIEVEMENT_CREATED = "achievement_created"
    ACHIEVEMENT_AWARDED = "achievement_awarded"
    ACHIEVEMENT_REVOKED = "achievement_revoked"
    
    # Badge events
    BADGE_CREATED = "badge_created"
    BADGE_EARNED = "badge_earned"
    BADGE_PINNED = "badge_pinned"
    BADGE_UNPINNED = "badge_unpinned"
    
    # Challenge events
    CHALLENGE_CREATED = "challenge_created"
    CHALLENGE_COMPLETED = "challenge_completed"
    CHALLENGE_EXPIRED = "challenge_expired"
    
    # Streak events
    STREAK_CREATED = "streak_created"
    STREAK_UPDATED = "streak_updated"
    STREAK_RESET = "streak_reset"
    STREAK_EXPIRED = "streak_expired"
    
    # Level events
    LEVEL_UP = "level_up"
    LEVEL_CREATED = "level_created"
    
    # Points events
    POINTS_AWARDED = "points_awarded"
    POINTS_DEDUCTED = "points_deducted"
    POINTS_UPDATED = "points_updated"
    
    # User events
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # System events
    SYSTEM_INITIALIZED = "system_initialized"
    SYSTEM_ERROR = "system_error"


@dataclass
class Event:
    """Base event class for gamification events."""
    
    event_type: EventType
    user_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: timezone.now())
    source: str = "gamification"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(
            event_type=EventType(data['event_type']),
            user_id=data.get('user_id'),
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else timezone.now(),
            source=data.get('source', 'gamification'),
            metadata=data.get('metadata', {})
        )


class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    def handle(self, event: Event) -> None:
        """Handle an event."""
        pass
    
    @abstractmethod
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        pass


class BaseEventHandler(EventHandler):
    """Base event handler with common functionality."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Default implementation - override in subclasses."""
        return False
    
    def handle(self, event: Event) -> None:
        """Handle an event - override in subclasses."""
        self.logger.info(f"Handling event: {event.event_type.value}")
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class ContestEventHandler(BaseEventHandler):
    """Handler for contest-related events."""
    
    def __init__(self):
        super().__init__("ContestEventHandler")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        return event_type in [
            EventType.CONTEST_CREATED,
            EventType.CONTEST_UPDATED,
            EventType.CONTEST_ACTIVATED,
            EventType.CONTEST_COMPLETED,
            EventType.CONTEST_ARCHIVED
        ]
    
    def handle(self, event: Event) -> None:
        """Handle contest events."""
        super().handle(event)
        
        try:
            if event.event_type == EventType.CONTEST_ACTIVATED:
                self._handle_contest_activated(event)
            elif event.event_type == EventType.CONTEST_COMPLETED:
                self._handle_contest_completed(event)
            elif event.event_type == EventType.CONTEST_ARCHIVED:
                self._handle_contest_archived(event)
                
        except Exception as e:
            self.logger.error(f"Error handling contest event {event.event_type.value}: {e}")
    
    def _handle_contest_activated(self, event: Event) -> None:
        """Handle contest activation event."""
        self.logger.info(f"Contest activated: {event.data.get('contest_id')}")
        # Add specific logic for contest activation
    
    def _handle_contest_completed(self, event: Event) -> None:
        """Handle contest completion event."""
        self.logger.info(f"Contest completed: {event.data.get('contest_id')}")
        # Add specific logic for contest completion
    
    def _handle_contest_archived(self, event: Event) -> None:
        """Handle contest archival event."""
        self.logger.info(f"Contest archived: {event.data.get('contest_id')}")
        # Add specific logic for contest archival


class AchievementEventHandler(BaseEventHandler):
    """Handler for achievement-related events."""
    
    def __init__(self):
        super().__init__("AchievementEventHandler")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        return event_type in [
            EventType.ACHIEVEMENT_CREATED,
            EventType.ACHIEVEMENT_AWARDED,
            EventType.ACHIEVEMENT_REVOKED
        ]
    
    def handle(self, event: Event) -> None:
        """Handle achievement events."""
        super().handle(event)
        
        try:
            if event.event_type == EventType.ACHIEVEMENT_AWARDED:
                self._handle_achievement_awarded(event)
            elif event.event_type == EventType.ACHIEVEMENT_REVOKED:
                self._handle_achievement_revoked(event)
                
        except Exception as e:
            self.logger.error(f"Error handling achievement event {event.event_type.value}: {e}")
    
    def _handle_achievement_awarded(self, event: Event) -> None:
        """Handle achievement award event."""
        self.logger.info(f"Achievement awarded to user {event.user_id}: {event.data.get('achievement_id')}")
        # Add specific logic for achievement awarding
    
    def _handle_achievement_revoked(self, event: Event) -> None:
        """Handle achievement revocation event."""
        self.logger.info(f"Achievement revoked from user {event.user_id}: {event.data.get('achievement_id')}")
        # Add specific logic for achievement revocation


class BadgeEventHandler(BaseEventHandler):
    """Handler for badge-related events."""
    
    def __init__(self):
        super().__init__("BadgeEventHandler")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        return event_type in [
            EventType.BADGE_CREATED,
            EventType.BADGE_EARNED,
            EventType.BADGE_PINNED,
            EventType.BADGE_UNPINNED
        ]
    
    def handle(self, event: Event) -> None:
        """Handle badge events."""
        super().handle(event)
        
        try:
            if event.event_type == EventType.BADGE_EARNED:
                self._handle_badge_earned(event)
            elif event.event_type == EventType.BADGE_PINNED:
                self._handle_badge_pinned(event)
            elif event.event_type == EventType.BADGE_UNPINNED:
                self._handle_badge_unpinned(event)
                
        except Exception as e:
            self.logger.error(f"Error handling badge event {event.event_type.value}: {e}")
    
    def _handle_badge_earned(self, event: Event) -> None:
        """Handle badge earning event."""
        self.logger.info(f"Badge earned by user {event.user_id}: {event.data.get('badge_id')}")
        # Add specific logic for badge earning
    
    def _handle_badge_pinned(self, event: Event) -> None:
        """Handle badge pinning event."""
        self.logger.info(f"Badge pinned by user {event.user_id}: {event.data.get('badge_id')}")
        # Add specific logic for badge pinning
    
    def _handle_badge_unpinned(self, event: Event) -> None:
        """Handle badge unpinning event."""
        self.logger.info(f"Badge unpinned by user {event.user_id}: {event.data.get('badge_id')}")
        # Add specific logic for badge unpinning


class PointsEventHandler(BaseEventHandler):
    """Handler for points-related events."""
    
    def __init__(self):
        super().__init__("PointsEventHandler")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        return event_type in [
            EventType.POINTS_AWARDED,
            EventType.POINTS_DEDUCTED,
            EventType.POINTS_UPDATED
        ]
    
    def handle(self, event: Event) -> None:
        """Handle points events."""
        super().handle(event)
        
        try:
            if event.event_type == EventType.POINTS_AWARDED:
                self._handle_points_awarded(event)
            elif event.event_type == EventType.POINTS_DEDUCTED:
                self._handle_points_deducted(event)
            elif event.event_type == EventType.POINTS_UPDATED:
                self._handle_points_updated(event)
                
        except Exception as e:
            self.logger.error(f"Error handling points event {event.event_type.value}: {e}")
    
    def _handle_points_awarded(self, event: Event) -> None:
        """Handle points awarding event."""
        points = event.data.get('points', 0)
        self.logger.info(f"Points awarded to user {event.user_id}: {points}")
        # Add specific logic for points awarding
    
    def _handle_points_deducted(self, event: Event) -> None:
        """Handle points deduction event."""
        points = event.data.get('points', 0)
        self.logger.info(f"Points deducted from user {event.user_id}: {points}")
        # Add specific logic for points deduction
    
    def _handle_points_updated(self, event: Event) -> None:
        """Handle points update event."""
        old_points = event.data.get('old_points', 0)
        new_points = event.data.get('new_points', 0)
        self.logger.info(f"Points updated for user {event.user_id}: {old_points} -> {new_points}")
        # Add specific logic for points update


class UserEventHandler(BaseEventHandler):
    """Handler for user-related events."""
    
    def __init__(self):
        super().__init__("UserEventHandler")
    
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle the event type."""
        return event_type in [
            EventType.USER_REGISTERED,
            EventType.USER_LOGIN,
            EventType.USER_LOGOUT
        ]
    
    def handle(self, event: Event) -> None:
        """Handle user events."""
        super().handle(event)
        
        try:
            if event.event_type == EventType.USER_REGISTERED:
                self._handle_user_registered(event)
            elif event.event_type == EventType.USER_LOGIN:
                self._handle_user_login(event)
            elif event.event_type == EventType.USER_LOGOUT:
                self._handle_user_logout(event)
                
        except Exception as e:
            self.logger.error(f"Error handling user event {event.event_type.value}: {e}")
    
    def _handle_user_registered(self, event: Event) -> None:
        """Handle user registration event."""
        self.logger.info(f"User registered: {event.user_id}")
        # Add specific logic for user registration
    
    def _handle_user_login(self, event: Event) -> None:
        """Handle user login event."""
        self.logger.info(f"User logged in: {event.user_id}")
        # Add specific logic for user login
    
    def _handle_user_logout(self, event: Event) -> None:
        """Handle user logout event."""
        self.logger.info(f"User logged out: {event.user_id}")
        # Add specific logic for user logout


class EventDispatcher:
    """Event dispatcher for managing event handlers and dispatching events."""
    
    def __init__(self):
        self.handlers: List[EventHandler] = []
        self.logger = logging.getLogger(__name__)
    
    def register_handler(self, handler: EventHandler) -> None:
        """Register an event handler."""
        self.handlers.append(handler)
        self.logger.info(f"Registered event handler: {handler}")
    
    def unregister_handler(self, handler: EventHandler) -> None:
        """Unregister an event handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
            self.logger.info(f"Unregistered event handler: {handler}")
    
    def dispatch(self, event: Event) -> None:
        """Dispatch an event to all registered handlers."""
        self.logger.info(f"Dispatching event: {event.event_type.value}")
        
        for handler in self.handlers:
            try:
                if handler.can_handle(event.event_type):
                    handler.handle(event)
            except Exception as e:
                self.logger.error(f"Error in handler {handler}: {e}")
    
    def dispatch_async(self, event: Event) -> None:
        """Dispatch an event asynchronously."""
        # This would typically use a task queue like Celery
        # For now, we'll dispatch synchronously
        self.dispatch(event)
    
    def get_handlers_for_event(self, event_type: EventType) -> List[EventHandler]:
        """Get all handlers that can handle a specific event type."""
        return [handler for handler in self.handlers if handler.can_handle(event_type)]
    
    def clear_handlers(self) -> None:
        """Clear all registered handlers."""
        self.handlers.clear()
        self.logger.info("Cleared all event handlers")


class EventStore:
    """Event store for persisting and retrieving events."""
    
    def __init__(self):
        self.events: List[Event] = []
        self.logger = logging.getLogger(__name__)
    
    def store_event(self, event: Event) -> None:
        """Store an event."""
        self.events.append(event)
        self.logger.debug(f"Stored event: {event.event_type.value}")
    
    def get_events(self, event_type: Optional[EventType] = None, 
                   user_id: Optional[str] = None,
                   limit: Optional[int] = None) -> List[Event]:
        """Get events with optional filtering."""
        filtered_events = self.events
        
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        
        if user_id:
            filtered_events = [e for e in filtered_events if e.user_id == user_id]
        
        # Sort by timestamp (newest first)
        filtered_events.sort(key=lambda e: e.timestamp, reverse=True)
        
        if limit:
            filtered_events = filtered_events[:limit]
        
        return filtered_events
    
    def get_events_for_user(self, user_id: str, limit: int = 100) -> List[Event]:
        """Get events for a specific user."""
        return self.get_events(user_id=user_id, limit=limit)
    
    def get_events_by_type(self, event_type: EventType, limit: int = 100) -> List[Event]:
        """Get events by type."""
        return self.get_events(event_type=event_type, limit=limit)
    
    def clear_events(self) -> None:
        """Clear all stored events."""
        self.events.clear()
        self.logger.info("Cleared all events")
    
    def get_event_count(self, event_type: Optional[EventType] = None,
                       user_id: Optional[str] = None) -> int:
        """Get count of events with optional filtering."""
        return len(self.get_events(event_type=event_type, user_id=user_id))


# Global instances
event_dispatcher = EventDispatcher()
event_store = EventStore()


# Initialize default handlers
def initialize_event_handlers() -> None:
    """Initialize default event handlers."""
    try:
        # Register default handlers
        event_dispatcher.register_handler(ContestEventHandler())
        event_dispatcher.register_handler(AchievementEventHandler())
        event_dispatcher.register_handler(BadgeEventHandler())
        event_dispatcher.register_handler(PointsEventHandler())
        event_dispatcher.register_handler(UserEventHandler())
        
        logger.info("Initialized default event handlers")
        
    except Exception as e:
        logger.error(f"Error initializing event handlers: {e}")


# Event creation utilities
def create_event(event_type: EventType, user_id: Optional[str] = None,
                data: Optional[Dict[str, Any]] = None,
                source: str = "gamification",
                metadata: Optional[Dict[str, Any]] = None) -> Event:
    """Create an event."""
    return Event(
        event_type=event_type,
        user_id=user_id,
        data=data or {},
        source=source,
        metadata=metadata or {}
    )


def dispatch_event(event_type: EventType, user_id: Optional[str] = None,
                   data: Optional[Dict[str, Any]] = None,
                   source: str = "gamification",
                   metadata: Optional[Dict[str, Any]] = None) -> None:
    """Create and dispatch an event."""
    event = create_event(event_type, user_id, data, source, metadata)
    
    # Store the event
    event_store.store_event(event)
    
    # Dispatch the event
    event_dispatcher.dispatch(event)


# Decorators for event handling
def event_handler(event_types: List[EventType]):
    """Decorator to register a function as an event handler."""
    def decorator(func):
        class FunctionEventHandler(BaseEventHandler):
            def __init__(self):
                super().__init__(func.__name__)
                self.event_types = event_types
                self.function = func
            
            def can_handle(self, event_type: EventType) -> bool:
                return event_type in self.event_types
            
            def handle(self, event: Event) -> None:
                return self.function(event)
        
        # Register the handler
        handler = FunctionEventHandler()
        event_dispatcher.register_handler(handler)
        
        return func
    return decorator


# Event monitoring and analytics
class EventMonitor:
    """Monitor events for analytics and debugging."""
    
    def __init__(self):
        self.event_counts: Dict[str, int] = {}
        self.event_times: Dict[str, List[datetime]] = {}
        self.logger = logging.getLogger(__name__)
    
    def record_event(self, event: Event) -> None:
        """Record an event for monitoring."""
        event_type = event.event_type.value
        
        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1
        
        if event_type not in self.event_times:
            self.event_times[event_type] = []
        
        self.event_times[event_type].append(event.timestamp)
        
        # Keep only last 100 occurrences per event type
        if len(self.event_times[event_type]) > 100:
            self.event_times[event_type] = self.event_times[event_type][-100:]
    
    def get_event_stats(self) -> Dict[str, Any]:
        """Get event statistics."""
        return {
            'total_events': sum(self.event_counts.values()),
            'event_counts': self.event_counts.copy(),
            'event_times': {
                name: [time.isoformat() for time in times]
                for name, times in self.event_times.items()
            }
        }
    
    def get_event_type_stats(self, event_type: EventType) -> Dict[str, Any]:
        """Get statistics for a specific event type."""
        type_str = event_type.value
        return {
            'count': self.event_counts.get(type_str, 0),
            'times': [time.isoformat() for time in self.event_times.get(type_str, [])]
        }
    
    def reset_stats(self) -> None:
        """Reset event statistics."""
        self.event_counts.clear()
        self.event_times.clear()
        self.logger.info("Event monitor stats reset")


# Global event monitor
event_monitor = EventMonitor()


# Initialize on module import
try:
    initialize_event_handlers()
    logger.info("Gamification events module initialized")
except Exception as e:
    logger.error(f"Error initializing events module: {e}")
