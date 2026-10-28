# api/admin_panel/INTEGRATION_SYSTEM/message_queue.py
"""
MessageQueue — High Traffic Manager for admin_panel.
Queues admin commands during peak load, batch processes them,
prevents thundering herd, rate-limits heavy operations.

New — handles: bulk user bans, mass broadcast, bulk payout processing.
"""
import json
import logging
import time
import threading
from collections import deque
from typing import Any, Callable, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import QUEUE_NAMES, RETRY_CONFIG

logger = logging.getLogger(__name__)


class QueueMessage:
    """A single message in the queue."""

    def __init__(self, action: str, payload: dict, priority: int = 5,
                 max_retries: int = 3, correlation_id: str = ''):
        import uuid
        self.message_id = str(uuid.uuid4())
        self.action = action
        self.payload = payload
        self.priority = priority  # 1=highest, 10=lowest
        self.max_retries = max_retries
        self.retry_count = 0
        self.correlation_id = correlation_id or self.message_id
        self.enqueued_at = timezone.now()
        self.status = 'pending'
        self.error = None

    def to_dict(self) -> Dict:
        return {
            'message_id': self.message_id,
            'action': self.action,
            'payload': self.payload,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'status': self.status,
            'error': self.error,
            'enqueued_at': self.enqueued_at.isoformat(),
        }


class MessageQueue:
    """
    In-process priority queue with overflow to Redis/Celery.
    Supports: bulk operations, rate limiting, dead letter queue.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._queues: Dict[str, deque] = {
            'high': deque(maxlen=10000),
            'standard': deque(maxlen=50000),
            'bulk': deque(maxlen=100000),
        }
        self._handlers: Dict[str, Callable] = {}
        self._dead_letter: deque = deque(maxlen=1000)
        self._processed = 0
        self._failed = 0
        self._rate_limits: Dict[str, float] = {}  # action -> last_fired_timestamp

    # ==================== ENQUEUE ====================

    def enqueue(self, action: str, payload: dict, priority: int = 5,
                queue_name: str = 'standard', max_retries: int = 3) -> str:
        """Add a message to the queue. Returns message_id."""
        msg = QueueMessage(action=action, payload=payload, priority=priority, max_retries=max_retries)
        q = self._queues.get(queue_name, self._queues['standard'])
        q.appendleft(msg)  # Priority: left = highest priority
        logger.debug(f"[MessageQueue] Enqueued: {action} queue={queue_name} id={msg.message_id}")
        return msg.message_id

    def enqueue_bulk(self, action: str, items: List[dict], chunk_size: int = 100) -> List[str]:
        """Enqueue a bulk operation in chunks."""
        ids = []
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            msg_id = self.enqueue(
                action=f'{action}_bulk',
                payload={'items': chunk, 'chunk_index': i // chunk_size},
                queue_name='bulk',
                priority=8,
            )
            ids.append(msg_id)
        logger.info(f"[MessageQueue] Bulk enqueued: {action} total={len(items)} chunks={len(ids)}")
        return ids

    # ==================== PROCESS ====================

    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a handler function for an action."""
        self._handlers[action] = handler
        logger.debug(f"[MessageQueue] Handler registered: {action}")

    def process_next(self, queue_name: str = 'standard') -> Optional[Dict]:
        """Process the next message from a queue."""
        q = self._queues.get(queue_name)
        if not q:
            return None
        try:
            msg = q.pop()
        except IndexError:
            return None

        handler = self._handlers.get(msg.action)
        if not handler:
            logger.warning(f"[MessageQueue] No handler for action: {msg.action}")
            self._dead_letter.append(msg)
            return None

        try:
            result = handler(payload=msg.payload)
            msg.status = 'processed'
            self._processed += 1
            return {'success': True, 'message_id': msg.message_id, 'result': result}
        except Exception as e:
            msg.retry_count += 1
            msg.error = str(e)
            if msg.retry_count <= msg.max_retries:
                msg.status = 'retry'
                q.appendleft(msg)  # Re-queue for retry
                logger.warning(f"[MessageQueue] Retry {msg.retry_count}/{msg.max_retries}: {msg.action}: {e}")
            else:
                msg.status = 'failed'
                self._dead_letter.append(msg)
                self._failed += 1
                logger.error(f"[MessageQueue] Dead letter: {msg.action} after {msg.max_retries} retries: {e}")
            return {'success': False, 'message_id': msg.message_id, 'error': str(e)}

    def process_all(self, queue_name: str = 'standard', max_messages: int = 100) -> Dict:
        """Process up to max_messages messages from a queue."""
        results = []
        for _ in range(max_messages):
            q = self._queues.get(queue_name)
            if not q:
                break
            result = self.process_next(queue_name)
            if result is None:
                break
            results.append(result)
        success = sum(1 for r in results if r.get('success'))
        return {'processed': len(results), 'success': success, 'failed': len(results) - success}

    # ==================== RATE LIMITING ====================

    def is_rate_limited(self, action: str, min_interval_seconds: float = 1.0) -> bool:
        """Check if an action is being rate limited."""
        now = time.monotonic()
        last = self._rate_limits.get(action, 0)
        if now - last < min_interval_seconds:
            return True
        self._rate_limits[action] = now
        return False

    # ==================== MONITORING ====================

    def queue_sizes(self) -> Dict[str, int]:
        return {name: len(q) for name, q in self._queues.items()}

    def dead_letter_count(self) -> int:
        return len(self._dead_letter)

    def get_dead_letters(self, limit: int = 50) -> List[Dict]:
        return [msg.to_dict() for msg in list(self._dead_letter)[:limit]]

    def retry_dead_letters(self, action_filter: Optional[str] = None) -> int:
        """Re-queue dead letter messages."""
        retried = 0
        to_retry = [
            msg for msg in self._dead_letter
            if (action_filter is None or msg.action == action_filter)
        ]
        for msg in to_retry:
            msg.retry_count = 0
            msg.status = 'pending'
            self._queues['standard'].appendleft(msg)
            self._dead_letter.remove(msg)
            retried += 1
        return retried

    def get_stats(self) -> Dict:
        return {
            'queue_sizes': self.queue_sizes(),
            'processed': self._processed,
            'failed': self._failed,
            'dead_letter': self.dead_letter_count(),
            'registered_handlers': list(self._handlers.keys()),
        }

    def __repr__(self) -> str:
        return f"<MessageQueue processed={self._processed} failed={self._failed} sizes={self.queue_sizes()}>"


# Global singleton
message_queue = MessageQueue()


# ==================== DEFAULT HANDLERS ====================

def _handle_bulk_ban(payload: dict):
    """Handle bulk user ban operation."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_ids = payload.get('items', [])
    count = User.objects.filter(pk__in=user_ids, is_active=True).update(is_active=False)
    return {'banned': count}

def _handle_bulk_wallet_adjust(payload: dict):
    """Handle bulk wallet adjustments."""
    from api.wallet.models import Wallet
    items = payload.get('items', [])
    processed = 0
    for item in items:
        try:
            Wallet.objects.filter(user_id=item['user_id']).update(
                balance=__import__('django.db.models', fromlist=['F']).F('balance') + item['amount']
            )
            processed += 1
        except Exception:
            pass
    return {'processed': processed}


message_queue.register_handler('ban_user_bulk', _handle_bulk_ban)
message_queue.register_handler('adjust_wallet_bulk', _handle_bulk_wallet_adjust)