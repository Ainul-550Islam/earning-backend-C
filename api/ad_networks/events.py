"""
api/ad_networks/events.py
Event system for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for ad networks"""
    
    # Offer events
    OFFER_CREATED = "offer_created"
    OFFER_UPDATED = "offer_updated"
    OFFER_ACTIVATED = "offer_activated"
    OFFER_EXPIRED = "offer_expired"
    OFFER_CLICKED = "offer_clicked"
    OFFER_VIEWED = "offer_viewed"
    
    # Conversion events
    CONVERSION_CREATED = "conversion_created"
    CONVERSION_APPROVED = "conversion_approved"
    CONVERSION_REJECTED = "conversion_rejected"
    CONVERSION_FLAGGED_AS_FRAUD = "conversion_flagged_as_fraud"
    CONVERSION_CHARGEBACK = "conversion_chargeback"
    
    # Reward events
    REWARD_CREATED = "reward_created"
    REWARD_APPROVED = "reward_approved"
    REWARD_PAID = "reward_paid"
    REWARD_CANCELLED = "reward_cancelled"
    
    # User events
    USER_ENGAGEMENT_CREATED = "user_engagement_created"
    USER_ENGAGEMENT_COMPLETED = "user_engagement_completed"
    USER_CONVERSION_CREATED = "user_conversion_created"
    USER_REWARD_EARNED = "user_reward_earned"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # Network events
    NETWORK_CREATED = "network_created"
    NETWORK_UPDATED = "network_updated"
    NETWORK_HEALTH_CHECK = "network_health_check"
    NETWORK_SYNC_COMPLETED = "network_sync_completed"
    NETWORK_SYNC_FAILED = "network_sync_failed"
    
    # Fraud events
    FRAUD_DETECTED = "fraud_detected"
    FRAUD_SCORE_UPDATED = "fraud_score_updated"
    SUSPICIOUS_ACTIVITY_DETECTED = "suspicious_activity_detected"
    SECURITY_ALERT_TRIGGERED = "security_alert_triggered"
    
    # System events
    CACHE_CLEARED = "cache_cleared"
    DATA_EXPORTED = "data_exported"
    REPORT_GENERATED = "report_generated"
    NOTIFICATION_SENT = "notification_sent"
    
    # WebSocket events
    WEBSOCKET_CONNECTED = "websocket_connected"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    MESSAGE_RECEIVED = "message_received"
    BROADCAST_SENT = "broadcast_sent"
    
    # Task events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRY = "task_retry"
    
    # Integration events
    EXTERNAL_API_CALL = "external_api_call"
    WEBHOOK_RECEIVED = "webhook_received"
    SYNC_OPERATION_COMPLETED = "sync_operation_completed"
    SYNC_OPERATION_FAILED = "sync_operation_failed"


class EventPriority(Enum):
    """Event priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Event:
    """Event class for ad networks"""
    
    def __init__(self, event_type: EventType, data: Dict[str, Any], 
                 priority: EventPriority = EventPriority.MEDIUM,
                 tenant_id: str = None, user_id: int = None,
                 timestamp: datetime = None):
        self.event_type = event_type
        self.data = data
        self.priority = priority
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.timestamp = timestamp or timezone.now()
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique event ID"""
        import uuid
        return str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'data': self.data,
            'priority': self.priority.value,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert event to JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        event_type = EventType(data['event_type'])
        priority = EventPriority(data.get('priority', 'medium'))
        timestamp = datetime.fromisoformat(data['timestamp'])
        
        return cls(
            event_type=event_type,
            data=data['data'],
            priority=priority,
            tenant_id=data.get('tenant_id'),
            user_id=data.get('user_id'),
            timestamp=timestamp
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        """Create event from JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class EventListener:
    """Event listener interface"""
    
    def __init__(self, event_type: EventType, handler: Callable):
        self.event_type = event_type
        self.handler = handler
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique listener ID"""
        import uuid
        return str(uuid.uuid4())
    
    def handle(self, event: Event) -> Any:
        """Handle event"""
        if event.event_type == self.event_type:
            return self.handler(event)
        return None


class EventDispatcher:
    """Event dispatcher for ad networks"""
    
    def __init__(self):
        self.listeners: Dict[EventType, List[EventListener]] = {}
        self.event_history: List[Event] = []
        self.max_history = 1000
    
    def register_listener(self, event_type: EventType, handler: Callable) -> EventListener:
        """Register event listener"""
        listener = EventListener(event_type, handler)
        
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        
        self.listeners[event_type].append(listener)
        
        logger.info(f"Registered listener for {event_type.value}")
        
        return listener
    
    def unregister_listener(self, listener: EventListener):
        """Unregister event listener"""
        if listener.event_type in self.listeners:
            try:
                self.listeners[listener.event_type].remove(listener)
                logger.info(f"Unregistered listener for {listener.event_type.value}")
            except ValueError:
                pass
    
    def dispatch(self, event: Event) -> List[Any]:
        """Dispatch event to listeners"""
        results = []
        
        # Add to history
        self._add_to_history(event)
        
        # Get listeners for this event type
        listeners = self.listeners.get(event.event_type, [])
        
        # Dispatch to all listeners
        for listener in listeners:
            try:
                result = listener.handle(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in event listener: {str(e)}")
                results.append(None)
        
        # Log event
        self._log_event(event)
        
        return results
    
    def dispatch_async(self, event: Event):
        """Dispatch event asynchronously"""
        from .tasks import dispatch_event_task
        dispatch_event_task.delay(event.to_dict())
    
    def _add_to_history(self, event: Event):
        """Add event to history"""
        self.event_history.append(event)
        
        # Trim history if too long
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    def _log_event(self, event: Event):
        """Log event"""
        log_data = {
            'event_type': event.event_type.value,
            'event_id': event.id,
            'tenant_id': event.tenant_id,
            'user_id': event.user_id,
            'priority': event.priority.value,
            'timestamp': event.timestamp.isoformat()
        }
        
        if event.priority == EventPriority.CRITICAL:
            logger.critical(f"Critical event: {log_data}")
        elif event.priority == EventPriority.HIGH:
            logger.error(f"High priority event: {log_data}")
        elif event.priority == EventPriority.MEDIUM:
            logger.info(f"Medium priority event: {log_data}")
        else:
            logger.debug(f"Low priority event: {log_data}")
    
    def get_history(self, event_type: EventType = None, 
                    tenant_id: str = None, user_id: int = None,
                    limit: int = 100) -> List[Event]:
        """Get event history"""
        history = self.event_history
        
        # Filter by event type
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        # Filter by tenant
        if tenant_id:
            history = [e for e in history if e.tenant_id == tenant_id]
        
        # Filter by user
        if user_id:
            history = [e for e in history if e.user_id == user_id]
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Limit results
        return history[:limit]
    
    def get_listener_count(self, event_type: EventType) -> int:
        """Get number of listeners for event type"""
        return len(self.listeners.get(event_type, []))
    
    def clear_history(self):
        """Clear event history"""
        self.event_history.clear()
        logger.info("Event history cleared")


class EventStore:
    """Event store for persistence"""
    
    def __init__(self):
        self.cache_prefix = "ad_networks_events"
        self.cache_timeout = 3600  # 1 hour
    
    def store_event(self, event: Event):
        """Store event"""
        cache_key = f"{self.cache_prefix}_{event.id}"
        cache.set(cache_key, event.to_json(), self.cache_timeout)
        
        # Add to tenant-specific list
        if event.tenant_id:
            tenant_key = f"{self.cache_prefix}_tenant_{event.tenant_id}"
            tenant_events = cache.get(tenant_key, [])
            tenant_events.append(event.id)
            
            # Keep only last 100 events per tenant
            if len(tenant_events) > 100:
                tenant_events = tenant_events[-100:]
            
            cache.set(tenant_key, tenant_events, self.cache_timeout)
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID"""
        cache_key = f"{self.cache_prefix}_{event_id}"
        event_json = cache.get(cache_key)
        
        if event_json:
            return Event.from_json(event_json)
        
        return None
    
    def get_tenant_events(self, tenant_id: str, limit: int = 50) -> List[Event]:
        """Get events for tenant"""
        tenant_key = f"{self.cache_prefix}_tenant_{tenant_id}"
        event_ids = cache.get(tenant_key, [])
        
        events = []
        for event_id in event_ids[-limit:]:
            event = self.get_event(event_id)
            if event:
                events.append(event)
        
        return events
    
    def cleanup_expired_events(self):
        """Clean up expired events"""
        # This would be called by a periodic task
        logger.info("Cleaning up expired events")


class EventBus:
    """Event bus for ad networks"""
    
    def __init__(self):
        self.dispatcher = EventDispatcher()
        self.store = EventStore()
        self.is_enabled = True
    
    def publish(self, event_type: EventType, data: Dict[str, Any],
                priority: EventPriority = EventPriority.MEDIUM,
                tenant_id: str = None, user_id: int = None,
                async_dispatch: bool = False) -> Event:
        """Publish event"""
        if not self.is_enabled:
            return None
        
        # Create event
        event = Event(
            event_type=event_type,
            data=data,
            priority=priority,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        # Store event
        self.store.store_event(event)
        
        # Dispatch event
        if async_dispatch:
            self.dispatcher.dispatch_async(event)
        else:
            self.dispatcher.dispatch(event)
        
        return event
    
    def subscribe(self, event_type: EventType, handler: Callable) -> EventListener:
        """Subscribe to event"""
        return self.dispatcher.register_listener(event_type, handler)
    
    def unsubscribe(self, listener: EventListener):
        """Unsubscribe from event"""
        self.dispatcher.unregister_listener(listener)
    
    def get_events(self, event_type: EventType = None,
                   tenant_id: str = None, user_id: int = None,
                   limit: int = 100) -> List[Event]:
        """Get events"""
        return self.dispatcher.get_history(event_type, tenant_id, user_id, limit)
    
    def enable(self):
        """Enable event bus"""
        self.is_enabled = True
        logger.info("Event bus enabled")
    
    def disable(self):
        """Disable event bus"""
        self.is_enabled = False
        logger.info("Event bus disabled")


# Global event bus instance
event_bus = EventBus()


# Event decorators
def event_handler(event_type: EventType, priority: EventPriority = EventPriority.MEDIUM):
    """Decorator for event handlers"""
    def decorator(func):
        def wrapper(event: Event):
            if event.event_type == event_type:
                return func(event)
            return None
        
        # Register handler
        event_bus.subscribe(event_type, wrapper)
        
        return wrapper
    return decorator


def async_event_handler(event_type: EventType, priority: EventPriority = EventPriority.MEDIUM):
    """Decorator for async event handlers"""
    def decorator(func):
        def wrapper(event: Event):
            if event.event_type == event_type:
                # Dispatch asynchronously
                from .tasks import handle_event_task
                handle_event_task.delay(event.to_dict(), func.__name__)
                return True
            return False
        
        # Register handler
        event_bus.subscribe(event_type, wrapper)
        
        return wrapper
    return decorator


# Event helper functions
def publish_offer_created(offer_id: int, tenant_id: str, user_id: int = None):
    """Publish offer created event"""
    return event_bus.publish(
        EventType.OFFER_CREATED,
        {'offer_id': offer_id},
        priority=EventPriority.MEDIUM,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_offer_clicked(offer_id: int, user_id: int, tenant_id: str,
                        ip_address: str = None, user_agent: str = None):
    """Publish offer clicked event"""
    data = {'offer_id': offer_id, 'user_id': user_id}
    
    if ip_address:
        data['ip_address'] = ip_address
    
    if user_agent:
        data['user_agent'] = user_agent
    
    return event_bus.publish(
        EventType.OFFER_CLICKED,
        data,
        priority=EventPriority.LOW,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_conversion_created(conversion_id: int, tenant_id: str, user_id: int = None):
    """Publish conversion created event"""
    return event_bus.publish(
        EventType.CONVERSION_CREATED,
        {'conversion_id': conversion_id},
        priority=EventPriority.HIGH,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_conversion_approved(conversion_id: int, tenant_id: str, user_id: int = None):
    """Publish conversion approved event"""
    return event_bus.publish(
        EventType.CONVERSION_APPROVED,
        {'conversion_id': conversion_id},
        priority=EventPriority.HIGH,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_reward_created(reward_id: int, tenant_id: str, user_id: int = None):
    """Publish reward created event"""
    return event_bus.publish(
        EventType.REWARD_CREATED,
        {'reward_id': reward_id},
        priority=EventPriority.HIGH,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_fraud_detected(conversion_id: int, fraud_score: float, 
                         tenant_id: str, user_id: int = None):
    """Publish fraud detected event"""
    return event_bus.publish(
        EventType.FRAUD_DETECTED,
        {
            'conversion_id': conversion_id,
            'fraud_score': fraud_score
        },
        priority=EventPriority.CRITICAL,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_network_health_check(network_id: int, is_healthy: bool,
                              response_time_ms: int, tenant_id: str):
    """Publish network health check event"""
    return event_bus.publish(
        EventType.NETWORK_HEALTH_CHECK,
        {
            'network_id': network_id,
            'is_healthy': is_healthy,
            'response_time_ms': response_time_ms
        },
        priority=EventPriority.MEDIUM,
        tenant_id=tenant_id
    )


def publish_user_login(user_id: int, tenant_id: str, ip_address: str = None):
    """Publish user login event"""
    data = {'user_id': user_id}
    
    if ip_address:
        data['ip_address'] = ip_address
    
    return event_bus.publish(
        EventType.USER_LOGIN,
        data,
        priority=EventPriority.LOW,
        tenant_id=tenant_id,
        user_id=user_id
    )


def publish_webhook_received(network_id: int, webhook_data: Dict[str, Any],
                           tenant_id: str):
    """Publish webhook received event"""
    return event_bus.publish(
        EventType.WEBHOOK_RECEIVED,
        {
            'network_id': network_id,
            'webhook_data': webhook_data
        },
        priority=EventPriority.HIGH,
        tenant_id=tenant_id
    )


# Event monitoring
class EventMonitor:
    """Event monitoring and analytics"""
    
    def __init__(self):
        self.event_counts = {}
        self.event_rates = {}
        self.alert_thresholds = {
            EventType.FRAUD_DETECTED: 10,  # Alert if >10 fraud events per hour
            EventType.CONVERSION_REJECTED: 50,  # Alert if >50 rejections per hour
            EventType.SECURITY_ALERT_TRIGGERED: 1  # Alert on any security alert
        }
    
    def track_event(self, event: Event):
        """Track event for monitoring"""
        event_type = event.event_type
        
        # Increment count
        if event_type not in self.event_counts:
            self.event_counts[event_type] = 0
        self.event_counts[event_type] += 1
        
        # Calculate rate (events per hour)
        self._calculate_event_rate(event_type)
        
        # Check alerts
        self._check_alerts(event)
    
    def _calculate_event_rate(self, event_type: EventType):
        """Calculate event rate per hour"""
        # This would be more sophisticated in production
        if event_type not in self.event_rates:
            self.event_rates[event_type] = 0
        
        self.event_rates[event_type] += 1
    
    def _check_alerts(self, event: Event):
        """Check if event should trigger alert"""
        if event.event_type in self.alert_thresholds:
            threshold = self.alert_thresholds[event.event_type]
            current_rate = self.event_rates.get(event.event_type, 0)
            
            if current_rate >= threshold:
                self._trigger_alert(event)
    
    def _trigger_alert(self, event: Event):
        """Trigger alert for event"""
        logger.warning(f"Alert triggered for event {event.event_type.value}")
        
        # Publish security alert
        event_bus.publish(
            EventType.SECURITY_ALERT_TRIGGERED,
            {
                'trigger_event': event.event_type.value,
                'event_id': event.id,
                'threshold_exceeded': True
            },
            priority=EventPriority.CRITICAL,
            tenant_id=event.tenant_id
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event monitoring stats"""
        return {
            'total_events': sum(self.event_counts.values()),
            'event_counts': {k.value: v for k, v in self.event_counts.items()},
            'event_rates': {k.value: v for k, v in self.event_rates.items()},
            'alert_thresholds': {k.value: v for k, v in self.alert_thresholds.items()}
        }


# Global event monitor
event_monitor = EventMonitor()

# Register event monitor as listener
@event_handler(EventType.FRAUD_DETECTED)
def track_fraud_event(event: Event):
    """Track fraud events"""
    event_monitor.track_event(event)

@event_handler(EventType.CONVERSION_REJECTED)
def track_rejection_event(event: Event):
    """Track rejection events"""
    event_monitor.track_event(event)

@event_handler(EventType.SECURITY_ALERT_TRIGGERED)
def track_security_event(event: Event):
    """Track security events"""
    event_monitor.track_event(event)


# Export all classes and functions
__all__ = [
    # Enums
    'EventType',
    'EventPriority',
    
    # Classes
    'Event',
    'EventListener',
    'EventDispatcher',
    'EventStore',
    'EventBus',
    'EventMonitor',
    
    # Global instances
    'event_bus',
    'event_monitor',
    
    # Decorators
    'event_handler',
    'async_event_handler',
    
    # Helper functions
    'publish_offer_created',
    'publish_offer_clicked',
    'publish_conversion_created',
    'publish_conversion_approved',
    'publish_reward_created',
    'publish_fraud_detected',
    'publish_network_health_check',
    'publish_user_login',
    'publish_webhook_received'
]
