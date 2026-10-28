"""
Event Bus
Central event bus for managing integration events and message routing
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid
from collections import defaultdict, deque
import threading

from .integ_exceptions import IntegrationException, EventBusException
from .integ_constants import EventTypes, EventPriorities

logger = logging.getLogger(__name__)


class EventStatus(Enum):
    """Event status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryMode(Enum):
    """Event delivery mode enumeration"""
    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"
    PERSISTENT = "persistent"


@dataclass
class Event:
    """Event data structure"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    source: str = ""
    target: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriorities = EventPriorities.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl: Optional[float] = None  # Time to live in seconds
    retry_count: int = 0
    max_retries: int = 3
    delivery_mode: DeliveryMode = DeliveryMode.FIRE_AND_FORGET
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


@dataclass
class EventSubscription:
    """Event subscription configuration"""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    handler: Callable = None
    filter_func: Optional[Callable] = None
    priority: int = 5
    enabled: bool = True
    max_concurrent: int = 10
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EventBusMetrics:
    """Event bus performance metrics"""
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    queued_events: int = 0
    active_subscriptions: int = 0
    average_processing_time: float = 0.0
    throughput_per_second: float = 0.0
    error_rate: float = 0.0


class EventBus:
    """
    Central event bus for integration events
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._subscriptions: Dict[str, List[EventSubscription]] = defaultdict(list)
        self._event_store: Dict[str, Event] = {}  # For persistent events
        self._processing_events: Dict[str, Event] = {}
        self._failed_events: Dict[str, Event] = {}
        
        # Metrics
        self.metrics = EventBusMetrics()
        
        # State
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._lock = threading.RLock()
        
        # Configuration
        self._worker_count = 4
        self._batch_size = 10
        self._batch_timeout = 1.0  # seconds
        
        # Event history (circular buffer)
        self._event_history: deque = deque(maxlen=1000)
        
        # Retry queue
        self._retry_queue: asyncio.Queue = asyncio.Queue()
    
    async def start(self):
        """Start the event bus"""
        if self._running:
            return
        
        try:
            self._running = True
            
            # Start worker tasks
            for i in range(self._worker_count):
                task = asyncio.create_task(self._worker(f"worker-{i}"))
                self._worker_tasks.append(task)
            
            # Start retry worker
            retry_task = asyncio.create_task(self._retry_worker())
            self._worker_tasks.append(retry_task)
            
            # Start cleanup worker
            cleanup_task = asyncio.create_task(self._cleanup_worker())
            self._worker_tasks.append(cleanup_task)
            
            logger.info(f"Event bus started with {self._worker_count} workers")
            
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start event bus: {e}")
            raise EventBusException(f"Failed to start event bus: {e}")
    
    async def stop(self):
        """Stop the event bus"""
        if not self._running:
            return
        
        try:
            self._running = False
            
            # Cancel all worker tasks
            for task in self._worker_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            
            self._worker_tasks.clear()
            
            logger.info("Event bus stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping event bus: {e}")
    
    async def publish(self, event: Event) -> str:
        """
        Publish an event to the event bus
        
        Args:
            event: Event to publish
            
        Returns:
            Event ID
        """
        try:
            # Validate event
            if not event.event_type:
                raise EventBusException("Event type is required")
            
            # Set timestamp if not provided
            if not event.timestamp:
                event.timestamp = datetime.utcnow()
            
            # Check TTL
            if event.ttl and (datetime.utcnow() - event.timestamp).total_seconds() > event.ttl:
                logger.warning(f"Event {event.event_id} expired, discarding")
                return event.event_id
            
            # Add to metrics
            self.metrics.total_events += 1
            
            # Store persistent events
            if event.delivery_mode in [DeliveryMode.PERSISTENT, DeliveryMode.EXACTLY_ONCE]:
                self._event_store[event.event_id] = event
            
            # Add to history
            self._event_history.append(event)
            
            # Add to queue
            await self._event_queue.put(event)
            self.metrics.queued_events = self._event_queue.qsize()
            
            logger.debug(f"Published event: {event.event_type} ({event.event_id})")
            
            return event.event_id
            
        except Exception as e:
            self.metrics.failed_events += 1
            logger.error(f"Failed to publish event: {e}")
            raise EventBusException(f"Failed to publish event: {e}")
    
    async def publish_batch(self, events: List[Event]) -> List[str]:
        """
        Publish multiple events in batch
        
        Args:
            events: List of events to publish
            
        Returns:
            List of event IDs
        """
        event_ids = []
        
        for event in events:
            try:
                event_id = await self.publish(event)
                event_ids.append(event_id)
            except Exception as e:
                logger.error(f"Failed to publish event in batch: {e}")
                event_ids.append(None)
        
        return event_ids
    
    def subscribe(self, event_type: str, handler: Callable, 
                filter_func: Optional[Callable] = None, 
                priority: int = 5, max_concurrent: int = 10) -> str:
        """
        Subscribe to events
        
        Args:
            event_type: Type of events to subscribe to
            handler: Handler function
            filter_func: Optional filter function
            priority: Subscription priority
            max_concurrent: Maximum concurrent executions
            
        Returns:
            Subscription ID
        """
        with self._lock:
            subscription = EventSubscription(
                event_type=event_type,
                handler=handler,
                filter_func=filter_func,
                priority=priority,
                max_concurrent=max_concurrent
            )
            
            # Add to subscriptions (sorted by priority)
            self._subscriptions[event_type].append(subscription)
            self._subscriptions[event_type].sort(key=lambda s: s.priority)
            
            self.metrics.active_subscriptions = sum(
                len(subs) for subs in self._subscriptions.values()
            )
            
            logger.info(f"Subscribed to event type: {event_type} ({subscription.subscription_id})")
            
            return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            for event_type, subscriptions in self._subscriptions.items():
                for i, subscription in enumerate(subscriptions):
                    if subscription.subscription_id == subscription_id:
                        subscriptions.pop(i)
                        
                        self.metrics.active_subscriptions = sum(
                            len(subs) for subs in self._subscriptions.values()
                        )
                        
                        logger.info(f"Unsubscribed: {subscription_id}")
                        return True
            
            return False
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """
        Get an event by ID
        
        Args:
            event_id: Event ID
            
        Returns:
            Event or None
        """
        return self._event_store.get(event_id)
    
    def get_event_history(self, event_type: Optional[str] = None, 
                         limit: int = 100) -> List[Event]:
        """
        Get event history
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        history = list(self._event_history)
        
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        return history[-limit:]
    
    def get_subscriptions(self, event_type: Optional[str] = None) -> List[EventSubscription]:
        """
        Get subscriptions
        
        Args:
            event_type: Filter by event type (optional)
            
        Returns:
            List of subscriptions
        """
        with self._lock:
            if event_type:
                return self._subscriptions.get(event_type, []).copy()
            
            all_subscriptions = []
            for subscriptions in self._subscriptions.values():
                all_subscriptions.extend(subscriptions)
            
            return all_subscriptions
    
    def get_metrics(self) -> EventBusMetrics:
        """
        Get event bus metrics
        
        Returns:
            Event bus metrics
        """
        # Update dynamic metrics
        self.metrics.queued_events = self._event_queue.qsize()
        
        # Calculate error rate
        if self.metrics.total_events > 0:
            self.metrics.error_rate = (self.metrics.failed_events / self.metrics.total_events) * 100
        
        return self.metrics
    
    async def _worker(self, worker_name: str):
        """Worker task for processing events"""
        logger.info(f"Event bus worker {worker_name} started")
        
        while self._running:
            try:
                # Get batch of events
                events = []
                deadline = asyncio.get_event_loop().time() + self._batch_timeout
                
                while len(events) < self._batch_size and asyncio.get_event_loop().time() < deadline:
                    try:
                        event = await asyncio.wait_for(
                            self._event_queue.get(), 
                            timeout=deadline - asyncio.get_event_loop().time()
                        )
                        events.append(event)
                    except asyncio.TimeoutError:
                        break
                
                if not events:
                    continue
                
                # Process events
                for event in events:
                    await self._process_event(event, worker_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1.0)
        
        logger.info(f"Event bus worker {worker_name} stopped")
    
    async def _process_event(self, event: Event, worker_name: str):
        """Process a single event"""
        start_time = datetime.utcnow()
        
        try:
            # Check if event is still valid
            if event.ttl and (datetime.utcnow() - event.timestamp).total_seconds() > event.ttl:
                logger.warning(f"Event {event.event_id} expired during processing")
                return
            
            # Mark as processing
            self._processing_events[event.event_id] = event
            
            # Get subscriptions for this event type
            subscriptions = self._subscriptions.get(event.event_type, [])
            
            if not subscriptions:
                logger.debug(f"No subscriptions for event type: {event.event_type}")
                return
            
            # Process subscriptions
            successful_deliveries = 0
            failed_deliveries = 0
            
            for subscription in subscriptions:
                if not subscription.enabled:
                    continue
                
                # Apply filter if present
                if subscription.filter_func and not subscription.filter_func(event):
                    continue
                
                try:
                    # Call handler
                    if asyncio.iscoroutinefunction(subscription.handler):
                        await subscription.handler(event)
                    else:
                        subscription.handler(event)
                    
                    successful_deliveries += 1
                    
                except Exception as e:
                    failed_deliveries += 1
                    logger.error(f"Handler failed for event {event.event_id}: {e}")
            
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.processed_events += 1
            
            # Update average processing time
            total_processed = self.metrics.processed_events
            current_avg = self.metrics.average_processing_time
            self.metrics.average_processing_time = (
                (current_avg * (total_processed - 1) + processing_time) / total_processed
            )
            
            # Remove from processing
            self._processing_events.pop(event.event_id, None)
            
            # Remove from event store if not persistent
            if event.delivery_mode == DeliveryMode.FIRE_AND_FORGET:
                self._event_store.pop(event.event_id, None)
            
            logger.debug(f"Processed event {event.event_id} in {processing_time:.3f}s")
            
        except Exception as e:
            self.metrics.failed_events += 1
            logger.error(f"Failed to process event {event.event_id}: {e}")
            
            # Add to retry queue if retries available
            if event.retry_count < event.max_retries:
                event.retry_count += 1
                await self._retry_queue.put(event)
            else:
                self._failed_events[event.event_id] = event
            
            # Remove from processing
            self._processing_events.pop(event.event_id, None)
    
    async def _retry_worker(self):
        """Worker for retrying failed events"""
        logger.info("Event bus retry worker started")
        
        while self._running:
            try:
                event = await asyncio.wait_for(self._retry_queue.get(), timeout=5.0)
                
                # Add delay before retry
                await asyncio.sleep(event.retry_count * 2.0)  # Exponential backoff
                
                # Re-queue for processing
                await self._event_queue.put(event)
                
                logger.info(f"Retrying event {event.event_id} (attempt {event.retry_count})")
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry worker error: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("Event bus retry worker stopped")
    
    async def _cleanup_worker(self):
        """Worker for cleaning up expired events"""
        logger.info("Event bus cleanup worker started")
        
        while self._running:
            try:
                # Clean up expired events
                now = datetime.utcnow()
                expired_events = []
                
                for event_id, event in self._event_store.items():
                    if event.ttl and (now - event.timestamp).total_seconds() > event.ttl:
                        expired_events.append(event_id)
                
                for event_id in expired_events:
                    self._event_store.pop(event_id, None)
                    logger.debug(f"Cleaned up expired event: {event_id}")
                
                # Clean up old failed events
                if len(self._failed_events) > 1000:
                    # Keep only the most recent 1000 failed events
                    failed_items = list(self._failed_events.items())
                    failed_items.sort(key=lambda x: x[1].timestamp, reverse=True)
                    self._failed_events = dict(failed_items[:1000])
                
                # Sleep for cleanup interval
                await asyncio.sleep(60.0)  # Cleanup every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(10.0)
        
        logger.info("Event bus cleanup worker stopped")


# Global event bus instance
_event_bus = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def initialize_event_bus(max_queue_size: int = 10000, worker_count: int = 4) -> EventBus:
    """Initialize the global event bus"""
    global _event_bus
    _event_bus = EventBus(max_queue_size=max_queue_size)
    _event_bus._worker_count = worker_count
    return _event_bus


# Export main classes and functions
__all__ = [
    'EventBus',
    'Event',
    'EventSubscription',
    'EventBusMetrics',
    'EventStatus',
    'DeliveryMode',
    'get_event_bus',
    'initialize_event_bus',
]
