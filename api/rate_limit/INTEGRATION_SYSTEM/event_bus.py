"""
Event Bus - Central Event Management System

Event-driven architecture implementation for the rate limiting system,
providing publish-subscribe pattern for loose coupling between components.
"""

import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from collections import defaultdict
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationPriority
from .integ_exceptions import IntegrationError, EventBusError

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types in the system."""
    SYSTEM = "system"
    BUSINESS = "business"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    USER = "user"
    INTEGRATION = "integration"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class Event:
    """Event data structure."""
    event_type: str
    data: Dict[str, Any]
    source: str = "unknown"
    timestamp: datetime = field(default_factory=timezone.now)
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.correlation_id:
            self.correlation_id = f"{self.event_type}_{self.timestamp.timestamp()}"


@dataclass
class EventSubscription:
    """Event subscription information."""
    event_pattern: str
    handler: Callable
    priority: EventPriority = EventPriority.NORMAL
    filter_func: Optional[Callable] = None
    async_handler: bool = False
    max_concurrent: int = 10
    timeout: int = 30
    retry_on_failure: bool = True
    subscription_id: str = field(default_factory=lambda: f"sub_{timezone.now().timestamp()}")
    created_at: datetime = field(default_factory=timezone.now)
    call_count: int = 0
    error_count: int = 0
    last_called: Optional[datetime] = None


class EventBus:
    """Central event bus for system-wide event management."""
    
    def __init__(self):
        self._subscriptions: Dict[str, List[EventSubscription]] = defaultdict(list)
        self._event_queue = Queue(maxsize=10000)
        self._dead_letter_queue = Queue(maxsize=1000)
        self._statistics = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'subscriptions_count': 0,
            'dead_letter_count': 0,
            'average_processing_time': 0.0,
            'last_event_time': None
        }
        self._lock = threading.RLock()
        self._running = False
        self._worker_threads: List[threading.Thread] = []
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        
        # Start background workers
        self._start_workers()
    
    def _start_workers(self):
        """Start background worker threads."""
        self._running = True
        num_workers = min(4, max(1, settings.LOGGING.get('workers', 2)))
        
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"EventBusWorker-{i}")
            worker.daemon = True
            worker.start()
            self._worker_threads.append(worker)
        
        logger.info(f"Started {num_workers} event bus workers")
    
    def _worker_loop(self):
        """Worker thread loop for processing events."""
        while self._running:
            try:
                # Get event from queue
                event = self._event_queue.get(timeout=1)
                
                # Process event
                self._process_event_sync(event)
                
                # Mark task as done
                self._event_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Event bus worker error: {str(e)}")
                self._statistics['events_failed'] += 1
    
    def _process_event_sync(self, event: Event):
        """Process event synchronously."""
        start_time = timezone.now()
        
        try:
            # Find matching subscriptions
            subscriptions = self._find_subscriptions(event.event_type)
            
            # Process each subscription
            for subscription in subscriptions:
                try:
                    # Apply filter if exists
                    if subscription.filter_func and not subscription.filter_func(event):
                        continue
                    
                    # Call handler
                    if subscription.async_handler:
                        # Run async handler in thread
                        asyncio.run(subscription.handler(event))
                    else:
                        # Run sync handler directly
                        subscription.handler(event)
                    
                    # Update statistics
                    subscription.call_count += 1
                    subscription.last_called = timezone.now()
                    
                except Exception as e:
                    logger.error(f"Event handler failed: {subscription.subscription_id} - {str(e)}")
                    subscription.error_count += 1
                    
                    # Retry if configured
                    if subscription.retry_on_failure and event.retry_count < event.max_retries:
                        event.retry_count += 1
                        self._event_queue.put(event)
                    else:
                        self._dead_letter_queue.put(event)
                        self._statistics['dead_letter_count'] += 1
            
            # Update statistics
            self._statistics['events_processed'] += 1
            processing_time = (timezone.now() - start_time).total_seconds()
            self._update_processing_time(processing_time)
            
        except Exception as e:
            logger.error(f"Event processing failed: {str(e)}")
            self._statistics['events_failed'] += 1
    
    def _find_subscriptions(self, event_type: str) -> List[EventSubscription]:
        """Find subscriptions matching event type."""
        subscriptions = []
        
        # Direct match
        subscriptions.extend(self._subscriptions.get(event_type, []))
        
        # Pattern matching (wildcard support)
        for pattern, subs in self._subscriptions.items():
            if pattern != event_type and self._matches_pattern(event_type, pattern):
                subscriptions.extend(subs)
        
        # Sort by priority
        subscriptions.sort(key=lambda s: s.priority.value, reverse=True)
        
        return subscriptions
    
    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches pattern."""
        # Simple wildcard matching
        if pattern == "*":
            return True
        
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return event_type.startswith(prefix)
        
        if pattern.startswith("*"):
            suffix = pattern[1:]
            return event_type.endswith(suffix)
        
        if "*" in pattern:
            parts = pattern.split("*")
            if len(parts) == 2:
                return event_type.startswith(parts[0]) and event_type.endswith(parts[1])
        
        return False
    
    def _update_processing_time(self, processing_time: float):
        """Update average processing time."""
        current_avg = self._statistics['average_processing_time']
        total_events = self._statistics['events_processed']
        
        if total_events == 1:
            self._statistics['average_processing_time'] = processing_time
        else:
            self._statistics['average_processing_time'] = (
                (current_avg * (total_events - 1) + processing_time) / total_events
            )
    
    async def publish(self, event: Event) -> bool:
        """Publish event to the bus."""
        try:
            # Add to history
            self._add_to_history(event)
            
            # Add to queue
            self._event_queue.put(event)
            
            # Update statistics
            self._statistics['events_published'] += 1
            self._statistics['last_event_time'] = timezone.now()
            
            logger.debug(f"Published event: {event.event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event: {str(e)}")
            self._statistics['events_failed'] += 1
            return False
    
    def subscribe(self, event_pattern: str, handler: Callable, **kwargs) -> str:
        """Subscribe to events."""
        subscription = EventSubscription(
            event_pattern=event_pattern,
            handler=handler,
            priority=kwargs.get('priority', EventPriority.NORMAL),
            filter_func=kwargs.get('filter_func'),
            async_handler=kwargs.get('async_handler', asyncio.iscoroutinefunction(handler)),
            max_concurrent=kwargs.get('max_concurrent', 10),
            timeout=kwargs.get('timeout', 30),
            retry_on_failure=kwargs.get('retry_on_failure', True)
        )
        
        with self._lock:
            self._subscriptions[event_pattern].append(subscription)
            self._statistics['subscriptions_count'] += 1
        
        logger.info(f"Subscribed to events: {event_pattern} ({subscription.subscription_id})")
        return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            for pattern, subscriptions in self._subscriptions.items():
                for i, sub in enumerate(subscriptions):
                    if sub.subscription_id == subscription_id:
                        subscriptions.pop(i)
                        self._statistics['subscriptions_count'] -= 1
                        logger.info(f"Unsubscribed: {subscription_id}")
                        return True
        return False
    
    def _add_to_history(self, event: Event):
        """Add event to history."""
        with self._lock:
            self._event_history.append(event)
            
            # Limit history size
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)
    
    def get_event_history(self, limit: int = 100) -> List[Event]:
        """Get recent event history."""
        with self._lock:
            return self._event_history[-limit:] if limit > 0 else self._event_history.copy()
    
    def get_subscriptions(self, event_pattern: str = None) -> List[EventSubscription]:
        """Get subscriptions."""
        if event_pattern:
            return self._subscriptions.get(event_pattern, []).copy()
        else:
            all_subs = []
            for subs in self._subscriptions.values():
                all_subs.extend(subs)
            return all_subs
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        stats = self._statistics.copy()
        stats.update({
            'queue_size': self._event_queue.qsize(),
            'dead_letter_queue_size': self._dead_letter_queue.qsize(),
            'worker_threads': len(self._worker_threads),
            'running': self._running,
            'history_size': len(self._event_history)
        })
        return stats
    
    def get_dead_letter_events(self, limit: int = 50) -> List[Event]:
        """Get events from dead letter queue."""
        events = []
        
        for _ in range(min(limit, self._dead_letter_queue.qsize())):
            try:
                event = self._dead_letter_queue.get_nowait()
                events.append(event)
            except Empty:
                break
        
        return events
    
    def retry_dead_letter_events(self) -> int:
        """Retry events from dead letter queue."""
        retried_count = 0
        
        while not self._dead_letter_queue.empty():
            try:
                event = self._dead_letter_queue.get_nowait()
                event.retry_count = 0  # Reset retry count
                self._event_queue.put(event)
                retried_count += 1
            except Empty:
                break
        
        logger.info(f"Retried {retried_count} events from dead letter queue")
        return retried_count
    
    def clear_dead_letter_queue(self) -> int:
        """Clear dead letter queue."""
        cleared_count = self._dead_letter_queue.qsize()
        
        while not self._dead_letter_queue.empty():
            try:
                self._dead_letter_queue.get_nowait()
            except Empty:
                break
        
        logger.info(f"Cleared {cleared_count} events from dead letter queue")
        return cleared_count
    
    def shutdown(self):
        """Shutdown event bus."""
        logger.info("Shutting down event bus...")
        
        # Stop workers
        self._running = False
        
        # Wait for workers to finish
        for worker in self._worker_threads:
            worker.join(timeout=5)
        
        # Clear queues
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except Empty:
                break
        
        logger.info("Event bus shutdown complete")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        queue_size = self._event_queue.qsize()
        dead_letter_size = self._dead_letter_queue.qsize()
        error_rate = (
            self._statistics['events_failed'] / 
            max(1, self._statistics['events_published'])
        )
        
        health_status = {
            'status': 'healthy',
            'queue_size': queue_size,
            'dead_letter_size': dead_letter_size,
            'error_rate': error_rate,
            'worker_threads': len(self._worker_threads),
            'running': self._running,
            'issues': []
        }
        
        # Check for issues
        if queue_size > 1000:
            health_status['issues'].append('High queue size')
            health_status['status'] = 'warning'
        
        if dead_letter_size > 100:
            health_status['issues'].append('High dead letter queue size')
            health_status['status'] = 'warning'
        
        if error_rate > 0.1:
            health_status['issues'].append('High error rate')
            health_status['status'] = 'warning'
        
        if not self._running:
            health_status['issues'].append('Event bus not running')
            health_status['status'] = 'error'
        
        return health_status


class EventBuilder:
    """Builder for creating events."""
    
    @staticmethod
    def create_system_event(event_type: str, data: Dict[str, Any], 
                           source: str = "system", priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Create system event."""
        return Event(
            event_type=f"system.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_business_event(event_type: str, data: Dict[str, Any],
                             source: str = "business", priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Create business event."""
        return Event(
            event_type=f"business.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_security_event(event_type: str, data: Dict[str, Any],
                             source: str = "security", priority: EventPriority = EventPriority.HIGH) -> Event:
        """Create security event."""
        return Event(
            event_type=f"security.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_performance_event(event_type: str, data: Dict[str, Any],
                                source: str = "performance", priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Create performance event."""
        return Event(
            event_type=f"performance.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_compliance_event(event_type: str, data: Dict[str, Any],
                               source: str = "compliance", priority: EventPriority = EventPriority.HIGH) -> Event:
        """Create compliance event."""
        return Event(
            event_type=f"compliance.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_user_event(event_type: str, data: Dict[str, Any],
                         source: str = "user", priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Create user event."""
        return Event(
            event_type=f"user.{event_type}",
            data=data,
            source=source,
            priority=priority
        )
    
    @staticmethod
    def create_integration_event(event_type: str, data: Dict[str, Any],
                                source: str = "integration", priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Create integration event."""
        return Event(
            event_type=f"integration.{event_type}",
            data=data,
            source=source,
            priority=priority
        )


# Decorators for easy event subscription
def event_handler(event_pattern: str, **kwargs):
    """Decorator for event handlers."""
    def decorator(func):
        # Subscribe to event bus
        event_bus.subscribe(event_pattern, func, **kwargs)
        return func
    return decorator


def async_event_handler(event_pattern: str, **kwargs):
    """Decorator for async event handlers."""
    def decorator(func):
        kwargs['async_handler'] = True
        event_bus.subscribe(event_pattern, func, **kwargs)
        return func
    return decorator


def event_filter(filter_func: Callable):
    """Decorator for event filtering."""
    def decorator(func):
        # This would need to be applied to the subscription
        # For now, it's a placeholder
        return func
    return decorator


# Global event bus instance
event_bus = EventBus()


# Convenience functions
async def publish_system_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish system event."""
    event = EventBuilder.create_system_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_business_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish business event."""
    event = EventBuilder.create_business_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_security_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish security event."""
    event = EventBuilder.create_security_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_performance_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish performance event."""
    event = EventBuilder.create_performance_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_compliance_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish compliance event."""
    event = EventBuilder.create_compliance_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_user_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish user event."""
    event = EventBuilder.create_user_event(event_type, data, **kwargs)
    return await event_bus.publish(event)


async def publish_integration_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """Publish integration event."""
    event = EventBuilder.create_integration_event(event_type, data, **kwargs)
    return await event_bus.publish(event)
