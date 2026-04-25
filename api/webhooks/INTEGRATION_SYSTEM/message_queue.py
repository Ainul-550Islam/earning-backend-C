"""Message Queue System

This module provides high-traffic message queue functionality for integration system
with comprehensive message processing, routing, and load balancing capabilities.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import uuid

from .integ_constants import QueueType, HealthStatus
from .integ_exceptions import QueueError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class Message:
    """
    Message class for message queue system.
    Represents a message with metadata and payload.
    """
    
    def __init__(self, payload: Dict[str, Any], **kwargs):
        """Initialize a message."""
        self.id = str(uuid.uuid4())
        self.payload = payload
        self.timestamp = kwargs.get('timestamp', timezone.now())
        self.source = kwargs.get('source', 'unknown')
        self.destination = kwargs.get('destination', 'default')
        self.priority = kwargs.get('priority', 'normal')
        self.headers = kwargs.get('headers', {})
        self.metadata = kwargs.get('metadata', {})
        self.retry_count = kwargs.get('retry_count', 0)
        self.max_retries = kwargs.get('max_retries', 3)
        self.timeout = kwargs.get('timeout', 30)
        self.delay_until = kwargs.get('delay_until', None)
        
        # Add system metadata
        self.metadata.update({
            'message_id': self.id,
            'created_at': self.timestamp.isoformat(),
            'queue_system': True
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            'id': self.id,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'destination': self.destination,
            'priority': self.priority,
            'headers': self.headers,
            'metadata': self.metadata,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'delay_until': self.delay_until.isoformat() if self.delay_until else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        delay_until = None
        if data.get('delay_until'):
            delay_until = timezone.parse(data['delay_until'])
        
        return cls(
            payload=data['payload'],
            timestamp=timezone.parse(data['timestamp']),
            source=data.get('source'),
            destination=data.get('destination'),
            priority=data.get('priority', 'normal'),
            headers=data.get('headers', {}),
            metadata=data.get('metadata', {}),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout=data.get('timeout', 30),
            delay_until=delay_until
        )
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries
    
    def is_ready(self) -> bool:
        """Check if message is ready for processing."""
        if self.delay_until:
            return timezone.now() >= self.delay_until
        return True
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1


class Queue:
    """
    Queue class for message queue system.
    Represents a message queue with processing logic.
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        """Initialize a queue."""
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Queue storage
        self.messages = []
        self.processing = []
        self.dead_letter = []
        
        # Configuration
        self.max_size = self.config.get('max_size', 10000)
        self.max_processing = self.config.get('max_processing', 100)
        self.max_dead_letter = self.config.get('max_dead_letter', 1000)
        self.enable_priority = self.config.get('enable_priority', True)
        self.enable_dead_letter = self.config.get('enable_dead_letter', True)
        
        # Statistics
        self.stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'dead_lettered_messages': 0,
            'created_at': timezone.now()
        }
    
    def enqueue(self, message: Message) -> bool:
        """
        Enqueue a message.
        
        Args:
            message: Message to enqueue
            
        Returns:
            True if enqueue successful
        """
        try:
            # Check queue size limit
            if len(self.messages) >= self.max_size:
                self.logger.warning(f"Queue {self.name} is full")
                return False
            
            # Add to queue
            self.messages.append(message)
            self.stats['total_messages'] += 1
            
            # Sort by priority if enabled
            if self.enable_priority:
                self._sort_by_priority()
            
            self.logger.debug(f"Message {message.id} enqueued in {self.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error enqueuing message: {str(e)}")
            return False
    
    def dequeue(self) -> Optional[Message]:
        """
        Dequeue a message.
        
        Returns:
            Message or None
        """
        try:
            # Check processing limit
            if len(self.processing) >= self.max_processing:
                return None
            
            # Find ready message
            for i, message in enumerate(self.messages):
                if message.is_ready():
                    # Move to processing
                    self.messages.pop(i)
                    self.processing.append(message)
                    return message
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error dequeuing message: {str(e)}")
            return None
    
    def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge message processing.
        
        Args:
            message_id: Message ID
            
        Returns:
            True if acknowledge successful
        """
        try:
            for i, message in enumerate(self.processing):
                if message.id == message_id:
                    self.processing.pop(i)
                    self.stats['processed_messages'] += 1
                    self.logger.debug(f"Message {message_id} acknowledged")
                    return True
            
            self.logger.warning(f"Message {message_id} not found in processing")
            return False
            
        except Exception as e:
            self.logger.error(f"Error acknowledging message: {str(e)}")
            return False
    
    def reject(self, message_id: str, error: str = None) -> bool:
        """
        Reject message processing.
        
        Args:
            message_id: Message ID
            error: Optional error message
            
        Returns:
            True if reject successful
        """
        try:
            for i, message in enumerate(self.processing):
                if message.id == message_id:
                    message = self.processing.pop(i)
                    
                    # Add error to metadata
                    if error:
                        message.metadata['last_error'] = error
                    
                    # Check if can retry
                    if message.can_retry():
                        message.increment_retry()
                        self.messages.append(message)
                        self.logger.debug(f"Message {message_id} rejected, retrying")
                    else:
                        # Move to dead letter
                        if self.enable_dead_letter:
                            self.dead_letter.append(message)
                            self.stats['dead_lettered_messages'] += 1
                            self.logger.debug(f"Message {message_id} moved to dead letter")
                        else:
                            self.logger.debug(f"Message {message_id} rejected, no retry")
                    
                    self.stats['failed_messages'] += 1
                    return True
            
            self.logger.warning(f"Message {message_id} not found in processing")
            return False
            
        except Exception as e:
            self.logger.error(f"Error rejecting message: {str(e)}")
            return False
    
    def _sort_by_priority(self):
        """Sort messages by priority."""
        try:
            priority_order = {'high': 0, 'normal': 1, 'low': 2}
            self.messages.sort(key=lambda m: priority_order.get(m.priority, 1))
        except Exception as e:
            self.logger.error(f"Error sorting by priority: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'queue_name': self.name,
            'queue_size': len(self.messages),
            'processing_size': len(self.processing),
            'dead_letter_size': len(self.dead_letter),
            'max_size': self.max_size,
            'stats': self.stats.copy()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of queue."""
        try:
            status = HealthStatus.HEALTHY
            
            # Check queue size
            if len(self.messages) >= self.max_size * 0.9:
                status = HealthStatus.DEGRADED
            if len(self.messages) >= self.max_size:
                status = HealthStatus.UNHEALTHY
            
            # Check processing backlog
            if len(self.processing) >= self.max_processing * 0.9:
                status = HealthStatus.DEGRADED
            if len(self.processing) >= self.max_processing:
                status = HealthStatus.UNHEALTHY
            
            return {
                'status': status,
                'queue_name': self.name,
                'queue_size': len(self.messages),
                'processing_size': len(self.processing),
                'dead_letter_size': len(self.dead_letter),
                'max_size': self.max_size,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class MessageQueue:
    """
    Main message queue for integration system.
    Provides comprehensive message processing and routing.
    """
    
    def __init__(self):
        """Initialize the message queue."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Queue storage
        self.queues = {}
        self.processors = {}
        self.consumers = {}
        
        # Load configuration
        self._load_configuration()
        
        # Initialize queue system
        self._initialize_queue_system()
    
    def _load_configuration(self):
        """Load queue configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_MESSAGE_QUEUE_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.default_queue_config = self.config.get('default_queue', {})
            self.max_queues = self.config.get('max_queues', 100)
            self.enable_persistence = self.config.get('enable_persistence', True)
            self.enable_dead_letter = self.config.get('enable_dead_letter', True)
            
            self.logger.info("Message queue configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading message queue configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.default_queue_config = {}
            self.max_queues = 100
            self.enable_persistence = True
            self.enable_dead_letter = True
    
    def _initialize_queue_system(self):
        """Initialize the queue system."""
        try:
            # Create default queues
            default_queues = self.config.get('queues', {})
            for queue_name, queue_config in default_queues.items():
                self.create_queue(queue_name, queue_config)
            
            # Initialize processors
            self._initialize_processors()
            
            # Start consumers
            self._start_consumers()
            
            self.logger.info(f"Message queue system initialized with {len(self.queues)} queues")
            
        except Exception as e:
            self.logger.error(f"Error initializing queue system: {str(e)}")
    
    def _initialize_processors(self):
        """Initialize message processors."""
        try:
            processor_configs = self.config.get('processors', {})
            
            for processor_name, processor_config in processor_configs.items():
                if processor_config.get('enabled', True):
                    self.processors[processor_name] = self._create_processor(processor_config)
            
        except Exception as e:
            self.logger.error(f"Error initializing processors: {str(e)}")
    
    def _start_consumers(self):
        """Start message consumers."""
        try:
            consumer_configs = self.config.get('consumers', {})
            
            for consumer_name, consumer_config in consumer_configs.items():
                if consumer_config.get('enabled', True):
                    self.consumers[consumer_name] = self._create_consumer(consumer_config)
            
        except Exception as e:
            self.logger.error(f"Error starting consumers: {str(e)}")
    
    def _create_processor(self, config: Dict[str, Any]):
        """Create a message processor."""
        try:
            processor_type = config.get('type')
            
            if processor_type == 'webhook':
                return WebhookMessageProcessor(config)
            elif processor_type == 'integration':
                return IntegrationMessageProcessor(config)
            elif processor_type == 'custom':
                return CustomMessageProcessor(config)
            else:
                raise QueueError(f"Unknown processor type: {processor_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating processor: {str(e)}")
            raise
    
    def _create_consumer(self, config: Dict[str, Any]):
        """Create a message consumer."""
        try:
            consumer_type = config.get('type')
            
            if consumer_type == 'worker':
                return WorkerConsumer(config)
            elif consumer_type == 'scheduler':
                return SchedulerConsumer(config)
            elif consumer_type == 'custom':
                return CustomConsumer(config)
            else:
                raise QueueError(f"Unknown consumer type: {consumer_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating consumer: {str(e)}")
            raise
    
    def create_queue(self, name: str, config: Dict[str, Any] = None) -> bool:
        """
        Create a new queue.
        
        Args:
            name: Queue name
            config: Queue configuration
            
        Returns:
            True if creation successful
        """
        try:
            # Check queue limit
            if len(self.queues) >= self.max_queues:
                raise QueueError(f"Maximum queues limit reached: {self.max_queues}")
            
            # Merge with default config
            queue_config = {**self.default_queue_config, **(config or {})}
            
            # Create queue
            self.queues[name] = Queue(name, queue_config)
            
            self.logger.info(f"Queue {name} created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating queue {name}: {str(e)}")
            return False
    
    def delete_queue(self, name: str) -> bool:
        """
        Delete a queue.
        
        Args:
            name: Queue name
            
        Returns:
            True if deletion successful
        """
        try:
            if name in self.queues:
                del self.queues[name]
                self.logger.info(f"Queue {name} deleted successfully")
                return True
            else:
                self.logger.warning(f"Queue {name} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting queue {name}: {str(e)}")
            return False
    
    def send_message(self, message: Message, queue_name: str = 'default') -> bool:
        """
        Send a message to a queue.
        
        Args:
            message: Message to send
            queue_name: Target queue name
            
        Returns:
            True if send successful
        """
        try:
            if not self.enabled:
                raise QueueError("Message queue is disabled")
            
            # Create queue if not exists
            if queue_name not in self.queues:
                if not self.create_queue(queue_name):
                    return False
            
            # Send message
            queue = self.queues[queue_name]
            success = queue.enqueue(message)
            
            if success:
                # Persist if enabled
                if self.enable_persistence:
                    self._persist_message(message, queue_name)
                
                self.logger.info(f"Message {message.id} sent to queue {queue_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            return False
    
    def receive_message(self, queue_name: str = 'default') -> Optional[Message]:
        """
        Receive a message from a queue.
        
        Args:
            queue_name: Source queue name
            
        Returns:
            Message or None
        """
        try:
            if queue_name not in self.queues:
                return None
            
            queue = self.queues[queue_name]
            return queue.dequeue()
            
        except Exception as e:
            self.logger.error(f"Error receiving message: {str(e)}")
            return None
    
    def acknowledge_message(self, message_id: str, queue_name: str = 'default') -> bool:
        """
        Acknowledge message processing.
        
        Args:
            message_id: Message ID
            queue_name: Queue name
            
        Returns:
            True if acknowledge successful
        """
        try:
            if queue_name not in self.queues:
                return False
            
            queue = self.queues[queue_name]
            success = queue.acknowledge(message_id)
            
            if success:
                # Update persistence
                if self.enable_persistence:
                    self._update_message_status(message_id, 'acknowledged')
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error acknowledging message: {str(e)}")
            return False
    
    def reject_message(self, message_id: str, queue_name: str = 'default', error: str = None) -> bool:
        """
        Reject message processing.
        
        Args:
            message_id: Message ID
            queue_name: Queue name
            error: Optional error message
            
        Returns:
            True if reject successful
        """
        try:
            if queue_name not in self.queues:
                return False
            
            queue = self.queues[queue_name]
            success = queue.reject(message_id, error)
            
            if success:
                # Update persistence
                if self.enable_persistence:
                    self._update_message_status(message_id, 'rejected', error)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error rejecting message: {str(e)}")
            return False
    
    def get_queue_stats(self, queue_name: str = None) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Args:
            queue_name: Optional queue name
            
        Returns:
            Queue statistics
        """
        try:
            if queue_name:
                if queue_name in self.queues:
                    return self.queues[queue_name].get_stats()
                else:
                    return {'error': f'Queue {queue_name} not found'}
            else:
                return {
                    'total_queues': len(self.queues),
                    'queues': {
                        name: queue.get_stats()
                        for name, queue in self.queues.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting queue stats: {str(e)}")
            return {'error': str(e)}
    
    def process_messages(self, queue_name: str = 'default', processor_name: str = None) -> Dict[str, Any]:
        """
        Process messages from queue.
        
        Args:
            queue_name: Queue name
            processor_name: Processor name
            
        Returns:
            Processing results
        """
        try:
            if queue_name not in self.queues:
                return {'error': f'Queue {queue_name} not found'}
            
            queue = self.queues[queue_name]
            processor = self.processors.get(processor_name) if processor_name else None
            
            results = {
                'queue_name': queue_name,
                'processor': processor_name,
                'processed': 0,
                'failed': 0,
                'errors': []
            }
            
            # Process messages
            while True:
                message = queue.dequeue()
                if not message:
                    break
                
                try:
                    # Process message
                    if processor:
                        success = processor.process(message)
                    else:
                        success = self._default_process_message(message)
                    
                    if success:
                        queue.acknowledge(message.id)
                        results['processed'] += 1
                    else:
                        queue.reject(message.id, "Processing failed")
                        results['failed'] += 1
                        
                except Exception as e:
                    queue.reject(message.id, str(e))
                    results['failed'] += 1
                    results['errors'].append(str(e))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing messages: {str(e)}")
            return {
                'error': str(e),
                'queue_name': queue_name,
                'processor': processor_name
            }
    
    def _default_process_message(self, message: Message) -> bool:
        """Default message processing."""
        try:
            # Log message
            self.logger.info(f"Processing message {message.id} from {message.source}")
            
            # Add processing metadata
            message.metadata['processed_at'] = timezone.now().isoformat()
            message.metadata['processed_by'] = 'default_processor'
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in default processing: {str(e)}")
            return False
    
    def _persist_message(self, message: Message, queue_name: str):
        """Persist message to storage."""
        try:
            # This would integrate with your persistence layer
            # For now, just log the operation
            self.logger.debug(f"Persisting message {message.id} to queue {queue_name}")
            
        except Exception as e:
            self.logger.error(f"Error persisting message: {str(e)}")
    
    def _update_message_status(self, message_id: str, status: str, error: str = None):
        """Update message status in storage."""
        try:
            # This would integrate with your persistence layer
            # For now, just log the operation
            self.logger.debug(f"Updating message {message_id} status to {status}")
            
        except Exception as e:
            self.logger.error(f"Error updating message status: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of message queue system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check queues
            for queue_name, queue in self.queues.items():
                queue_health = queue.health_check()
                health_status['components'][queue_name] = queue_health
                
                if queue_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check processors
            health_status['components']['processors'] = {
                'status': HealthStatus.HEALTHY,
                'total_processors': len(self.processors)
            }
            
            # Check consumers
            health_status['components']['consumers'] = {
                'status': HealthStatus.HEALTHY,
                'total_consumers': len(self.consumers)
            }
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get message queue system status.
        
        Returns:
            System status
        """
        try:
            return {
                'message_queue': {
                    'status': 'running' if self.enabled else 'disabled',
                    'total_queues': len(self.queues),
                    'total_processors': len(self.processors),
                    'total_consumers': len(self.consumers),
                    'enable_persistence': self.enable_persistence,
                    'enable_dead_letter': self.enable_dead_letter,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'queues': {
                    name: queue.get_stats()
                    for name, queue in self.queues.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            return {'error': str(e)}


class WebhookMessageProcessor:
    """Webhook message processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the webhook processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, message: Message) -> bool:
        """Process webhook message."""
        try:
            # Process webhook payload
            payload = message.payload
            
            # Validate webhook data
            if not self._validate_webhook_payload(payload):
                return False
            
            # Process webhook
            success = self._process_webhook(payload)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing webhook message: {str(e)}")
            return False
    
    def _validate_webhook_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate webhook payload."""
        try:
            # Basic validation
            if not isinstance(payload, dict):
                return False
            
            if 'event_type' not in payload:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating webhook payload: {str(e)}")
            return False
    
    def _process_webhook(self, payload: Dict[str, Any]) -> bool:
        """Process webhook."""
        try:
            # This would integrate with your webhook processing system
            self.logger.info(f"Processing webhook: {payload.get('event_type')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing webhook: {str(e)}")
            return False


class IntegrationMessageProcessor:
    """Integration message processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the integration processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, message: Message) -> bool:
        """Process integration message."""
        try:
            # Process integration payload
            payload = message.payload
            
            # Validate integration data
            if not self._validate_integration_payload(payload):
                return False
            
            # Process integration
            success = self._process_integration(payload)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing integration message: {str(e)}")
            return False
    
    def _validate_integration_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate integration payload."""
        try:
            # Basic validation
            if not isinstance(payload, dict):
                return False
            
            if 'integration_type' not in payload:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating integration payload: {str(e)}")
            return False
    
    def _process_integration(self, payload: Dict[str, Any]) -> bool:
        """Process integration."""
        try:
            # This would integrate with your integration processing system
            self.logger.info(f"Processing integration: {payload.get('integration_type')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing integration: {str(e)}")
            return False


class CustomMessageProcessor:
    """Custom message processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the custom processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, message: Message) -> bool:
        """Process custom message."""
        try:
            # Get custom processor function
            processor_path = self.config.get('processor_function')
            if not processor_path:
                self.logger.error("No processor function specified")
                return False
            
            # Import and execute processor
            module_path, function_name = processor_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            processor_func = getattr(module, function_name)
            
            return processor_func(message)
            
        except Exception as e:
            self.logger.error(f"Error processing custom message: {str(e)}")
            return False


class WorkerConsumer:
    """Worker consumer for message processing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the worker consumer."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.running = False
        
        # Configuration
        self.queue_name = self.config.get('queue', 'default')
        self.processor_name = self.config.get('processor')
        self.poll_interval = self.config.get('poll_interval', 1)
        self.max_batch_size = self.config.get('max_batch_size', 10)
    
    def start(self):
        """Start the worker consumer."""
        try:
            self.running = True
            self.logger.info(f"Worker consumer started for queue {self.queue_name}")
            
            while self.running:
                # Process messages
                self._process_batch()
                
                # Sleep between batches
                time.sleep(self.poll_interval)
                
        except Exception as e:
            self.logger.error(f"Error in worker consumer: {str(e)}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the worker consumer."""
        self.running = False
        self.logger.info(f"Worker consumer stopped for queue {self.queue_name}")
    
    def _process_batch(self):
        """Process a batch of messages."""
        try:
            from .message_queue import message_queue
            
            processed = 0
            while processed < self.max_batch_size:
                message = message_queue.receive_message(self.queue_name)
                if not message:
                    break
                
                # Process message
                success = message_queue.process_messages(
                    self.queue_name,
                    self.processor_name
                )
                
                processed += 1
                
        except Exception as e:
            self.logger.error(f"Error processing batch: {str(e)}")


class SchedulerConsumer:
    """Scheduler consumer for delayed message processing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the scheduler consumer."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.running = False
        
        # Configuration
        self.check_interval = self.config.get('check_interval', 60)  # seconds
    
    def start(self):
        """Start the scheduler consumer."""
        try:
            self.running = True
            self.logger.info("Scheduler consumer started")
            
            while self.running:
                # Check for delayed messages
                self._check_delayed_messages()
                
                # Sleep between checks
                time.sleep(self.check_interval)
                
        except Exception as e:
            self.logger.error(f"Error in scheduler consumer: {str(e)}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the scheduler consumer."""
        self.running = False
        self.logger.info("Scheduler consumer stopped")
    
    def _check_delayed_messages(self):
        """Check for delayed messages ready for processing."""
        try:
            from .message_queue import message_queue
            
            # Check all queues for delayed messages
            for queue_name, queue in message_queue.queues.items():
                ready_messages = []
                
                # Find ready messages
                for message in queue.messages:
                    if message.is_ready():
                        ready_messages.append(message)
                
                # Move ready messages to front
                for message in ready_messages:
                    queue.messages.remove(message)
                    queue.messages.insert(0, message)
                
                if ready_messages:
                    self.logger.info(f"Moved {len(ready_messages)} delayed messages to front of queue {queue_name}")
                
        except Exception as e:
            self.logger.error(f"Error checking delayed messages: {str(e)}")


class CustomConsumer:
    """Custom consumer for message processing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the custom consumer."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.running = False
    
    def start(self):
        """Start the custom consumer."""
        try:
            self.running = True
            self.logger.info("Custom consumer started")
            
            # Get custom consumer function
            consumer_path = self.config.get('consumer_function')
            if not consumer_path:
                self.logger.error("No consumer function specified")
                return
            
            # Import and execute consumer
            module_path, function_name = consumer_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            consumer_func = getattr(module, function_name)
            
            consumer_func(self.config)
            
        except Exception as e:
            self.logger.error(f"Error in custom consumer: {str(e)}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the custom consumer."""
        self.running = False
        self.logger.info("Custom consumer stopped")


# Global message queue instance
message_queue = MessageQueue()
