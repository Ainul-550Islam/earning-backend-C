# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/message_queue.py
# =============================================================================
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger('fraud_detection.message_queue')


@dataclass
class Message:
    queue   : str
    payload : Dict[str, Any]
    msg_id  : str = ''
    created : float = field(default_factory=time.time)
    retries : int = 0

    def __post_init__(self):
        if not self.msg_id:
            import uuid
            self.msg_id = str(uuid.uuid4())


class MessageQueueManager:
    """In-process FIFO queue manager with optional Celery delegation."""

    def __init__(self):
        self._lock    = threading.Lock()
        self._queues  : Dict[str, deque] = defaultdict(deque)
        self._handlers: Dict[str, Callable] = {}
        self._stats   : Dict[str, Dict] = defaultdict(lambda: {'published': 0, 'consumed': 0, 'failed': 0})

    def publish(self, queue: str, payload: Dict[str, Any]) -> str:
        """Enqueue a message; returns its msg_id."""
        msg = Message(queue=queue, payload=payload)
        with self._lock:
            self._queues[queue].append(msg)
            self._stats[queue]['published'] += 1
        logger.debug('MQ publish → %s: %s', queue, msg.msg_id)
        self._try_delegate_celery(queue, payload)
        return msg.msg_id

    def consume(self, queue: str) -> Optional[Message]:
        with self._lock:
            q = self._queues.get(queue)
            if q:
                msg = q.popleft()
                self._stats[queue]['consumed'] += 1
                return msg
        return None

    def register_handler(self, queue: str, handler: Callable[[Dict], None]) -> None:
        self._handlers[queue] = handler

    def process_one(self, queue: str) -> bool:
        msg = self.consume(queue)
        if not msg:
            return False
        handler = self._handlers.get(queue)
        if handler:
            try:
                handler(msg.payload)
            except Exception as exc:
                logger.error('MQ handler error on %s: %s', queue, exc)
                with self._lock:
                    self._stats[queue]['failed'] += 1
        return True

    def queue_size(self, queue: str) -> int:
        return len(self._queues.get(queue, []))

    def get_statistics(self) -> Dict[str, Dict]:
        with self._lock:
            out = {}
            for q, stats in self._stats.items():
                out[q] = {**stats, 'pending': self.queue_size(q)}
        return out

    @staticmethod
    def _try_delegate_celery(queue: str, payload: dict) -> None:
        try:
            from celery import current_app
            current_app.send_task(
                f'fraud_detection.process_{queue}',
                kwargs={'payload': payload},
                ignore_result=True,
            )
        except Exception:
            pass   # Celery not configured — in-process queue is the fallback


_mq : MessageQueueManager | None = None
_mq_lock = threading.Lock()


def get_message_queue_manager() -> MessageQueueManager:
    global _mq
    if _mq is None:
        with _mq_lock:
            if _mq is None:
                _mq = MessageQueueManager()
    return _mq


def publish_message(queue: str, payload: Dict[str, Any]) -> str:
    return get_message_queue_manager().publish(queue, payload)


def get_queue_statistics() -> Dict[str, Dict]:
    return get_message_queue_manager().get_statistics()
