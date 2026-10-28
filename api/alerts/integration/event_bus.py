"""
Integration Event Bus - Event-driven communication for integration system
Provides safe event handling with existing alerts architecture
"""
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_constants import (
    EVENT_TYPES,
    CACHE_KEYS,
    CACHE_TIMEOUTS,
    DEFAULT_TIMEOUTS
)

logger = logging.getLogger(__name__)


class IntegrationEventBus:
    """
    Event bus for integration system
    Maintains existing validation and security logic
    """
    
    def __init__(self):
        self.subscribers = {}
        self.event_queue = []
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.event_stats = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'last_event': None
        }
    
    def subscribe(self, event_type: str, handler: Callable, priority: int = 0) -> bool:
        """
        Subscribe to event type
        """
        try:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            subscriber_data = {
                'handler': handler,
                'priority': priority,
                'subscribed_at': django_tz.now().isoformat()
            }
            
            self.subscribers[event_type].append(subscriber_data)
            
            # Sort by priority (higher priority first)
            self.subscribers[event_type].sort(key=lambda x: x['priority'], reverse=True)
            
            logger.info(f"Subscribed to event: {event_type} (priority: {priority})")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to event {event_type}: {e}")
            return False
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Unsubscribe from event type
        """
        try:
            if event_type in self.subscribers:
                self.subscribers[event_type] = [
                    sub for sub in self.subscribers[event_type]
                    if sub['handler'] != handler
                ]
                
                logger.info(f"Unsubscribed from event: {event_type}")
                return True
            else:
                logger.warning(f"No subscribers for event: {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error unsubscribing from event {event_type}: {e}")
            return False
    
    def publish(self, event_type: str, data: Dict[str, Any], 
               async_processing: bool = True) -> bool:
        """
        Publish event to subscribers
        Validates event data using existing validators
        """
        try:
            # Validate event data
            validation_result = self._validate_event_data(event_type, data)
            if not validation_result['valid']:
                logger.error(f"Invalid event data for {event_type}: {validation_result['errors']}")
                return False
            
            # Create event
            event = {
                'id': self._generate_event_id(),
                'type': event_type,
                'data': data,
                'timestamp': django_tz.now().isoformat(),
                'processed': False,
                'async': async_processing
            }
            
            # Update stats
            self.event_stats['total_events'] += 1
            self.event_stats['last_event'] = event['timestamp']
            
            # Add to queue
            self.event_queue.append(event)
            
            # Process event
            if async_processing:
                self.executor.submit(self._process_event, event)
            else:
                self._process_event(event)
            
            logger.info(f"Published event: {event_type} (ID: {event['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {e}")
            self.event_stats['failed_events'] += 1
            return False
    
    def _validate_event_data(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate event data using existing validators
        """
        try:
            errors = []
            
            # Validate alert-related data
            if 'alert_data' in data:
                alert_data = data['alert_data']
                
                # Validate condition if present
                if 'condition' in alert_data:
                    condition_validation = validate_alert_rule_condition(alert_data['condition'])
                    if not condition_validation['valid']:
                        errors.extend(condition_validation['errors'])
                
                # Validate threshold if present
                if 'threshold' in alert_data:
                    threshold_validation = validate_threshold_value(alert_data['threshold'])
                    if not threshold_validation['valid']:
                        errors.extend(threshold_validation['errors'])
            
            # Validate integration data
            if 'integration_data' in data:
                integration_data = data['integration_data']
                
                # Basic validation
                if 'type' not in integration_data:
                    errors.append("Integration type is required")
                
                if 'config' not in integration_data:
                    errors.append("Integration config is required")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating event data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _process_event(self, event: Dict[str, Any]):
        """
        Process event by notifying subscribers
        """
        try:
            event_type = event['type']
            data = event['data']
            
            # Get subscribers for event type
            subscribers = self.subscribers.get(event_type, [])
            
            if not subscribers:
                logger.warning(f"No subscribers for event: {event_type}")
                event['processed'] = True
                return
            
            # Notify subscribers
            success_count = 0
            failure_count = 0
            
            for subscriber in subscribers:
                try:
                    handler = subscriber['handler']
                    handler(event_type, data)
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
                    failure_count += 1
            
            # Update event status
            event['processed'] = True
            event['success_count'] = success_count
            event['failure_count'] = failure_count
            
            # Update stats
            self.event_stats['processed_events'] += 1
            if failure_count > 0:
                self.event_stats['failed_events'] += 1
            
            logger.info(f"Processed event {event['id']}: {success_count} success, {failure_count} failures")
            
        except Exception as e:
            logger.error(f"Error processing event {event['id']}: {e}")
            self.event_stats['failed_events'] += 1
    
    def _generate_event_id(self) -> str:
        """
        Generate unique event ID
        """
        import uuid
        return str(uuid.uuid4())
    
    def get_event_stats(self) -> Dict[str, Any]:
        """
        Get event statistics
        """
        try:
            total_events = self.event_stats['total_events']
            processed_events = self.event_stats['processed_events']
            failed_events = self.event_stats['failed_events']
            
            # Calculate processing rate
            processing_rate = (processed_events / max(total_events, 1)) * 100
            
            # Calculate failure rate
            failure_rate = (failed_events / max(total_events, 1)) * 100
            
            # Get subscriber counts
            subscriber_counts = {}
            for event_type, subscribers in self.subscribers.items():
                subscriber_counts[event_type] = len(subscribers)
            
            return {
                'total_events': total_events,
                'processed_events': processed_events,
                'failed_events': failed_events,
                'processing_rate': processing_rate,
                'failure_rate': failure_rate,
                'queue_size': len(self.event_queue),
                'subscriber_counts': subscriber_counts,
                'last_event': self.event_stats['last_event'],
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting event stats: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }
    
    def get_subscribers(self, event_type: str = None) -> Dict[str, Any]:
        """
        Get subscribers for event type or all subscribers
        """
        try:
            if event_type:
                subscribers = self.subscribers.get(event_type, [])
                return {
                    'event_type': event_type,
                    'subscribers': [
                        {
                            'priority': sub['priority'],
                            'subscribed_at': sub['subscribed_at']
                        }
                        for sub in subscribers
                    ]
                }
            else:
                all_subscribers = {}
                for evt_type, subs in self.subscribers.items():
                    all_subscribers[evt_type] = [
                        {
                            'priority': sub['priority'],
                            'subscribed_at': sub['subscribed_at']
                        }
                        for sub in subs
                    ]
                
                return all_subscribers
                
        except Exception as e:
            logger.error(f"Error getting subscribers: {e}")
            return {
                'error': 'Operation failed'
            }
    
    def clear_queue(self) -> int:
        """
        Clear event queue
        """
        try:
            queue_size = len(self.event_queue)
            self.event_queue.clear()
            
            logger.info(f"Cleared event queue: {queue_size} events removed")
            return queue_size
            
        except Exception as e:
            logger.error(f"Error clearing event queue: {e}")
            return 0
    
    def shutdown(self):
        """
        Shutdown event bus
        """
        try:
            # Clear queue
            self.clear_queue()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Event bus shutdown complete")
            
        except Exception as e:
            logger.error(f"Error shutting down event bus: {e}")


# Global event bus instance
integration_event_bus = IntegrationEventBus()


# Event decorators and utilities
def event_handler(event_type: str, priority: int = 0):
    """
    Decorator for event handlers
    """
    def decorator(func):
        integration_event_bus.subscribe(event_type, func, priority)
        return func
    return decorator


def publish_integration_event(event_type: str, data: Dict[str, Any], 
                           async_processing: bool = True) -> bool:
    """
    Publish integration event
    """
    return integration_event_bus.publish(event_type, data, async_processing)


def get_event_statistics() -> Dict[str, Any]:
    """
    Get event statistics
    """
    return integration_event_bus.get_event_stats()


# Predefined event handlers
@event_handler('integration_triggered', priority=10)
def handle_integration_triggered(event_type: str, data: Dict[str, Any]):
    """
    Handle integration triggered events
    """
    try:
        alert_id = data.get('alert_id')
        integration_data = data.get('integration_data', {})
        
        logger.info(f"Integration triggered for alert {alert_id}")
        
        # Process integration through handler
        result = integration_handler.process_alert_data(integration_data)
        
        # Publish completion event
        if result.get('success', False):
            publish_integration_event('integration_completed', {
                'alert_id': alert_id,
                'result': result
            })
        else:
            publish_integration_event('integration_failed', {
                'alert_id': alert_id,
                'error': result.get('error', 'Unknown error'),
                'result': result
            })
            
    except Exception as e:
        logger.error(f"Error handling integration triggered event: {e}")


@event_handler('integration_completed', priority=5)
def handle_integration_completed(event_type: str, data: Dict[str, Any]):
    """
    Handle integration completed events
    """
    try:
        alert_id = data.get('alert_id')
        result = data.get('result', {})
        
        logger.info(f"Integration completed for alert {alert_id}")
        
        # Update alert status if needed
        try:
            alert_log = AlertLog.objects.get(id=alert_id)
            metadata = getattr(alert_log, 'metadata', {})
            metadata['integration_completed'] = True
            metadata['integration_result'] = result
            alert_log.metadata = metadata
            alert_log.save(update_fields=['metadata'])
        except AlertLog.DoesNotExist:
            logger.warning(f"Alert log not found for id: {alert_id}")
            
    except Exception as e:
        logger.error(f"Error handling integration completed event: {e}")


@event_handler('integration_failed', priority=5)
def handle_integration_failed(event_type: str, data: Dict[str, Any]):
    """
    Handle integration failed events
    """
    try:
        alert_id = data.get('alert_id')
        error = data.get('error', 'Unknown error')
        result = data.get('result')
        
        logger.error(f"Integration failed for alert {alert_id}: {error}")
        
        # Update alert status if needed
        try:
            alert_log = AlertLog.objects.get(id=alert_id)
            metadata = getattr(alert_log, 'metadata', {})
            metadata['integration_failed'] = True
            metadata['integration_error'] = error
            if result:
                metadata['integration_result'] = result
            alert_log.metadata = metadata
            alert_log.save(update_fields=['metadata'])
        except AlertLog.DoesNotExist:
            logger.warning(f"Alert log not found for id: {alert_id}")
            
    except Exception as e:
        logger.error(f"Error handling integration failed event: {e}")


@event_handler('circuit_breaker_opened', priority=8)
def handle_circuit_breaker_opened(event_type: str, data: Dict[str, Any]):
    """
    Handle circuit breaker opened events
    """
    try:
        channel = data.get('channel', 'unknown')
        logger.warning(f"Circuit breaker opened for channel: {channel}")
        
        # Publish alert for circuit breaker opening
        publish_integration_event('integration_failed', {
            'alert_id': None,
            'error': f'Circuit breaker opened for channel: {channel}',
            'circuit_breaker_event': True
        })
        
    except Exception as e:
        logger.error(f"Error handling circuit breaker opened event: {e}")


# Utility functions
def subscribe_to_integration_events(handler: Callable, event_types: List[str] = None, priority: int = 0):
    """
    Subscribe to multiple integration events
    """
    if not event_types:
        event_types = list(EVENT_TYPES.keys())
    
    for event_type in event_types:
        integration_event_bus.subscribe(event_type, handler, priority)


def create_alert_event(alert_id: int, event_data: Dict[str, Any]) -> bool:
    """
    Create alert-related event
    """
    return publish_integration_event('integration_triggered', {
        'alert_id': alert_id,
        'integration_data': event_data
    })


def get_event_bus_status() -> Dict[str, Any]:
    """
    Get event bus status
    """
    return {
        'stats': integration_event_bus.get_event_stats(),
        'subscribers': integration_event_bus.get_subscribers(),
        'timestamp': django_tz.now().isoformat()
    }
