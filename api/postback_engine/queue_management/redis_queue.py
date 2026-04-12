"""
queue_management/redis_queue.py
────────────────────────────────
Redis-backed priority queue for high-throughput postback processing.
Used when DB queue is too slow for burst traffic.
Implements FIFO per priority level using Redis sorted sets (ZADD/ZPOPMIN).
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

_KEY_QUEUE   = "pe:queue:{priority}"
_KEY_COUNTER = "pe:queue:counter"
_PRIORITIES  = [1, 2, 3, 4, 5]  # 1=critical, 5=background


class RedisQueue:
    """
    Sorted-set based priority queue.
    Score = timestamp + priority_offset for ordering.
    """

    def enqueue(self, data: dict, priority: int = 3) -> str:
        """Add an item to the queue. Returns item_id."""
        import uuid
        item_id = str(uuid.uuid4())
        data["_item_id"] = item_id
        data["_enqueued_at"] = time.time()
        key = _KEY_QUEUE.format(priority=priority)
        score = time.time() + (priority * 0.001)  # tie-break by priority
        try:
            client = self._get_client()
            if client:
                client.zadd(key, {json.dumps(data): score})
        except Exception as exc:
            logger.warning("RedisQueue.enqueue failed: %s", exc)
        return item_id

    def dequeue(self, timeout: float = 0.1) -> Optional[dict]:
        """Pop the highest-priority item from any queue. Returns None if empty."""
        try:
            client = self._get_client()
            if not client:
                return None
            for priority in _PRIORITIES:
                key = _KEY_QUEUE.format(priority=priority)
                result = client.zpopmin(key, count=1)
                if result:
                    raw, score = result[0]
                    return json.loads(raw)
        except Exception as exc:
            logger.warning("RedisQueue.dequeue failed: %s", exc)
        return None

    def dequeue_batch(self, batch_size: int = 50) -> List[dict]:
        """Dequeue up to batch_size items across all priority levels."""
        items = []
        try:
            client = self._get_client()
            if not client:
                return items
            remaining = batch_size
            for priority in _PRIORITIES:
                if remaining <= 0:
                    break
                key = _KEY_QUEUE.format(priority=priority)
                results = client.zpopmin(key, count=remaining)
                for raw, _ in results:
                    try:
                        items.append(json.loads(raw))
                        remaining -= 1
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("RedisQueue.dequeue_batch failed: %s", exc)
        return items

    def depth(self, priority: int = None) -> int:
        """Return total items in queue (or in specific priority level)."""
        try:
            client = self._get_client()
            if not client:
                return 0
            if priority is not None:
                return int(client.zcard(_KEY_QUEUE.format(priority=priority)))
            return sum(
                int(client.zcard(_KEY_QUEUE.format(priority=p)))
                for p in _PRIORITIES
            )
        except Exception:
            return 0

    def flush(self) -> int:
        """Clear all queues. Returns count of flushed items."""
        total = 0
        try:
            client = self._get_client()
            if not client:
                return 0
            for priority in _PRIORITIES:
                key = _KEY_QUEUE.format(priority=priority)
                total += int(client.zcard(key))
                client.delete(key)
        except Exception as exc:
            logger.warning("RedisQueue.flush failed: %s", exc)
        return total

    @staticmethod
    def _get_client():
        try:
            return cache.client.get_client()
        except Exception:
            return None


redis_queue = RedisQueue()
