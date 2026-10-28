# =============================================================================
# auto_mod/events.py
# =============================================================================

"""
Event system for auto moderation system.
Provides event definitions, dispatching, and handling capabilities.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Event:
    """Base event data structure."""
    event_type: str
    source: str
    timestamp: datetime = field(default_factory=timezone.now)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[int] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.correlation_id:
            self.correlation_id = f"evt_{int(time.time() * 1000)}_{id(self)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_type': self.event_type,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'metadata': self.metadata,
            'priority': self.priority.value,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'correlation_id': self.correlation_id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        event = cls(
            event_type=data['event_type'],
            source=data['source'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            priority=EventPriority(data.get('priority', EventPriority.NORMAL.value)),
            status=EventStatus(data.get('status', EventStatus.PENDING.value)),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout=data.get('timeout'),
            correlation_id=data.get('correlation_id'),
            user_id=data.get('user_id'),
            tenant_id=data.get('tenant_id')
        )
        return event


class EventHandler:
    """Base event handler class."""
    
    def __init__(self, name: str, handler_func: Callable, **kwargs):
        self.name = name
        self.handler_func = handler_func
        self.enabled = kwargs.get('enabled', True)
        self.async_handler = kwargs.get('async', False)
        self.priority = kwargs.get('priority', EventPriority.NORMAL)
        self.timeout = kwargs.get('timeout', 300)
        self.max_retries = kwargs.get('max_retries', 3)
        self.conditions: List[Callable] = kwargs.get('conditions', [])
        self.filters: List[Callable] = kwargs.get('filters', [])
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_execution = None
        self.average_execution_time = 0.0
        self.execution_times: List[float] = []
        self.max_execution_times = 100
        self._lock = threading.Lock()
    
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the event."""
        if not self.enabled:
            return False
        
        # Check priority
        if event.priority.value < self.priority.value:
            return False
        
        # Check conditions
        for condition in self.conditions:
            try:
                if not condition(event):
                    return False
            except Exception as exc:
                logger.error(f"EventHandler {self.name}: condition error: {exc}")
                return False
        
        return True
    
    async def handle_async(self, event: Event) -> bool:
        """Handle event asynchronously."""
        start_time = time.time()
        
        try:
            # Apply filters
            filtered_event = event
            for filter_func in self.filters:
                try:
                    filtered_event = filter_func(filtered_event)
                except Exception as exc:
                    logger.error(f"EventHandler {self.name}: filter error: {exc}")
                    return False
            
            # Execute handler
            if self.async_handler:
                result = await self.handler_func(filtered_event)
            else:
                result = self.handler_func(filtered_event)
            
            # Update statistics
            execution_time = time.time() - start_time
            self._update_execution_time(execution_time)
            self.execution_count += 1
            self.success_count += 1
            self.last_execution = timezone.now()
            
            return bool(result)
            
        except Exception as exc:
            self.error_count += 1
            logger.error(f"EventHandler {self.name}: handling error: {exc}")
            return False
    
    def handle(self, event: Event) -> bool:
        """Handle event synchronously."""
        start_time = time.time()
        
        try:
            # Apply filters
            filtered_event = event
            for filter_func in self.filters:
                try:
                    filtered_event = filter_func(filtered_event)
                except Exception as exc:
                    logger.error(f"EventHandler {self.name}: filter error: {exc}")
                    return False
            
            # Execute handler
            result = self.handler_func(filtered_event)
            
            # Update statistics
            execution_time = time.time() - start_time
            self._update_execution_time(execution_time)
            self.execution_count += 1
            self.success_count += 1
            self.last_execution = timezone.now()
            
            return bool(result)
            
        except Exception as exc:
            self.error_count += 1
            logger.error(f"EventHandler {self.name}: handling error: {exc}")
            return False
    
    def _update_execution_time(self, execution_time: float) -> None:
        """Update execution time statistics."""
        with self._lock:
            self.execution_times.append(execution_time)
            
            # Keep only recent execution times
            if len(self.execution_times) > self.max_execution_times:
                self.execution_times = self.execution_times[-self.max_execution_times:]
            
            # Update average
            if self.execution_times:
                self.average_execution_time = sum(self.execution_times) / len(self.execution_times)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': round(success_rate, 2),
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'average_execution_time': round(self.average_execution_time, 3),
            'priority': self.priority.value,
            'async_handler': self.async_handler
        }


class EventDispatcher:
    """
    Central event dispatcher for the moderation system.
    Handles event registration, dispatching, and management.
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[EventHandler]] = {}
        self.global_handlers: List[EventHandler] = []
        self.event_history: List[Event] = []
        self.max_history_size = 10000
        self.dispatch_stats: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler for a specific event type."""
        with self._lock:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            
            self.handlers[event_type].append(handler)
            
            # Sort by priority (higher priority first)
            self.handlers[event_type].sort(key=lambda h: h.priority.value, reverse=True)
            
            logger.info(f"EventDispatcher: registered handler {handler.name} for {event_type}")
    
    def register_global_handler(self, handler: EventHandler) -> None:
        """Register a global handler for all events."""
        with self._lock:
            self.global_handlers.append(handler)
            
            # Sort by priority
            self.global_handlers.sort(key=lambda h: h.priority.value, reverse=True)
            
            logger.info(f"EventDispatcher: registered global handler {handler.name}")
    
    def unregister_handler(self, event_type: str, handler_name: str) -> None:
        """Unregister an event handler."""
        with self._lock:
            if event_type in self.handlers:
                self.handlers[event_type] = [
                    h for h in self.handlers[event_type] if h.name != handler_name
                ]
                logger.info(f"EventDispatcher: unregistered handler {handler_name} for {event_type}")
    
    def unregister_global_handler(self, handler_name: str) -> None:
        """Unregister a global handler."""
        with self._lock:
            self.global_handlers = [
                h for h in self.global_handlers if h.name != handler_name
            ]
            logger.info(f"EventDispatcher: unregistered global handler {handler_name}")
    
    def dispatch(self, event: Event) -> bool:
        """
        Dispatch an event to all applicable handlers.
        
        Args:
            event: Event to dispatch
            
        Returns:
            True if at least one handler succeeded, False otherwise
        """
        start_time = time.time()
        
        try:
            # Add to history
            self._add_to_history(event)
            
            # Update dispatch stats
            event_type = event.event_type
            self.dispatch_stats[event_type] = self.dispatch_stats.get(event_type, 0) + 1
            
            # Get applicable handlers
            applicable_handlers = []
            
            # Event-specific handlers
            if event_type in self.handlers:
                applicable_handlers.extend([
                    h for h in self.handlers[event_type] if h.can_handle(event)
                ])
            
            # Global handlers
            applicable_handlers.extend([
                h for h in self.global_handlers if h.can_handle(event)
            ])
            
            if not applicable_handlers:
                logger.warning(f"EventDispatcher: no handlers for event {event_type}")
                return False
            
            # Execute handlers
            success_count = 0
            total_handlers = len(applicable_handlers)
            
            for handler in applicable_handlers:
                try:
                    if handler.async_handler:
                        # For async handlers, we'll need to run them in an async context
                        # For now, we'll skip async handlers in sync dispatch
                        logger.warning(f"EventDispatcher: skipping async handler {handler.name} in sync dispatch")
                        continue
                    
                    if handler.handle(event):
                        success_count += 1
                    
                except Exception as exc:
                    logger.error(f"EventDispatcher: handler {handler.name} failed: {exc}")
            
            # Update event status
            if success_count > 0:
                event.status = EventStatus.COMPLETED
            else:
                event.status = EventStatus.FAILED
            
            dispatch_time = time.time() - start_time
            logger.debug(f"EventDispatcher: dispatched {event_type} in {dispatch_time:.3f}s, "
                        f"{success_count}/{total_handlers} handlers succeeded")
            
            return success_count > 0
            
        except Exception as exc:
            logger.error(f"EventDispatcher: dispatch error for {event.event_type}: {exc}")
            event.status = EventStatus.FAILED
            return False
    
    async def dispatch_async(self, event: Event) -> bool:
        """
        Dispatch an event asynchronously to all applicable handlers.
        
        Args:
            event: Event to dispatch
            
        Returns:
            True if at least one handler succeeded, False otherwise
        """
        start_time = time.time()
        
        try:
            # Add to history
            self._add_to_history(event)
            
            # Update dispatch stats
            event_type = event.event_type
            self.dispatch_stats[event_type] = self.dispatch_stats.get(event_type, 0) + 1
            
            # Get applicable handlers
            applicable_handlers = []
            
            # Event-specific handlers
            if event_type in self.handlers:
                applicable_handlers.extend([
                    h for h in self.handlers[event_type] if h.can_handle(event)
                ])
            
            # Global handlers
            applicable_handlers.extend([
                h for h in self.global_handlers if h.can_handle(event)
            ])
            
            if not applicable_handlers:
                logger.warning(f"EventDispatcher: no handlers for event {event_type}")
                return False
            
            # Execute handlers concurrently
            import asyncio
            
            tasks = []
            for handler in applicable_handlers:
                if handler.async_handler:
                    tasks.append(handler.handle_async(event))
                else:
                    # Run sync handlers in thread pool
                    tasks.append(asyncio.get_event_loop().run_in_executor(
                        None, handler.handle, event
                    ))
            
            # Wait for all handlers to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes
            success_count = sum(1 for result in results if result is True)
            total_handlers = len(applicable_handlers)
            
            # Log exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"EventDispatcher: handler {applicable_handlers[i].name} failed: {result}")
            
            # Update event status
            if success_count > 0:
                event.status = EventStatus.COMPLETED
            else:
                event.status = EventStatus.FAILED
            
            dispatch_time = time.time() - start_time
            logger.debug(f"EventDispatcher: dispatched {event_type} async in {dispatch_time:.3f}s, "
                        f"{success_count}/{total_handlers} handlers succeeded")
            
            return success_count > 0
            
        except Exception as exc:
            logger.error(f"EventDispatcher: async dispatch error for {event.event_type}: {exc}")
            event.status = EventStatus.FAILED
            return False
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        with self._lock:
            self.event_history.append(event)
            
            # Trim history if too large
            if len(self.event_history) > self.max_history_size:
                self.event_history = self.event_history[-self.max_history_size:]
    
    def get_event_history(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """Get event history."""
        with self._lock:
            events = self.event_history
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            return events[-limit:]
    
    def get_dispatch_stats(self) -> Dict[str, Any]:
        """Get dispatch statistics."""
        with self._lock:
            return {
                'total_events': len(self.event_history),
                'dispatch_stats': dict(self.dispatch_stats),
                'registered_handlers': {
                    event_type: len(handlers) for event_type, handlers in self.handlers.items()
                },
                'global_handlers': len(self.global_handlers)
            }
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        with self._lock:
            stats = {}
            
            for event_type, handlers in self.handlers.items():
                for handler in handlers:
                    stats[handler.name] = handler.get_stats()
            
            for handler in self.global_handlers:
                stats[handler.name] = handler.get_stats()
            
            return stats


# Global event dispatcher
event_dispatcher = EventDispatcher()


# Event utility functions
def create_event(event_type: str, source: str, data: Dict[str, Any] = None, 
                priority: EventPriority = EventPriority.NORMAL, **kwargs) -> Event:
    """
    Create a new event.
    
    Args:
        event_type: Type of the event
        source: Source of the event
        data: Event data
        priority: Event priority
        **kwargs: Additional event parameters
        
    Returns:
        Created event
    """
    return Event(
        event_type=event_type,
        source=source,
        data=data or {},
        priority=priority,
        **kwargs
    )


def dispatch_event(event_type: str, source: str, data: Dict[str, Any] = None,
                  priority: EventPriority = EventPriority.NORMAL, **kwargs) -> bool:
    """
    Create and dispatch an event.
    
    Args:
        event_type: Type of the event
        source: Source of the event
        data: Event data
        priority: Event priority
        **kwargs: Additional event parameters
        
    Returns:
        True if dispatch succeeded, False otherwise
    """
    event = create_event(event_type, source, data, priority, **kwargs)
    return event_dispatcher.dispatch(event)


async def dispatch_event_async(event_type: str, source: str, data: Dict[str, Any] = None,
                             priority: EventPriority = EventPriority.NORMAL, **kwargs) -> bool:
    """
    Create and dispatch an event asynchronously.
    
    Args:
        event_type: Type of the event
        source: Source of the event
        data: Event data
        priority: Event priority
        **kwargs: Additional event parameters
        
    Returns:
        True if dispatch succeeded, False otherwise
    """
    event = create_event(event_type, source, data, priority, **kwargs)
    return await event_dispatcher.dispatch_async(event)


def event_handler(event_type: str, **kwargs):
    """
    Decorator to register an event handler.
    
    Args:
        event_type: Type of event to handle
        **kwargs: Handler configuration
    """
    def decorator(func: Callable) -> Callable:
        handler = EventHandler(
            name=func.__name__,
            handler_func=func,
            **kwargs
        )
        event_dispatcher.register_handler(event_type, handler)
        return func
    return decorator


def global_event_handler(**kwargs):
    """
    Decorator to register a global event handler.
    
    Args:
        **kwargs: Handler configuration
    """
    def decorator(func: Callable) -> Callable:
        handler = EventHandler(
            name=func.__name__,
            handler_func=func,
            **kwargs
        )
        event_dispatcher.register_global_handler(handler)
        return func
    return decorator


# Event filtering utilities
class EventFilter:
    """Event filtering utilities."""
    
    @staticmethod
    def by_priority(min_priority: EventPriority) -> Callable:
        """Filter events by minimum priority."""
        def filter_func(event: Event) -> Event:
            if event.priority.value >= min_priority.value:
                return event
            return None
        return filter_func
    
    @staticmethod
    def by_source(source: str) -> Callable:
        """Filter events by source."""
        def filter_func(event: Event) -> Event:
            if event.source == source:
                return event
            return None
        return filter_func
    
    @staticmethod
    def by_user(user_id: str) -> Callable:
        """Filter events by user ID."""
        def filter_func(event: Event) -> Event:
            if event.user_id == user_id:
                return event
            return None
        return filter_func
    
    @staticmethod
    def by_tenant(tenant_id: str) -> Callable:
        """Filter events by tenant ID."""
        def filter_func(event: Event) -> Event:
            if event.tenant_id == tenant_id:
                return event
            return None
        return filter_func
    
    @staticmethod
    def by_data_key(key: str, value: Any) -> Callable:
        """Filter events by data key-value pair."""
        def filter_func(event: Event) -> Event:
            if event.data.get(key) == value:
                return event
            return None
        return filter_func
    
    @staticmethod
    def by_time_range(start_time: datetime, end_time: datetime) -> Callable:
        """Filter events by time range."""
        def filter_func(event: Event) -> Event:
            if start_time <= event.timestamp <= end_time:
                return event
            return None
        return filter_func


# Event condition utilities
class EventCondition:
    """Event condition utilities."""
    
    @staticmethod
    def during_business_hours(start_hour: int = 9, end_hour: int = 17) -> Callable:
        """Condition: event occurs during business hours."""
        def condition_func(event: Event) -> bool:
            return start_hour <= event.timestamp.hour <= end_hour
        return condition_func
    
    @staticmethod
    def on_weekdays() -> Callable:
        """Condition: event occurs on weekdays."""
        def condition_func(event: Event) -> bool:
            return event.timestamp.weekday() < 5
        return condition_func
    
    @staticmethod
    def has_data_key(key: str) -> Callable:
        """Condition: event has specific data key."""
        def condition_func(event: Event) -> bool:
            return key in event.data
        return condition_func
    
    @staticmethod
    def data_key_equals(key: str, value: Any) -> Callable:
        """Condition: event data key equals specific value."""
        def condition_func(event: Event) -> bool:
            return event.data.get(key) == value
        return condition_func
    
    @staticmethod
    def max_retry_count(max_retries: int) -> Callable:
        """Condition: event has not exceeded max retries."""
        def condition_func(event: Event) -> bool:
            return event.retry_count <= max_retries
        return condition_func


# Common moderation events
class ModerationEvents:
    """Common moderation event types."""
    
    SUBMISSION_RECEIVED = "submission.received"
    SUBMISSION_SCANNED = "submission.scanned"
    SUBMISSION_APPROVED = "submission.approved"
    SUBMISSION_REJECTED = "submission.rejected"
    SUBMISSION_ESCALATED = "submission.escalated"
    
    RULE_MATCHED = "rule.matched"
    RULE_FAILED = "rule.failed"
    
    SCAN_STARTED = "scan.started"
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED = "scan.failed"
    
    BOT_STARTED = "bot.started"
    BOT_STOPPED = "bot.stopped"
    BOT_ERROR = "bot.error"
    
    QUEUE_ITEM_ADDED = "queue.item_added"
    QUEUE_ITEM_ASSIGNED = "queue.item_assigned"
    QUEUE_ITEM_ESCALATED = "queue.item_escalated"
    
    DECISION_CREATED = "decision.created"
    DECISION_OVERRIDDEN = "decision.overridden"
    
    APPEAL_CREATED = "appeal.created"
    APPEAL_RESOLVED = "appeal.resolved"
    
    MODEL_TRAINED = "model.trained"
    MODEL_DEPLOYED = "model.deployed"
    
    SIGNAL_DETECTED = "signal.detected"
    SIGNAL_PROCESSED = "signal.processed"
    
    SYSTEM_ALERT = "system.alert"
    SYSTEM_ERROR = "system.error"


# Auto-registration of common event handlers
def register_common_event_handlers():
    """Register common event handlers."""
    # This would be implemented with actual handler functions
    # For now, it's a placeholder
    pass


# Initialize common event handlers on import
register_common_event_handlers()
