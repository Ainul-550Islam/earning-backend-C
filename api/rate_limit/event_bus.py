# api/rate_limit/event_bus.py
"""
Event bus system for rate limit module.

Provides centralized event distribution and handling.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable, Set
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from collections import defaultdict
import json
import threading
import queue

from api.rate_limit.integ_constants import IntegrationEvent
from api.rate_limit.integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


class Event:
    """Represents an event in the event bus."""
    
    def __init__(self, event_type: str, data: Dict[str, Any] = None, 
                 source: str = None, priority: str = 'normal',
                 timestamp: datetime = None, metadata: Dict[str, Any] = None):
        self.event_id = f"event_{timezone.now().timestamp()}_{id(self)}"
        self.event_type = event_type
        self.data = data or {}
        self.source = source or 'unknown'
        self.priority = priority
        self.timestamp = timestamp or timezone.now()
        self.metadata = metadata or {}
        self.processed = False
        self.processed_at = None
        self.error = None
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'data': self.data,
            'source': self.source,
            'priority': self.priority,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'processed': self.processed,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'error': str(self.error) if self.error else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
    
    def mark_processed(self):
        """Mark event as processed."""
        self.processed = True
        self.processed_at = timezone.now()
    
    def mark_error(self, error: Exception):
        """Mark event with error."""
        self.error = error
        self.retry_count += 1
    
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.retry_count < self.max_retries


class EventHandler:
    """Base class for event handlers."""
    
    def __init__(self, name: str, event_types: List[str] = None, 
                 priority: str = 'normal', async_handler: bool = False):
        self.name = name
        self.event_types = event_types or []
        self.priority = priority
        self.async_handler = async_handler
        self.enabled = True
        self.processed_count = 0
        self.error_count = 0
        self.last_activity = None
    
    def can_handle(self, event_type: str) -> bool:
        """Check if handler can handle event type."""
        return event_type in self.event_types or '*' in self.event_types
    
    def handle(self, event: Event) -> bool:
        """
        Handle an event.
        
        Args:
            event: Event to handle
            
        Returns:
            True if handled successfully
        """
        if not self.enabled or not self.can_handle(event.event_type):
            return False
        
        try:
            result = self._handle_event(event)
            
            if result:
                self.processed_count += 1
                self.last_activity = timezone.now()
            else:
                self.error_count += 1
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Event handler {self.name} failed: {str(e)}")
            return False
    
    def _handle_event(self, event: Event) -> bool:
        """Handle event implementation."""
        raise NotImplementedError("Subclasses must implement _handle_event()")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'event_types': self.event_types,
            'priority': self.priority,
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'success_rate': (
                self.processed_count / max(self.processed_count + self.error_count, 1)
            ) * 100,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }


class EventBus:
    """
    Central event bus for event distribution.
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self.event_queue = queue.Queue()
        self.processed_events: List[Event] = []
        self.failed_events: List[Event] = []
        self.max_history_size = 1000
        self.max_queue_size = 10000
        self.is_running = False
        self.worker_thread = None
        self.statistics = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'queued_events': 0
        }
    
    def register_handler(self, handler: EventHandler, event_types: List[str] = None):
        """
        Register an event handler.
        
        Args:
            handler: Event handler instance
            event_types: Event types to handle
        """
        if event_types:
            handler.event_types = event_types
        
        for event_type in handler.event_types:
            self.handlers[event_type].append(handler)
        
        logger.info(f"Registered event handler: {handler.name} for {handler.event_types}")
    
    def unregister_handler(self, handler: EventHandler):
        """
        Unregister an event handler.
        
        Args:
            handler: Event handler instance
        """
        for event_type in handler.event_types:
            if handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
        
        logger.info(f"Unregistered event handler: {handler.name}")
    
    def publish(self, event_type: str, data: Dict[str, Any] = None, 
               source: str = None, priority: str = 'normal',
               metadata: Dict[str, Any] = None) -> Event:
        """
        Publish an event.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Event source
            priority: Event priority
            metadata: Event metadata
            
        Returns:
            Published event
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority,
            metadata=metadata
        )
        
        # Add to queue
        try:
            self.event_queue.put(event, timeout=1)
            self.statistics['total_events'] += 1
            self.statistics['queued_events'] = self.event_queue.qsize()
            
            logger.debug(f"Published event: {event_type} ({event.event_id})")
            
        except queue.Full:
            logger.error(f"Event queue is full, dropping event: {event_type}")
            self.statistics['failed_events'] += 1
        
        return event
    
    def start(self):
        """Start the event bus worker."""
        if self.is_running:
            logger.warning("Event bus is already running")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logger.info("Event bus started")
    
    def stop(self):
        """Stop the event bus worker."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        logger.info("Event bus stopped")
    
    def _worker_loop(self):
        """Main worker loop for processing events."""
        while self.is_running:
            try:
                # Get event from queue
                event = self.event_queue.get(timeout=1)
                
                # Process event
                self._process_event(event)
                
                # Mark task done
                self.event_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in event bus worker: {str(e)}")
    
    def _process_event(self, event: Event):
        """Process a single event."""
        try:
            # Get handlers for event type
            handlers = self.handlers.get(event.event_type, [])
            wildcard_handlers = self.handlers.get('*', [])
            
            all_handlers = handlers + wildcard_handlers
            
            # Sort by priority
            priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
            all_handlers.sort(key=lambda h: priority_order.get(h.priority, 2))
            
            # Process with handlers
            processed = False
            
            for handler in all_handlers:
                try:
                    if handler.handle(event):
                        processed = True
                        
                except Exception as e:
                    logger.error(f"Handler {handler.name} failed for event {event.event_id}: {str(e)}")
                    event.mark_error(e)
            
            # Mark event as processed
            if processed:
                event.mark_processed()
                self.processed_events.append(event)
                self.statistics['processed_events'] += 1
            else:
                self.failed_events.append(event)
                self.statistics['failed_events'] += 1
            
            # Maintain history size
            self._maintain_history()
            
        except Exception as e:
            logger.error(f"Failed to process event {event.event_id}: {str(e)}")
            self.failed_events.append(event)
            self.statistics['failed_events'] += 1
    
    def _maintain_history(self):
        """Maintain event history size."""
        if len(self.processed_events) > self.max_history_size:
            self.processed_events = self.processed_events[-self.max_history_size:]
        
        if len(self.failed_events) > self.max_history_size:
            self.failed_events = self.failed_events[-self.max_history_size:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        handler_stats = {}
        
        for event_type, handlers in self.handlers.items():
            handler_stats[event_type] = [
                handler.get_statistics() for handler in handlers
            ]
        
        return {
            'is_running': self.is_running,
            'statistics': self.statistics.copy(),
            'queue_size': self.event_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'processed_events_count': len(self.processed_events),
            'failed_events_count': len(self.failed_events),
            'handlers': handler_stats
        }
    
    def get_event_history(self, event_type: str = None, 
                         limit: int = 100, include_failed: bool = False) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events
            include_failed: Include failed events
            
        Returns:
            List of event data
        """
        events = self.processed_events.copy()
        
        if include_failed:
            events.extend(self.failed_events)
        
        # Filter by event type
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Sort by timestamp (most recent first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Limit results
        events = events[:limit]
        
        return [event.to_dict() for event in events]
    
    def retry_failed_events(self) -> Dict[str, Any]:
        """Retry failed events."""
        retried_count = 0
        failed_to_retry = 0
        
        # Get events that can be retried
        retryable_events = [
            event for event in self.failed_events
            if event.can_retry()
        ]
        
        for event in retryable_events:
            try:
                # Reset event for retry
                event.processed = False
                event.processed_at = None
                event.error = None
                
                # Re-queue event
                self.event_queue.put(event, timeout=1)
                retried_count += 1
                
                # Remove from failed events
                self.failed_events.remove(event)
                
            except Exception as e:
                logger.error(f"Failed to retry event {event.event_id}: {str(e)}")
                failed_to_retry += 1
        
        return {
            'retried_count': retried_count,
            'failed_to_retry': failed_to_retry,
            'total_failed': len(self.failed_events)
        }
    
    def clear_history(self, event_type: str = None):
        """Clear event history."""
        if event_type:
            self.processed_events = [
                e for e in self.processed_events
                if e.event_type != event_type
            ]
            self.failed_events = [
                e for e in self.failed_events
                if e.event_type != event_type
            ]
        else:
            self.processed_events.clear()
            self.failed_events.clear()
        
        logger.info(f"Cleared event history for {event_type or 'all events'}")


class RateLimitEventHandler(EventHandler):
    """Handler for rate limit events."""
    
    def __init__(self):
        super().__init__(
            name='rate_limit_handler',
            event_types=[
                IntegrationEvent.RATE_LIMIT_EXCEEDED,
                IntegrationEvent.RATE_LIMIT_ALLOWED,
                IntegrationEvent.ABUSE_DETECTED,
                IntegrationEvent.IP_BLOCKED,
                IntegrationEvent.IP_UNBLOCKED
            ]
        )
    
    def _handle_event(self, event: Event) -> bool:
        """Handle rate limit events."""
        try:
            # Store event in cache for immediate access
            cache_key = f"rate_limit_event:{event.event_type}:{timezone.now().date()}"
            events = cache.get(cache_key, [])
            events.append(event.to_dict())
            cache.set(cache_key, events, timeout=86400)  # 24 hours
            
            # Trigger integration handlers
            from api.rate_limit.integ_handler import integration_handler
            
            # Get active integrations
            for integration_id, integration_info in integration_handler.active_integrations.items():
                adapter = integration_info['adapter']
                
                # Check if adapter handles this event type
                if hasattr(adapter, f'handle_{event.event_type}'):
                    try:
                        getattr(adapter, f'handle_{event.event_type}')(event.data)
                    except Exception as e:
                        logger.error(f"Integration {integration_id} failed to handle {event.event_type}: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit event handler failed: {str(e)}")
            return False


class ConfigEventHandler(EventHandler):
    """Handler for configuration events."""
    
    def __init__(self):
        super().__init__(
            name='config_handler',
            event_types=[
                IntegrationEvent.CONFIG_CREATED,
                IntegrationEvent.CONFIG_UPDATED,
                IntegrationEvent.CONFIG_DELETED
            ]
        )
    
    def _handle_event(self, event: Event) -> bool:
        """Handle configuration events."""
        try:
            # Clear configuration cache
            cache_key = "rate_limit_config_cache"
            cache.delete(cache_key)
            
            # Notify integrations of config changes
            if event.event_type in [IntegrationEvent.CONFIG_UPDATED, IntegrationEvent.CONFIG_DELETED]:
                from api.rate_limit.integ_handler import integration_handler
                
                for integration_id, integration_info in integration_handler.active_integrations.items():
                    adapter = integration_info['adapter']
                    
                    if hasattr(adapter, 'handle_config_updated'):
                        try:
                            adapter.handle_config_updated(event.data)
                        except Exception as e:
                            logger.error(f"Integration {integration_id} failed to handle config change: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Config event handler failed: {str(e)}")
            return False


class UserEventHandler(EventHandler):
    """Handler for user events."""
    
    def __init__(self):
        super().__init__(
            name='user_handler',
            event_types=[
                IntegrationEvent.USER_PROFILE_CREATED,
                IntegrationEvent.USER_PROFILE_UPDATED,
                IntegrationEvent.USER_PROFILE_DELETED
            ]
        )
    
    def _handle_event(self, event: Event) -> bool:
        """Handle user events."""
        try:
            # Update user profile cache
            if event.event_type in [IntegrationEvent.USER_PROFILE_CREATED, IntegrationEvent.USER_PROFILE_UPDATED]:
                user_id = event.data.get('user_id')
                if user_id:
                    cache_key = f"user_profile:{user_id}"
                    cache.set(cache_key, event.data, timeout=3600)  # 1 hour
            
            # Notify integrations of user changes
            from api.rate_limit.integ_handler import integration_handler
            
            for integration_id, integration_info in integration_handler.active_integrations.items():
                adapter = integration_info['adapter']
                
                if hasattr(adapter, 'handle_user_profile_updated'):
                    try:
                        getattr(adapter, f'handle_{event.event_type}')(event.data)
                    except Exception as e:
                        logger.error(f"Integration {integration_id} failed to handle user event: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"User event handler failed: {str(e)}")
            return False


class SystemEventHandler(EventHandler):
    """Handler for system events."""
    
    def __init__(self):
        super().__init__(
            name='system_handler',
            event_types=[
                IntegrationEvent.SYSTEM_ALERT,
                IntegrationEvent.HEALTH_CHECK,
                IntegrationEvent.INTEGRATION_SUCCESS,
                IntegrationEvent.INTEGRATION_FAILURE,
                IntegrationEvent.INTEGRATION_ERROR,
                IntegrationEvent.STATUS_CHANGE,
                IntegrationEvent.PERFORMANCE_UPDATE
            ]
        )
    
    def _handle_event(self, event: Event) -> bool:
        """Handle system events."""
        try:
            # Store system events for monitoring
            cache_key = f"system_events:{timezone.now().date()}"
            events = cache.get(cache_key, [])
            events.append(event.to_dict())
            cache.set(cache_key, events, timeout=86400)  # 24 hours
            
            # Handle critical system alerts
            if event.event_type == IntegrationEvent.SYSTEM_ALERT:
                # Send to notification system
                from api.rate_limit.integ_handler import integration_handler
                
                notification_integration = integration_handler.active_integrations.get('notification')
                if notification_integration:
                    try:
                        integration_handler.execute_integration(
                            'notification',
                            'send_notification',
                            {
                                'title': 'System Alert',
                                'message': event.data.get('message', 'System alert triggered'),
                                'priority': 'high',
                                'data': event.data
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to send system alert notification: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"System event handler failed: {str(e)}")
            return False


# Global event bus instance
event_bus = EventBus()

# Register default handlers
event_bus.register_handler(RateLimitEventHandler())
event_bus.register_handler(ConfigEventHandler())
event_bus.register_handler(UserEventHandler())
event_bus.register_handler(SystemEventHandler())

# Start event bus
event_bus.start()


# Export classes and functions
__all__ = [
    'Event',
    'EventHandler',
    'EventBus',
    'RateLimitEventHandler',
    'ConfigEventHandler',
    'UserEventHandler',
    'SystemEventHandler',
    'event_bus'
]
