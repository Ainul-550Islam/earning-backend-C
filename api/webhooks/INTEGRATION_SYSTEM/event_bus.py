"""Event Bus System

This module provides event bus functionality for integration system
with comprehensive event publishing, subscription, and routing capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import json
import uuid

from .integ_constants import SignalType, HealthStatus
from .integ_exceptions import EventBusError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class Event:
    """
    Event class for event bus system.
    Represents an event with metadata and payload.
    """
    
    def __init__(self, event_type: str, payload: Dict[str, Any], **kwargs):
        """Initialize an event."""
        self.id = str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.timestamp = kwargs.get('timestamp', timezone.now())
        self.source = kwargs.get('source', 'unknown')
        self.correlation_id = kwargs.get('correlation_id')
        self.metadata = kwargs.get('metadata', {})
        self.priority = kwargs.get('priority', 'normal')
        self.tags = kwargs.get('tags', [])
        
        # Add system metadata
        self.metadata.update({
            'event_id': self.id,
            'created_at': self.timestamp.isoformat(),
            'event_bus': True
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata,
            'priority': self.priority,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(
            event_type=data['event_type'],
            payload=data['payload'],
            timestamp=timezone.parse(data['timestamp']),
            source=data.get('source'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {}),
            priority=data.get('priority', 'normal'),
            tags=data.get('tags', [])
        )


class Subscription:
    """
    Subscription class for event bus system.
    Represents a subscription to event types with filters and handlers.
    """
    
    def __init__(self, event_type: str, handler: Callable, **kwargs):
        """Initialize a subscription."""
        self.id = str(uuid.uuid4())
        self.event_type = event_type
        self.handler = handler
        self.filter_func = kwargs.get('filter_func')
        self.priority = kwargs.get('priority', 0)
        self.max_retries = kwargs.get('max_retries', 3)
        self.timeout = kwargs.get('timeout', 30)
        self.enabled = kwargs.get('enabled', True)
        self.metadata = kwargs.get('metadata', {})
        self.created_at = timezone.now()
        self.last_called = None
        self.call_count = 0
        self.error_count = 0
        
        # Add system metadata
        self.metadata.update({
            'subscription_id': self.id,
            'created_at': self.created_at.isoformat(),
            'event_bus': True
        })
    
    def matches_event(self, event: Event) -> bool:
        """Check if subscription matches event."""
        try:
            # Check if enabled
            if not self.enabled:
                return False
            
            # Check event type
            if self.event_type != event.event_type and self.event_type != '*':
                return False
            
            # Apply filter function
            if self.filter_func:
                return self.filter_func(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching event: {str(e)}")
            return False
    
    def handle_event(self, event: Event) -> bool:
        """Handle an event."""
        try:
            self.last_called = timezone.now()
            self.call_count += 1
            
            # Call handler
            if self.timeout:
                # Implement timeout handling
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Handler timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.timeout)
                
                try:
                    result = self.handler(event)
                finally:
                    signal.alarm(0)
            else:
                result = self.handler(event)
            
            return True
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error handling event {event.id}: {str(e)}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert subscription to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'priority': self.priority,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'enabled': self.enabled,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'last_called': self.last_called.isoformat() if self.last_called else None,
            'call_count': self.call_count,
            'error_count': self.error_count
        }


class EventBus:
    """
    Main event bus for integration system.
    Provides comprehensive event publishing, subscription, and routing.
    """
    
    def __init__(self):
        """Initialize the event bus."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Storage
        self.subscriptions = {}  # event_type -> [Subscription]
        self.event_history = []
        self.subscriber_stats = {}
        
        # Configuration
        self._load_configuration()
        
        # Initialize event bus
        self._initialize_event_bus()
    
    def _load_configuration(self):
        """Load event bus configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_EVENT_BUS_CONFIG', {})
            self.max_history = self.config.get('max_history', 10000)
            self.enable_persistence = self.config.get('enable_persistence', True)
            self.enable_async = self.config.get('enable_async', True)
            self.max_subscribers = self.config.get('max_subscribers', 1000)
            self.default_timeout = self.config.get('default_timeout', 30)
            
            self.logger.info("Event bus configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading event bus configuration: {str(e)}")
            self.config = {}
            self.max_history = 10000
            self.enable_persistence = True
            self.enable_async = True
            self.max_subscribers = 1000
            self.default_timeout = 30
    
    def _initialize_event_bus(self):
        """Initialize the event bus."""
        try:
            # Load initial subscriptions from configuration
            initial_subscriptions = self.config.get('initial_subscriptions', [])
            for sub_config in initial_subscriptions:
                self._register_subscription_from_config(sub_config)
            
            # Start background tasks if enabled
            if self.enable_async:
                self._start_background_tasks()
            
            self.logger.info(f"Event bus initialized with {len(self.subscriptions)} subscriptions")
            
        except Exception as e:
            self.logger.error(f"Error initializing event bus: {str(e)}")
    
    def _register_subscription_from_config(self, config: Dict[str, Any]):
        """Register subscription from configuration."""
        try:
            event_type = config.get('event_type')
            handler_path = config.get('handler')
            
            if not event_type or not handler_path:
                self.logger.warning(f"Invalid subscription config: {config}")
                return
            
            # Import handler
            module_path, function_name = handler_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            handler = getattr(module, function_name)
            
            # Create subscription
            subscription = Subscription(
                event_type=event_type,
                handler=handler,
                priority=config.get('priority', 0),
                max_retries=config.get('max_retries', 3),
                timeout=config.get('timeout', self.default_timeout),
                enabled=config.get('enabled', True),
                metadata=config.get('metadata', {})
            )
            
            self._add_subscription(subscription)
            
        except Exception as e:
            self.logger.error(f"Error registering subscription from config: {str(e)}")
    
    def _start_background_tasks(self):
        """Start background tasks for event bus."""
        try:
            # This would integrate with your task system
            # For now, just log that background tasks are enabled
            self.logger.info("Background tasks enabled for event bus")
        except Exception as e:
            self.logger.error(f"Error starting background tasks: {str(e)}")
    
    def publish(self, event: Union[Event, Dict[str, Any]], **kwargs) -> str:
        """
        Publish an event to the event bus.
        
        Args:
            event: Event object or event data
            **kwargs: Additional event parameters
            
        Returns:
            Event ID
        """
        try:
            with self.monitor.measure_event_bus('publish') as measurement:
                # Create event if needed
                if isinstance(event, dict):
                    event = Event(
                        event_type=event.get('event_type'),
                        payload=event.get('payload', {}),
                        **kwargs
                    )
                
                # Validate event
                if not self._validate_event(event):
                    raise EventBusError("Invalid event")
                
                # Add to history
                self._add_to_history(event)
                
                # Get matching subscriptions
                subscriptions = self._get_matching_subscriptions(event)
                
                # Notify subscribers
                notified_count = self._notify_subscribers(event, subscriptions)
                
                # Persist if enabled
                if self.enable_persistence:
                    self._persist_event(event)
                
                # Update statistics
                self._update_statistics(event, notified_count)
                
                self.logger.info(f"Event {event.event_type} published to {notified_count} subscribers")
                return event.id
                
        except Exception as e:
            self.logger.error(f"Error publishing event: {str(e)}")
            raise EventBusError(f"Event publishing failed: {str(e)}")
    
    def subscribe(self, event_type: str, handler: Callable, **kwargs) -> str:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Event type to subscribe to
            handler: Handler function
            **kwargs: Additional subscription parameters
            
        Returns:
            Subscription ID
        """
        try:
            # Check subscriber limit
            total_subscribers = sum(len(subs) for subs in self.subscriptions.values())
            if total_subscribers >= self.max_subscribers:
                raise EventBusError(f"Maximum subscribers limit reached: {self.max_subscribers}")
            
            # Create subscription
            subscription = Subscription(
                event_type=event_type,
                handler=handler,
                **kwargs
            )
            
            # Add subscription
            self._add_subscription(subscription)
            
            self.logger.info(f"Subscribed to event type: {event_type}")
            return subscription.id
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {event_type}: {str(e)}")
            raise EventBusError(f"Subscription failed: {str(e)}")
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if unsubscription successful
        """
        try:
            # Find and remove subscription
            for event_type, subscriptions in self.subscriptions.items():
                for i, subscription in enumerate(subscriptions):
                    if subscription.id == subscription_id:
                        subscriptions.pop(i)
                        
                        # Remove empty subscription lists
                        if not subscriptions:
                            del self.subscriptions[event_type]
                        
                        self.logger.info(f"Unsubscribed: {subscription_id}")
                        return True
            
            self.logger.warning(f"Subscription not found: {subscription_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing {subscription_id}: {str(e)}")
            return False
    
    def _add_subscription(self, subscription: Subscription):
        """Add subscription to event bus."""
        try:
            event_type = subscription.event_type
            
            if event_type not in self.subscriptions:
                self.subscriptions[event_type] = []
            
            self.subscriptions[event_type].append(subscription)
            
            # Sort by priority (higher priority first)
            self.subscriptions[event_type].sort(key=lambda x: x.priority, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error adding subscription: {str(e)}")
            raise
    
    def _validate_event(self, event: Event) -> bool:
        """Validate event."""
        try:
            # Basic validation
            if not event.event_type:
                return False
            
            if not isinstance(event.payload, dict):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating event: {str(e)}")
            return False
    
    def _add_to_history(self, event: Event):
        """Add event to history."""
        try:
            self.event_history.append(event.to_dict())
            
            # Limit history size
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
                
        except Exception as e:
            self.logger.error(f"Error adding to history: {str(e)}")
    
    def _get_matching_subscriptions(self, event: Event) -> List[Subscription]:
        """Get subscriptions that match the event."""
        try:
            matching_subscriptions = []
            
            # Get subscriptions for exact event type
            if event.event_type in self.subscriptions:
                matching_subscriptions.extend([
                    sub for sub in self.subscriptions[event.event_type]
                    if sub.matches_event(event)
                ])
            
            # Get wildcard subscriptions
            if '*' in self.subscriptions:
                matching_subscriptions.extend([
                    sub for sub in self.subscriptions['*']
                    if sub.matches_event(event)
                ])
            
            return matching_subscriptions
            
        except Exception as e:
            self.logger.error(f"Error getting matching subscriptions: {str(e)}")
            return []
    
    def _notify_subscribers(self, event: Event, subscriptions: List[Subscription]) -> int:
        """Notify subscribers of event."""
        try:
            notified_count = 0
            
            for subscription in subscriptions:
                try:
                    success = subscription.handle_event(event)
                    if success:
                        notified_count += 1
                        self._update_subscriber_stats(subscription.id, 'success')
                    else:
                        self._update_subscriber_stats(subscription.id, 'error')
                        
                except Exception as e:
                    self.logger.error(f"Error notifying subscriber {subscription.id}: {str(e)}")
                    self._update_subscriber_stats(subscription.id, 'error')
                    continue
            
            return notified_count
            
        except Exception as e:
            self.logger.error(f"Error notifying subscribers: {str(e)}")
            return 0
    
    def _update_subscriber_stats(self, subscription_id: str, status: str):
        """Update subscriber statistics."""
        try:
            if subscription_id not in self.subscriber_stats:
                self.subscriber_stats[subscription_id] = {
                    'success_count': 0,
                    'error_count': 0,
                    'last_status': None,
                    'last_updated': None
                }
            
            stats = self.subscriber_stats[subscription_id]
            stats['last_status'] = status
            stats['last_updated'] = timezone.now()
            
            if status == 'success':
                stats['success_count'] += 1
            elif status == 'error':
                stats['error_count'] += 1
            
        except Exception as e:
            self.logger.error(f"Error updating subscriber stats: {str(e)}")
    
    def _update_statistics(self, event: Event, notified_count: int):
        """Update event bus statistics."""
        try:
            # Update cache
            stats_key = 'event_bus_stats'
            stats = cache.get(stats_key, {
                'total_events': 0,
                'total_notifications': 0,
                'event_types': {},
                'last_updated': None
            })
            
            stats['total_events'] += 1
            stats['total_notifications'] += notified_count
            stats['last_updated'] = timezone.now().isoformat()
            
            # Update event type stats
            if event.event_type not in stats['event_types']:
                stats['event_types'][event.event_type] = {
                    'count': 0,
                    'notifications': 0
                }
            
            stats['event_types'][event.event_type]['count'] += 1
            stats['event_types'][event.event_type]['notifications'] += notified_count
            
            # Save to cache
            cache.set(stats_key, stats, timeout=300)  # 5 minutes
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {str(e)}")
    
    def _persist_event(self, event: Event):
        """Persist event to storage."""
        try:
            # This would integrate with your persistence layer
            # For now, just log the event
            self.logger.debug(f"Persisting event: {event.id}")
            
        except Exception as e:
            self.logger.error(f"Error persisting event: {str(e)}")
    
    def get_subscriptions(self, event_type: str = None) -> List[Dict[str, Any]]:
        """
        Get subscription information.
        
        Args:
            event_type: Optional event type filter
            
        Returns:
            List of subscription information
        """
        try:
            if event_type:
                if event_type in self.subscriptions:
                    return [sub.to_dict() for sub in self.subscriptions[event_type]]
                else:
                    return []
            else:
                all_subscriptions = []
                for subscriptions in self.subscriptions.values():
                    all_subscriptions.extend([sub.to_dict() for sub in subscriptions])
                return all_subscriptions
                
        except Exception as e:
            self.logger.error(f"Error getting subscriptions: {str(e)}")
            return []
    
    def get_event_history(self, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            event_type: Optional event type filter
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        try:
            history = self.event_history
            
            # Filter by event type
            if event_type:
                history = [
                    event for event in history
                    if event['event_type'] == event_type
                ]
            
            # Limit results
            if limit:
                history = history[-limit:]
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting event history: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event bus statistics.
        
        Returns:
            Statistics
        """
        try:
            # Get from cache
            stats_key = 'event_bus_stats'
            stats = cache.get(stats_key, {
                'total_events': 0,
                'total_notifications': 0,
                'event_types': {},
                'last_updated': None
            })
            
            # Add current state
            stats['total_subscriptions'] = sum(len(subs) for subs in self.subscriptions.values())
            stats['event_types_count'] = len(self.subscriptions)
            stats['history_size'] = len(self.event_history)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {str(e)}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of event bus.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check subscriptions
            total_subscriptions = sum(len(subs) for subs in self.subscriptions.values())
            health_status['components']['subscriptions'] = {
                'status': HealthStatus.HEALTHY,
                'total_subscriptions': total_subscriptions,
                'event_types': len(self.subscriptions)
            }
            
            # Check history
            health_status['components']['history'] = {
                'status': HealthStatus.HEALTHY,
                'history_size': len(self.event_history),
                'max_history': self.max_history
            }
            
            # Check cache
            try:
                cache.set('health_check', 'test', 10)
                cache_result = cache.get('health_check')
                health_status['components']['cache'] = {
                    'status': HealthStatus.HEALTHY if cache_result == 'test' else HealthStatus.UNHEALTHY
                }
            except Exception:
                health_status['components']['cache'] = {
                    'status': HealthStatus.UNHEALTHY,
                    'error': 'Cache connection failed'
                }
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def clear_history(self, event_type: str = None) -> bool:
        """
        Clear event history.
        
        Args:
            event_type: Optional event type filter
            
        Returns:
            True if clear successful
        """
        try:
            if event_type:
                self.event_history = [
                    event for event in self.event_history
                    if event['event_type'] != event_type
                ]
            else:
                self.event_history = []
            
            self.logger.info("Event history cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing history: {str(e)}")
            return False


# Global event bus instance
event_bus = EventBus()
