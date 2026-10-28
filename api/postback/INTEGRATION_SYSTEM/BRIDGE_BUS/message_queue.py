"""
message_queue.py – High Traffic Message Queue Manager for postback module.

Provides comprehensive message queue functionality including:
- High-throughput message processing
- Queue management and monitoring
- Message routing and filtering
- Load balancing and scaling
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import queue
import json
import time
import hashlib
from collections import defaultdict, deque

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationType, IntegrationProtocol
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class QueueType(Enum):
    """Queue type enumeration."""
    FIFO = "fifo"
    LIFO = "lifo"
    PRIORITY = "priority"
    DELAYED = "delayed"
    DEAD_LETTER = "dead_letter"
    RETRY = "retry"


class MessageStatus(Enum):
    """Message status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


class MessageType(Enum):
    """Message type enumeration."""
    WEBHOOK = "webhook"
    POSTBACK = "postback"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class Message:
    """Message data structure."""
    id: str
    message_type: MessageType
    payload: Dict[str, Any]
    headers: Dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    timestamp: datetime = field(default_factory=timezone.now)
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    delay_until: Optional[datetime] = None
    ttl: Optional[int] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'message_type': self.message_type.value,
            'payload': self.payload,
            'headers': self.headers,
            'priority': self.priority,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'delay_until': self.delay_until.isoformat() if self.delay_until else None,
            'ttl': self.ttl,
            'correlation_id': self.correlation_id,
            'causation_id': self.causation_id,
            'metadata': self.metadata,
        }
    
    def is_expired(self) -> bool:
        """Check if message is expired."""
        if not self.ttl:
            return False
        return timezone.now() > self.timestamp + timedelta(seconds=self.ttl)
    
    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.retry_count < self.max_retries
    
    def calculate_backoff(self, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay."""
        return base_delay * (2 ** self.retry_count)


@dataclass
class QueueConfig:
    """Queue configuration."""
    name: str
    queue_type: QueueType
    max_size: int = 10000
    max_workers: int = 5
    batch_size: int = 100
    batch_timeout: int = 5
    dead_letter_queue: Optional[str] = None
    retry_queue: Optional[str] = None
    message_ttl: int = 3600
    enable_persistence: bool = True
    enable_compression: bool = False
    enable_deduplication: bool = True
    deduplication_window: int = 300  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageQueue:
    """
    High-performance message queue implementation.
    
    Handles message queuing, processing, and management
    with support for high traffic scenarios.
    """
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.name = config.name
        self.queue_type = config.queue_type
        self.max_size = config.max_size
        self.max_workers = config.max_workers
        self.batch_size = config.batch_size
        self.batch_timeout = config.batch_timeout
        
        # Queue implementations
        if config.queue_type == QueueType.FIFO:
            self.queue = queue.Queue(maxsize=config.max_size)
        elif config.queue_type == QueueType.PRIORITY:
            self.queue = queue.PriorityQueue(maxsize=config.max_size)
        elif config.queue_type == QueueType.DELAYED:
            self.queue = queue.PriorityQueue(maxsize=config.max_size)
        else:
            self.queue = queue.Queue(maxsize=config.max_size)
        
        # Worker threads
        self.workers: List[threading.Thread] = []
        self.running = False
        self.worker_lock = threading.Lock()
        
        # Statistics
        self.total_messages = 0
        self.processed_messages = 0
        self.failed_messages = 0
        self.dead_letter_messages = 0
        self.queue_size = 0
        self.avg_processing_time = 0.0
        self.total_processing_time = 0.0
        
        # Message handlers
        self.handlers: Dict[MessageType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        
        # Deduplication
        self.deduplication_cache = set()
        self.last_cleanup = timezone.now()
        
        self.logger = logging.getLogger(f"message_queue.{self.name}")
    
    def start(self):
        """Start message queue workers."""
        with self.worker_lock:
            if self.running:
                return
            
            self.running = True
            
            # Start worker threads
            for i in range(self.max_workers):
                worker = threading.Thread(target=self._worker_loop, name=f"worker-{i}", daemon=True)
                worker.start()
                self.workers.append(worker)
            
            self.logger.info(f"Message queue started: {self.name} with {self.max_workers} workers")
    
    def stop(self):
        """Stop message queue workers."""
        with self.worker_lock:
            if not self.running:
                return
            
            self.running = False
            
            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=5)
            
            self.workers.clear()
            self.logger.info(f"Message queue stopped: {self.name}")
    
    def enqueue(self, message: Message) -> bool:
        """
        Enqueue message.
        
        Args:
            message: Message to enqueue
            
        Returns:
            True if enqueued successfully
        """
        try:
            # Check queue size
            if self.queue_size >= self.max_size:
                self.logger.warning(f"Queue full: {self.name}")
                return False
            
            # Check TTL
            if message.is_expired():
                self.logger.warning(f"Message expired: {message.id}")
                return False
            
            # Deduplication
            if self.config.enable_deduplication:
                message_hash = self._calculate_message_hash(message)
                if message_hash in self.deduplication_cache:
                    self.logger.debug(f"Duplicate message: {message.id}")
                    return False
                
                self.deduplication_cache.add(message_hash)
                self._cleanup_deduplication_cache()
            
            # Handle delayed messages
            if message.delay_until and message.delay_until > timezone.now():
                # Add to delayed queue
                priority = message.delay_until.timestamp()
                self.queue.put((priority, message))
            else:
                # Add to regular queue
                if self.queue_type == QueueType.PRIORITY:
                    priority = 100 - message.priority  # Higher priority = lower number
                    self.queue.put((priority, message))
                else:
                    self.queue.put(message)
            
            self.total_messages += 1
            self.queue_size += 1
            
            self.logger.debug(f"Message enqueued: {message.id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error enqueuing message: {str(e)}")
            return False
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Message]:
        """
        Dequeue message.
        
        Args:
            timeout: Dequeue timeout
            
        Returns:
            Message or None
        """
        try:
            if self.queue_type == QueueType.DELAYED:
                # Check for delayed messages
                while True:
                    if self.queue.empty():
                        return None
                    
                    priority, message = self.queue.get(timeout=timeout)
                    
                    if message.delay_until and message.delay_until > timezone.now():
                        # Put back and wait
                        self.queue.put((priority, message))
                        time.sleep(0.1)
                        continue
                    else:
                        self.queue_size -= 1
                        return message
            else:
                if self.queue_type == QueueType.PRIORITY:
                    priority, message = self.queue.get(timeout=timeout)
                else:
                    message = self.queue.get(timeout=timeout)
                
                self.queue_size -= 1
                return message
        
        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"Error dequeuing message: {str(e)}")
            return None
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register message handler.
        
        Args:
            message_type: Message type
            handler: Handler function
        """
        if message_type not in self.handlers:
            self.handlers[message_type] = []
        
        self.handlers[message_type].append(handler)
        self.logger.info(f"Handler registered for {message_type.value}")
    
    def register_global_handler(self, handler: Callable):
        """
        Register global message handler.
        
        Args:
            handler: Handler function
        """
        self.global_handlers.append(handler)
        self.logger.info("Global handler registered")
    
    def _worker_loop(self):
        """Worker thread loop."""
        batch = []
        batch_start_time = time.time()
        
        while self.running:
            try:
                # Collect batch
                while len(batch) < self.batch_size and (time.time() - batch_start_time) < self.batch_timeout:
                    message = self.dequeue(timeout=0.1)
                    if message:
                        batch.append(message)
                    else:
                        break
                
                # Process batch
                if batch:
                    self._process_batch(batch)
                    batch.clear()
                    batch_start_time = time.time()
                else:
                    # No messages, wait a bit
                    time.sleep(0.1)
            
            except Exception as e:
                self.logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(1)
    
    def _process_batch(self, batch: List[Message]):
        """Process batch of messages."""
        for message in batch:
            try:
                self._process_message(message)
            except Exception as e:
                self.logger.error(f"Error processing message {message.id}: {str(e)}")
                self._handle_failed_message(message, str(e))
    
    def _process_message(self, message: Message):
        """Process single message."""
        start_time = time.time()
        
        try:
            # Update status
            message.status = MessageStatus.PROCESSING
            
            # Check TTL
            if message.is_expired():
                self.logger.warning(f"Message expired during processing: {message.id}")
                self._handle_expired_message(message)
                return
            
            # Process with global handlers
            for handler in self.global_handlers:
                try:
                    handler(message)
                except Exception as e:
                    self.logger.error(f"Error in global handler: {str(e)}")
            
            # Process with specific handlers
            if message.message_type in self.handlers:
                for handler in self.handlers[message.message_type]:
                    try:
                        handler(message)
                    except Exception as e:
                        self.logger.error(f"Error in handler: {str(e)}")
                        raise
            
            # Mark as completed
            message.status = MessageStatus.COMPLETED
            self.processed_messages += 1
            
            # Update processing time
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            self.avg_processing_time = self.total_processing_time / self.processed_messages
            
            self.logger.debug(f"Message processed: {message.id}")
        
        except Exception as e:
            self._handle_failed_message(message, str(e))
    
    def _handle_failed_message(self, message: Message, error: str):
        """Handle failed message."""
        message.status = MessageStatus.FAILED
        self.failed_messages += 1
        
        # Check if should retry
        if message.should_retry():
            message.retry_count += 1
            message.status = MessageStatus.RETRY
            
            # Calculate backoff delay
            backoff = message.calculate_backoff()
            message.delay_until = timezone.now() + timedelta(seconds=backoff)
            
            # Re-enqueue with delay
            self.enqueue(message)
            self.logger.info(f"Message retry scheduled: {message.id} (attempt {message.retry_count})")
        else:
            # Send to dead letter queue
            self._send_to_dead_letter(message, error)
    
    def _handle_expired_message(self, message: Message):
        """Handle expired message."""
        message.status = MessageStatus.DEAD_LETTER
        self.dead_letter_messages += 1
        self._send_to_dead_letter(message, "Message expired")
    
    def _send_to_dead_letter(self, message: Message, error: str):
        """Send message to dead letter queue."""
        if self.config.dead_letter_queue:
            # This would integrate with other queue systems
            # For now, just log
            self.logger.warning(f"Message sent to dead letter: {message.id} - {error}")
    
    def _calculate_message_hash(self, message: Message) -> str:
        """Calculate message hash for deduplication."""
        content = json.dumps(message.payload, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _cleanup_deduplication_cache(self):
        """Cleanup deduplication cache."""
        if timezone.now() - self.last_cleanup > timedelta(seconds=60):
            # Clear cache
            self.deduplication_cache.clear()
            self.last_cleanup = timezone.now()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'name': self.name,
            'queue_type': self.queue_type.value,
            'total_messages': self.total_messages,
            'processed_messages': self.processed_messages,
            'failed_messages': self.failed_messages,
            'dead_letter_messages': self.dead_letter_messages,
            'queue_size': self.queue_size,
            'max_size': self.max_size,
            'workers': len(self.workers),
            'running': self.running,
            'avg_processing_time': self.avg_processing_time,
            'success_rate': (self.processed_messages / self.total_messages * 100) if self.total_messages > 0 else 0,
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            'overall': 'healthy',
            'queue_size': self.queue_size,
            'max_size': self.max_size,
            'workers': len(self.workers),
            'running': self.running,
            'issues': [],
        }
        
        # Check queue size
        if self.queue_size > self.max_size * 0.9:
            health_status['overall'] = 'degraded'
            health_status['issues'].append(f"Queue nearly full: {self.queue_size}/{self.max_size}")
        
        # Check workers
        if not self.running or len(self.workers) == 0:
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append("No active workers")
        
        # Check failure rate
        if self.total_messages > 0:
            failure_rate = (self.failed_messages / self.total_messages) * 100
            if failure_rate > 10:
                health_status['overall'] = 'degraded'
                health_status['issues'].append(f"High failure rate: {failure_rate:.2f}%")
        
        return health_status


class MessageQueueManager:
    """
    Manager for multiple message queues.
    
    Handles queue registration, lifecycle management,
    and monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.queues: Dict[str, MessageQueue] = {}
        self.queue_configs: Dict[str, QueueConfig] = {}
        self._setup_default_queues()
    
    def _setup_default_queues(self):
        """Setup default message queues."""
        default_configs = [
            QueueConfig(
                name="webhook_queue",
                queue_type=QueueType.PRIORITY,
                max_size=5000,
                max_workers=10,
                batch_size=50,
                dead_letter_queue="webhook_dead_letter",
                message_ttl=3600,
            ),
            QueueConfig(
                name="postback_queue",
                queue_type=QueueType.FIFO,
                max_size=10000,
                max_workers=5,
                batch_size=100,
                message_ttl=7200,
            ),
            QueueConfig(
                name="analytics_queue",
                queue_type=QueueType.DELAYED,
                max_size=2000,
                max_workers=3,
                batch_size=25,
                message_ttl=86400,
            ),
            QueueConfig(
                name="notification_queue",
                queue_type=QueueType.PRIORITY,
                max_size=3000,
                max_workers=8,
                batch_size=75,
                message_ttl=1800,
            ),
        ]
        
        for config in default_configs:
            self.create_queue(config)
    
    def create_queue(self, config: QueueConfig) -> bool:
        """
        Create message queue.
        
        Args:
            config: Queue configuration
            
        Returns:
            True if created successfully
        """
        try:
            queue = MessageQueue(config)
            self.queues[config.name] = queue
            self.queue_configs[config.name] = config
            self.logger.info(f"Message queue created: {config.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to create queue {config.name}: {str(e)}")
            return False
    
    def remove_queue(self, name: str) -> bool:
        """
        Remove message queue.
        
        Args:
            name: Queue name
            
        Returns:
            True if removed successfully
        """
        if name in self.queues:
            queue = self.queues[name]
            queue.stop()
            del self.queues[name]
            del self.queue_configs[name]
            self.logger.info(f"Message queue removed: {name}")
            return True
        return False
    
    def get_queue(self, name: str) -> Optional[MessageQueue]:
        """
        Get queue by name.
        
        Args:
            name: Queue name
            
        Returns:
            Queue or None
        """
        return self.queues.get(name)
    
    def start_queue(self, name: str) -> bool:
        """
        Start queue.
        
        Args:
            name: Queue name
            
        Returns:
            True if started successfully
        """
        queue = self.get_queue(name)
        if queue:
            queue.start()
            return True
        return False
    
    def stop_queue(self, name: str) -> bool:
        """
        Stop queue.
        
        Args:
            name: Queue name
            
        Returns:
            True if stopped successfully
        """
        queue = self.get_queue(name)
        if queue:
            queue.stop()
            return True
        return False
    
    def enqueue_message(self, queue_name: str, message: Message) -> bool:
        """
        Enqueue message to specific queue.
        
        Args:
            queue_name: Queue name
            message: Message to enqueue
            
        Returns:
            True if enqueued successfully
        """
        queue = self.get_queue(queue_name)
        if queue:
            return queue.enqueue(message)
        return False
    
    def broadcast_message(self, message: Message, queue_names: List[str] = None) -> Dict[str, bool]:
        """
        Broadcast message to multiple queues.
        
        Args:
            message: Message to broadcast
            queue_names: Queue names (None = all queues)
            
        Returns:
            Dictionary of queue names to success status
        """
        if queue_names is None:
            queue_names = list(self.queues.keys())
        
        results = {}
        for queue_name in queue_names:
            results[queue_name] = self.enqueue_message(queue_name, message)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {
            'total_queues': len(self.queues),
            'active_queues': len([q for q in self.queues.values() if q.running]),
            'queue_details': {},
            'queue_types': {},
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'dead_letter_messages': 0,
        }
        
        for name, queue in self.queues.items():
            queue_stats = queue.get_statistics()
            stats['queue_details'][name] = queue_stats
            
            # Aggregate totals
            stats['total_messages'] += queue_stats['total_messages']
            stats['processed_messages'] += queue_stats['processed_messages']
            stats['failed_messages'] += queue_stats['failed_messages']
            stats['dead_letter_messages'] += queue_stats['dead_letter_messages']
            
            # Count by type
            queue_type = queue_stats['queue_type']
            stats['queue_types'][queue_type] = stats['queue_types'].get(queue_type, 0) + 1
        
        # Calculate overall success rate
        if stats['total_messages'] > 0:
            stats['overall_success_rate'] = (stats['processed_messages'] / stats['total_messages']) * 100
        else:
            stats['overall_success_rate'] = 0
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all queues."""
        health_status = {
            'overall': 'healthy',
            'total_queues': len(self.queues),
            'healthy_queues': 0,
            'unhealthy_queues': 0,
            'queue_health': {},
            'issues': [],
        }
        
        for name, queue in self.queues.items():
            try:
                queue_health = queue.health_check()
                health_status['queue_health'][name] = queue_health
                
                if queue_health['overall'] == 'healthy':
                    health_status['healthy_queues'] += 1
                else:
                    health_status['unhealthy_queues'] += 1
                    health_status['issues'].append(f"Queue {name} is {queue_health['overall']}")
            
            except Exception as e:
                health_status['unhealthy_queues'] += 1
                health_status['issues'].append(f"Error checking queue {name}: {str(e)}")
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status


# Global message queue manager instance
message_queue_manager = MessageQueueManager()


# Convenience functions
def create_message_queue(config: QueueConfig) -> bool:
    """Create message queue."""
    return message_queue_manager.create_queue(config)


def enqueue_message(queue_name: str, message_type: MessageType, payload: Dict[str, Any],
                    priority: int = 50, headers: Dict[str, Any] = None,
                    correlation_id: str = None, causation_id: str = None) -> bool:
    """Enqueue message."""
    import uuid
    
    message = Message(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        message_type=message_type,
        payload=payload,
        headers=headers or {},
        priority=priority,
        correlation_id=correlation_id,
        causation_id=causation_id
    )
    
    return message_queue_manager.enqueue_message(queue_name, message)


def broadcast_message(message_type: MessageType, payload: Dict[str, Any],
                      queue_names: List[str] = None, priority: int = 50,
                      headers: Dict[str, Any] = None) -> Dict[str, bool]:
    """Broadcast message to multiple queues."""
    import uuid
    
    message = Message(
        id=f"msg_{uuid.uuid4().hex[:12]}",
        message_type=message_type,
        payload=payload,
        headers=headers or {},
        priority=priority
    )
    
    return message_queue_manager.broadcast_message(message, queue_names)


def get_message_queue_statistics() -> Dict[str, Any]:
    """Get message queue statistics."""
    return message_queue_manager.get_statistics()


def perform_message_queue_health_check() -> Dict[str, Any]:
    """Perform message queue health check."""
    return message_queue_manager.health_check()
