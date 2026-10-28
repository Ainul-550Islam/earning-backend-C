# engagement/integration_system/message_queue.py
"""
High traffic message queue manager for integration system.
Handles message processing, queuing, and flow control.
"""
import asyncio
import json
import time
import threading
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union
import logging

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, DEFAULT_CONFIG, CACHE_KEYS
)
from .integ_exceptions import IntegrationException, SystemOverloadError


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class MessageStatus(Enum):
    """Message processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class QueueType(Enum):
    """Queue types for different purposes."""
    FIFO = "fifo"
    PRIORITY = "priority"
    DELAYED = "delayed"
    DEAD_LETTER = "dead_letter"


@dataclass
class Message:
    """Message object for queue processing."""
    id: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    queue_name: str = "default"
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    delay_ms: int = 0
    timeout_ms: int = 30000
    metadata: Dict[str, Any] = field(default_factory=dict)
    callback: Optional[Callable] = None
    error: Optional[Exception] = None
    trace_id: Optional[str] = None

    def __lt__(self, other):
        """For priority queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        return self.created_at < other.created_at


@dataclass
class QueueStats:
    """Queue statistics."""
    queue_name: str
    total_messages: int = 0
    pending_messages: int = 0
    processing_messages: int = 0
    completed_messages: int = 0
    failed_messages: int = 0
    average_processing_time_ms: float = 0.0
    throughput_per_second: float = 0.0
    last_processed: Optional[datetime] = None
    error_rate: float = 0.0


class BaseQueueBackend(ABC):
    """Base queue backend interface."""
    
    @abstractmethod
    def enqueue(self, message: Message) -> bool:
        """Add message to queue."""
        pass
    
    @abstractmethod
    def dequeue(self, queue_name: str, timeout_ms: int = 1000) -> Optional[Message]:
        """Get message from queue."""
        pass
    
    @abstractmethod
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message completion."""
        pass
    
    @abstractmethod
    def reject(self, message_id: str, requeue: bool = False) -> bool:
        """Reject message."""
        pass
    
    @abstractmethod
    def size(self, queue_name: str) -> int:
        """Get queue size."""
        pass
    
    @abstractmethod
    def clear(self, queue_name: str) -> bool:
        """Clear queue."""
        pass


class MemoryQueueBackend(BaseQueueBackend):
    """In-memory queue backend."""
    
    def __init__(self):
        self.queues: Dict[str, deque] = defaultdict(deque)
        self.priority_queues: Dict[str, list] = defaultdict(list)
        self.processing: Dict[str, Message] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.MemoryQueueBackend")
    
    def enqueue(self, message: Message) -> bool:
        """Add message to queue."""
        try:
            with self._lock:
                if message.priority == MessagePriority.NORMAL:
                    self.queues[message.queue_name].append(message)
                else:
                    # Priority queue
                    queue = self.priority_queues[message.queue_name]
                    queue.append(message)
                    queue.sort()
                
                self.logger.debug(f"Enqueued message {message.id} to {message.queue_name}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to enqueue message: {exc}")
            return False
    
    def dequeue(self, queue_name: str, timeout_ms: int = 1000) -> Optional[Message]:
        """Get message from queue."""
        try:
            with self._lock:
                # Check priority queue first
                if self.priority_queues[queue_name]:
                    message = self.priority_queues[queue_name].pop(0)
                elif self.queues[queue_name]:
                    message = self.queues[queue_name].popleft()
                else:
                    return None
                
                message.status = MessageStatus.PROCESSING
                self.processing[message.id] = message
                
                self.logger.debug(f"Dequeued message {message.id} from {queue_name}")
                return message
        except Exception as exc:
            self.logger.error(f"Failed to dequeue message: {exc}")
            return None
    
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message completion."""
        try:
            with self._lock:
                if message_id in self.processing:
                    message = self.processing.pop(message_id)
                    message.status = MessageStatus.COMPLETED
                    self.logger.debug(f"Acknowledged message {message_id}")
                    return True
                return False
        except Exception as exc:
            self.logger.error(f"Failed to acknowledge message: {exc}")
            return False
    
    def reject(self, message_id: str, requeue: bool = False) -> bool:
        """Reject message."""
        try:
            with self._lock:
                if message_id in self.processing:
                    message = self.processing.pop(message_id)
                    
                    if requeue:
                        message.status = MessageStatus.RETRY
                        message.retry_count += 1
                        return self.enqueue(message)
                    else:
                        message.status = MessageStatus.FAILED
                        self.logger.debug(f"Rejected message {message_id}")
                        return True
                return False
        except Exception as exc:
            self.logger.error(f"Failed to reject message: {exc}")
            return False
    
    def size(self, queue_name: str) -> int:
        """Get queue size."""
        with self._lock:
            return len(self.queues[queue_name]) + len(self.priority_queues[queue_name])
    
    def clear(self, queue_name: str) -> bool:
        """Clear queue."""
        try:
            with self._lock:
                self.queues[queue_name].clear()
                self.priority_queues[queue_name].clear()
                self.logger.debug(f"Cleared queue {queue_name}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to clear queue: {exc}")
            return False


class RedisQueueBackend(BaseQueueBackend):
    """Redis-based queue backend for distributed processing."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or self._get_redis_client()
        self.logger = logging.getLogger(f"{__name__}.RedisQueueBackend")
    
    def _get_redis_client(self):
        """Get Redis client."""
        try:
            import redis
            return redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True
            )
        except ImportError:
            raise IntegrationException("Redis package not installed")
    
    def enqueue(self, message: Message) -> bool:
        """Add message to Redis queue."""
        try:
            message_data = {
                'id': message.id,
                'payload': json.dumps(message.payload),
                'priority': message.priority.value,
                'queue_name': message.queue_name,
                'created_at': message.created_at.isoformat(),
                'max_retries': message.max_retries,
                'retry_count': message.retry_count,
                'metadata': json.dumps(message.metadata)
            }
            
            queue_key = f"queue:{message.queue_name}"
            
            if message.priority == MessagePriority.NORMAL:
                self.redis_client.lpush(queue_key, json.dumps(message_data))
            else:
                # Use sorted set for priority queue
                priority_key = f"priority_queue:{message.queue_name}"
                score = message.priority.value * 1000000 + time.time()
                self.redis_client.zadd(priority_key, {json.dumps(message_data): score})
            
            self.logger.debug(f"Enqueued message {message.id} to Redis")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to enqueue to Redis: {exc}")
            return False
    
    def dequeue(self, queue_name: str, timeout_ms: int = 1000) -> Optional[Message]:
        """Get message from Redis queue."""
        try:
            # Try priority queue first
            priority_key = f"priority_queue:{queue_name}"
            result = self.redis_client.zpopmin(priority_key)
            
            if result:
                message_data = json.loads(result[0][0])
            else:
                # Try regular queue
                queue_key = f"queue:{queue_name}"
                result = self.redis_client.brpop(queue_key, timeout=timeout_ms/1000)
                
                if result:
                    message_data = json.loads(result[1])
                else:
                    return None
            
            return self._deserialize_message(message_data)
        except Exception as exc:
            self.logger.error(f"Failed to dequeue from Redis: {exc}")
            return None
    
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message completion."""
        try:
            processing_key = f"processing:{message_id}"
            self.redis_client.delete(processing_key)
            return True
        except Exception as exc:
            self.logger.error(f"Failed to acknowledge message: {exc}")
            return False
    
    def reject(self, message_id: str, requeue: bool = False) -> bool:
        """Reject message."""
        try:
            processing_key = f"processing:{message_id}"
            message_data = self.redis_client.get(processing_key)
            
            if message_data:
                self.redis_client.delete(processing_key)
                
                if requeue:
                    message = json.loads(message_data)
                    message['retry_count'] += 1
                    return self.enqueue(self._deserialize_message(message))
            
            return True
        except Exception as exc:
            self.logger.error(f"Failed to reject message: {exc}")
            return False
    
    def size(self, queue_name: str) -> int:
        """Get queue size."""
        try:
            queue_key = f"queue:{queue_name}"
            priority_key = f"priority_queue:{queue_name}"
            
            size = self.redis_client.llen(queue_key)
            size += self.redis_client.zcard(priority_key)
            
            return size
        except Exception as exc:
            self.logger.error(f"Failed to get queue size: {exc}")
            return 0
    
    def clear(self, queue_name: str) -> bool:
        """Clear queue."""
        try:
            queue_key = f"queue:{queue_name}"
            priority_key = f"priority_queue:{queue_name}"
            
            self.redis_client.delete(queue_key)
            self.redis_client.delete(priority_key)
            
            return True
        except Exception as exc:
            self.logger.error(f"Failed to clear queue: {exc}")
            return False
    
    def _deserialize_message(self, data: Dict[str, Any]) -> Message:
        """Deserialize message from Redis data."""
        return Message(
            id=data['id'],
            payload=json.loads(data['payload']),
            priority=MessagePriority(data['priority']),
            queue_name=data['queue_name'],
            created_at=datetime.fromisoformat(data['created_at']),
            max_retries=data['max_retries'],
            retry_count=data['retry_count'],
            metadata=json.loads(data['metadata'])
        )


class MessageQueue:
    """High traffic message queue manager."""
    
    def __init__(self, backend: BaseQueueBackend = None, max_workers: int = 10):
        self.backend = backend or MemoryQueueBackend()
        self.max_workers = max_workers
        self.workers: List[threading.Thread] = []
        self.handlers: Dict[str, Callable] = {}
        self.stats: Dict[str, QueueStats] = {}
        self.running = False
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.MessageQueue")
        
        # Performance tracking
        self.processing_times: Dict[str, List[float]] = defaultdict(list)
        self.message_counts: Dict[str, int] = defaultdict(int)
    
    def start(self):
        """Start queue processing."""
        with self._lock:
            if self.running:
                return
            
            self.running = True
            
            # Start worker threads
            for i in range(self.max_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"QueueWorker-{i}",
                    daemon=True
                )
                worker.start()
                self.workers.append(worker)
            
            self.logger.info(f"Started message queue with {self.max_workers} workers")
    
    def stop(self):
        """Stop queue processing."""
        with self._lock:
            self.running = False
            
            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=5)
            
            self.workers.clear()
            self.logger.info("Stopped message queue")
    
    def register_handler(self, queue_name: str, handler: Callable):
        """Register message handler for queue."""
        self.handlers[queue_name] = handler
        self.logger.info(f"Registered handler for queue: {queue_name}")
    
    def enqueue(self, payload: Dict[str, Any], queue_name: str = "default",
                priority: MessagePriority = MessagePriority.NORMAL,
                **kwargs) -> str:
        """Enqueue message."""
        message = Message(
            id=self._generate_message_id(),
            payload=payload,
            priority=priority,
            queue_name=queue_name,
            **kwargs
        )
        
        success = self.backend.enqueue(message)
        
        if success:
            self._update_stats(queue_name, 'enqueued')
            return message.id
        else:
            raise IntegrationException(f"Failed to enqueue message to {queue_name}")
    
    def dequeue(self, queue_name: str, timeout_ms: int = 1000) -> Optional[Message]:
        """Dequeue message."""
        return self.backend.dequeue(queue_name, timeout_ms)
    
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message completion."""
        success = self.backend.acknowledge(message_id)
        if success:
            self._update_stats('default', 'completed')
        return success
    
    def reject(self, message_id: str, requeue: bool = False) -> bool:
        """Reject message."""
        success = self.backend.reject(message_id, requeue)
        if success and not requeue:
            self._update_stats('default', 'failed')
        return success
    
    def get_stats(self, queue_name: str = None) -> Union[QueueStats, Dict[str, QueueStats]]:
        """Get queue statistics."""
        if queue_name:
            return self.stats.get(queue_name, QueueStats(queue_name))
        return self.stats.copy()
    
    def clear_queue(self, queue_name: str) -> bool:
        """Clear queue."""
        return self.backend.clear(queue_name)
    
    def _worker_loop(self):
        """Worker thread loop."""
        while self.running:
            try:
                # Process all registered queues
                for queue_name in self.handlers.keys():
                    message = self.dequeue(queue_name, timeout_ms=100)
                    
                    if message:
                        self._process_message(message, queue_name)
                
                # Small delay to prevent busy waiting
                time.sleep(0.01)
                
            except Exception as exc:
                self.logger.error(f"Worker error: {exc}")
                time.sleep(1)
    
    def _process_message(self, message: Message, queue_name: str):
        """Process single message."""
        start_time = time.time()
        
        try:
            handler = self.handlers.get(queue_name)
            if not handler:
                self.logger.warning(f"No handler for queue {queue_name}")
                self.reject(message.id)
                return
            
            # Process message
            result = handler(message.payload)
            
            # Acknowledge success
            self.acknowledge(message.id)
            
            # Update processing time
            processing_time = (time.time() - start_time) * 1000
            self._record_processing_time(queue_name, processing_time)
            
            self.logger.debug(f"Processed message {message.id}")
            
        except Exception as exc:
            self.logger.error(f"Failed to process message {message.id}: {exc}")
            
            # Retry logic
            if message.retry_count < message.max_retries:
                message.retry_count += 1
                self.backend.enqueue(message)
            else:
                self.reject(message.id)
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _update_stats(self, queue_name: str, action: str):
        """Update queue statistics."""
        with self._lock:
            if queue_name not in self.stats:
                self.stats[queue_name] = QueueStats(queue_name=queue_name)
            
            stats = self.stats[queue_name]
            
            if action == 'enqueued':
                stats.total_messages += 1
                stats.pending_messages += 1
            elif action == 'completed':
                stats.pending_messages = max(0, stats.pending_messages - 1)
                stats.completed_messages += 1
                stats.last_processed = timezone.now()
            elif action == 'failed':
                stats.pending_messages = max(0, stats.pending_messages - 1)
                stats.failed_messages += 1
            
            # Calculate error rate
            total_processed = stats.completed_messages + stats.failed_messages
            if total_processed > 0:
                stats.error_rate = (stats.failed_messages / total_processed) * 100
    
    def _record_processing_time(self, queue_name: str, processing_time_ms: float):
        """Record processing time for statistics."""
        self.processing_times[queue_name].append(processing_time_ms)
        
        # Keep only last 1000 times
        if len(self.processing_times[queue_name]) > 1000:
            self.processing_times[queue_name] = self.processing_times[queue_name][-1000:]
        
        # Update average
        times = self.processing_times[queue_name]
        if times:
            avg_time = sum(times) / len(times)
            if queue_name in self.stats:
                self.stats[queue_name].average_processing_time_ms = avg_time


# Global message queue instance
message_queue = MessageQueue()


# Decorator for queue processing
def queue_message(queue_name: str = "default", priority: MessagePriority = MessagePriority.NORMAL):
    """Decorator to queue function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Queue the function call
            payload = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            
            return message_queue.enqueue(
                payload=payload,
                queue_name=queue_name,
                priority=priority
            )
        
        # Register handler if not already registered
        if queue_name not in message_queue.handlers:
            def handler(payload):
                func_name = payload['function']
                args = payload['args']
                kwargs = payload['kwargs']
                
                # Call the original function
                return func(*args, **kwargs)
            
            message_queue.register_handler(queue_name, handler)
        
        return wrapper
    return decorator


# Utility functions
class QueueUtils:
    """Utilities for queue management."""
    
    @staticmethod
    def create_batch_processor(queue_name: str, batch_size: int = 100):
        """Create batch processor for queue."""
        def batch_processor(handler: Callable):
            def wrapper(messages: List[Message]):
                # Process messages in batches
                for i in range(0, len(messages), batch_size):
                    batch = messages[i:i + batch_size]
                    handler(batch)
            
            message_queue.register_handler(queue_name, wrapper)
            return wrapper
        
        return batch_processor
    
    @staticmethod
    def create_delayed_queue(delay_ms: int):
        """Create delayed message processing."""
        def delayed_handler(message: Message):
            # Add delay before processing
            time.sleep(delay_ms / 1000)
            return message.payload
        
        return delayed_handler
    
    @staticmethod
    def create_dead_letter_queue(max_retries: int = 3):
        """Create dead letter queue for failed messages."""
        def dead_letter_handler(message: Message):
            if message.retry_count >= max_retries:
                # Move to dead letter queue
                message.queue_name = "dead_letter"
                message_queue.backend.enqueue(message)
            else:
                # Retry the message
                message.retry_count += 1
                message_queue.backend.enqueue(message)
        
        return dead_letter_handler
