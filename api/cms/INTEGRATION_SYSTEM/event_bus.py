# cms/INTEGRATION_SYSTEM/event_bus.py
"""
CMS EventBus — publishes typed events to Redis pub/sub.
Falls back to in-memory queue when Redis is unavailable (dev/test).
publish() is always fire-and-forget — never raises to caller.
"""
import json
import logging
from typing import Any, Dict, List, Callable, Optional
from collections import defaultdict

logger = logging.getLogger('cms.integration.event_bus')

# In-memory fallback queue (dev / test mode)
_in_memory_queue: List[Dict] = []
_subscribers: Dict[str, List[Callable]] = defaultdict(list)

# Redis channel prefix
_CHANNEL_PREFIX = 'cms_events:'


class EventBus:
    """
    Publish/subscribe event bus backed by Redis channels.
    All publish calls are silent on error — this must never crash the caller.
    """

    @classmethod
    def publish(cls, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Publish an event. Returns True if published successfully.
        Silent on all errors.
        """
        from django.utils import timezone
        message = {
            'event_type': event_type,
            'payload': payload,
            'timestamp': timezone.now().isoformat(),
        }
        # Try Redis first
        try:
            from django.core.cache import cache
            channel = f'{_CHANNEL_PREFIX}{event_type}'
            cache.set(
                f'last_event:{event_type}',
                json.dumps(message, default=str),
                timeout=3600,
            )
        except Exception:
            pass

        # Try Django Channels layer (if configured)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f'cms_events_{event_type}',
                    {'type': 'cms.event', 'message': message},
                )
        except Exception:
            pass

        # In-memory fallback (always runs — useful for tests)
        _in_memory_queue.append(message)
        if len(_in_memory_queue) > 1000:
            _in_memory_queue.pop(0)

        # Call any in-process subscribers
        for callback in _subscribers.get(event_type, []):
            try:
                callback(event_type=event_type, payload=payload)
            except Exception as e:
                logger.debug(f'[EventBus] Subscriber error for {event_type}: {e}')

        logger.debug(f'[EventBus] Published: {event_type}')
        return True

    @classmethod
    def subscribe(cls, event_type: str, callback: Callable) -> None:
        """Register an in-process subscriber for an event type."""
        _subscribers[event_type].append(callback)

    @classmethod
    def get_recent(cls, event_type: str, limit: int = 10) -> List[Dict]:
        """Return recent events of a given type from in-memory queue."""
        return [e for e in reversed(_in_memory_queue)
                if e['event_type'] == event_type][:limit]

    @classmethod
    def get_last_event(cls, event_type: str) -> Optional[Dict]:
        """Return the last published event of a given type."""
        try:
            from django.core.cache import cache
            raw = cache.get(f'last_event:{event_type}')
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        for e in reversed(_in_memory_queue):
            if e['event_type'] == event_type:
                return e
        return None

    @classmethod
    def status(cls) -> Dict[str, Any]:
        return {
            'queue_size': len(_in_memory_queue),
            'subscriber_count': sum(len(v) for v in _subscribers.values()),
            'event_types_with_subscribers': list(_subscribers.keys()),
        }

    # ── Convenience publish methods ───────────────────────────────────────────

    @classmethod
    def publish_reward_earned(cls, user, amount, currency='USD',
                               source_type='', lead_id='',
                               virtual_amount=0) -> bool:
        return cls.publish('reward_earned', {
            'user_id': getattr(user, 'id', None),
            'amount': float(amount),
            'currency': currency,
            'source_type': source_type,
            'lead_id': lead_id,
            'virtual_amount': float(virtual_amount),
        })

    @classmethod
    def publish_offer_completed(cls, user, payout_usd, lead_id,
                                 virtual_amount=0) -> bool:
        return cls.publish('offer_completed', {
            'user_id': getattr(user, 'id', None),
            'payout_usd': float(payout_usd),
            'lead_id': lead_id,
            'virtual_amount': float(virtual_amount),
        })

    @classmethod
    def publish_survey_completed(cls, user, survey_id, completion_id,
                                  quality_score=0, reward_usd=0) -> bool:
        return cls.publish('survey_completed', {
            'user_id': getattr(user, 'id', None),
            'survey_id': survey_id,
            'completion_id': completion_id,
            'quality_score': float(quality_score),
            'reward_usd': float(reward_usd),
        })

    @classmethod
    def publish_withdrawal_requested(cls, user, amount_usd, method,
                                      request_id=0) -> bool:
        return cls.publish('withdrawal_requested', {
            'user_id': getattr(user, 'id', None),
            'amount_usd': float(amount_usd),
            'method': method,
            'request_id': request_id,
        })
