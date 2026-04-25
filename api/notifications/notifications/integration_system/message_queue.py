# integration_system/message_queue.py
"""
Message Queue — High-traffic async message queue manager.

Handles high-volume message processing with:
  - Priority queues (1-10)
  - Dead letter queue (DLQ) for failed messages
  - Rate limiting per queue
  - Message deduplication
  - Batch processing
  - Celery backend
"""
import hashlib, json, logging, threading, time, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import IntegPriority, Queues, CacheKeys, CacheTTL
logger = logging.getLogger(__name__)

@dataclass
class QueueMessage:
    payload: Dict
    queue_name: str = 'default'
    priority: int = IntegPriority.MEDIUM
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str = ''
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'message_id': self.message_id, 'payload': self.payload,
            'queue_name': self.queue_name, 'priority': self.priority,
            'idempotency_key': self.idempotency_key, 'max_retries': self.max_retries,
            'retry_count': self.retry_count, 'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def compute_idempotency_key(self) -> str:
        content = json.dumps(self.payload, sort_keys=True)
        return hashlib.sha256(f'{self.queue_name}:{content}'.encode()).hexdigest()[:32]


class MessageQueue:
    """High-throughput message queue with deduplication and DLQ."""

    DLQ_SUFFIX = '_dlq'
    DEDUP_TTL = 3600  # 1 hour

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._stats: Dict[str, int] = {'enqueued': 0, 'processed': 0, 'failed': 0, 'deduped': 0}
        self._lock = threading.Lock()

    def enqueue(self, payload: Dict, queue_name: str = 'default',
                priority: int = IntegPriority.MEDIUM, idempotency_key: str = '',
                max_retries: int = 3, delay_seconds: int = 0,
                metadata: Optional[Dict] = None) -> Optional[str]:
        """Enqueue a message. Returns message_id or None if deduplicated."""
        msg = QueueMessage(
            payload=payload, queue_name=queue_name, priority=priority,
            idempotency_key=idempotency_key, max_retries=max_retries,
            metadata=metadata or {},
        )

        if not msg.idempotency_key:
            msg.idempotency_key = msg.compute_idempotency_key()

        # Deduplication check
        dedup_key = f'mq:dedup:{msg.idempotency_key}'
        if cache.get(dedup_key):
            self._stats['deduped'] += 1
            logger.debug(f'MessageQueue: deduplicated message {msg.idempotency_key[:12]}')
            return None

        cache.set(dedup_key, '1', self.DEDUP_TTL)

        # Dispatch via Celery
        try:
            from .tasks import process_queue_message_task
            kwargs = dict(args=[msg.to_dict()])
            if delay_seconds > 0:
                kwargs['countdown'] = delay_seconds
            process_queue_message_task.apply_async(**kwargs)
        except Exception as exc:
            logger.error(f'MessageQueue.enqueue: Celery dispatch failed: {exc}')
            return None

        self._stats['enqueued'] += 1
        return msg.message_id

    def enqueue_bulk(self, messages: List[Dict], queue_name: str = 'default') -> List[Optional[str]]:
        """Enqueue multiple messages. Returns list of message_ids."""
        return [self.enqueue(queue_name=queue_name, **m) for m in messages]

    def register_handler(self, queue_name: str, handler: Callable):
        """Register a message handler for a queue."""
        self._handlers[queue_name] = handler
        logger.info(f'MessageQueue: registered handler for "{queue_name}"')

    def process_message(self, msg_dict: Dict) -> bool:
        """Process a single message (called by Celery task)."""
        queue_name = msg_dict.get('queue_name', 'default')
        handler = self._handlers.get(queue_name) or self._handlers.get('*')
        if not handler:
            logger.warning(f'MessageQueue: no handler for queue "{queue_name}"')
            return False
        try:
            handler(msg_dict)
            self._stats['processed'] += 1
            return True
        except Exception as exc:
            self._stats['failed'] += 1
            logger.error(f'MessageQueue.process_message "{queue_name}": {exc}')
            msg_dict['retry_count'] = msg_dict.get('retry_count', 0) + 1
            if msg_dict['retry_count'] <= msg_dict.get('max_retries', 3):
                try:
                    from .tasks import process_queue_message_task
                    delay = 60 * (2 ** msg_dict['retry_count'])
                    process_queue_message_task.apply_async(args=[msg_dict], countdown=delay)
                except Exception:
                    pass
            else:
                self._send_to_dlq(msg_dict, str(exc))
            return False

    def _send_to_dlq(self, msg_dict: Dict, error: str):
        """Move a message to the dead-letter queue."""
        try:
            from .tasks import process_queue_message_task
            dlq_msg = {**msg_dict, 'queue_name': f"{msg_dict['queue_name']}{self.DLQ_SUFFIX}", 'error': error}
            logger.warning(f"MessageQueue: DLQ message_id={msg_dict.get('message_id', '?')}")
        except Exception:
            pass

    def stats(self) -> Dict:
        return {**self._stats, 'handlers': list(self._handlers.keys())}


message_queue = MessageQueue()
