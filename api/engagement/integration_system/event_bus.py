# engagement/integration_system/event_bus.py
"""
Event bus system for integration communication.
Provides publish-subscribe pattern for event handling.
"""
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import threading
import weakref
from datetime import datetime, timedelta
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    EventPriority, ERROR_CODES, SUCCESS_CODES,
    DEFAULT_CONFIG, CACHE_KEYS, QUEUE_NAMES
)

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types."""
    SYSTEM = "system"
    USER = "user"
    INTEGRATION = "integration"
    DATA = "data"
    ERROR = "error"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    CUSTOM = "custom"


class EventStatus(Enum):
    """Event status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Event:
    """Event data structure."""
    id: str
    type: EventType
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    target: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'type': self.type.value,
            'name': self.name,
            'data': self.data,
            'source': self.source,
            'target': self.target,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
        }


@dataclass
class Subscription:
    """Event subscription."""
    id: str
    event_type: EventType
    event_name: str
    handler: Callable
    filter_func: Optional[Callable] = None
    priority: int = 0
    enabled: bool = True
    async_handler: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)


class BaseEventHandler(ABC):
    """Base event handler."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def handle(self, event: Event) -> Any:
        """Handle event."""
        pass
    
    def can_handle(self, event: Event) -> bool:
        """Check if handler can handle event."""
        return True
    
    def get_priority(self) -> int:
        """Get handler priority."""
        return 0


class EventBus:
    """Event bus for publish-subscribe pattern."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Subscription]] = defaultdict(list)
        self._event_queue: List[Event] = []
        self._processing_events: Set[str] = set()
        self._lock = threading.RLock()
        self._running = False
        self._worker_thread = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._event_history: List[Event] = []
        self._max_history_size = 1000
    
    def subscribe(self, event_type: EventType, event_name: str, 
                 handler: Callable, filter_func: Callable = None,
                 priority: int = 0, async_handler: bool = False,
                 metadata: Dict[str, Any] = None) -> str:
        """Subscribe to events."""
        subscription_id = f"sub_{timezone.now().timestamp()}"
        
        subscription = Subscription(
            id=subscription_id,
            event_type=event_type,
            event_name=event_name,
            handler=handler,
            filter_func=filter_func,
            priority=priority,
            async_handler=async_handler,
            metadata=metadata or {}
        )
        
        with self._lock:
            # Add to subscribers
            key = f"{event_type.value}:{event_name}"
            self._subscribers[key].append(subscription)
            
            # Sort by priority (higher priority first)
            self._subscribers[key].sort(key=lambda s: s.priority, reverse=True)
        
        self.logger.info(f"Subscribed to {event_type.value}:{event_name} with ID {subscription_id}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            for key, subscriptions in self._subscribers.items():
                for i, subscription in enumerate(subscriptions):
                    if subscription.id == subscription_id:
                        subscriptions.pop(i)
                        self.logger.info(f"Unsubscribed from {key} with ID {subscription_id}")
                        return True
        
        return False
    
    def publish(self, event: Event) -> str:
        """Publish event to bus."""
        with self._lock:
            # Add to queue
            self._event_queue.append(event)
            
            # Add to history
            self._add_to_history(event)
            
            # Start processing if not running
            if not self._running:
                self._start_processing()
        
        self.logger.info(f"Published event {event.id}: {event.type.value}:{event.name}")
        return event.id
    
    def publish_async(self, event: Event) -> str:
        """Publish event asynchronously."""
        # For now, use synchronous publish
        # In a real implementation, this would use async processing
        return self.publish(event)
    
    def get_event_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event status."""
        with self._lock:
            # Check queue
            for event in self._event_queue:
                if event.id == event_id:
                    return event.to_dict()
            
            # Check processing events
            for event_id in self._processing_events:
                # This would need to store event references
                pass
            
            # Check history
            for event in self._event_history:
                if event.id == event_id:
                    return event.to_dict()
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            total_subscribers = sum(len(subs) for subs in self._subscribers.values())
            queue_size = len(self._event_queue)
            processing_count = len(self._processing_events)
            history_size = len(self._event_history)
            
            # Count by event type
            type_counts = defaultdict(int)
            for event in self._event_history:
                type_counts[event.type.value] += 1
            
            # Count by status
            status_counts = defaultdict(int)
            for event in self._event_history:
                status_counts[event.status.value] += 1
            
            return {
                'total_subscribers': total_subscribers,
                'queue_size': queue_size,
                'processing_count': processing_count,
                'history_size': history_size,
                'type_counts': dict(type_counts),
                'status_counts': dict(status_counts),
                'is_running': self._running,
                'last_updated': timezone.now().isoformat(),
            }
    
    def clear_history(self) -> int:
        """Clear event history."""
        with self._lock:
            cleared_count = len(self._event_history)
            self._event_history.clear()
            return cleared_count
    
    def _start_processing(self):
        """Start event processing worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_events, daemon=True)
        self._worker_thread.start()
        self.logger.info("Started event processing worker")
    
    def _stop_processing(self):
        """Stop event processing worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self.logger.info("Stopped event processing worker")
    
    def _process_events(self):
        """Process events from queue."""
        while self._running:
            try:
                with self._lock:
                    if not self._event_queue:
                        # No events to process, wait a bit
                        self._lock.release()
                        threading.Event().wait(0.1)
                        continue
                    
                    event = self._event_queue.pop(0)
                    self._processing_events.add(event.id)
                
                # Process event
                self._process_single_event(event)
                
                with self._lock:
                    self._processing_events.discard(event.id)
                
            except Exception as exc:
                self.logger.error(f"Error processing events: {exc}")
                threading.Event().wait(1)  # Wait before retrying
    
    def _process_single_event(self, event: Event):
        """Process a single event."""
        try:
            event.status = EventStatus.PROCESSING
            
            # Get subscribers for this event
            key = f"{event.type.value}:{event.name}"
            subscribers = self._subscribers.get(key, [])
            
            if not subscribers:
                self.logger.warning(f"No subscribers for event {event.id}: {key}")
                event.status = EventStatus.COMPLETED
                return
            
            # Process each subscriber
            for subscription in subscribers:
                if not subscription.enabled:
                    continue
                
                try:
                    # Check filter function
                    if subscription.filter_func and not subscription.filter_func(event):
                        continue
                    
                    # Check if handler can handle event
                    if hasattr(subscription.handler, 'can_handle'):
                        if not subscription.handler.can_handle(event):
                            continue
                    
                    # Handle event
                    if subscription.async_handler:
                        # Async handler (simplified)
                        threading.Thread(
                            target=subscription.handler,
                            args=(event,),
                            daemon=True
                        ).start()
                    else:
                        # Sync handler
                        result = subscription.handler(event)
                        self.logger.debug(f"Handler {subscription.id} processed event {event.id}")
                    
                except Exception as exc:
                    self.logger.error(f"Handler {subscription.id} failed for event {event.id}: {exc}")
                    # Continue with other handlers
            
            event.status = EventStatus.COMPLETED
            
        except Exception as exc:
            self.logger.error(f"Error processing event {event.id}: {exc}")
            event.status = EventStatus.FAILED
            event.retry_count += 1
            
            # Retry if needed
            if event.retry_count < event.max_retries:
                event.status = EventStatus.PENDING
                with self._lock:
                    self._event_queue.append(event)
    
    def _add_to_history(self, event: Event):
        """Add event to history."""
        self._event_history.append(event)
        
        # Limit history size
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]


class EventFilter:
    """Event filter utilities."""
    
    @staticmethod
    def by_source(source: str) -> Callable:
        """Filter events by source."""
        def filter_func(event: Event) -> bool:
            return event.source == source
        return filter_func
    
    @staticmethod
    def by_priority(min_priority: EventPriority) -> Callable:
        """Filter events by minimum priority."""
        def filter_func(event: Event) -> bool:
            priority_values = {
                EventPriority.LOW: 1,
                EventPriority.NORMAL: 2,
                EventPriority.HIGH: 3,
                EventPriority.CRITICAL: 4,
                EventPriority.URGENT: 5,
            }
            return priority_values.get(event.priority, 0) >= priority_values.get(min_priority, 0)
        return filter_func
    
    @staticmethod
    def by_data_key(key: str, value: Any = None) -> Callable:
        """Filter events by data key/value."""
        def filter_func(event: Event) -> bool:
            if key not in event.data:
                return False
            if value is not None:
                return event.data[key] == value
            return True
        return filter_func
    
    @staticmethod
    def by_time_range(start_time: datetime, end_time: datetime = None) -> Callable:
        """Filter events by time range."""
        def filter_func(event: Event) -> bool:
            if end_time:
                return start_time <= event.timestamp <= end_time
            else:
                return event.timestamp >= start_time
        return filter_func
    
    @staticmethod
    def custom(filter_func: Callable) -> Callable:
        """Custom filter function."""
        return filter_func


class EventBuilder:
    """Builder for creating events."""
    
    @staticmethod
    def create(event_type: EventType, name: str, **kwargs) -> Event:
        """Create an event."""
        import uuid
        
        return Event(
            id=str(uuid.uuid4()),
            type=event_type,
            name=name,
            **kwargs
        )
    
    @staticmethod
    def system_event(name: str, data: Dict[str, Any] = None, **kwargs) -> Event:
        """Create a system event."""
        return EventBuilder.create(
            EventType.SYSTEM,
            name,
            data=data or {},
            **kwargs
        )
    
    @staticmethod
    def user_event(name: str, user_id: str, data: Dict[str, Any] = None, **kwargs) -> Event:
        """Create a user event."""
        return EventBuilder.create(
            EventType.USER,
            name,
            data=data or {},
            source=f"user:{user_id}",
            **kwargs
        )
    
    @staticmethod
    def integration_event(name: str, integration_id: str, data: Dict[str, Any] = None, **kwargs) -> Event:
        """Create an integration event."""
        return EventBuilder.create(
            EventType.INTEGRATION,
            name,
            data=data or {},
            source=f"integration:{integration_id}",
            **kwargs
        )
    
    @staticmethod
    def error_event(name: str, error: Exception, data: Dict[str, Any] = None, **kwargs) -> Event:
        """Create an error event."""
        return EventBuilder.create(
            EventType.ERROR,
            name,
            data={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'error_traceback': traceback.format_exc(),
                **(data or {})
            },
            priority=EventPriority.HIGH,
            **kwargs
        )
    
    @staticmethod
    def security_event(name: str, data: Dict[str, Any] = None, **kwargs) -> Event:
        """Create a security event."""
        return EventBuilder.create(
            EventType.SECURITY,
            name,
            data=data or {},
            priority=EventPriority.CRITICAL,
            **kwargs
        )


class EventStore:
    """Event storage and retrieval."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def store_event(self, event: Event) -> bool:
        """Store event in persistent storage."""
        try:
            # This would store event in database or other persistent storage
            # For now, just log it
            self.logger.info(f"Stored event {event.id}: {event.type.value}:{event.name}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to store event {event.id}: {exc}")
            return False
    
    def get_events(self, event_type: EventType = None, event_name: str = None,
                   start_time: datetime = None, end_time: datetime = None,
                   limit: int = 100) -> List[Event]:
        """Retrieve events from storage."""
        try:
            # This would retrieve events from database
            # For now, return empty list
            return []
        except Exception as exc:
            self.logger.error(f"Failed to retrieve events: {exc}")
            return []
    
    def get_event_by_id(self, event_id: str) -> Optional[Event]:
        """Get specific event by ID."""
        try:
            # This would retrieve specific event from database
            # For now, return None
            return None
        except Exception as exc:
            self.logger.error(f"Failed to retrieve event {event_id}: {exc}")
            return None


class EventMetrics:
    """Event metrics and analytics."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._metrics = defaultdict(int)
        self._lock = threading.Lock()
    
    def increment_metric(self, metric_name: str, value: int = 1):
        """Increment metric."""
        with self._lock:
            self._metrics[metric_name] += value
    
    def get_metrics(self) -> Dict[str, int]:
        """Get all metrics."""
        with self._lock:
            return dict(self._metrics)
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()


# Global instances
event_bus = EventBus()
event_store = EventStore()
event_metrics = EventMetrics()


# Event handlers
class DefaultEventHandlers:
    """Default event handlers."""
    
    @staticmethod
    def log_event(event: Event):
        """Log event handler."""
        logger.info(f"Event logged: {event.id} - {event.type.value}:{event.name}")
    
    @staticmethod
    def store_event(event: Event):
        """Store event handler."""
        event_store.store_event(event)
    
    @staticmethod
    def update_metrics(event: Event):
        """Update metrics handler."""
        event_metrics.increment_metric(f"event_{event.type.value}")
        event_metrics.increment_metric(f"event_{event.name}")
    
    @staticmethod
    def send_notification(event: Event):
        """Send notification handler."""
        if event.type == EventType.ERROR:
            # Send error notification
            pass
        elif event.type == EventType.SECURITY:
            # Send security alert
            pass


# Event utilities
class EventUtils:
    """Event utilities."""
    
    @staticmethod
    def create_event_id() -> str:
        """Create unique event ID."""
        import uuid
        return str(uuid.uuid4())
    
    @staticmethod
    def validate_event(event: Event) -> bool:
        """Validate event structure."""
        return (
            event.id and
            event.type and
            event.name and
            event.timestamp
        )
    
    @staticmethod
    def serialize_event(event: Event) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return event.to_dict()
    
    @staticmethod
    def deserialize_event(data: Dict[str, Any]) -> Event:
        """Deserialize event from dictionary."""
        return Event(
            id=data['id'],
            type=EventType(data['type']),
            name=data['name'],
            data=data.get('data', {}),
            source=data.get('source', ''),
            target=data.get('target'),
            priority=EventPriority(data.get('priority', 'normal')),
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {}),
            status=EventStatus(data.get('status', 'pending')),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout=data.get('timeout', 30)
        )


# Decorators
def event_handler(event_type: EventType, event_name: str = None, 
                 priority: int = 0, async_handler: bool = False):
    """Decorator to register event handler."""
    def decorator(handler_func):
        # Subscribe the handler
        subscription_id = event_bus.subscribe(
            event_type=event_type,
            event_name=event_name or handler_func.__name__,
            handler=handler_func,
            priority=priority,
            async_handler=async_handler
        )
        
        # Add subscription ID to function
        handler_func._subscription_id = subscription_id
        
        return handler_func
    return decorator


def event_filter(filter_func: Callable):
    """Decorator to add filter to event handler."""
    def decorator(handler_func):
        # This would modify the subscription to add filter
        # For now, just return the function
        return handler_func
    return decorator
