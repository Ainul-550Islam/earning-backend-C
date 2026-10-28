"""
Message Queue Manager — High-traffic message queue management system.

This module provides comprehensive message queue capabilities for handling
high-volume message processing with advanced queuing strategies.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
import heapq

from .integ_constants import Priority, MessageType, DEFAULT_TIMEOUT, DEFAULT_RETRY_ATTEMPTS
from .integ_exceptions import (
    IntegrationError, QueueFullError, QueueEmptyError, TimeoutError,
    ValidationError
)
from .integ_signals import (
    message_queued, message_dequeued, queue_full, queue_empty,
    message_processing_failed
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message Queue Types
# ---------------------------------------------------------------------------

class QueueType(Enum):
    """Queue type enumeration."""
    FIFO = "fifo"                    # First In, First Out
    LIFO = "lifo"                    # Last In, First Out
    PRIORITY = "priority"            # Priority-based
    DELAYED = "delayed"              # Delayed processing
    DEAD_LETTER = "dead_letter"      # Dead letter queue
    RETRY = "retry"                  # Retry queue


class MessageStatus(Enum):
    """Message status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD = "dead"


class ProcessingMode(Enum):
    """Processing mode enumeration."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BATCH = "batch"


# ---------------------------------------------------------------------------
# Message Queue Data Classes
# ---------------------------------------------------------------------------

@dataclass
class QueueMessage:
    """Message in the queue."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload: Any = None
    headers: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    message_type: MessageType = MessageType.REQUEST
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    delay_until: Optional[datetime] = None
    timeout: Optional[float] = None
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at
    
    def is_delayed(self) -> bool:
        """Check if message is delayed."""
        return self.delay_until and datetime.now(timezone.utc) < self.delay_until
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "payload": self.payload,
            "headers": self.headers,
            "metadata": self.metadata,
            "priority": self.priority.value,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "delay_until": self.delay_until.isoformat() if self.delay_until else None,
            "timeout": self.timeout,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to
        }


@dataclass
class QueueConfig:
    """Queue configuration."""
    
    name: str
    queue_type: QueueType = QueueType.FIFO
    max_size: int = 10000
    max_message_size: int = 10 * 1024 * 1024  # 10MB
    default_priority: Priority = Priority.NORMAL
    default_timeout: float = DEFAULT_TIMEOUT
    default_retries: int = DEFAULT_RETRY_ATTEMPTS
    processing_mode: ProcessingMode = ProcessingMode.SEQUENTIAL
    batch_size: int = 100
    max_concurrent_processors: int = 10
    dead_letter_queue: Optional[str] = None
    retry_queue: Optional[str] = None
    message_ttl: Optional[float] = None  # Time to live in seconds
    auto_ack: bool = True
    persistent: bool = True
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "queue_type": self.queue_type.value,
            "max_size": self.max_size,
            "max_message_size": self.max_message_size,
            "default_priority": self.default_priority.value,
            "default_timeout": self.default_timeout,
            "default_retries": self.default_retries,
            "processing_mode": self.processing_mode.value,
            "batch_size": self.batch_size,
            "max_concurrent_processors": self.max_concurrent_processors,
            "dead_letter_queue": self.dead_letter_queue,
            "retry_queue": self.retry_queue,
            "message_ttl": self.message_ttl,
            "auto_ack": self.auto_ack,
            "persistent": self.persistent,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


@dataclass
class QueueMetrics:
    """Queue metrics."""
    
    queue_name: str
    total_messages: int = 0
    pending_messages: int = 0
    processing_messages: int = 0
    completed_messages: int = 0
    failed_messages: int = 0
    dead_messages: int = 0
    average_processing_time: float = 0.0
    average_wait_time: float = 0.0
    throughput: float = 0.0  # messages per second
    last_activity: Optional[datetime] = None
    queue_depth: int = 0
    memory_usage: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total_processed = self.completed_messages + self.failed_messages
        if total_processed == 0:
            return 1.0
        return self.completed_messages / total_processed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "queue_name": self.queue_name,
            "total_messages": self.total_messages,
            "pending_messages": self.pending_messages,
            "processing_messages": self.processing_messages,
            "completed_messages": self.completed_messages,
            "failed_messages": self.failed_messages,
            "dead_messages": self.dead_messages,
            "success_rate": self.success_rate,
            "average_processing_time": self.average_processing_time,
            "average_wait_time": self.average_wait_time,
            "throughput": self.throughput,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "queue_depth": self.queue_depth,
            "memory_usage": self.memory_usage
        }


@dataclass
class ProcessingResult:
    """Result of message processing."""
    
    success: bool
    message_id: str
    processing_time: float = 0.0
    error: Optional[Exception] = None
    result_data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message_id": self.message_id,
            "processing_time": self.processing_time,
            "error": str(self.error) if self.error else None,
            "result_data": self.result_data,
            "timestamp": self.timestamp.isoformat()
        }


# ---------------------------------------------------------------------------
# Abstract Message Processor
# ---------------------------------------------------------------------------

class BaseMessageProcessor(ABC):
    """Abstract base class for message processors."""
    
    @abstractmethod
    def process(self, message: QueueMessage) -> ProcessingResult:
        """Process a message."""
        pass
    
    @abstractmethod
    def can_process(self, message: QueueMessage) -> bool:
        """Check if processor can handle the message."""
        pass


# ---------------------------------------------------------------------------
# Message Queue Implementation
# ---------------------------------------------------------------------------

class MessageQueue:
    """High-performance message queue implementation."""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.metrics = QueueMetrics(queue_name=config.name)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = threading.RLock()
        
        # Queue storage based on type
        if config.queue_type == QueueType.PRIORITY:
            self._queue: List[tuple[int, datetime, QueueMessage]] = []
        elif config.queue_type == QueueType.LIFO:
            self._queue = deque()
        else:  # FIFO
            self._queue = deque()
        
        # Processing state
        self._processing_messages: Dict[str, QueueMessage] = {}
        self._processors: List[BaseMessageProcessor] = []
        self._executor = ThreadPoolExecutor(max_workers=config.max_concurrent_processors)
        self._running = False
        self._processing_thread: Optional[threading.Thread] = None
        
        # Delayed messages
        self._delayed_queue: List[tuple[datetime, QueueMessage]] = []
        
        # Statistics
        self._start_time = datetime.now(timezone.utc)
        self._last_throughput_update = datetime.now(timezone.utc)
        self._last_throughput_count = 0
    
    def start(self) -> None:
        """Start the message queue."""
        if self._running:
            return
        
        self._running = True
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        
        self.logger.info(f"Message queue started: {self.config.name}")
    
    def stop(self) -> None:
        """Stop the message queue."""
        self._running = False
        
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        
        self._executor.shutdown(wait=True)
        self.logger.info(f"Message queue stopped: {self.config.name}")
    
    def enqueue(self, message: QueueMessage) -> bool:
        """Enqueue a message."""
        if not self.config.enabled:
            return False
        
        with self._lock:
            # Check queue size
            if len(self._queue) >= self.config.max_size:
                queue_full.send(
                    sender=self,
                    queue_name=self.config.name,
                    current_size=len(self._queue),
                    max_size=self.config.max_size
                )
                raise QueueFullError(f"Queue '{self.config.name}' is full")
            
            # Validate message
            validation_errors = self._validate_message(message)
            if validation_errors:
                raise ValidationError(f"Message validation failed: {', '.join(validation_errors)}")
            
            # Apply defaults
            if message.priority == Priority.NORMAL:
                message.priority = self.config.default_priority
            
            if not message.timeout:
                message.timeout = self.config.default_timeout
            
            if message.max_retries == 3:
                message.max_retries = self.config.default_retries
            
            # Set expiration if configured
            if self.config.message_ttl and not message.expires_at:
                message.expires_at = message.timestamp + timedelta(seconds=self.config.message_ttl)
            
            # Add to appropriate queue
            if message.is_delayed():
                heapq.heappush(self._delayed_queue, (message.delay_until, message))
            else:
                self._add_to_queue(message)
            
            # Update metrics
            self.metrics.total_messages += 1
            self.metrics.pending_messages += 1
            self.metrics.last_activity = datetime.now(timezone.utc)
            
            # Emit signal
            message_queued.send(
                sender=self,
                queue_name=self.config.name,
                message_id=message.id,
                message_type=message.message_type.value,
                priority=message.priority.value
            )
            
            self.logger.debug(f"Message enqueued: {message.id}")
            return True
    
    def dequeue(self, timeout: Optional[float] = None) -> Optional[QueueMessage]:
        """Dequeue a message."""
        start_time = time.time()
        
        while True:
            with self._lock:
                # Check for delayed messages ready to process
                self._process_delayed_messages()
                
                # Get message from queue
                message = self._get_from_queue()
                
                if message:
                    # Move to processing state
                    self._processing_messages[message.id] = message
                    self.metrics.pending_messages -= 1
                    self.metrics.processing_messages += 1
                    
                    # Emit signal
                    message_dequeued.send(
                        sender=self,
                        queue_name=self.config.name,
                        message_id=message.id
                    )
                    
                    return message
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            # Wait a bit
            time.sleep(0.01)
    
    def add_processor(self, processor: BaseMessageProcessor) -> None:
        """Add a message processor."""
        with self._lock:
            self._processors.append(processor)
            self.logger.info(f"Added processor to queue: {self.config.name}")
    
    def remove_processor(self, processor: BaseMessageProcessor) -> bool:
        """Remove a message processor."""
        with self._lock:
            try:
                self._processors.remove(processor)
                self.logger.info(f"Removed processor from queue: {self.config.name}")
                return True
            except ValueError:
                return False
    
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message completion."""
        with self._lock:
            if message_id in self._processing_messages:
                message = self._processing_messages.pop(message_id)
                self.metrics.processing_messages -= 1
                self.metrics.completed_messages += 1
                
                # Update throughput
                self._update_throughput()
                
                return True
            return False
    
    def reject(self, message_id: str, requeue: bool = True) -> bool:
        """Reject a message."""
        with self._lock:
            if message_id in self._processing_messages:
                message = self._processing_messages.pop(message_id)
                self.metrics.processing_messages -= 1
                
                if requeue and message.can_retry():
                    # Retry the message
                    message.retry_count += 1
                    message.delay_until = datetime.now(timezone.utc) + timedelta(seconds=2 ** message.retry_count)
                    heapq.heappush(self._delayed_queue, (message.delay_until, message))
                else:
                    # Move to dead letter queue
                    self.metrics.dead_messages += 1
                    self._send_to_dead_letter_queue(message)
                
                self.metrics.failed_messages += 1
                return True
            return False
    
    def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        with self._lock:
            self.metrics.queue_depth = len(self._queue) + len(self._delayed_queue)
            self._update_throughput()
            return self.metrics
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        metrics = self.get_metrics()
        
        return {
            "name": self.config.name,
            "enabled": self.config.enabled,
            "running": self._running,
            "queue_type": self.config.queue_type.value,
            "processing_mode": self.config.processing_mode.value,
            "metrics": metrics.to_dict(),
            "config": self.config.to_dict()
        }
    
    # ---------------------------------------------------------------------------
    # Private Methods
    # ---------------------------------------------------------------------------
    
    def _add_to_queue(self, message: QueueMessage) -> None:
        """Add message to the appropriate queue."""
        if self.config.queue_type == QueueType.PRIORITY:
            # Priority queue (min-heap with negative priority for max-heap behavior)
            priority_value = -message.priority.value
            heapq.heappush(self._queue, (priority_value, message.timestamp, message))
        elif self.config.queue_type == QueueType.LIFO:
            self._queue.append(message)
        else:  # FIFO
            self._queue.append(message)
    
    def _get_from_queue(self) -> Optional[QueueMessage]:
        """Get message from the appropriate queue."""
        if not self._queue:
            return None
        
        if self.config.queue_type == QueueType.PRIORITY:
            if self._queue:
                _, _, message = heapq.heappop(self._queue)
                return message
        elif self.config.queue_type == QueueType.LIFO:
            return self._queue.pop()
        else:  # FIFO
            return self._queue.popleft()
        
        return None
    
    def _process_delayed_messages(self) -> None:
        """Process delayed messages that are ready."""
        now = datetime.now(timezone.utc)
        
        while self._delayed_queue and self._delayed_queue[0][0] <= now:
            _, message = heapq.heappop(self._delayed_queue)
            message.delay_until = None
            self._add_to_queue(message)
    
    def _processing_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                if self.config.processing_mode == ProcessingMode.BATCH:
                    self._process_batch()
                else:
                    self._process_single()
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                time.sleep(0.1)
    
    def _process_single(self) -> None:
        """Process a single message."""
        message = self.dequeue(timeout=0.1)
        
        if not message:
            return
        
        # Find appropriate processor
        processor = None
        for p in self._processors:
            if p.can_process(message):
                processor = p
                break
        
        if not processor:
            # No processor available, reject message
            self.reject(message.id, requeue=False)
            return
        
        # Process message
        future = self._executor.submit(self._process_message, processor, message)
        
        # Handle auto-ack
        if self.config.auto_ack:
            future.add_done_callback(lambda f: self._handle_processing_result(f, message))
    
    def _process_batch(self) -> None:
        """Process messages in batch."""
        batch = []
        
        # Collect batch
        for _ in range(self.config.batch_size):
            message = self.dequeue(timeout=0.01)
            if not message:
                break
            batch.append(message)
        
        if not batch:
            return
        
        # Process batch
        futures = []
        for message in batch:
            processor = None
            for p in self._processors:
                if p.can_process(message):
                    processor = p
                    break
            
            if processor:
                future = self._executor.submit(self._process_message, processor, message)
                futures.append((future, message))
        
        # Wait for completion
        for future, message in futures:
            if self.config.auto_ack:
                future.add_done_callback(lambda f, msg=message: self._handle_processing_result(f, msg))
    
    def _process_message(self, processor: BaseMessageProcessor, message: QueueMessage) -> ProcessingResult:
        """Process a single message."""
        start_time = time.time()
        
        try:
            result = processor.process(message)
            result.processing_time = time.time() - start_time
            
            # Update metrics
            self._update_processing_metrics(result)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            result = ProcessingResult(
                success=False,
                message_id=message.id,
                processing_time=processing_time,
                error=e
            )
            
            # Update metrics
            self._update_processing_metrics(result)
            
            # Emit signal
            message_processing_failed.send(
                sender=self,
                queue_name=self.config.name,
                message_id=message.id,
                error=e,
                retry_count=message.retry_count
            )
            
            return result
    
    def _handle_processing_result(self, future: Future, message: QueueMessage) -> None:
        """Handle processing result."""
        try:
            result = future.result()
            
            if result.success:
                self.acknowledge(message.id)
            else:
                self.reject(message.id, requeue=True)
                
        except Exception as e:
            self.logger.error(f"Error handling processing result for message {message.id}: {e}")
            self.reject(message.id, requeue=True)
    
    def _update_processing_metrics(self, result: ProcessingResult) -> None:
        """Update processing metrics."""
        with self._lock:
            total_processed = self.metrics.completed_messages + self.metrics.failed_messages
            
            if total_processed > 0:
                self.metrics.average_processing_time = (
                    (self.metrics.average_processing_time * (total_processed - 1) + result.processing_time) / total_processed
                )
    
    def _update_throughput(self) -> None:
        """Update throughput metrics."""
        now = datetime.now(timezone.utc)
        time_diff = (now - self._last_throughput_update).total_seconds()
        
        if time_diff >= 1.0:  # Update every second
            current_count = self.metrics.completed_messages
            count_diff = current_count - self._last_throughput_count
            
            self.metrics.throughput = count_diff / time_diff
            self._last_throughput_update = now
            self._last_throughput_count = current_count
    
    def _validate_message(self, message: QueueMessage) -> List[str]:
        """Validate a message."""
        errors = []
        
        if not message.id:
            errors.append("Message ID is required")
        
        if not message.payload:
            errors.append("Message payload is required")
        
        # Check message size
        import sys
        message_size = sys.getsizeof(str(message.payload))
        if message_size > self.config.max_message_size:
            errors.append(f"Message size ({message_size}) exceeds maximum ({self.config.max_message_size})")
        
        return errors
    
    def _send_to_dead_letter_queue(self, message: QueueMessage) -> None:
        """Send message to dead letter queue."""
        if self.config.dead_letter_queue:
            # This would send to the dead letter queue
            # For now, we'll just log it
            self.logger.warning(f"Message {message.id} sent to dead letter queue")


# ---------------------------------------------------------------------------
# Message Queue Manager
# ---------------------------------------------------------------------------

class MessageQueueManager:
    """Manager for multiple message queues."""
    
    def __init__(self):
        self.queues: Dict[str, MessageQueue] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a new message queue."""
        with self._lock:
            if config.name in self.queues:
                raise IntegrationError(f"Queue '{config.name}' already exists")
            
            queue = MessageQueue(config)
            self.queues[config.name] = queue
            self.logger.info(f"Created message queue: {config.name}")
            
            return queue
    
    def delete_queue(self, queue_name: str) -> bool:
        """Delete a message queue."""
        with self._lock:
            if queue_name in self.queues:
                queue = self.queues[queue_name]
                queue.stop()
                del self.queues[queue_name]
                self.logger.info(f"Deleted message queue: {queue_name}")
                return True
            return False
    
    def get_queue(self, queue_name: str) -> Optional[MessageQueue]:
        """Get a queue by name."""
        with self._lock:
            return self.queues.get(queue_name)
    
    def list_queues(self) -> List[MessageQueue]:
        """List all queues."""
        with self._lock:
            return list(self.queues.values())
    
    def start_queue(self, queue_name: str) -> bool:
        """Start a queue."""
        queue = self.get_queue(queue_name)
        if not queue:
            raise IntegrationNotFoundError(f"Queue '{queue_name}' not found")
        
        queue.start()
        return True
    
    def stop_queue(self, queue_name: str) -> bool:
        """Stop a queue."""
        queue = self.get_queue(queue_name)
        if not queue:
            raise IntegrationNotFoundError(f"Queue '{queue_name}' not found")
        
        queue.stop()
        return True
    
    def send_message(
        self,
        queue_name: str,
        payload: Any,
        priority: Priority = Priority.NORMAL,
        **kwargs: Any
    ) -> bool:
        """Send a message to a queue."""
        queue = self.get_queue(queue_name)
        if not queue:
            raise IntegrationNotFoundError(f"Queue '{queue_name}' not found")
        
        message = QueueMessage(
            payload=payload,
            priority=priority,
            **kwargs
        )
        
        return queue.enqueue(message)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all queues."""
        metrics = {}
        
        for queue_name, queue in self.queues.items():
            try:
                metrics[queue_name] = queue.get_metrics().to_dict()
            except Exception as e:
                metrics[queue_name] = {"error": str(e)}
        
        return {
            "queues": metrics,
            "total_queues": len(self.queues),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all queues."""
        status = {}
        
        for queue_name, queue in self.queues.items():
            try:
                status[queue_name] = queue.get_status()
            except Exception as e:
                status[queue_name] = {"error": str(e)}
        
        return {
            "queues": status,
            "total_queues": len(self.queues),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def shutdown_all(self) -> None:
        """Shutdown all queues."""
        for queue_name, queue in self.queues.items():
            try:
                queue.stop()
            except Exception as e:
                self.logger.error(f"Error stopping queue '{queue_name}': {e}")
        
        self.logger.info("All message queues shutdown")


# Global message queue manager instance
message_queue_manager = MessageQueueManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_queue(
    name: str,
    queue_type: QueueType = QueueType.FIFO,
    max_size: int = 10000,
    **kwargs: Any
) -> MessageQueue:
    """Create a message queue."""
    config = QueueConfig(
        name=name,
        queue_type=queue_type,
        max_size=max_size,
        **kwargs
    )
    
    return message_queue_manager.create_queue(config)


def send_message(
    queue_name: str,
    payload: Any,
    priority: Priority = Priority.NORMAL,
    **kwargs: Any
) -> bool:
    """Send a message to a queue."""
    return message_queue_manager.send_message(queue_name, payload, priority, **kwargs)


# Initialize logging
logger.info("Message queue module initialized")
