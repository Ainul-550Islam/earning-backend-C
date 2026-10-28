"""
Message Queue - High Traffic Message Management

High-performance message queue system for handling large volumes of messages
with support for priority queuing, batching, and distributed processing.
"""

import logging
import asyncio
import threading
import time
import json
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue, Empty, Queue
from collections import defaultdict, deque
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, MessageQueueError
from .event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types."""
    EVENT = "event"
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BATCH = "batch"


class QueueType(Enum):
    """Queue types."""
    FIFO = "fifo"                    # First In, First Out
    LIFO = "lifo"                    # Last In, First Out
    PRIORITY = "priority"            # Priority-based
    DELAYED = "delayed"              # Delayed processing
    DEAD_LETTER = "dead_letter"      # Failed messages


@dataclass
class Message:
    """Message data structure."""
    message_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    priority: IntegrationPriority = IntegrationPriority.NORMAL
    queue_name: str = "default"
    headers: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    def __lt__(self, other):
        """Priority queue comparison."""
        if not isinstance(other, Message):
            return NotImplemented
        return self.priority.value > other.priority.value  # Higher priority first


@dataclass
class QueueConfig:
    """Queue configuration."""
    name: str
    queue_type: QueueType
    max_size: int = 10000
    max_memory_mb: int = 100
    retention_hours: int = 24
    dead_letter_queue: Optional[str] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 100
    batch_timeout_ms: int = 1000
    consumer_threads: int = 1
    enable_persistence: bool = False
    enable_compression: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueStats:
    """Queue statistics."""
    name: str
    total_messages: int = 0
    pending_messages: int = 0
    processing_messages: int = 0
    completed_messages: int = 0
    failed_messages: int = 0
    dead_letter_messages: int = 0
    average_processing_time: float = 0.0
    last_message_time: Optional[datetime] = None
    oldest_message_time: Optional[datetime] = None
    memory_usage_mb: float = 0.0


class MessageQueue:
    """High-performance message queue implementation."""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.queues: Dict[QueueType, Union[Queue, PriorityQueue]] = {
            QueueType.FIFO: Queue(maxsize=config.max_size),
            QueueType.LIFO: Queue(maxsize=config.max_size),
            QueueType.PRIORITY: PriorityQueue(maxsize=config.max_size),
            QueueType.DELAYED: PriorityQueue(maxsize=config.max_size),
            QueueType.DEAD_LETTER: Queue(maxsize=config.max_size)
        }
        
        self.processing_queue: Dict[str, Message] = {}
        self.completed_messages: deque = deque(maxlen=1000)
        self.stats = QueueStats(name=config.name)
        self.handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self.middleware: List[Callable] = []
        self._lock = threading.RLock()
        self._running = False
        self._consumer_threads: List[threading.Thread] = []
        self._batch_buffer: List[Message] = []
        self._batch_last_process = timezone.now()
        
        # Start consumer threads
        self._start_consumers()
    
    def _start_consumers(self):
        """Start consumer threads."""
        self._running = True
        
        for i in range(self.config.consumer_threads):
            consumer = threading.Thread(
                target=self._consumer_loop,
                name=f"MessageQueueConsumer-{self.config.name}-{i}",
                daemon=True
            )
            consumer.start()
            self._consumer_threads.append(consumer)
        
        logger.info(f"Started {self.config.consumer_threads} consumer threads for queue: {self.config.name}")
    
    def _consumer_loop(self):
        """Consumer thread loop."""
        while self._running:
            try:
                if self.config.queue_type == QueueType.DELAYED:
                    message = self._get_delayed_message()
                else:
                    message = self._get_message()
                
                if message:
                    self._process_message(message)
                else:
                    time.sleep(0.1)  # Brief pause when no messages
                    
            except Exception as e:
                logger.error(f"Consumer loop error: {str(e)}")
                time.sleep(1)  # Pause on error
    
    def _get_delayed_message(self) -> Optional[Message]:
        """Get message that is ready for processing."""
        delayed_queue = self.queues[QueueType.DELAYED]
        current_time = timezone.now()
        
        # Check if any delayed messages are ready
        try:
            while not delayed_queue.empty():
                message = delayed_queue.get_nowait()
                
                if message.scheduled_at and message.scheduled_at <= current_time:
                    return message
                else:
                    # Put it back if not ready
                    delayed_queue.put(message)
                    break
        except Empty:
            pass
        
        return None
    
    def _get_message(self) -> Optional[Message]:
        """Get message from queue."""
        try:
            if self.config.queue_type == QueueType.PRIORITY:
                return self.queues[QueueType.PRIORITY].get_nowait()
            elif self.config.queue_type == QueueType.LIFO:
                return self.queues[QueueType.LIFO].get_nowait()
            else:  # FIFO
                return self.queues[QueueType.FIFO].get_nowait()
        except Empty:
            return None
    
    def _process_message(self, message: Message):
        """Process a single message."""
        start_time = timezone.now()
        
        try:
            # Add to processing queue
            self.processing_queue[message.message_id] = message
            self.stats.processing_messages += 1
            
            # Apply middleware
            processed_message = self._apply_middleware(message)
            
            # Handle batching if enabled
            if self.config.batch_size > 1:
                self._handle_batch_processing(processed_message)
            else:
                self._handle_single_message(processed_message)
            
            # Update statistics
            processing_time = (timezone.now() - start_time).total_seconds()
            self._update_processing_stats(processing_time, True)
            
            # Mark as completed
            self.completed_messages.append(message)
            self.stats.completed_messages += 1
            
        except Exception as e:
            logger.error(f"Message processing failed: {message.message_id} - {str(e)}")
            
            # Handle retry or dead letter
            self._handle_failed_message(message, str(e))
            
            # Update statistics
            processing_time = (timezone.now() - start_time).total_seconds()
            self._update_processing_stats(processing_time, False)
        
        finally:
            # Remove from processing queue
            self.processing_queue.pop(message.message_id, None)
            self.stats.processing_messages -= 1
    
    def _handle_batch_processing(self, message: Message):
        """Handle batch message processing."""
        self._batch_buffer.append(message)
        
        # Check if batch is ready
        current_time = timezone.now()
        batch_ready = (
            len(self._batch_buffer) >= self.config.batch_size or
            (current_time - self._batch_last_process).total_seconds() * 1000 >= self.config.batch_timeout_ms
        )
        
        if batch_ready:
            batch_messages = self._batch_buffer.copy()
            self._batch_buffer.clear()
            self._batch_last_process = current_time
            
            # Process batch
            self._process_batch_messages(batch_messages)
    
    def _process_batch_messages(self, messages: List[Message]):
        """Process a batch of messages."""
        try:
            # Group by message type
            grouped_messages = defaultdict(list)
            for msg in messages:
                grouped_messages[msg.message_type].append(msg)
            
            # Process each group
            for message_type, msg_list in grouped_messages.items():
                handlers = self.handlers.get(message_type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            # Run async handler in thread
                            asyncio.run(handler(msg_list))
                        else:
                            handler(msg_list)
                    except Exception as e:
                        logger.error(f"Batch handler failed: {str(e)}")
            
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
    
    def _handle_single_message(self, message: Message):
        """Handle single message processing."""
        handlers = self.handlers.get(message.message_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Run async handler in thread
                    asyncio.run(handler(message))
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler failed: {str(e)}")
                raise  # Re-raise to trigger retry logic
    
    def _apply_middleware(self, message: Message) -> Message:
        """Apply middleware to message."""
        processed_message = message
        
        for middleware in self.middleware:
            try:
                if asyncio.iscoroutinefunction(middleware):
                    processed_message = asyncio.run(middleware(processed_message))
                else:
                    processed_message = middleware(processed_message)
            except Exception as e:
                logger.error(f"Middleware failed: {middleware.__name__} - {str(e)}")
                raise MessageQueueError(f"Middleware error: {str(e)}")
        
        return processed_message
    
    def _handle_failed_message(self, message: Message, error_message: str):
        """Handle failed message."""
        message.retry_count += 1
        
        # Check if we should retry
        if message.retry_count <= message.max_retries:
            # Calculate retry delay
            retry_delay = self._calculate_retry_delay(message.retry_count)
            
            # Schedule retry
            message.scheduled_at = timezone.now() + timedelta(seconds=retry_delay)
            
            # Add to delayed queue
            self.queues[QueueType.DELAYED].put(message)
            
            logger.info(f"Message scheduled for retry: {message.message_id} (attempt {message.retry_count})")
        else:
            # Send to dead letter queue
            self._send_to_dead_letter_queue(message, error_message)
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate retry delay using exponential backoff."""
        base_delay = self.config.retry_policy.get('base_delay', 1)
        max_delay = self.config.retry_policy.get('max_delay', 300)
        backoff_multiplier = self.config.retry_policy.get('backoff_multiplier', 2)
        
        delay = base_delay * (backoff_multiplier ** (retry_count - 1))
        return min(delay, max_delay)
    
    def _send_to_dead_letter_queue(self, message: Message, error_message: str):
        """Send message to dead letter queue."""
        # Add error information to metadata
        message.metadata['error_message'] = error_message
        message.metadata['failed_at'] = timezone.now().isoformat()
        
        try:
            self.queues[QueueType.DEAD_LETTER].put(message)
            self.stats.dead_letter_messages += 1
            
            logger.warning(f"Message sent to dead letter queue: {message.message_id}")
            
            # Publish dead letter event
            self._publish_dead_letter_event(message, error_message)
            
        except Exception as e:
            logger.error(f"Failed to send to dead letter queue: {str(e)}")
    
    def _publish_dead_letter_event(self, message: Message, error_message: str):
        """Publish dead letter event."""
        try:
            import asyncio
            
            event_data = {
                'queue_name': self.config.name,
                'message_id': message.message_id,
                'message_type': message.message_type.value,
                'error_message': error_message,
                'retry_count': message.retry_count,
                'created_at': message.created_at.isoformat(),
                'failed_at': timezone.now().isoformat()
            }
            
            asyncio.create_task(event_bus.publish(
                Event("message_queue.dead_letter", event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish dead letter event: {str(e)}")
    
    def _update_processing_stats(self, processing_time: float, success: bool):
        """Update processing statistics."""
        with self._lock:
            self.stats.total_messages += 1
            self.stats.last_message_time = timezone.now()
            
            if not success:
                self.stats.failed_messages += 1
            
            # Update average processing time
            if self.stats.total_messages == 1:
                self.stats.average_processing_time = processing_time
            else:
                current_avg = self.stats.average_processing_time
                self.stats.average_processing_time = (
                    (current_avg * (self.stats.total_messages - 1) + processing_time) / self.stats.total_messages
                )
    
    def enqueue(self, message: Message) -> bool:
        """Enqueue message."""
        try:
            # Check if message has expired
            if message.expires_at and message.expires_at <= timezone.now():
                logger.warning(f"Message expired: {message.message_id}")
                return False
            
            # Apply middleware
            processed_message = self._apply_middleware(message)
            
            # Add to appropriate queue
            if processed_message.scheduled_at and processed_message.scheduled_at > timezone.now():
                self.queues[QueueType.DELAYED].put(processed_message)
            else:
                if self.config.queue_type == QueueType.PRIORITY:
                    self.queues[QueueType.PRIORITY].put(processed_message)
                elif self.config.queue_type == QueueType.LIFO:
                    self.queues[QueueType.LIFO].put(processed_message)
                else:  # FIFO
                    self.queues[QueueType.FIFO].put(processed_message)
            
            self.stats.pending_messages += 1
            self.stats.total_messages += 1
            
            # Update oldest message time
            if not self.stats.oldest_message_time or processed_message.created_at < self.stats.oldest_message_time:
                self.stats.oldest_message_time = processed_message.created_at
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue message: {str(e)}")
            return False
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Message]:
        """Dequeue message."""
        try:
            if self.config.queue_type == QueueType.PRIORITY:
                return self.queues[QueueType.PRIORITY].get(timeout=timeout)
            elif self.config.queue_type == QueueType.LIFO:
                return self.queues[QueueType.LIFO].get(timeout=timeout)
            else:  # FIFO
                return self.queues[QueueType.FIFO].get(timeout=timeout)
        except Empty:
            return None
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register message handler."""
        self.handlers[message_type].append(handler)
        logger.info(f"Registered handler for message type: {message_type.value}")
    
    def add_middleware(self, middleware: Callable):
        """Add middleware to the queue."""
        self.middleware.append(middleware)
        logger.info(f"Added middleware: {middleware.__name__}")
    
    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        with self._lock:
            # Update pending count
            total_pending = 0
            for queue_type, queue in self.queues.items():
                if queue_type != QueueType.DEAD_LETTER:
                    total_pending += queue.qsize()
            
            self.stats.pending_messages = total_pending
            
            # Estimate memory usage
            self.stats.memory_usage_mb = self._estimate_memory_usage()
            
            return self.stats
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        # Simple estimation based on queue sizes
        total_messages = 0
        
        for queue in self.queues.values():
            total_messages += queue.qsize()
        
        # Assume average message size of 1KB
        return (total_messages * 1024) / (1024 * 1024)
    
    def purge(self) -> int:
        """Purge all messages from the queue."""
        purged_count = 0
        
        for queue in self.queues.values():
            while not queue.empty():
                try:
                    queue.get_nowait()
                    purged_count += 1
                except Empty:
                    break
        
        self._batch_buffer.clear()
        self.processing_queue.clear()
        self.completed_messages.clear()
        
        logger.info(f"Purged {purged_count} messages from queue: {self.config.name}")
        return purged_count
    
    def purge_expired(self) -> int:
        """Purge expired messages."""
        purged_count = 0
        current_time = timezone.now()
        
        # Check all queues for expired messages
        for queue_type, queue in self.queues.items():
            if queue_type == QueueType.DELAYED:
                continue  # Delayed messages are handled differently
            
            temp_messages = []
            
            # Extract all messages
            while not queue.empty():
                try:
                    message = queue.get_nowait()
                    if message.expires_at and message.expires_at <= current_time:
                        purged_count += 1
                    else:
                        temp_messages.append(message)
                except Empty:
                    break
            
            # Put non-expired messages back
            for message in temp_messages:
                queue.put(message)
        
        logger.info(f"Purged {purged_count} expired messages from queue: {self.config.name}")
        return purged_count
    
    def get_dead_letter_messages(self, limit: int = 100) -> List[Message]:
        """Get messages from dead letter queue."""
        messages = []
        
        for _ in range(min(limit, self.queues[QueueType.DEAD_LETTER].qsize())):
            try:
                message = self.queues[QueueType.DEAD_LETTER].get_nowait()
                messages.append(message)
            except Empty:
                break
        
        return messages
    
    def retry_dead_letter_messages(self) -> int:
        """Retry messages from dead letter queue."""
        retried_count = 0
        
        while not self.queues[QueueType.DEAD_LETTER].empty():
            try:
                message = self.queues[QueueType.DEAD_LETTER].get_nowait()
                
                # Reset retry count
                message.retry_count = 0
                message.metadata.pop('error_message', None)
                message.metadata.pop('failed_at', None)
                
                # Re-enqueue
                if self.enqueue(message):
                    retried_count += 1
                
            except Empty:
                break
        
        logger.info(f"Retried {retried_count} messages from dead letter queue")
        return retried_count
    
    def shutdown(self):
        """Shutdown message queue."""
        logger.info(f"Shutting down message queue: {self.config.name}")
        
        self._running = False
        
        # Wait for consumers to finish
        for consumer in self._consumer_threads:
            consumer.join(timeout=5)
        
        logger.info(f"Message queue shutdown complete: {self.config.name}")


class MessageQueueManager:
    """Manager for multiple message queues."""
    
    def __init__(self):
        self.queues: Dict[str, MessageQueue] = {}
        self.queue_configs: Dict[str, QueueConfig] = {}
        self._lock = threading.RLock()
    
    def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a new message queue."""
        with self._lock:
            if config.name in self.queues:
                logger.warning(f"Message queue already exists: {config.name}")
                return self.queues[config.name]
            
            queue = MessageQueue(config)
            self.queues[config.name] = queue
            self.queue_configs[config.name] = config
            
            logger.info(f"Created message queue: {config.name}")
            return queue
    
    def get_queue(self, name: str) -> Optional[MessageQueue]:
        """Get queue by name."""
        return self.queues.get(name)
    
    def remove_queue(self, name: str) -> bool:
        """Remove queue."""
        with self._lock:
            if name in self.queues:
                queue = self.queues[name]
                queue.shutdown()
                del self.queues[name]
                del self.queue_configs[name]
                logger.info(f"Removed message queue: {name}")
                return True
            return False
    
    def get_all_queues(self) -> Dict[str, MessageQueue]:
        """Get all queues."""
        return self.queues.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all queues."""
        stats = {
            'total_queues': len(self.queues),
            'total_messages': 0,
            'pending_messages': 0,
            'processing_messages': 0,
            'completed_messages': 0,
            'failed_messages': 0,
            'dead_letter_messages': 0,
            'total_memory_usage_mb': 0.0,
            'queues': {}
        }
        
        for name, queue in self.queues.items():
            queue_stats = queue.get_stats()
            stats['queues'][name] = {
                'total_messages': queue_stats.total_messages,
                'pending_messages': queue_stats.pending_messages,
                'processing_messages': queue_stats.processing_messages,
                'completed_messages': queue_stats.completed_messages,
                'failed_messages': queue_stats.failed_messages,
                'dead_letter_messages': queue_stats.dead_letter_messages,
                'average_processing_time': queue_stats.average_processing_time,
                'memory_usage_mb': queue_stats.memory_usage_mb,
                'last_message_time': queue_stats.last_message_time.isoformat() if queue_stats.last_message_time else None,
                'oldest_message_time': queue_stats.oldest_message_time.isoformat() if queue_stats.oldest_message_time else None
            }
            
            stats['total_messages'] += queue_stats.total_messages
            stats['pending_messages'] += queue_stats.pending_messages
            stats['processing_messages'] += queue_stats.processing_messages
            stats['completed_messages'] += queue_stats.completed_messages
            stats['failed_messages'] += queue_stats.failed_messages
            stats['dead_letter_messages'] += queue_stats.dead_letter_messages
            stats['total_memory_usage_mb'] += queue_stats.memory_usage_mb
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all queues."""
        health_status = {
            'total_queues': len(self.queues),
            'healthy_queues': 0,
            'unhealthy_queues': 0,
            'queues': {}
        }
        
        for name, queue in self.queues.items():
            queue_stats = queue.get_stats()
            
            # Determine health based on various factors
            is_healthy = (
                queue_stats.memory_usage_mb < queue.config.max_memory_mb * 0.8 and
                queue_stats.pending_messages < queue.config.max_size * 0.8 and
                queue_stats.failed_messages / max(1, queue_stats.total_messages) < 0.1
            )
            
            if is_healthy:
                health_status['healthy_queues'] += 1
            else:
                health_status['unhealthy_queues'] += 1
            
            health_status['queues'][name] = {
                'healthy': is_healthy,
                'memory_usage_mb': queue_stats.memory_usage_mb,
                'memory_limit_mb': queue.config.max_memory_mb,
                'pending_messages': queue_stats.pending_messages,
                'max_size': queue.config.max_size,
                'error_rate': queue_stats.failed_messages / max(1, queue_stats.total_messages),
                'running': queue._running
            }
        
        return health_status
    
    def shutdown(self):
        """Shutdown all queues."""
        for queue in self.queues.values():
            queue.shutdown()
        
        self.queues.clear()
        self.queue_configs.clear()
        logger.info("Shutdown all message queues")


# Global message queue manager
message_queue_manager = MessageQueueManager()


# Convenience functions
def create_fifo_queue(name: str, max_size: int = 10000, **config) -> MessageQueue:
    """Create FIFO message queue."""
    queue_config = QueueConfig(
        name=name,
        queue_type=QueueType.FIFO,
        max_size=max_size,
        **config
    )
    
    return message_queue_manager.create_queue(queue_config)


def create_priority_queue(name: str, max_size: int = 10000, **config) -> MessageQueue:
    """Create priority message queue."""
    queue_config = QueueConfig(
        name=name,
        queue_type=QueueType.PRIORITY,
        max_size=max_size,
        **config
    )
    
    return message_queue_manager.create_queue(queue_config)


def create_delayed_queue(name: str, max_size: int = 10000, **config) -> MessageQueue:
    """Create delayed message queue."""
    queue_config = QueueConfig(
        name=name,
        queue_type=QueueType.DELAYED,
        max_size=max_size,
        **config
    )
    
    return message_queue_manager.create_queue(queue_config)


def create_message(message_id: str, message_type: MessageType, payload: Dict[str, Any],
                 priority: IntegrationPriority = IntegrationPriority.NORMAL, **kwargs) -> Message:
    """Create a message."""
    return Message(
        message_id=message_id,
        message_type=message_type,
        payload=payload,
        priority=priority,
        **kwargs
    )
