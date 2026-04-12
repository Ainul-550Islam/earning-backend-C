"""
Message Delivery Manager — ACK-based guaranteed delivery system.
Like WhatsApp's "two ticks" system.

Flow:
  1. Message sent → status=SENT (one tick)
  2. Server delivers to recipient WS → status=DELIVERED (two ticks, grey)
  3. Recipient opens chat → status=READ (two ticks, blue)

Offline queue: messages stored in Redis pending delivery.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis key patterns
OFFLINE_QUEUE_KEY = "msg:offline:{user_id}"
DELIVERY_ACK_KEY  = "msg:ack:{message_id}"
UNREAD_COUNT_KEY  = "msg:unread:{user_id}:{chat_id}"


def queue_message_for_offline_user(user_id: Any, message_data: dict, ttl_seconds: int = 604_800) -> bool:
    """
    Push message to Redis offline queue for a user who is not connected.
    Messages are retained for 7 days (WhatsApp-compatible).
    """
    try:
        from django.core.cache import cache
        import json as _json
        key = OFFLINE_QUEUE_KEY.format(user_id=user_id)
        # Use Redis LPUSH via cache.client if available, else fallback
        existing = cache.get(key) or []
        existing.append(message_data)
        # Keep max 1000 pending messages per user
        if len(existing) > 1000:
            existing = existing[-1000:]
        cache.set(key, existing, ttl_seconds)
        return True
    except Exception as exc:
        logger.error("queue_message_for_offline_user: user=%s error=%s", user_id, exc)
        return False


def flush_offline_queue(user_id: Any) -> list:
    """
    Get and clear all pending messages for a user when they come online.
    Called in ChatConsumer.connect().
    """
    try:
        from django.core.cache import cache
        key = OFFLINE_QUEUE_KEY.format(user_id=user_id)
        messages = cache.get(key) or []
        if messages:
            cache.delete(key)
            logger.info("flush_offline_queue: user=%s delivered %d queued msgs", user_id, len(messages))
        return messages
    except Exception as exc:
        logger.error("flush_offline_queue: user=%s error=%s", user_id, exc)
        return []


def mark_delivered(message_id: Any, user_id: Any) -> bool:
    """
    Record that message was delivered to user's device.
    Updates both DB and Redis for fast reads.
    """
    try:
        from django.core.cache import cache
        from django.utils import timezone
        import json as _json
        now = timezone.now().isoformat()
        # Update Redis ACK cache
        key = DELIVERY_ACK_KEY.format(message_id=message_id)
        acks = cache.get(key) or {}
        acks[str(user_id)] = {"delivered_at": now}
        cache.set(key, acks, 86_400)

        # Update DB asynchronously
        from .tasks import update_delivery_status_task
        update_delivery_status_task.delay(str(message_id), str(user_id), "DELIVERED", now)
        return True
    except Exception as exc:
        logger.error("mark_delivered: msg=%s user=%s error=%s", message_id, user_id, exc)
        return False


def mark_read(message_id: Any, user_id: Any) -> bool:
    """Record that user has read the message."""
    try:
        from django.core.cache import cache
        from django.utils import timezone
        now = timezone.now().isoformat()
        key = DELIVERY_ACK_KEY.format(message_id=message_id)
        acks = cache.get(key) or {}
        existing = acks.get(str(user_id), {})
        existing["read_at"] = now
        acks[str(user_id)] = existing
        cache.set(key, acks, 86_400)
        from .tasks import update_delivery_status_task
        update_delivery_status_task.delay(str(message_id), str(user_id), "READ", now)
        # Clear unread count cache
        clear_unread_cache(user_id)
        return True
    except Exception as exc:
        logger.error("mark_read: msg=%s user=%s error=%s", message_id, user_id, exc)
        return False


def get_delivery_status(message_id: Any) -> dict:
    """Return {user_id: {delivered_at, read_at}} from Redis cache."""
    try:
        from django.core.cache import cache
        key = DELIVERY_ACK_KEY.format(message_id=message_id)
        return cache.get(key) or {}
    except Exception:
        return {}


def increment_unread(user_id: Any, chat_id: Any, count: int = 1) -> int:
    """Increment unread message count for user in a chat."""
    try:
        from django.core.cache import cache
        key = UNREAD_COUNT_KEY.format(user_id=user_id, chat_id=chat_id)
        current = cache.get(key) or 0
        new_count = current + count
        cache.set(key, new_count, 86_400)
        return new_count
    except Exception:
        return 0


def get_unread_for_chat(user_id: Any, chat_id: Any) -> int:
    """Get unread count for a specific chat."""
    try:
        from django.core.cache import cache
        key = UNREAD_COUNT_KEY.format(user_id=user_id, chat_id=chat_id)
        return cache.get(key) or 0
    except Exception:
        return 0


def clear_unread_cache(user_id: Any, chat_id: Any = None) -> None:
    """Clear unread count cache for user."""
    try:
        from django.core.cache import cache
        if chat_id:
            cache.delete(UNREAD_COUNT_KEY.format(user_id=user_id, chat_id=chat_id))
        # Also clear total unread
        cache.delete(f"msg:total_unread:{user_id}")
    except Exception:
        pass


def get_total_unread(user_id: Any) -> int:
    """Get total unread count across all chats (cached)."""
    try:
        from django.core.cache import cache
        key = f"msg:total_unread:{user_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        # Recompute from DB
        from ..models import UserInbox
        count = UserInbox.objects.filter(
            user_id=user_id, is_read=False, is_archived=False
        ).count()
        cache.set(key, count, 300)
        return count
    except Exception:
        return 0
