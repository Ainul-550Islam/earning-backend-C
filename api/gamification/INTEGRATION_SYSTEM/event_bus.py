"""
Event Bus System — Event-driven communication and messaging system.

This module provides a comprehensive event bus system for handling
event-driven communication between different components and systems.
"""

from __future__ import annotations

import logging
import asyncio
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type, Set
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

from .integ_constants import Priority, MessageType
from .integ_exceptions import (
    IntegrationError, ValidationError, TimeoutError,
    QueueFullError, QueueEmptyError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event Bus Types
# ---------------------------------------------------------------------------

class EventType(Enum):
    """Event type enumeration."""
    SYSTEM = "system"
    USER = "user"
    INTEGRATION = "integration"
    BUSINESS = "business"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR = "error"
    CUSTOM = "custom"


class EventDeliveryMode(Enum):
    """Event delivery mode enumeration."""
    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"
    GUARANTEED = "guaranteed"


class EventPriority(Enum):
    """Event priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class EventBusState(Enum):
    """Event bus state enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Event Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """Event data structure."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    source: str = ""
    target: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: EventPriority = EventPriority.NORMAL
    delivery_mode: EventDeliveryMode = EventDeliveryMode.FIRE_AND_FORGET
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if event has expired."""
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "headers": self.headers,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "delivery_mode": self.delivery_mode.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout
        }


@dataclass
class EventHandler:
    """Event handler configuration."""
    
    id: str
    event_type: str
    handler: Callable[[Event], Any]
    priority: EventPriority = EventPriority.NORMAL
    enabled: bool = True
    filter_func: Optional[Callable[[Event], bool]] = None
    async_handler: bool = False
    max_concurrent: int = 10
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def can_handle(self, event: Event) -> bool:
        """Check if handler can handle the event."""
        if not self.enabled:
            return False
        
        if self.event_type != "*" and event.type != self.event_type:
            return False
        
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True


@dataclass
class EventSubscription:
    """Event subscription configuration."""
    
    id: str
    subscriber: str
    event_types: List[str]
    handler: Callable[[Event], Any]
    filters: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    enabled: bool = True
    
    def matches(self, event: Event) -> bool:
        """Check if subscription matches the event."""
        if not self.enabled:
            return False
        
        if "*" not in self.event_types and event.type not in self.event_types:
            return False
        
        # Apply filters
        for key, value in self.filters.items():
            if key == "source":
                if event.source != value:
                    return False
            elif key == "priority":
                if event.priority.value < value:
                    return False
            elif key in event.metadata:
                if event.metadata[key] != value:
                    return False
        
        return True


@dataclass
class EventBusMetrics:
    """Event bus metrics."""
    
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    queued_events: int = 0
    active_handlers: int = 0
    average_processing_time: float = 0.0
    events_per_second: float = 0.0
    last_event_time: Optional[datetime] = None
    uptime: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "queued_events": self.queued_events,
            "active_handlers": self.active_handlers,
            "average_processing_time": self.average_processing_time,
            "events_per_second": self.events_per_second,
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "uptime": self.uptime
        }


# ---------------------------------------------------------------------------
# Abstract Event Bus
# ---------------------------------------------------------------------------

class BaseEventBus(ABC):
    """Abstract base class for event buses."""
    
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.state = EventBusState.STOPPED
        self.metrics = EventBusMetrics()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = threading.RLock()
        self._start_time: Optional[datetime] = None
        self._shutdown_event = threading.Event()
    
    @abstractmethod
    def start(self) -> None:
        """Start the event bus."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the event bus."""
        pass
    
    @abstractmethod
    def publish(self, event: Event) -> bool:
        """Publish an event."""
        pass
    
    @abstractmethod
    def subscribe(self, subscription: EventSubscription) -> str:
        """Subscribe to events."""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> EventBusMetrics:
        """Get event bus metrics."""
        pass
    
    def is_running(self) -> bool:
        """Check if event bus is running."""
        return self.state == EventBusState.RUNNING
    
    def create_event(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        **kwargs: Any
    ) -> Event:
        """Create a new event."""
        return Event(
            type=event_type,
            source=source,
            payload=payload,
            priority=kwargs.get("priority", EventPriority.NORMAL),
            delivery_mode=kwargs.get("delivery_mode", EventDeliveryMode.FIRE_AND_FORGET),
            target=kwargs.get("target"),
            headers=kwargs.get("headers", {}),
            metadata=kwargs.get("metadata", {}),
            correlation_id=kwargs.get("correlation_id"),
            reply_to=kwargs.get("reply_to"),
            expires_at=kwargs.get("expires_at"),
            max_retries=kwargs.get("max_retries", 3),
            timeout=kwargs.get("timeout")
        )


# ---------------------------------------------------------------------------
# In-Memory Event Bus Implementation
# ---------------------------------------------------------------------------

class InMemoryEventBus(BaseEventBus):
    """In-memory event bus implementation."""
    
    def __init__(self, max_queue_size: int = 10000, num_workers: int = 4):
        super().__init__(max_queue_size)
        self.num_workers = num_workers
        self.event_queue: deque[Event] = deque()
        self.handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self.subscriptions: Dict[str, EventSubscription] = {}
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self._processing_thread: Optional[threading.Thread] = None
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    def start(self) -> None:
        """Start the event bus."""
        if self.state != EventBusState.STOPPED:
            raise IntegrationError("Event bus is already running")
        
        self.state = EventBusState.STARTING
        self._start_time = datetime.now(timezone.utc)
        
        try:
            # Start processing thread
            self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
            self._processing_thread.start()
            
            self.state = EventBusState.RUNNING
            self.logger.info("Event bus started")
            
        except Exception as e:
            self.state = EventBusState.ERROR
            raise IntegrationError(f"Failed to start event bus: {e}")
    
    def stop(self) -> None:
        """Stop the event bus."""
        if self.state != EventBusState.RUNNING:
            return
        
        self.state = EventBusState.STOPPING
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for processing thread to finish
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.state = EventBusState.STOPPED
        self.logger.info("Event bus stopped")
    
    def publish(self, event: Event) -> bool:
        """Publish an event."""
        if not self.is_running():
            raise IntegrationError("Event bus is not running")
        
        if event.is_expired():
            self.logger.warning(f"Event {event.id} is expired, discarding")
            return False
        
        with self._lock:
            if len(self.event_queue) >= self.max_queue_size:
                raise QueueFullError("Event queue is full")
            
            self.event_queue.append(event)
            self.metrics.total_events += 1
            self.metrics.queued_events += 1
            self.metrics.last_event_time = datetime.now(timezone.utc)
        
        self.logger.debug(f"Published event {event.id} of type {event.type}")
        return True
    
    def subscribe(self, subscription: EventSubscription) -> str:
        """Subscribe to events."""
        with self._lock:
            self.subscriptions[subscription.id] = subscription
            
            # Add handlers for each event type
            for event_type in subscription.event_types:
                handler = EventHandler(
                    id=f"{subscription.id}_{event_type}",
                    event_type=event_type,
                    handler=subscription.handler,
                    priority=subscription.priority,
                    filter_func=lambda e, sub=subscription: sub.matches(e)
                )
                self.handlers[event_type].append(handler)
                self.handlers[event_type].sort(key=lambda h: h.priority.value, reverse=True)
        
        self.logger.info(f"Subscribed {subscription.subscriber} to events {subscription.event_types}")
        return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            if subscription_id not in self.subscriptions:
                return False
            
            subscription = self.subscriptions[subscription_id]
            
            # Remove handlers
            for event_type in subscription.event_types:
                handler_id = f"{subscription_id}_{event_type}"
                self.handlers[event_type] = [
                    h for h in self.handlers[event_type] if h.id != handler_id
                ]
            
            del self.subscriptions[subscription_id]
        
        self.logger.info(f"Unsubscribed {subscription_id}")
        return True
    
    def add_handler(self, event_type: str, handler: EventHandler) -> None:
        """Add an event handler."""
        with self._lock:
            self.handlers[event_type].append(handler)
            self.handlers[event_type].sort(key=lambda h: h.priority.value, reverse=True)
        
        self.logger.info(f"Added handler for event type {event_type}")
    
    def remove_handler(self, event_type: str, handler_id: str) -> bool:
        """Remove an event handler."""
        with self._lock:
            if event_type not in self.handlers:
                return False
            
            original_count = len(self.handlers[event_type])
            self.handlers[event_type] = [
                h for h in self.handlers[event_type] if h.id != handler_id
            ]
            
            return len(self.handlers[event_type]) < original_count
    
    def get_metrics(self) -> EventBusMetrics:
        """Get event bus metrics."""
        with self._lock:
            # Update uptime
            if self._start_time:
                self.metrics.uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            # Calculate events per second
            if self.metrics.uptime > 0:
                self.metrics.events_per_second = self.metrics.total_events / self.metrics.uptime
            
            # Update active handlers count
            self.metrics.active_handlers = sum(len(handlers) for handlers in self.handlers.values())
            
            return self.metrics
    
    def _process_events(self) -> None:
        """Process events from the queue."""
        while not self._shutdown_event.is_set():
            try:
                event = None
                
                with self._lock:
                    if self.event_queue:
                        event = self.event_queue.popleft()
                        self.metrics.queued_events -= 1
                
                if event:
                    self._handle_event(event)
                else:
                    # No events, wait a bit
                    time.sleep(0.01)
                    
            except Exception as e:
                self.logger.error(f"Error processing events: {e}")
                self.metrics.failed_events += 1
    
    def _handle_event(self, event: Event) -> None:
        """Handle a single event."""
        start_time = time.time()
        
        try:
            # Get handlers for this event type
            handlers = self.handlers.get(event.type, [])
            wildcard_handlers = self.handlers.get("*", [])
            all_handlers = handlers + wildcard_handlers
            
            # Filter handlers that can handle this event
            eligible_handlers = [h for h in all_handlers if h.can_handle(event)]
            
            if not eligible_handlers:
                self.logger.debug(f"No handlers for event {event.id} of type {event.type}")
                return
            
            # Process handlers
            futures = []
            for handler in eligible_handlers:
                if handler.async_handler:
                    future = self.executor.submit(self._handle_async_event, handler, event)
                    futures.append(future)
                else:
                    self._handle_sync_event(handler, event)
            
            # Wait for async handlers
            for future in futures:
                try:
                    future.result(timeout=handler.timeout)
                except Exception as e:
                    self.logger.error(f"Async handler failed: {e}")
                    self.metrics.failed_events += 1
            
            self.metrics.processed_events += 1
            
        except Exception as e:
            self.logger.error(f"Error handling event {event.id}: {e}")
            self.metrics.failed_events += 1
        
        finally:
            # Update processing time
            processing_time = time.time() - start_time
            total_events = self.metrics.processed_events + self.metrics.failed_events
            if total_events > 0:
                self.metrics.average_processing_time = (
                    (self.metrics.average_processing_time * (total_events - 1) + processing_time) / total_events
                )
    
    def _handle_sync_event(self, handler: EventHandler, event: Event) -> None:
        """Handle event synchronously."""
        try:
            handler.handler(event)
        except Exception as e:
            self.logger.error(f"Sync handler {handler.id} failed: {e}")
            raise
    
    def _handle_async_event(self, handler: EventHandler, event: Event) -> None:
        """Handle event asynchronously."""
        try:
            if handler.async_handler:
                # Run async handler in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(handler.handler(event))
                finally:
                    loop.close()
            else:
                handler.handler(event)
        except Exception as e:
            self.logger.error(f"Async handler {handler.id} failed: {e}")
            raise


# ---------------------------------------------------------------------------
# Event Bus Manager
# ---------------------------------------------------------------------------

class EventBusManager:
    """Manager for multiple event buses."""
    
    def __init__(self):
        self.buses: Dict[str, BaseEventBus] = {}
        self.default_bus_name = "default"
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def create_bus(
        self,
        name: str,
        bus_type: str = "memory",
        **kwargs: Any
    ) -> BaseEventBus:
        """Create a new event bus."""
        with self._lock:
            if name in self.buses:
                raise IntegrationError(f"Event bus '{name}' already exists")
            
            if bus_type == "memory":
                bus = InMemoryEventBus(**kwargs)
            else:
                raise IntegrationError(f"Unknown bus type: {bus_type}")
            
            self.buses[name] = bus
            self.logger.info(f"Created event bus '{name}' of type '{bus_type}'")
            
            return bus
    
    def get_bus(self, name: Optional[str] = None) -> BaseEventBus:
        """Get an event bus by name."""
        bus_name = name or self.default_bus_name
        
        if bus_name not in self.buses:
            raise IntegrationNotFoundError(f"Event bus '{bus_name}' not found")
        
        return self.buses[bus_name]
    
    def delete_bus(self, name: str) -> bool:
        """Delete an event bus."""
        with self._lock:
            if name not in self.buses:
                return False
            
            bus = self.buses[name]
            
            # Stop the bus if running
            if bus.is_running():
                bus.stop()
            
            del self.buses[name]
            self.logger.info(f"Deleted event bus '{name}'")
            
            return True
    
    def start_bus(self, name: Optional[str] = None) -> bool:
        """Start an event bus."""
        bus = self.get_bus(name)
        
        try:
            bus.start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start event bus '{name}': {e}")
            return False
    
    def stop_bus(self, name: Optional[str] = None) -> bool:
        """Stop an event bus."""
        bus = self.get_bus(name)
        
        try:
            bus.stop()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop event bus '{name}': {e}")
            return False
    
    def publish_event(
        self,
        event: Event,
        bus_name: Optional[str] = None
    ) -> bool:
        """Publish an event to a specific bus."""
        bus = self.get_bus(bus_name)
        return bus.publish(event)
    
    def subscribe_to_events(
        self,
        subscription: EventSubscription,
        bus_name: Optional[str] = None
    ) -> str:
        """Subscribe to events on a specific bus."""
        bus = self.get_bus(bus_name)
        return bus.subscribe(subscription)
    
    def unsubscribe_from_events(
        self,
        subscription_id: str,
        bus_name: Optional[str] = None
    ) -> bool:
        """Unsubscribe from events on a specific bus."""
        bus = self.get_bus(bus_name)
        return bus.unsubscribe(subscription_id)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all event buses."""
        metrics = {}
        
        for name, bus in self.buses.items():
            try:
                metrics[name] = bus.get_metrics().to_dict()
            except Exception as e:
                metrics[name] = {"error": str(e)}
        
        return {
            "buses": metrics,
            "total_buses": len(self.buses),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def shutdown_all(self) -> None:
        """Shutdown all event buses."""
        for name, bus in self.buses.items():
            try:
                if bus.is_running():
                    bus.stop()
            except Exception as e:
                self.logger.error(f"Error stopping bus '{name}': {e}")
        
        self.logger.info("All event buses shutdown")


# Global event bus manager instance
event_bus_manager = EventBusManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def get_event_bus(name: Optional[str] = None) -> BaseEventBus:
    """Get an event bus."""
    return event_bus_manager.get_bus(name)


def publish_event(
    event_type: str,
    source: str,
    payload: Dict[str, Any],
    bus_name: Optional[str] = None,
    **kwargs: Any
) -> bool:
    """Publish an event."""
    bus = event_bus_manager.get_bus(bus_name)
    event = bus.create_event(event_type, source, payload, **kwargs)
    return bus.publish(event)


def subscribe_to_events(
    subscriber: str,
    event_types: List[str],
    handler: Callable[[Event], Any],
    bus_name: Optional[str] = None,
    **kwargs: Any
) -> str:
    """Subscribe to events."""
    bus = event_bus_manager.get_bus(bus_name)
    
    import uuid
    subscription = EventSubscription(
        id=str(uuid.uuid4()),
        subscriber=subscriber,
        event_types=event_types,
        handler=handler,
        **kwargs
    )
    
    return bus.subscribe(subscription)


# Initialize logging
logger.info("Event bus system module initialized")
