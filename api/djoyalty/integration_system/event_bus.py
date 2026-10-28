# api/djoyalty/integration_system/event_bus.py
"""
Event Bus -- Internal pub/sub event system।
Decouples loyalty business logic from integrations।
All loyalty events flow through here।

Pattern: Observer + Event Bus (in-process)।
Production: Backed by Redis pub/sub or Celery for async।
"""
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from .integ_constants import EventType, MessagePriority

logger = logging.getLogger(__name__)

_bus_lock = threading.Lock()


class LoyaltyEvent:
    """
    A loyalty domain event।
    Carries customer + event data + metadata।
    """
    def __init__(self, event_type: str, customer=None, data: dict = None,
                  tenant=None, source: str = 'system', priority: MessagePriority = MessagePriority.NORMAL):
        self.event_type = event_type
        self.customer = customer
        self.data = data or {}
        self.tenant = tenant
        self.source = source
        self.priority = priority

    def __repr__(self):
        cust = getattr(self.customer, 'code', str(self.customer)) if self.customer else 'system'
        return f'LoyaltyEvent({self.event_type}: {cust})'


class EventSubscription:
    """A subscription to a specific event type।"""

    def __init__(self, event_type: str, handler: Callable,
                  name: str = '', is_async: bool = False):
        self.event_type = event_type
        self.handler = handler
        self.name = name or handler.__name__
        self.is_async = is_async
        self.call_count = 0
        self.error_count = 0

    def execute(self, event: LoyaltyEvent):
        """Execute the handler।"""
        self.call_count += 1
        try:
            if self.is_async:
                # Send to Celery task if available
                try:
                    from ..tasks.notification_tasks import dispatch_event_async
                    dispatch_event_async.delay(
                        event.event_type,
                        customer_id=event.customer.id if event.customer else None,
                        data=event.data,
                    )
                except ImportError:
                    self.handler(event)
            else:
                self.handler(event)
        except Exception as e:
            self.error_count += 1
            logger.error('EventBus handler [%s] error for %s: %s',
                         self.name, event.event_type, e)


class EventBus:
    """
    In-process event bus for loyalty events।
    Singleton -- app-wide event routing।

    Usage:
        # Subscribe
        @EventBus.subscribe(EventType.POINTS_EARNED)
        def on_points_earned(event):
            send_push_notification(event.customer, event.data['points'])

        # Publish
        EventBus.publish(
            EventType.POINTS_EARNED,
            customer=customer,
            data={'points': '100', 'balance': '500'},
        )
    """

    _subscriptions: Dict[str, List[EventSubscription]] = {}
    _global_handlers: List[EventSubscription] = []
    _instance = None

    @classmethod
    def subscribe(cls, event_type: str, name: str = '', is_async: bool = False):
        """Decorator for subscribing to events।"""
        def decorator(func: Callable) -> Callable:
            cls._add_subscription(event_type, func, name=name, is_async=is_async)
            return func
        return decorator

    @classmethod
    def subscribe_all(cls, name: str = '', is_async: bool = False):
        """Subscribe to ALL events (global handler)।"""
        def decorator(func: Callable) -> Callable:
            sub = EventSubscription('*', func, name=name or func.__name__, is_async=is_async)
            with _bus_lock:
                cls._global_handlers.append(sub)
            return func
        return decorator

    @classmethod
    def _add_subscription(cls, event_type: str, handler: Callable,
                            name: str = '', is_async: bool = False):
        sub = EventSubscription(event_type, handler, name=name, is_async=is_async)
        with _bus_lock:
            if event_type not in cls._subscriptions:
                cls._subscriptions[event_type] = []
            cls._subscriptions[event_type].append(sub)
        logger.debug('EventBus: subscribed %s to %s', sub.name, event_type)

    @classmethod
    def publish(cls, event_type: str, customer=None, data: dict = None,
                 tenant=None, source: str = 'system',
                 priority: MessagePriority = MessagePriority.NORMAL):
        """
        Publish a loyalty event।
        Synchronous by default; async handlers use Celery।
        """
        event = LoyaltyEvent(
            event_type=event_type,
            customer=customer,
            data=data or {},
            tenant=tenant or (customer.tenant if customer else None),
            source=source,
            priority=priority,
        )

        logger.debug('EventBus.publish: %s', event)

        # Call specific handlers
        handlers = cls._subscriptions.get(event_type, [])
        for sub in handlers:
            sub.execute(event)

        # Call global handlers
        for sub in cls._global_handlers:
            sub.execute(event)

        # Fire integration handler
        cls._fire_integration_handler(event)

    @classmethod
    def _fire_integration_handler(cls, event: LoyaltyEvent):
        """Route event to IntegrationHandler for external notifications।"""
        try:
            from .integ_handler import IntegrationHandler
            handler = IntegrationHandler()
            handler.dispatch_loyalty_event(event.event_type, event.customer, event.data)
        except Exception as e:
            logger.debug('EventBus._fire_integration_handler error: %s', e)

    @classmethod
    def get_stats(cls) -> dict:
        """Event bus statistics।"""
        total_subs = sum(len(subs) for subs in cls._subscriptions.values())
        total_calls = sum(
            sub.call_count
            for subs in cls._subscriptions.values()
            for sub in subs
        )
        total_errors = sum(
            sub.error_count
            for subs in cls._subscriptions.values()
            for sub in subs
        )
        return {
            'subscriptions': {
                event: len(subs)
                for event, subs in cls._subscriptions.items()
            },
            'total_subscriptions': total_subs,
            'global_handlers': len(cls._global_handlers),
            'total_calls': total_calls,
            'total_errors': total_errors,
            'error_rate': f'{(total_errors / total_calls * 100):.1f}%' if total_calls else '0%',
        }

    @classmethod
    def clear(cls):
        """Clear all subscriptions (for testing)।"""
        with _bus_lock:
            cls._subscriptions.clear()
            cls._global_handlers.clear()


# ─── Built-in Global Handler ─────────────────────────────────────────────────

@EventBus.subscribe_all(name='webhook_dispatcher', is_async=True)
def _dispatch_webhooks(event: LoyaltyEvent):
    """
    Automatically dispatch all events as outbound webhooks।
    Async -- doesn't block main request।
    """
    if not event.customer:
        return
    try:
        from ..webhooks.webhook_dispatcher import WebhookDispatcher
        WebhookDispatcher.dispatch(
            event_type=event.event_type,
            customer=event.customer,
            data=event.data,
        )
    except Exception as e:
        logger.debug('_dispatch_webhooks error for %s: %s', event.event_type, e)
