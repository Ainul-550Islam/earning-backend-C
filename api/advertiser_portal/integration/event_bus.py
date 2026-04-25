"""
Event Bus for Inter-Module Communication

This module provides a high-performance event bus for communication
between the advertiser_portal and external modules, ensuring
reliable event delivery and processing.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from .performance_monitor import performance_monitor

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """Event data structure."""
    event_type: str
    data: Dict[str, Any]
    source: str
    timestamp: datetime = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = None
    correlation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()
        if self.metadata is None:
            self.metadata = {}
        if self.correlation_id is None:
            self.correlation_id = f"{self.event_type}_{int(time.time())}"


@dataclass
class EventHandler:
    """Event handler configuration."""
    handler_func: Callable
    event_type: str
    priority: EventPriority = EventPriority.NORMAL
    async_handler: bool = False
    timeout_ms: int = 5000
    retry_on_failure: bool = True
    max_retries: int = 3


class EventBus:
    """
    High-performance event bus for inter-module communication.
    
    Provides reliable event delivery, priority processing, and
    comprehensive monitoring for all event operations.
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.event_queue = asyncio.Queue(maxsize=1000)
        self.running = False
        self.stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'handlers_registered': 0
        }
        
        # Performance targets
        self.PROCESSING_TIMEOUT_MS = 5000
        self.QUEUE_MAX_SIZE = 1000
        self.BATCH_SIZE = 50
        
    def register_handler(self, event_type: str, handler_func: Callable, 
                        priority: EventPriority = EventPriority.NORMAL,
                        async_handler: bool = False,
                        timeout_ms: int = 5000,
                        retry_on_failure: bool = True,
                        max_retries: int = 3):
        """
        Register an event handler.
        
        Args:
            event_type: Type of event to handle
            handler_func: Handler function
            priority: Handler priority
            async_handler: Whether handler is async
            timeout_ms: Handler timeout in milliseconds
            retry_on_failure: Whether to retry on failure
            max_retries: Maximum retry attempts
        """
        handler = EventHandler(
            handler_func=handler_func,
            event_type=event_type,
            priority=priority,
            async_handler=async_handler,
            timeout_ms=timeout_ms,
            retry_on_failure=retry_on_failure,
            max_retries=max_retries
        )
        
        self.handlers[event_type].append(handler)
        self.handlers[event_type].sort(key=lambda h: h.priority.value, reverse=True)
        
        self.stats['handlers_registered'] += 1
        
        logger.info(f"Registered handler for event type: {event_type}")
    
    def unregister_handler(self, event_type: str, handler_func: Callable):
        """Unregister an event handler."""
        handlers = self.handlers[event_type]
        self.handlers[event_type] = [h for h in handlers if h.handler_func != handler_func]
        
        logger.info(f"Unregistered handler for event type: {event_type}")
    
    async def emit(self, event_type: str, data: Dict[str, Any], 
                  source: str = "advertiser_portal",
                  priority: EventPriority = EventPriority.NORMAL,
                  metadata: Dict[str, Any] = None,
                  correlation_id: str = None) -> bool:
        """
        Emit an event to all registered handlers.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Event source
            priority: Event priority
            metadata: Additional metadata
            correlation_id: Correlation ID for tracking
            
        Returns:
            True if event was successfully queued
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority,
            metadata=metadata or {},
            correlation_id=correlation_id
        )
        
        try:
            # Check queue size
            if self.event_queue.qsize() >= self.QUEUE_MAX_SIZE:
                logger.warning(f"Event queue full, dropping event: {event_type}")
                return False
            
            await self.event_queue.put(event)
            self.stats['events_published'] += 1
            
            # Log high priority events
            if priority >= EventPriority.HIGH:
                logger.info(f"High priority event emitted: {event_type}")
            
            return True
            
        except asyncio.QueueFull:
            logger.error(f"Failed to queue event: {event_type} - queue full")
            return False
        except Exception as e:
            logger.error(f"Error emitting event {event_type}: {e}")
            return False
    
    async def start_processing(self):
        """Start the event processing loop."""
        if self.running:
            return
        
        self.running = True
        
        # Start processing tasks
        try:
            _loop = asyncio.get_running_loop()
            _loop.create_task(self._process_events())
        except RuntimeError:
            pass  # No running event loop at import time
        try:
            _loop = asyncio.get_running_loop()
            _loop.create_task(self._monitor_performance())
        except RuntimeError:
            pass  # No running event loop at import time
        
        logger.info("Event bus started processing events")
    
    async def stop_processing(self):
        """Stop the event processing loop."""
        self.running = False
        
        # Wait for queue to empty
        while not self.event_queue.empty():
            await asyncio.sleep(0.1)
        
        self.executor.shutdown(wait=True)
        
        logger.info("Event bus stopped processing events")
    
    async def _process_events(self):
        """Main event processing loop."""
        while self.running:
            try:
                # Get batch of events
                events = []
                for _ in range(min(self.BATCH_SIZE, self.event_queue.qsize())):
                    try:
                        event = self.event_queue.get_nowait()
                        events.append(event)
                    except asyncio.QueueEmpty:
                        break
                
                if not events:
                    await asyncio.sleep(0.01)  # Small delay when queue is empty
                    continue
                
                # Process events in parallel
                tasks = []
                for event in events:
                    task = asyncio.create_task(self._process_single_event(event))
                    tasks.append(task)
                
                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1)  # Delay on error
    
    async def _process_single_event(self, event: Event):
        """Process a single event."""
        start_time = time.time()
        
        try:
            with performance_monitor.measure(
                f"event_processing_{event.event_type}",
                metadata={'correlation_id': event.correlation_id}
            ):
                handlers = self.handlers.get(event.event_type, [])
                
                if not handlers:
                    logger.debug(f"No handlers registered for event: {event.event_type}")
                    return
                
                # Process handlers based on priority
                for handler in handlers:
                    await self._execute_handler(handler, event)
                
                self.stats['events_processed'] += 1
                
        except Exception as e:
            logger.error(f"Error processing event {event.event_type}: {e}")
            self.stats['events_failed'] += 1
            
            # Retry logic
            if event.retry_count < event.max_retries:
                event.retry_count += 1
                await asyncio.sleep(2 ** event.retry_count)  # Exponential backoff
                await self.event_queue.put(event)
            else:
                logger.error(f"Event {event.event_type} failed after {event.max_retries} retries")
        
        finally:
            processing_time = (time.time() - start_time) * 1000
            if processing_time > 1000:  # Log slow processing
                logger.warning(f"Slow event processing: {event.event_type} took {processing_time:.2f}ms")
    
    async def _execute_handler(self, handler: EventHandler, event: Event):
        """Execute a single event handler."""
        try:
            if handler.async_handler:
                # Async handler
                await asyncio.wait_for(
                    handler.handler_func(event),
                    timeout=handler.timeout_ms / 1000
                )
            else:
                # Sync handler - run in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: handler.handler_func(event)
                )
                
        except asyncio.TimeoutError:
            logger.error(f"Handler timeout for event {event.event_type}")
            raise
        except Exception as e:
            logger.error(f"Handler error for event {event.event_type}: {e}")
            
            if handler.retry_on_failure:
                raise
            else:
                logger.warning(f"Handler failed but retry disabled: {e}")
    
    async def _monitor_performance(self):
        """Monitor event bus performance."""
        while self.running:
            try:
                # Get performance stats
                queue_size = self.event_queue.qsize()
                processing_rate = self.stats['events_processed'] / max(1, time.time() - getattr(self, '_start_time', time.time()))
                
                # Log performance metrics
                if queue_size > self.QUEUE_MAX_SIZE * 0.8:
                    logger.warning(f"Event queue nearly full: {queue_size}/{self.QUEUE_MAX_SIZE}")
                
                if processing_rate < 10:  # Less than 10 events per second
                    logger.warning(f"Low processing rate: {processing_rate:.2f} events/sec")
                
                # Store stats in cache
                cache.set('event_bus_stats', {
                    'queue_size': queue_size,
                    'processing_rate': processing_rate,
                    'stats': self.stats.copy(),
                    'timestamp': timezone.now().isoformat()
                }, timeout=60)
                
                await asyncio.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(10)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            'stats': self.stats.copy(),
            'queue_size': self.event_queue.qsize(),
            'handlers': {
                event_type: len(handlers)
                for event_type, handlers in self.handlers.items()
            },
            'running': self.running,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_handler_info(self, event_type: str = None) -> Dict[str, Any]:
        """Get information about registered handlers."""
        if event_type:
            handlers = self.handlers.get(event_type, [])
            return {
                'event_type': event_type,
                'handler_count': len(handlers),
                'handlers': [
                    {
                        'function': h.handler_func.__name__,
                        'priority': h.priority.name,
                        'async': h.async_handler,
                        'timeout_ms': h.timeout_ms,
                        'retry_on_failure': h.retry_on_failure,
                        'max_retries': h.max_retries
                    }
                    for h in handlers
                ]
            }
        else:
            return {
                event_type: self.get_handler_info(event_type)
                for event_type in self.handlers.keys()
            }


# Global event bus instance
event_bus = EventBus()


# Decorator for easy event handler registration
def event_handler(event_type: str, priority: EventPriority = EventPriority.NORMAL,
                 async_handler: bool = False, timeout_ms: int = 5000,
                 retry_on_failure: bool = True, max_retries: int = 3):
    """
    Decorator for registering event handlers.
    
    Args:
        event_type: Type of event to handle
        priority: Handler priority
        async_handler: Whether handler is async
        timeout_ms: Handler timeout in milliseconds
        retry_on_failure: Whether to retry on failure
        max_retries: Maximum retry attempts
        
    Returns:
        Decorated function
    """
    def decorator(func):
        event_bus.register_handler(
            event_type=event_type,
            handler_func=func,
            priority=priority,
            async_handler=async_handler,
            timeout_ms=timeout_ms,
            retry_on_failure=retry_on_failure,
            max_retries=max_retries
        )
        return func
    return decorator


# Export main classes
__all__ = [
    'EventBus',
    'Event',
    'EventHandler',
    'EventPriority',
    'event_bus',
    'event_handler',
]
