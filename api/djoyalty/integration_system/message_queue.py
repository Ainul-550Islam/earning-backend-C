# api/djoyalty/integration_system/message_queue.py
"""
Message Queue Manager -- High Traffic Queue Handler।
Manages Celery task queues for loyalty events।
Handles: priority queuing, dead letter queue, retry logic।

World reference: AWS SQS + EventBridge pattern for loyalty systems।
Uses Redis + Celery under the hood।
"""
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from .integ_constants import (
    MessagePriority, EventType,
    QUEUE_NOTIFICATIONS, QUEUE_WEBHOOKS, QUEUE_POINTS_EVENTS,
    QUEUE_CASHOUT, QUEUE_AI_TASKS, QUEUE_BULK, QUEUE_CRITICAL,
)

logger = logging.getLogger(__name__)


class Message:
    """A message in the queue।"""

    def __init__(self, event_type: str, payload: dict,
                  priority: MessagePriority = MessagePriority.NORMAL,
                  customer_id: int = None, tenant_id: int = None,
                  retry_count: int = 0, max_retries: int = 3,
                  delay_seconds: int = 0, idempotency_key: str = ''):
        self.event_type = event_type
        self.payload = payload
        self.priority = priority
        self.customer_id = customer_id
        self.tenant_id = tenant_id
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.idempotency_key = idempotency_key
        self.created_at = datetime.utcnow().isoformat()
        self.message_id = self._generate_id()

    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            'message_id': self.message_id,
            'event_type': self.event_type,
            'payload': self.payload,
            'priority': int(self.priority),
            'customer_id': self.customer_id,
            'tenant_id': self.tenant_id,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'delay_seconds': self.delay_seconds,
            'idempotency_key': self.idempotency_key,
            'created_at': self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        msg = cls(
            event_type=data['event_type'],
            payload=data['payload'],
            priority=MessagePriority(data.get('priority', 5)),
            customer_id=data.get('customer_id'),
            tenant_id=data.get('tenant_id'),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            delay_seconds=data.get('delay_seconds', 0),
            idempotency_key=data.get('idempotency_key', ''),
        )
        msg.message_id = data.get('message_id', msg.message_id)
        msg.created_at = data.get('created_at', msg.created_at)
        return msg


class QueueRouter:
    """
    Routes messages to appropriate queues based on event type।
    High-priority events -> critical queue (processed first)।
    Bulk events -> bulk queue (lower priority)।
    """

    ROUTING_TABLE: Dict[str, str] = {
        # Critical -- immediate processing
        EventType.POINTS_EARNED:    QUEUE_POINTS_EVENTS,
        EventType.POINTS_REDEEMED:  QUEUE_POINTS_EVENTS,
        EventType.TIER_UPGRADED:    QUEUE_NOTIFICATIONS,
        EventType.BADGE_UNLOCKED:   QUEUE_NOTIFICATIONS,
        EventType.VOUCHER_GENERATED: QUEUE_NOTIFICATIONS,
        # Cashout -- high priority
        EventType.CASHOUT_REQUESTED: QUEUE_CASHOUT,
        EventType.CASHOUT_APPROVED:  QUEUE_CASHOUT,
        EventType.CASHOUT_COMPLETED: QUEUE_CASHOUT,
        # Webhooks -- async
        EventType.POSTBACK_RECEIVED: QUEUE_WEBHOOKS,
        EventType.OFFER_COMPLETED:   QUEUE_POINTS_EVENTS,
        # AI -- can be delayed
        EventType.CHURN_ALERT:       QUEUE_AI_TASKS,
        EventType.OFFER_PERSONALIZED: QUEUE_AI_TASKS,
        # Bulk
        EventType.POINTS_EXPIRED:    QUEUE_BULK,
    }

    @classmethod
    def get_queue(cls, event_type: str, priority: MessagePriority) -> str:
        """Get queue name for event type and priority।"""
        if priority >= MessagePriority.CRITICAL:
            return QUEUE_CRITICAL
        return cls.ROUTING_TABLE.get(event_type, QUEUE_NOTIFICATIONS)


class MessageQueueManager:
    """
    High-traffic message queue manager।
    Uses Celery for async processing with Redis broker।
    Falls back to synchronous if Celery unavailable।

    Usage:
        mq = MessageQueueManager()
        mq.enqueue(EventType.POINTS_EARNED, {'points': 100}, customer_id=1)
        mq.enqueue_bulk([...])  # Bulk enqueue
    """

    _stats = {
        'enqueued': 0,
        'processed': 0,
        'failed': 0,
        'dead_letter': 0,
    }

    def __init__(self):
        self._celery_available = self._check_celery()

    @staticmethod
    def _check_celery() -> bool:
        try:
            import celery
            return True
        except ImportError:
            return False

    def enqueue(self, event_type: str, payload: dict,
                 customer_id: int = None, tenant_id: int = None,
                 priority: MessagePriority = MessagePriority.NORMAL,
                 delay_seconds: int = 0,
                 idempotency_key: str = '') -> Optional[str]:
        """
        Enqueue a message for async processing।
        Returns message_id or None on failure।
        """
        # Idempotency check
        if idempotency_key and self._is_duplicate(idempotency_key):
            logger.debug('MessageQueue: duplicate message %s, skipping', idempotency_key)
            return None

        msg = Message(
            event_type=event_type,
            payload=payload,
            priority=priority,
            customer_id=customer_id,
            tenant_id=tenant_id,
            delay_seconds=delay_seconds,
            idempotency_key=idempotency_key,
        )

        queue_name = QueueRouter.get_queue(event_type, priority)

        if self._celery_available:
            success = self._enqueue_celery(msg, queue_name)
        else:
            # Synchronous fallback
            success = self._process_sync(msg)

        if success:
            MessageQueueManager._stats['enqueued'] += 1
            logger.debug('MessageQueue: enqueued %s (queue=%s, id=%s)',
                         event_type, queue_name, msg.message_id)
            return msg.message_id
        else:
            self._send_to_dead_letter(msg)
            return None

    def enqueue_bulk(self, messages: List[dict]) -> int:
        """Bulk enqueue messages।"""
        count = 0
        for msg_data in messages:
            result = self.enqueue(**msg_data)
            if result:
                count += 1
        logger.info('MessageQueue: bulk enqueued %d/%d messages', count, len(messages))
        return count

    def _enqueue_celery(self, msg: Message, queue_name: str) -> bool:
        """Send to Celery task queue।"""
        try:
            from ..tasks.notification_tasks import process_queued_message
            kwargs = {
                'message_data': msg.to_dict(),
            }
            if msg.delay_seconds > 0:
                process_queued_message.apply_async(
                    kwargs=kwargs,
                    queue=queue_name,
                    countdown=msg.delay_seconds,
                    priority=int(msg.priority),
                )
            else:
                process_queued_message.apply_async(
                    kwargs=kwargs,
                    queue=queue_name,
                    priority=int(msg.priority),
                )
            return True
        except Exception as e:
            logger.error('MessageQueue._enqueue_celery error: %s', e)
            return False

    def _process_sync(self, msg: Message) -> bool:
        """Synchronous processing fallback।"""
        try:
            from .event_bus import EventBus
            # Get customer if customer_id provided
            customer = None
            if msg.customer_id:
                try:
                    from ..models.core import Customer
                    customer = Customer.objects.get(id=msg.customer_id)
                except Exception:
                    pass

            EventBus._fire_integration_handler(
                type('Event', (), {
                    'event_type': msg.event_type,
                    'customer': customer,
                    'data': msg.payload,
                    'tenant': None,
                })()
            )
            MessageQueueManager._stats['processed'] += 1
            return True
        except Exception as e:
            logger.error('MessageQueue._process_sync error: %s', e)
            MessageQueueManager._stats['failed'] += 1
            return False

    def _send_to_dead_letter(self, msg: Message):
        """Send failed message to dead letter queue।"""
        try:
            MessageQueueManager._stats['dead_letter'] += 1
            logger.error('MessageQueue: DLQ %s (id=%s)', msg.event_type, msg.message_id)
            # Store in Redis if available
            try:
                from django.core.cache import cache
                dlq_key = f'djoyalty:dlq:{msg.message_id}'
                cache.set(dlq_key, msg.to_json(), timeout=86400 * 7)  # 7 days
            except Exception:
                pass
        except Exception as e:
            logger.debug('_send_to_dead_letter error: %s', e)

    @staticmethod
    def _is_duplicate(idempotency_key: str) -> bool:
        """Check if message with this key was already processed।"""
        try:
            from django.core.cache import cache
            key = f'djoyalty:msgq:idem:{idempotency_key}'
            if cache.get(key):
                return True
            cache.set(key, '1', timeout=86400)  # 24 hour window
            return False
        except Exception:
            return False

    @classmethod
    def get_stats(cls) -> dict:
        """Queue statistics।"""
        return {
            **cls._stats,
            'success_rate': (
                f"{cls._stats['processed'] / (cls._stats['processed'] + cls._stats['failed']) * 100:.1f}%"
                if cls._stats['processed'] + cls._stats['failed'] > 0 else '100%'
            ),
        }

    # ─── Convenience Methods ──────────────────────────────────────

    def enqueue_notification(self, event_type: str, customer_id: int,
                              data: dict, delay: int = 0):
        """Quick enqueue for notification events।"""
        return self.enqueue(
            event_type=event_type,
            payload=data,
            customer_id=customer_id,
            priority=MessagePriority.NORMAL,
            delay_seconds=delay,
        )

    def enqueue_cashout(self, cashout_id: int, customer_id: int):
        """Enqueue cashout processing।"""
        return self.enqueue(
            event_type=EventType.CASHOUT_REQUESTED,
            payload={'cashout_id': cashout_id},
            customer_id=customer_id,
            priority=MessagePriority.HIGH,
            idempotency_key=f'cashout-{cashout_id}',
        )

    def enqueue_ai_task(self, task_type: str, customer_id: int, data: dict = None):
        """Enqueue AI processing task।"""
        return self.enqueue(
            event_type=task_type,
            payload=data or {},
            customer_id=customer_id,
            priority=MessagePriority.LOW,
        )


# Module-level singleton
mq = MessageQueueManager()
