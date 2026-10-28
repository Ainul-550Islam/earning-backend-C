"""
events.py – Event system for postback module.

Provides comprehensive event management including:
- Event definition and registration
- Event publishing and subscribing
- Event filtering and routing
- Event aggregation and analytics
- Event-driven workflows
"""
import logging
import json
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import uuid

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Event:
    """
    Base event data structure.
    
    Represents an event in the postback system with metadata
    and payload data.
    """
    event_type: str
    source: str
    timestamp: datetime = field(default_factory=timezone.now)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'metadata': self.metadata,
            'priority': self.priority.value,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        event = cls(
            event_type=data['event_type'],
            source=data['source'],
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            priority=EventPriority(data.get('priority', 5)),
            max_retries=data.get('max_retries', 3),
        )
        
        # Set event_id if provided
        if 'event_id' in data:
            event.event_id = data['event_id']
        
        # Set timestamp if provided
        if 'timestamp' in data:
            event.timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        
        return event


class EventSubscriber:
    """
    Event subscriber with filtering and processing capabilities.
    
    Handles event subscription, filtering, and processing with
    error handling and retry logic.
    """
    
    def __init__(self, subscriber_id: str, handler_func: Callable, event_types: List[str] = None):
        self.subscriber_id = subscriber_id
        self.handler_func = handler_func
        self.event_types = event_types or []
        self.filters = []
        self.processed_count = 0
        self.failed_count = 0
        self.last_processed = None
        self.enabled = True
    
    def add_filter(self, filter_func: Callable):
        """
        Add a filter function for event filtering.
        
        Args:
            filter_func: Function that returns True/False for event processing
        """
        self.filters.append(filter_func)
    
    def should_process_event(self, event: Event) -> bool:
        """
        Check if subscriber should process the event.
        
        Args:
            event: Event to check
            
        Returns:
            True if event should be processed
        """
        if not self.enabled:
            return False
        
        # Check event type filter
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Apply custom filters
        for filter_func in self.filters:
            try:
                if not filter_func(event):
                    return False
            except Exception as e:
                logger.error(f"Error in event filter: {str(e)}")
                return False
        
        return True
    
    def process_event(self, event: Event) -> bool:
        """
        Process an event.
        
        Args:
            event: Event to process
            
        Returns:
            True if processing was successful
        """
        try:
            start_time = timezone.now()
            
            # Process the event
            result = self.handler_func(event)
            
            # Update statistics
            self.processed_count += 1
            self.last_processed = timezone.now()
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            logger.debug(f"Subscriber {self.subscriber_id} processed event {event.event_id} in {processing_time:.3f}s")
            
            return True
            
        except Exception as e:
            self.failed_count += 1
            logger.error(f"Subscriber {self.subscriber_id} failed to process event {event.event_id}: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get subscriber statistics."""
        total_events = self.processed_count + self.failed_count
        success_rate = (self.processed_count / total_events * 100) if total_events > 0 else 0
        
        return {
            'subscriber_id': self.subscriber_id,
            'processed_count': self.processed_count,
            'failed_count': self.failed_count,
            'total_events': total_events,
            'success_rate': f"{success_rate:.2f}%",
            'last_processed': self.last_processed.isoformat() if self.last_processed else None,
            'enabled': self.enabled,
            'event_types': self.event_types,
        }


class EventPublisher:
    """
    Event publishing system with routing and delivery capabilities.
    
    Handles event publishing, routing to subscribers, and
    delivery tracking with retry logic.
    """
    
    def __init__(self):
        self.subscribers = {}
        self.event_history = []
        self.delivery_stats = {}
        self.enabled = True
    
    def subscribe(self, subscriber_id: str, handler_func: Callable, event_types: List[str] = None) -> EventSubscriber:
        """
        Subscribe to events.
        
        Args:
            subscriber_id: Unique identifier for subscriber
            handler_func: Function to handle events
            event_types: List of event types to subscribe to
            
        Returns:
            EventSubscriber instance
        """
        subscriber = EventSubscriber(subscriber_id, handler_func, event_types)
        self.subscribers[subscriber_id] = subscriber
        
        logger.info(f"Subscriber {subscriber_id} subscribed to events: {event_types or 'all'}")
        
        return subscriber
    
    def unsubscribe(self, subscriber_id: str):
        """
        Unsubscribe from events.
        
        Args:
            subscriber_id: Subscriber ID to unsubscribe
        """
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            logger.info(f"Subscriber {subscriber_id} unsubscribed")
        else:
            logger.warning(f"Subscriber {subscriber_id} not found")
    
    def publish(self, event: Event) -> Dict[str, Any]:
        """
        Publish an event to all matching subscribers.
        
        Args:
            event: Event to publish
            
        Returns:
            Publishing results
        """
        if not self.enabled:
            return {'status': 'skipped', 'reason': 'Publisher disabled'}
        
        start_time = timezone.now()
        event.status = EventStatus.PROCESSING
        
        try:
            # Store event in history
            self._store_event(event)
            
            # Find matching subscribers
            matching_subscribers = [
                subscriber for subscriber in self.subscribers.values()
                if subscriber.should_process_event(event)
            ]
            
            if not matching_subscribers:
                event.status = EventStatus.SKIPPED
                logger.info(f"No subscribers for event {event.event_id} ({event.event_type})")
                return {
                    'event_id': event.event_id,
                    'status': 'skipped',
                    'subscribers_count': 0,
                    'processing_time': (timezone.now() - start_time).total_seconds(),
                }
            
            # Process event with matching subscribers
            successful_deliveries = 0
            failed_deliveries = 0
            
            for subscriber in matching_subscribers:
                if subscriber.process_event(event):
                    successful_deliveries += 1
                else:
                    failed_deliveries += 1
            
            # Update event status
            if failed_deliveries == 0:
                event.status = EventStatus.PROCESSED
            elif successful_deliveries > 0:
                event.status = EventStatus.PROCESSED  # Partial success
            else:
                event.status = EventStatus.FAILED
            
            # Update delivery statistics
            self._update_delivery_stats(event, successful_deliveries, failed_deliveries)
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            result = {
                'event_id': event.event_id,
                'status': event.status.value,
                'subscribers_count': len(matching_subscribers),
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'processing_time': processing_time,
            }
            
            logger.info(f"Event {event.event_id} published: {successful_deliveries}/{len(matching_subscribers)} deliveries")
            
            return result
            
        except Exception as e:
            event.status = EventStatus.FAILED
            logger.error(f"Error publishing event {event.event_id}: {str(e)}")
            
            return {
                'event_id': event.event_id,
                'status': 'failed',
                'error': str(e),
                'processing_time': (timezone.now() - start_time).total_seconds(),
            }
    
    def _store_event(self, event: Event):
        """Store event in history."""
        self.event_history.append(event.to_dict())
        
        # Keep only last 1000 events
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-1000:]
        
        # Cache event for retrieval
        cache_key = f"event_{event.event_id}"
        cache.set(cache_key, event.to_dict(), timeout=3600)  # 1 hour
    
    def _update_delivery_stats(self, event: Event, successful: int, failed: int):
        """Update delivery statistics."""
        event_type = event.event_type
        
        if event_type not in self.delivery_stats:
            self.delivery_stats[event_type] = {
                'total_events': 0,
                'successful_deliveries': 0,
                'failed_deliveries': 0,
                'last_event': None,
            }
        
        stats = self.delivery_stats[event_type]
        stats['total_events'] += 1
        stats['successful_deliveries'] += successful
        stats['failed_deliveries'] += failed
        stats['last_event'] = event.timestamp.isoformat()
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID."""
        cache_key = f"event_{event_id}"
        cached_event = cache.get(cache_key)
        
        if cached_event:
            return cached_event
        
        # Search in history
        for event_data in self.event_history:
            if event_data.get('event_id') == event_id:
                return event_data
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            'total_subscribers': len(self.subscribers),
            'total_events': len(self.event_history),
            'delivery_stats': self.delivery_stats,
            'subscriber_stats': {
                sub_id: sub.get_statistics()
                for sub_id, sub in self.subscribers.items()
            },
            'enabled': self.enabled,
        }
    
    def enable(self):
        """Enable event publishing."""
        self.enabled = True
        logger.info("Event publisher enabled")
    
    def disable(self):
        """Disable event publishing."""
        self.enabled = False
        logger.info("Event publisher disabled")


class EventAggregator:
    """
    Event aggregation and analytics system.
    
    Provides capabilities for:
    - Event aggregation by type and time
    - Event analytics and metrics
    - Event pattern detection
    - Event trend analysis
    """
    
    def __init__(self):
        self.aggregation_rules = {}
        self.aggregated_data = {}
        self.analytics_cache = {}
    
    def add_aggregation_rule(self, rule_name: str, event_types: List[str], aggregation_func: Callable, window_minutes: int = 60):
        """
        Add an aggregation rule.
        
        Args:
            rule_name: Name identifier for the rule
            event_types: List of event types to aggregate
            aggregation_func: Function to aggregate events
            window_minutes: Time window for aggregation in minutes
        """
        self.aggregation_rules[rule_name] = {
            'event_types': event_types,
            'aggregation_func': aggregation_func,
            'window_minutes': window_minutes,
            'last_run': None,
            'run_count': 0,
        }
        
        logger.info(f"Added aggregation rule: {rule_name}")
    
    def aggregate_events(self, events: List[Event]) -> Dict[str, Any]:
        """
        Aggregate events according to defined rules.
        
        Args:
            events: List of events to aggregate
            
        Returns:
            Aggregation results
        """
        results = {}
        
        for rule_name, rule in self.aggregation_rules.items():
            try:
                # Filter events by type
                filtered_events = [
                    event for event in events
                    if event.event_type in rule['event_types']
                ]
                
                # Apply time window
                window_start = timezone.now() - timedelta(minutes=rule['window_minutes'])
                filtered_events = [
                    event for event in filtered_events
                    if event.timestamp >= window_start
                ]
                
                if filtered_events:
                    # Apply aggregation function
                    aggregated_result = rule['aggregation_func'](filtered_events)
                    results[rule_name] = aggregated_result
                    
                    # Update rule stats
                    rule['last_run'] = timezone.now()
                    rule['run_count'] += 1
                
            except Exception as e:
                logger.error(f"Error in aggregation rule {rule_name}: {str(e)}")
                results[rule_name] = {'error': str(e)}
        
        return results
    
    def get_analytics(self, event_type: str = None, hours: int = 24) -> Dict[str, Any]:
        """
        Get event analytics.
        
        Args:
            event_type: Specific event type to analyze
            hours: Time window in hours
            
        Returns:
            Analytics data
        """
        cache_key = f"event_analytics_{event_type}_{hours}"
        cached_analytics = cache.get(cache_key)
        
        if cached_analytics:
            return cached_analytics
        
        # Calculate analytics
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        # Filter events by time window
        recent_events = [
            event for event in self.event_history
            if datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')) >= cutoff_time
        ]
        
        if event_type:
            recent_events = [
                event for event in recent_events
                if event['event_type'] == event_type
            ]
        
        # Calculate analytics
        analytics = {
            'total_events': len(recent_events),
            'event_types': {},
            'hourly_distribution': {},
            'priority_distribution': {},
            'status_distribution': {},
            'time_period': f"{hours} hours",
        }
        
        for event in recent_events:
            # Event type distribution
            event_type_name = event['event_type']
            analytics['event_types'][event_type_name] = analytics['event_types'].get(event_type_name, 0) + 1
            
            # Hourly distribution
            hour = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).hour
            analytics['hourly_distribution'][hour] = analytics['hourly_distribution'].get(hour, 0) + 1
            
            # Priority distribution
            priority = event['priority']
            analytics['priority_distribution'][priority] = analytics['priority_distribution'].get(priority, 0) + 1
            
            # Status distribution
            status = event['status']
            analytics['status_distribution'][status] = analytics['status_distribution'].get(status, 0) + 1
        
        # Cache analytics
        cache.set(cache_key, analytics, timeout=300)  # 5 minutes
        
        return analytics


# Built-in event types
class PostbackEventTypes:
    """Standard postback event types."""
    POSTBACK_RECEIVED = "postback.received"
    POSTBACK_PROCESSED = "postback.processed"
    POSTBACK_FAILED = "postback.failed"
    POSTBACK_RETRY = "postback.retry"
    INSIGHT_GENERATED = "insight.generated"
    ANOMALY_DETECTED = "anomaly.detected"
    HEALTH_CHECK = "health.check"
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    DUPLICATE_DETECTED = "duplicate.detected"


# Global instances
event_publisher = EventPublisher()
event_aggregator = EventAggregator()


# Decorators for event handling
def event_handler(event_types: List[str] = None, subscriber_id: str = None):
    """
    Decorator for event handler functions.
    
    Args:
        event_types: List of event types to handle
        subscriber_id: Unique subscriber identifier
    """
    def decorator(func):
        # Generate subscriber ID if not provided
        sub_id = subscriber_id or f"{func.__module__}.{func.__name__}"
        
        # Subscribe to events
        event_publisher.subscribe(sub_id, func, event_types)
        
        @wraps(func)
        def wrapper(event: Event):
            return func(event)
        
        wrapper.subscriber_id = sub_id
        wrapper.unsubscribe = lambda: event_publisher.unsubscribe(sub_id)
        
        return wrapper
    return decorator


def event_filter(filter_func: Callable):
    """
    Decorator for adding filters to event handlers.
    
    Args:
        filter_func: Filter function that returns True/False
    """
    def decorator(func):
        if hasattr(func, 'subscriber_id'):
            subscriber_id = func.subscriber_id
            subscriber = event_publisher.subscribers.get(subscriber_id)
            if subscriber:
                subscriber.add_filter(filter_func)
        
        @wraps(func)
        def wrapper(event: Event):
            return func(event)
        
        return wrapper
    return decorator


# Convenience functions for publishing events
def publish_postback_event(event_type: str, source: str, data: Dict[str, Any], priority: EventPriority = EventPriority.NORMAL) -> Dict[str, Any]:
    """
    Publish a postback event.
    
    Args:
        event_type: Type of event
        source: Event source identifier
        data: Event data
        priority: Event priority
        
    Returns:
        Publishing results
    """
    event = Event(
        event_type=event_type,
        source=source,
        data=data,
        priority=priority
    )
    
    return event_publisher.publish(event)


def publish_postback_received(postback_log: PostbackLog) -> Dict[str, Any]:
    """Publish postback received event."""
    return publish_postback_event(
        event_type=PostbackEventTypes.POSTBACK_RECEIVED,
        source="postback_processor",
        data={
            'postback_id': str(postback_log.id),
            'network_key': postback_log.network.network_key,
            'status': postback_log.status,
            'received_at': postback_log.received_at.isoformat(),
        },
        priority=EventPriority.NORMAL
    )


def publish_postback_processed(postback_log: PostbackLog) -> Dict[str, Any]:
    """Publish postback processed event."""
    return publish_postback_event(
        event_type=PostbackEventTypes.POSTBACK_PROCESSED,
        source="postback_processor",
        data={
            'postback_id': str(postback_log.id),
            'network_key': postback_log.network.network_key,
            'status': postback_log.status,
            'processed_at': postback_log.processed_at.isoformat() if postback_log.processed_at else None,
            'payout': float(postback_log.payout) if postback_log.payout else None,
        },
        priority=EventPriority.NORMAL
    )


def publish_postback_failed(postback_log: PostbackLog, error: str) -> Dict[str, Any]:
    """Publish postback failed event."""
    return publish_postback_event(
        event_type=PostbackEventTypes.POSTBACK_FAILED,
        source="postback_processor",
        data={
            'postback_id': str(postback_log.id),
            'network_key': postback_log.network.network_key,
            'status': postback_log.status,
            'rejection_reason': postback_log.rejection_reason,
            'error': error,
        },
        priority=EventPriority.HIGH
    )


def publish_anomaly_detected(network_key: str, anomaly_data: Dict[str, Any]) -> Dict[str, Any]:
    """Publish anomaly detected event."""
    return publish_postback_event(
        event_type=PostbackEventTypes.ANOMALY_DETECTED,
        source="anomaly_detector",
        data={
            'network_key': network_key,
            'anomaly_data': anomaly_data,
            'detected_at': timezone.now().isoformat(),
        },
        priority=EventPriority.HIGH
    )


# Built-in aggregation rules
def count_events_by_type(events: List[Event]) -> Dict[str, Any]:
    """Aggregate events by type."""
    counts = {}
    for event in events:
        event_type = event.event_type
        counts[event_type] = counts.get(event_type, 0) + 1
    
    return {
        'event_count': len(events),
        'type_distribution': counts,
        'time_window': f"{events[0].timestamp} to {events[-1].timestamp}" if events else None,
    }


def calculate_priority_distribution(events: List[Event]) -> Dict[str, Any]:
    """Calculate priority distribution of events."""
    distribution = {priority.value: 0 for priority in EventPriority}
    
    for event in events:
        distribution[event.priority.value] += 1
    
    return {
        'total_events': len(events),
        'priority_distribution': distribution,
        'high_priority_ratio': distribution[EventPriority.HIGH.value] / len(events) if events else 0,
    }


# Initialize built-in aggregation rules
event_aggregator.add_aggregation_rule(
    "event_count_by_type",
    list(PostbackEventTypes.__dict__.values()),
    count_events_by_type,
    window_minutes=60
)

event_aggregator.add_aggregation_rule(
    "priority_distribution",
    list(PostbackEventTypes.__dict__.values()),
    calculate_priority_distribution,
    window_minutes=60
)


# Event system initialization
def initialize_event_system():
    """Initialize the event system."""
    try:
        # The system is initialized through global instances
        logger.info("Event system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing event system: {str(e)}")


# Get system statistics
def get_event_system_statistics() -> Dict[str, Any]:
    """Get comprehensive event system statistics."""
    return {
        'publisher_stats': event_publisher.get_statistics(),
        'aggregation_stats': {
            rule_name: {
                'last_run': rule['last_run'].isoformat() if rule['last_run'] else None,
                'run_count': rule['run_count'],
                'window_minutes': rule['window_minutes'],
            }
            for rule_name, rule in event_aggregator.aggregation_rules.items()
        },
        'system_enabled': event_publisher.enabled,
    }
