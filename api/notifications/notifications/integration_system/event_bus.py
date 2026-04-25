# integration_system/event_bus.py
"""
Event Bus — Publish/Subscribe event system for cross-module communication.

All modules publish events here. Subscribers receive them asynchronously.
Replaces direct Django signal coupling between apps.

Usage:
    from .event_bus import event_bus

    # Subscribe (in apps.py ready())
    @event_bus.subscribe(Events.WITHDRAWAL_COMPLETED)
    def on_withdrawal(event):
        send_notification(event.user_id, ...)

    # Publish (in services/views)
    event_bus.publish(Events.WITHDRAWAL_COMPLETED, {
        'user_id': user.pk,
        'amount': 500,
        'transaction_id': 'TXN123',
    })
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from django.utils import timezone

from .integ_constants import Events, IntegPriority, Queues
from .integ_exceptions import EventBusPublishFailed, EventHandlerFailed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event Payload
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """Standard event payload published on the bus."""
    event_type: str
    data: Dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_module: str = ''
    user_id: Optional[int] = None
    priority: int = IntegPriority.MEDIUM
    published_at: datetime = field(default_factory=timezone.now)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'data': self.data,
            'source_module': self.source_module,
            'user_id': self.user_id,
            'priority': self.priority,
            'published_at': self.published_at.isoformat(),
            'metadata': self.metadata,
        }


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@dataclass
class Subscription:
    event_type: str
    handler: Callable
    subscriber_name: str = ''
    is_async: bool = True       # Run via Celery (True) or inline (False)
    priority: int = 5
    filter_fn: Optional[Callable] = None  # Optional filter function

    def matches(self, event: Event) -> bool:
        """Return True if this subscription should handle the event."""
        if self.filter_fn:
            try:
                return self.filter_fn(event)
            except Exception:
                return False
        return True


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    """
    Thread-safe, Celery-backed pub/sub event bus.

    Events can be dispatched:
      - Asynchronously via Celery (default) — non-blocking
      - Synchronously inline — blocking, for critical operations

    Wildcard subscriptions: subscribe to '*' to receive all events.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._subscriptions: Dict[str, List[Subscription]] = {}
                    cls._instance._published_count = 0
                    cls._instance._failed_count = 0
        return cls._instance

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type,
        handler: Optional[Callable] = None,
        subscriber_name: str = '',
        is_async: bool = True,
        priority: int = 5,
        filter_fn: Optional[Callable] = None,
    ):
        """
        Subscribe to an event type.

        Can be used as decorator:
            @event_bus.subscribe(Events.WITHDRAWAL_COMPLETED)
            def handler(event): ...

        Or called directly:
            event_bus.subscribe(Events.WITHDRAWAL_COMPLETED, my_handler)
        """
        event_key = event_type.value if isinstance(event_type, Events) else event_type

        def decorator(fn):
            sub = Subscription(
                event_type=event_key,
                handler=fn,
                subscriber_name=subscriber_name or fn.__name__,
                is_async=is_async,
                priority=priority,
                filter_fn=filter_fn,
            )
            with self._lock:
                self._subscriptions.setdefault(event_key, []).append(sub)
                # Keep sorted by priority (higher first)
                self._subscriptions[event_key].sort(key=lambda s: -s.priority)
            logger.debug(f'EventBus: "{sub.subscriber_name}" subscribed to "{event_key}"')
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    def unsubscribe(self, event_type, handler: Callable):
        """Remove a specific handler from subscriptions."""
        event_key = event_type.value if isinstance(event_type, Events) else event_type
        with self._lock:
            subs = self._subscriptions.get(event_key, [])
            self._subscriptions[event_key] = [s for s in subs if s.handler != handler]

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(
        self,
        event_type,
        data: Optional[Dict] = None,
        source_module: str = '',
        user_id: Optional[int] = None,
        priority: int = IntegPriority.MEDIUM,
        metadata: Optional[Dict] = None,
        async_dispatch: bool = True,
    ) -> str:
        """
        Publish an event to the bus.

        Args:
            event_type:      Event enum value or string key.
            data:            Event payload dict.
            source_module:   Publishing module name.
            user_id:         Affected user PK (optional).
            priority:        Dispatch priority (1-10).
            metadata:        Extra context.
            async_dispatch:  If True, dispatch via Celery. False = inline.

        Returns:
            event_id string.
        """
        event_key = event_type.value if isinstance(event_type, Events) else event_type

        event = Event(
            event_type=event_key,
            data=data or {},
            source_module=source_module,
            user_id=user_id,
            priority=priority,
            metadata=metadata or {},
        )

        self._published_count += 1

        if async_dispatch:
            self._dispatch_async(event)
        else:
            self._dispatch_sync(event)

        logger.debug(f'EventBus: published "{event_key}" (id={event.event_id})')
        return event.event_id

    def publish_many(self, events: List[Dict], async_dispatch: bool = True) -> List[str]:
        """Publish multiple events in one call."""
        return [self.publish(async_dispatch=async_dispatch, **ev) for ev in events]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch_sync(self, event: Event):
        """Call all handlers synchronously (blocking)."""
        handlers = self._get_handlers(event)
        for sub in handlers:
            if not sub.matches(event):
                continue
            try:
                sub.handler(event)
            except Exception as exc:
                self._failed_count += 1
                logger.error(
                    f'EventBus: handler "{sub.subscriber_name}" failed '
                    f'for "{event.event_type}": {exc}'
                )

    def _dispatch_async(self, event: Event):
        """Dispatch to Celery for async processing."""
        try:
            from .tasks import dispatch_event_task
            dispatch_event_task.apply_async(
                args=[event.to_dict()],
                queue=self._queue_for_priority(event.priority),
                priority=event.priority,
            )
        except Exception as exc:
            logger.warning(
                f'EventBus: Celery dispatch failed for "{event.event_type}", '
                f'falling back to sync: {exc}'
            )
            self._dispatch_sync(event)

    def execute_event(self, event_dict: Dict):
        """Execute handlers for an event dict (called by Celery task)."""
        event = Event(**{k: v for k, v in event_dict.items() if k != 'published_at'})
        # Re-parse published_at
        if 'published_at' in event_dict:
            try:
                from django.utils.dateparse import parse_datetime
                event.published_at = parse_datetime(event_dict['published_at']) or timezone.now()
            except Exception:
                pass
        self._dispatch_sync(event)

    def _get_handlers(self, event: Event) -> List[Subscription]:
        """Get all matching handlers (specific + wildcard)."""
        specific = self._subscriptions.get(event.event_type, [])
        wildcard = self._subscriptions.get('*', [])
        return specific + wildcard

    @staticmethod
    def _queue_for_priority(priority: int) -> str:
        if priority >= 9:
            return Queues.HIGH_PRIORITY
        if priority >= 5:
            return Queues.DEFAULT
        return Queues.MAINTENANCE

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict:
        return {
            'total_event_types': len(self._subscriptions),
            'total_subscriptions': sum(len(v) for v in self._subscriptions.values()),
            'published_count': self._published_count,
            'failed_count': self._failed_count,
            'subscriptions': {
                k: [s.subscriber_name for s in v]
                for k, v in self._subscriptions.items()
            },
        }

    def reset(self):
        """Clear all subscriptions. Use in tests only."""
        with self._lock:
            self._subscriptions.clear()
            self._published_count = 0
            self._failed_count = 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
event_bus = EventBus()


# ---------------------------------------------------------------------------
# Pre-wired subscriptions: notifications app listens to all earning events
# ---------------------------------------------------------------------------

def _wire_notification_subscriptions():
    """
    Wire all earning-site events to trigger notifications.
    Called once from apps.py ready().
    """

    @event_bus.subscribe(Events.WITHDRAWAL_COMPLETED, subscriber_name='notify_withdrawal_completed')
    def on_withdrawal_completed(event: Event):
        _trigger_notification(event, 'withdrawal_success',
            title=f'Withdrawal Successful 💰',
            message=f"৳{event.data.get('amount', 0)} has been sent to your account.",
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.WITHDRAWAL_REJECTED, subscriber_name='notify_withdrawal_rejected')
    def on_withdrawal_rejected(event: Event):
        _trigger_notification(event, 'withdrawal_rejected',
            title='Withdrawal Rejected ❌',
            message='Your withdrawal request was rejected. Contact support.',
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.TASK_APPROVED, subscriber_name='notify_task_approved')
    def on_task_approved(event: Event):
        reward = event.data.get('reward_amount', 0)
        _trigger_notification(event, 'task_approved',
            title=f'Task Approved! +৳{reward} 🎉',
            message=f"Your task submission was approved. ৳{reward} added to wallet.",
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.TASK_REJECTED, subscriber_name='notify_task_rejected')
    def on_task_rejected(event: Event):
        _trigger_notification(event, 'task_rejected',
            title='Task Rejected',
            message=f"Task rejected: {event.data.get('reason', 'Did not meet requirements.')}",
            priority='medium', channel='in_app')

    @event_bus.subscribe(Events.KYC_APPROVED, subscriber_name='notify_kyc_approved')
    def on_kyc_approved(event: Event):
        _trigger_notification(event, 'kyc_approved',
            title='KYC Verified ✅',
            message='Your identity is verified. Full access enabled.',
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.KYC_REJECTED, subscriber_name='notify_kyc_rejected')
    def on_kyc_rejected(event: Event):
        _trigger_notification(event, 'kyc_rejected',
            title='KYC Rejected ❌',
            message=f"KYC failed: {event.data.get('reason', 'Documents unclear.')}",
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.REFERRAL_REWARD_ISSUED, subscriber_name='notify_referral_reward')
    def on_referral_reward(event: Event):
        _trigger_notification(event, 'referral_reward',
            title=f'Referral Bonus +৳{event.data.get("bonus", 0)} 🎁',
            message=f"{event.data.get('friend_name', 'Your friend')} completed a task!",
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.USER_LEVEL_UP, subscriber_name='notify_level_up')
    def on_level_up(event: Event):
        level = event.data.get('new_level', '')
        _trigger_notification(event, 'level_up',
            title=f'🎉 Level Up! Level {level}',
            message=f'Congratulations! You reached Level {level}. New rewards unlocked!',
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.OFFER_COMPLETED, subscriber_name='notify_offer_completed')
    def on_offer_completed(event: Event):
        reward = event.data.get('reward', 0)
        _trigger_notification(event, 'offer_completed',
            title=f'Offer Completed! +৳{reward} 🎯',
            message=f"You completed '{event.data.get('offer_name', 'an offer')}'. ৳{reward} credited.",
            priority='high', channel='in_app')

    @event_bus.subscribe(Events.FRAUD_DETECTED, subscriber_name='notify_fraud_admin')
    def on_fraud_detected(event: Event):
        _trigger_admin_notification(event, 'fraud_detected',
            title=f'🚨 Fraud Alert',
            message=f"Fraud detected for user #{event.user_id}. Immediate review required.")

    @event_bus.subscribe(Events.COMMISSION_EARNED, subscriber_name='notify_commission')
    def on_commission_earned(event: Event):
        _trigger_notification(event, 'affiliate_commission',
            title=f'Commission Earned! +${event.data.get("amount", 0)}',
            message=f"Conversion recorded for offer '{event.data.get('offer_name', '')}'.",
            priority='medium', channel='in_app')

    logger.info('EventBus: notification subscriptions wired successfully.')


def _trigger_notification(event: Event, notif_type: str, title: str,
                           message: str, priority: str = 'medium', channel: str = 'in_app'):
    """Helper to trigger a notification from an event."""
    if not event.user_id:
        return
    try:
        from .integ_adapter import NotificationIntegrationAdapter
        adapter = NotificationIntegrationAdapter()
        adapter.send({
            'user_id': event.user_id,
            'notification_type': notif_type,
            'title': title,
            'message': message,
            'priority': priority,
            'channel': channel,
            'metadata': event.data,
        })
    except Exception as exc:
        logger.warning(f'_trigger_notification {notif_type}: {exc}')


def _trigger_admin_notification(event: Event, notif_type: str, title: str, message: str):
    """Trigger a notification to all admin users."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        from .integ_adapter import NotificationIntegrationAdapter
        adapter = NotificationIntegrationAdapter()
        for admin in User.objects.filter(is_staff=True, is_active=True)[:5]:
            adapter.send({
                'user_id': admin.pk,
                'notification_type': notif_type,
                'title': title,
                'message': message,
                'priority': 'urgent',
                'channel': 'in_app',
                'metadata': event.data,
            })
    except Exception as exc:
        logger.warning(f'_trigger_admin_notification: {exc}')
