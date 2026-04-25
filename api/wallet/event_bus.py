# api/wallet/event_bus.py
"""
Wallet Event Bus — internal publish/subscribe using Redis pub/sub.

Architecture:
  Producer → event_bus.publish(event) → Redis channel → Consumer handlers

Features:
  - Synchronous in-process handlers (for signals/Django)
  - Async Redis pub/sub for cross-service events
  - Dead letter queue for failed events
  - Event replay for debugging

Usage:
    from .event_bus import event_bus
    from .events import WalletCredited

    # Subscribe
    @event_bus.subscribe(WalletCredited)
    def on_credited(event: WalletCredited):
        send_push_notification(event.user_id, f"+{event.amount} BDT credited")

    # Publish
    event_bus.publish(WalletCredited(wallet_id=1, amount=500, txn_id="..."))
"""
import json
import logging
import dataclasses
from decimal import Decimal
from datetime import datetime
from typing import Callable, Dict, List, Type, Any
from django.utils import timezone

logger = logging.getLogger("wallet.event_bus")


def _serialize_event(event) -> str:
    """Serialize dataclass event to JSON string."""
    def default(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, list):
            return obj
        return str(obj)
    d = dataclasses.asdict(event) if dataclasses.is_dataclass(event) else vars(event)
    d["__event_type__"] = type(event).__name__
    return json.dumps(d, default=default)


class WalletEventBus:
    """
    In-process + Redis pub/sub event bus.
    Handlers registered with @event_bus.subscribe() are called synchronously.
    Redis channel publishing is async (non-blocking).
    """

    REDIS_CHANNEL = "wallet:events"

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._redis = None

    def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            try:
                from django.core.cache import cache
                if hasattr(cache, "client"):
                    self._redis = cache.client.get_client()
            except Exception:
                self._redis = None
        return self._redis

    def subscribe(self, event_class: Type) -> Callable:
        """Decorator to subscribe a handler to an event type."""
        def decorator(func: Callable) -> Callable:
            key = event_class.__name__
            self._handlers.setdefault(key, []).append(func)
            logger.debug(f"EventBus: subscribed {func.__name__} to {key}")
            return func
        return decorator

    def publish(self, event) -> None:
        """
        Publish an event.
        1. Call all synchronous in-process handlers.
        2. Publish to Redis pub/sub for cross-service consumers.
        """
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])

        # In-process handlers (synchronous)
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"EventBus handler error: {handler.__name__} on {event_type}: {e}", exc_info=True)
                self._dead_letter(event, handler.__name__, str(e))

        # Redis pub/sub (non-blocking, best-effort)
        try:
            redis = self._get_redis()
            if redis:
                payload = _serialize_event(event)
                redis.publish(self.REDIS_CHANNEL, payload)
        except Exception as e:
            logger.debug(f"EventBus Redis publish skip: {e}")

        logger.debug(f"EventBus: published {event_type} to {len(handlers)} handlers")

    def publish_async(self, event) -> None:
        """Publish event via Celery task (guaranteed delivery, retryable)."""
        try:
            from .tasks.notification_tasks import dispatch_event_async
            dispatch_event_async.delay(_serialize_event(event))
        except Exception as e:
            logger.warning(f"EventBus async publish failed, falling back to sync: {e}")
            self.publish(event)

    def _dead_letter(self, event, handler_name: str, error: str) -> None:
        """Store failed events for investigation."""
        try:
            from django.core.cache import cache
            key = f"wallet_event_dlq_{timezone.now().timestamp()}"
            cache.set(key, {
                "event": _serialize_event(event),
                "handler": handler_name,
                "error": error,
                "timestamp": timezone.now().isoformat(),
            }, timeout=86400 * 7)  # 7 days
        except Exception:
            pass

    def get_handlers(self, event_type: str) -> List[str]:
        """Return list of handler names for an event type (for debugging)."""
        return [h.__name__ for h in self._handlers.get(event_type, [])]

    def clear_handlers(self, event_type: str = None) -> None:
        """Clear handlers (for testing)."""
        if event_type:
            self._handlers.pop(event_type, None)
        else:
            self._handlers.clear()


# ── Singleton instance ────────────────────────────────────
event_bus = WalletEventBus()
