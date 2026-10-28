"""
event_bus.py – Event Bus implementation for postback module.

Provides comprehensive event bus functionality including:
- Event publishing and subscribing
- Event routing and filtering
- Event persistence and replay
- Event bus management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import queue
import json

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationEventType, IntegrationLogLevel
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class EventStatus(Enum):
    """Event status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventPriority(Enum):
    """Event priority enumeration."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class Event:
    """Event data structure."""
    id: str
    event_type: str
    source: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=timezone.now)
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'status': self.status.value,
            'metadata': self.metadata,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'correlation_id': self.correlation_id,
            'causation_id': self.causation_id,
        }


@dataclass
class EventSubscription:
    """Event subscription data structure."""
    id: str
    subscriber: str
    event_type: str
    handler: Callable
    filter_criteria: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: EventPriority = EventPriority.NORMAL
    created_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, event: Event) -> bool:
        """Check if subscription matches event."""
        if not self.enabled:
            return False
        
        if self.event_type != '*' and self.event_type != event.event_type:
            return False
        
        # Apply filter criteria
        for key, value in self.filter_criteria.items():
            event_value = event.data.get(key)
            if event_value != value:
                return False
        
        return True


class EventBus:
    """
    Event bus for managing event flow.
    
    Handles event publishing, subscribing, routing,
    and persistence.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.subscriptions: Dict[str, List[EventSubscription]] = defaultdict(list)
        self.event_queue = queue.PriorityQueue()
        self.processed_events: Dict[str, Event] = {}
        self.failed_events: Dict[str, Event] = {}
        self.event_history: List[Event] = []
        self.running = False
        self.worker_thread = None
        self.max_history_size = 10000
        self.persistence_enabled = True
        self._setup_event_bus()
    
    def _setup_event_bus(self):
        """Setup event bus."""
        self.logger.info("Event bus initialized")
    
    def start(self):
        """Start event bus."""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.logger.info("Event bus started")
    
    def stop(self):
        """Stop event bus."""
        if not self.running:
            return
        
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.logger.info("Event bus stopped")
    
    def publish(self, event_type: str, source: str, data: Dict[str, Any],
               priority: EventPriority = EventPriority.NORMAL,
               correlation_id: str = None, causation_id: str = None,
               metadata: Dict[str, Any] = None) -> str:
        """
        Publish event to event bus.
        
        Args:
            event_type: Type of event
            source: Event source
            data: Event data
            priority: Event priority
            correlation_id: Correlation ID
            causation_id: Causation ID
            metadata: Additional metadata
            
        Returns:
            Event ID
        """
        import uuid
        
        event = Event(
            id=f"event_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            source=source,
            data=data,
            priority=priority,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=metadata or {}
        )
        
        # Add to queue
        priority_value = 100 - event.priority.value  # Higher priority = lower number
        self.event_queue.put((priority_value, event.timestamp, event))
        
        # Persist event if enabled
        if self.persistence_enabled:
            self._persist_event(event)
        
        self.logger.debug(f"Event published: {event.id} - {event_type}")
        return event.id
    
    def subscribe(self, subscriber: str, event_type: str, handler: Callable,
                 filter_criteria: Dict[str, Any] = None,
                 priority: EventPriority = EventPriority.NORMAL) -> str:
        """
        Subscribe to events.
        
        Args:
            subscriber: Subscriber identifier
            event_type: Event type to subscribe to
            handler: Event handler function
            filter_criteria: Event filter criteria
            priority: Subscription priority
            
        Returns:
            Subscription ID
        """
        import uuid
        
        subscription = EventSubscription(
            id=f"sub_{uuid.uuid4().hex[:12]}",
            subscriber=subscriber,
            event_type=event_type,
            handler=handler,
            filter_criteria=filter_criteria or {},
            priority=priority
        )
        
        self.subscriptions[event_type].append(subscription)
        
        # Sort subscriptions by priority
        self.subscriptions[event_type].sort(key=lambda x: x.priority.value, reverse=True)
        
        self.logger.info(f"Subscription created: {subscription.id} - {subscriber} -> {event_type}")
        return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if unsubscribed successfully
        """
        for event_type, subscriptions in self.subscriptions.items():
            for i, subscription in enumerate(subscriptions):
                if subscription.id == subscription_id:
                    subscriptions.pop(i)
                    self.logger.info(f"Subscription removed: {subscription_id}")
                    return True
        
        return False
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """
        Get event by ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            Event or None
        """
        return self.processed_events.get(event_id)
    
    def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Event]:
        """
        Get events by type.
        
        Args:
            event_type: Event type
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        events = [event for event in self.event_history if event.event_type == event_type]
        return events[-limit:]
    
    def get_events_by_source(self, source: str, limit: int = 100) -> List[Event]:
        """
        Get events by source.
        
        Args:
            source: Event source
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        events = [event for event in self.event_history if event.source == source]
        return events[-limit:]
    
    def get_events_by_correlation(self, correlation_id: str) -> List[Event]:
        """
        Get events by correlation ID.
        
        Args:
            correlation_id: Correlation ID
            
        Returns:
            List of events
        """
        return [event for event in self.event_history if event.correlation_id == correlation_id]
    
    def replay_events(self, event_type: str = None, start_time: datetime = None,
                      end_time: datetime = None) -> int:
        """
        Replay events from history.
        
        Args:
            event_type: Event type filter
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            Number of events replayed
        """
        replayed_count = 0
        
        for event in self.event_history:
            # Apply filters
            if event_type and event.event_type != event_type:
                continue
            
            if start_time and event.timestamp < start_time:
                continue
            
            if end_time and event.timestamp > end_time:
                continue
            
            # Republish event
            self.publish(
                event.event_type,
                event.source,
                event.data,
                event.priority,
                event.correlation_id,
                event.causation_id,
                {**event.metadata, 'replayed': True}
            )
            replayed_count += 1
        
        self.logger.info(f"Replayed {replayed_count} events")
        return replayed_count
    
    def _worker_loop(self):
        """Worker loop for processing events."""
        while self.running:
            try:
                # Get event from queue
                try:
                    priority, timestamp, event = self.event_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Process event
                self._process_event(event)
                
            except Exception as e:
                self.logger.error(f"Error in event bus worker: {str(e)}")
    
    def _process_event(self, event: Event):
        """Process single event."""
        try:
            event.status = EventStatus.PROCESSING
            
            # Get matching subscriptions
            matching_subscriptions = []
            
            # Exact type match
            for subscription in self.subscriptions.get(event.event_type, []):
                if subscription.matches(event):
                    matching_subscriptions.append(subscription)
            
            # Wildcard match
            for subscription in self.subscriptions.get('*', []):
                if subscription.matches(event):
                    matching_subscriptions.append(subscription)
            
            # Execute handlers
            handlers_executed = 0
            for subscription in matching_subscriptions:
                try:
                    subscription.handler(event)
                    handlers_executed += 1
                except Exception as e:
                    self.logger.error(f"Error in event handler {subscription.id}: {str(e)}")
                    event.retry_count += 1
            
            # Update event status
            if handlers_executed > 0:
                event.status = EventStatus.COMPLETED
            else:
                event.status = EventStatus.FAILED
            
            # Store processed event
            self.processed_events[event.id] = event
            self.event_history.append(event)
            
            # Limit history size
            if len(self.event_history) > self.max_history_size:
                self.event_history = self.event_history[-self.max_history_size:]
            
            self.logger.debug(f"Event processed: {event.id} - {event.event_type} ({handlers_executed} handlers)")
        
        except Exception as e:
            event.status = EventStatus.FAILED
            self.logger.error(f"Error processing event {event.id}: {str(e)}")
            
            # Add to failed events
            self.failed_events[event.id] = event
    
    def _persist_event(self, event: Event):
        """Persist event to storage."""
        try:
            # Store in cache for quick access
            cache_key = f"event_{event.id}"
            cache.set(cache_key, event.to_dict(), timeout=3600)
            
            # Could also persist to database here
            # For now, just use cache
            
        except Exception as e:
            self.logger.error(f"Error persisting event {event.id}: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        total_events = len(self.event_history)
        completed_events = len([e for e in self.event_history if e.status == EventStatus.COMPLETED])
        failed_events = len([e for e in self.event_history if e.status == EventStatus.FAILED])
        
        # Event type distribution
        event_types = defaultdict(int)
        for event in self.event_history:
            event_types[event.event_type] += 1
        
        # Source distribution
        sources = defaultdict(int)
        for event in self.event_history:
            sources[event.source] += 1
        
        # Subscription statistics
        subscription_stats = {}
        for event_type, subscriptions in self.subscriptions.items():
            subscription_stats[event_type] = {
                'total': len(subscriptions),
                'active': len([s for s in subscriptions if s.enabled]),
            }
        
        return {
            'total_events': total_events,
            'completed_events': completed_events,
            'failed_events': failed_events,
            'success_rate': (completed_events / total_events * 100) if total_events > 0 else 0,
            'queue_size': self.event_queue.qsize(),
            'active_subscriptions': len([s for subs in self.subscriptions.values() for s in subs if s.enabled]),
            'event_types': dict(event_types),
            'sources': dict(sources),
            'subscription_stats': subscription_stats,
            'running': self.running,
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            'overall': 'healthy',
            'running': self.running,
            'queue_size': self.event_queue.qsize(),
            'worker_thread_alive': self.worker_thread.is_alive() if self.worker_thread else False,
            'issues': [],
        }
        
        # Check if event bus is running
        if not self.running:
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append("Event bus is not running")
        
        # Check worker thread
        if self.worker_thread and not self.worker_thread.is_alive():
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append("Worker thread is not alive")
        
        # Check queue size
        if self.event_queue.qsize() > 1000:
            health_status['overall'] = 'degraded'
            health_status['issues'].append(f"Large queue size: {self.event_queue.qsize()}")
        
        return health_status


class EventStore:
    """
    Event store for persistent event storage.
    
    Handles event persistence, querying, and replay.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enabled = True
    
    def store_event(self, event: Event) -> bool:
        """
        Store event in persistent storage.
        
        Args:
            event: Event to store
            
        Returns:
            True if stored successfully
        """
        if not self.enabled:
            return True
        
        try:
            # This would integrate with database storage
            # For now, just log the storage
            self.logger.debug(f"Event stored: {event.id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error storing event {event.id}: {str(e)}")
            return False
    
    def get_events(self, event_type: str = None, source: str = None,
                  start_time: datetime = None, end_time: datetime = None,
                  limit: int = 100) -> List[Event]:
        """
        Get events from storage.
        
        Args:
            event_type: Event type filter
            source: Source filter
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        # This would integrate with database querying
        # For now, return empty list
        return []
    
    def delete_events(self, before_time: datetime = None) -> int:
        """
        Delete events from storage.
        
        Args:
            before_time: Delete events before this time
            
        Returns:
            Number of events deleted
        """
        # This would integrate with database deletion
        # For now, return 0
        return 0


# Global event bus instance
event_bus = EventBus()
event_store = EventStore()


# Convenience functions
def publish_event(event_type: str, source: str, data: Dict[str, Any],
                priority: EventPriority = EventPriority.NORMAL,
                correlation_id: str = None, causation_id: str = None,
                metadata: Dict[str, Any] = None) -> str:
    """Publish event to event bus."""
    return event_bus.publish(event_type, source, data, priority, correlation_id, causation_id, metadata)


def subscribe_to_events(subscriber: str, event_type: str, handler: Callable,
                       filter_criteria: Dict[str, Any] = None,
                       priority: EventPriority = EventPriority.NORMAL) -> str:
    """Subscribe to events."""
    return event_bus.subscribe(subscriber, event_type, handler, filter_criteria, priority)


def unsubscribe_from_events(subscription_id: str) -> bool:
    """Unsubscribe from events."""
    return event_bus.unsubscribe(subscription_id)


def get_event(event_id: str) -> Optional[Event]:
    """Get event by ID."""
    return event_bus.get_event(event_id)


def get_event_statistics() -> Dict[str, Any]:
    """Get event bus statistics."""
    return event_bus.get_statistics()


def start_event_bus():
    """Start event bus."""
    event_bus.start()


def stop_event_bus():
    """Stop event bus."""
    event_bus.stop()


def perform_event_bus_health_check() -> Dict[str, Any]:
    """Perform event bus health check."""
    return event_bus.health_check()
