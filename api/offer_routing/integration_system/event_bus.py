"""
Event Bus

Central event bus for integration system
with publish-subscribe pattern.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.core.cache import cache
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for integration system.
    
    Provides publish-subscribe pattern for:
    - Integration events
    - System notifications
    - Data synchronization
    - Error handling
    - Performance monitoring
    """
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        self.cache_timeout = 3600  # 1 hour
        
        # Initialize event handlers
        self._initialize_event_handlers()
    
    def _initialize_event_handlers(self):
        """Initialize default event handlers."""
        try:
            # Register default handlers
            self.subscribe('integration.registered', self._handle_integration_registered)
            self.subscribe('integration.error', self._handle_integration_error)
            self.subscribe('integration.sync.completed', self._handle_sync_completed)
            self.subscribe('integration.health.changed', self._handle_health_changed)
            
        except Exception as e:
            logger.error(f"Error initializing event handlers: {e}")
    
    def publish(self, event_type: str, data: Dict[str, Any], 
                 metadata: Dict[str, Any] = None) -> bool:
        """
        Publish event to all subscribers.
        
        Args:
            event_type: Type of event
            data: Event data
            metadata: Additional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            event = {
                'id': self._generate_event_id(),
                'type': event_type,
                'data': data,
                'metadata': metadata or {},
                'timestamp': timezone.now().isoformat(),
                'source': 'integration_system'
            }
            
            # Add to history
            self._add_to_history(event)
            
            # Notify subscribers
            if event_type in self.subscribers:
                for subscriber in self.subscribers[event_type]:
                    try:
                        subscriber(event)
                    except Exception as e:
                        logger.error(f"Error in subscriber {subscriber.__name__}: {e}")
            
            # Cache recent events
            self._cache_recent_events()
            
            logger.debug(f"Published event: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {e}")
            return False
    
    def subscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Subscribe to event type.
        
        Args:
            event_type: Event type to subscribe to
            handler: Event handler function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            self.subscribers[event_type].append(handler)
            
            logger.debug(f"Subscribed to event: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to event {event_type}: {e}")
            return False
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Event type to unsubscribe from
            handler: Event handler function
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if event_type in self.subscribers:
                try:
                    self.subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed from event: {event_type}")
                    return True
                except ValueError:
                    logger.warning(f"Handler not found for event {event_type}")
                    return False
            
            logger.warning(f"Event type not found: {event_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error unsubscribing from event {event_type}: {e}")
            return False
    
    def get_subscribers(self, event_type: str = None) -> Dict[str, List[Callable]]:
        """
        Get subscribers for event type(s).
        
        Args:
            event_type: Specific event type (None for all)
            
        Returns:
            Dictionary of subscribers
        """
        if event_type:
            return {event_type: self.subscribers.get(event_type, [])}
        else:
            return self.subscribers.copy()
    
    def get_event_history(self, event_type: str = None, 
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        try:
            history = self.event_history
            
            if event_type:
                history = [e for e in history if e['type'] == event_type]
            
            return history[-limit:] if len(history) > limit else history
            
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return []
    
    def clear_history(self, event_type: str = None) -> bool:
        """
        Clear event history.
        
        Args:
            event_type: Clear specific event type (None for all)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if event_type:
                self.event_history = [
                    e for e in self.event_history if e['type'] != event_type
                ]
            else:
                self.event_history = []
            
            logger.info(f"Cleared event history for {event_type or 'all events'}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing event history: {e}")
            return False
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _add_to_history(self, event: Dict[str, Any]):
        """Add event to history."""
        self.event_history.append(event)
        
        # Maintain max history size
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    def _cache_recent_events(self):
        """Cache recent events for quick access."""
        try:
            recent_events = self.event_history[-100:]  # Last 100 events
            
            cache.set('recent_integration_events', recent_events, self.cache_timeout)
            
        except Exception as e:
            logger.error(f"Error caching recent events: {e}")
    
    def _handle_integration_registered(self, event: Dict[str, Any]):
        """Handle integration registered event."""
        try:
            integration_id = event['data'].get('integration_id')
            integration_name = event['data'].get('integration_name')
            
            logger.info(f"Integration registered: {integration_name} ({integration_id})")
            
            # Trigger integration initialization
            self.publish('integration.initialize', {
                'integration_id': integration_id,
                'integration_name': integration_name
            })
            
        except Exception as e:
            logger.error(f"Error handling integration registered event: {e}")
    
    def _handle_integration_error(self, event: Dict[str, Any]):
        """Handle integration error event."""
        try:
            integration_id = event['data'].get('integration_id')
            error = event['data'].get('error')
            
            logger.error(f"Integration error: {integration_id} - {error}")
            
            # Trigger error handling workflow
            self.publish('integration.error.handling', {
                'integration_id': integration_id,
                'error': error,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling integration error event: {e}")
    
    def _handle_sync_completed(self, event: Dict[str, Any]):
        """Handle sync completed event."""
        try:
            integration_id = event['data'].get('integration_id')
            sync_result = event['data'].get('result')
            
            logger.info(f"Sync completed: {integration_id}")
            
            # Update integration status
            self.publish('integration.status.update', {
                'integration_id': integration_id,
                'status': IntegrationStatus.ACTIVE.value,
                'last_sync': timezone.now().isoformat(),
                'sync_result': sync_result
            })
            
        except Exception as e:
            logger.error(f"Error handling sync completed event: {e}")
    
    def _handle_health_changed(self, event: Dict[str, Any]):
        """Handle health changed event."""
        try:
            integration_id = event['data'].get('integration_id')
            health_status = event['data'].get('health_status')
            
            logger.info(f"Health changed: {integration_id} - {health_status}")
            
            # Trigger alert if unhealthy
            if health_status == 'unhealthy':
                self.publish('integration.alert', {
                    'integration_id': integration_id,
                    'alert_type': 'health_check_failed',
                    'message': f"Integration {integration_id} is unhealthy",
                    'severity': 'high',
                    'timestamp': timezone.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error handling health changed event: {e}")
    
    def get_bus_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        try:
            total_events = len(self.event_history)
            total_subscribers = sum(len(subscribers) for subscribers in self.subscribers.values())
            
            # Get event type distribution
            event_types = {}
            for event in self.event_history:
                event_type = event['type']
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            return {
                'total_events': total_events,
                'total_subscribers': total_subscribers,
                'event_types': event_types,
                'event_types_count': len(event_types),
                'max_history': self.max_history,
                'cache_timeout': self.cache_timeout,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting bus stats: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on event bus."""
        try:
            # Test publishing
            test_event = {
                'type': 'health_check',
                'data': {'test': True},
                'timestamp': timezone.now().isoformat()
            }
            
            publish_success = self.publish('test.event', test_event)
            
            # Test subscribing
            test_handler = lambda event: True
            subscribe_success = self.subscribe('test.event', test_handler)
            
            # Test unsubscribing
            unsubscribe_success = self.unsubscribe('test.event', test_handler)
            
            # Clean up test event
            self.clear_history('test.event')
            
            return {
                'status': 'healthy' if all([publish_success, subscribe_success, unsubscribe_success]) else 'unhealthy',
                'publish_test': publish_success,
                'subscribe_test': subscribe_success,
                'unsubscribe_test': unsubscribe_success,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in event bus health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# Global event bus instance
event_bus = EventBus()
