"""
Integration Message Queue - High traffic message queue manager
Provides safe message queuing with existing alerts architecture
"""
import logging
import json
import threading
import time
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty, Full
from dataclasses import dataclass
from enum import Enum

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS,
    DEFAULT_TIMEOUTS
)

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class MessageStatus(Enum):
    """Message status"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class IntegrationMessage:
    """Integration message data structure"""
    id: str
    message_type: str
    data: Dict[str, Any]
    priority: MessagePriority
    status: MessageStatus
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IntegrationMessageQueue:
    """
    High-performance message queue for integration system
    Maintains existing validation and security logic
    """
    
    def __init__(self, max_size: int = 10000, num_workers: int = 4, start_workers: bool = True):
        self.max_size = max_size
        self.num_workers = num_workers
        self.queues = {
            MessagePriority.EMERGENCY: Queue(maxsize=max_size // 10),
            MessagePriority.CRITICAL: Queue(maxsize=max_size // 10),
            MessagePriority.HIGH: Queue(maxsize=max_size // 4),
            MessagePriority.MEDIUM: Queue(maxsize=max_size // 2),
            MessagePriority.LOW: Queue(maxsize=max_size // 4)
        }
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self.message_handlers = {}
        self.queue_stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'queue_sizes': {},
            'last_activity': None
        }
        self.is_running = False
        self.worker_threads = []
        
        # Start workers (skipped in tests - see initialize_integration())
        if start_workers:
            self.start_workers()
    
    def start_workers(self):
        """
        Start worker threads
        """
        try:
            self.is_running = True
            
            for i in range(self.num_workers):
                worker = threading.Thread(target=self._worker_loop, name=f"MessageWorker-{i}")
                worker.daemon = True
                worker.start()
                self.worker_threads.append(worker)
            
            logger.info(f"Started {self.num_workers} message queue workers")
            
        except Exception as e:
            logger.error(f"Error starting workers: {e}")
            self.is_running = False
    
    def stop_workers(self):
        """
        Stop worker threads
        """
        try:
            self.is_running = False
            
            # Wait for workers to finish
            for worker in self.worker_threads:
                worker.join(timeout=5)
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Stopped message queue workers")
            
        except Exception as e:
            logger.error(f"Error stopping workers: {e}")
    
    def _worker_loop(self):
        """
        Worker thread loop
        """
        while self.is_running:
            try:
                # Get message from highest priority queue
                message = self._get_next_message()
                
                if message:
                    self._process_message(message)
                else:
                    # No messages available, sleep briefly
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
    
    def _get_next_message(self) -> Optional[IntegrationMessage]:
        """
        Get next message from queues (priority-based)
        """
        try:
            # Check queues in priority order
            for priority in [MessagePriority.EMERGENCY, MessagePriority.CRITICAL, 
                           MessagePriority.HIGH, MessagePriority.MEDIUM, MessagePriority.LOW]:
                queue = self.queues[priority]
                
                try:
                    message = queue.get_nowait()
                    return message
                except Empty:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next message: {e}")
            return None
    
    def _process_message(self, message: IntegrationMessage):
        """
        Process individual message
        """
        try:
            # Update message status
            message.status = MessageStatus.PROCESSING
            self.queue_stats['last_activity'] = django_tz.now().isoformat()
            
            # Get handler for message type
            handler = self.message_handlers.get(message.message_type)
            if not handler:
                logger.error(f"No handler for message type: {message.message_type}")
                message.status = MessageStatus.FAILED
                self.queue_stats['failed_messages'] += 1
                return
            
            # Validate message data
            validation_result = self._validate_message_data(message)
            if not validation_result['valid']:
                logger.error(f"Invalid message data: {validation_result['errors']}")
                message.status = MessageStatus.FAILED
                self.queue_stats['failed_messages'] += 1
                return
            
            # Process message with timeout
            future = self.executor.submit(handler, message)
            
            try:
                result = future.result(timeout=message.timeout)
                
                if result.get('success', False):
                    message.status = MessageStatus.COMPLETED
                    self.queue_stats['processed_messages'] += 1
                    logger.info(f"Processed message {message.id}: {message.message_type}")
                else:
                    message.status = MessageStatus.FAILED
                    self.queue_stats['failed_messages'] += 1
                    logger.error(f"Failed to process message {message.id}: {result.get('error')}")
                    
            except Exception as e:
                message.status = MessageStatus.FAILED
                self.queue_stats['failed_messages'] += 1
                logger.error(f"Error processing message {message.id}: {e}")
            
            # Handle retries
            if message.status == MessageStatus.FAILED and message.retry_count < message.max_retries:
                message.retry_count += 1
                message.status = MessageStatus.PENDING
                self._requeue_message(message)
                logger.info(f"Retrying message {message.id} (attempt {message.retry_count})")
            
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            message.status = MessageStatus.FAILED
            self.queue_stats['failed_messages'] += 1
    
    def _validate_message_data(self, message: IntegrationMessage) -> Dict[str, Any]:
        """
        Validate message data using existing validators
        """
        try:
            errors = []
            data = message.data
            
            # Validate alert-related data
            if 'alert_data' in data:
                alert_data = data['alert_data']
                
                # Validate condition if present
                if 'condition' in alert_data:
                    condition_validation = validate_alert_rule_condition(alert_data['condition'])
                    if not condition_validation['valid']:
                        errors.extend(condition_validation['errors'])
                
                # Validate threshold if present
                if 'threshold' in alert_data:
                    threshold_validation = validate_threshold_value(alert_data['threshold'])
                    if not threshold_validation['valid']:
                        errors.extend(threshold_validation['errors'])
            
            # Validate integration data
            if 'integration_data' in data:
                integration_data = data['integration_data']
                
                # Basic validation
                if 'type' not in integration_data:
                    errors.append("Integration type is required")
                
                if 'config' not in integration_data:
                    errors.append("Integration config is required")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating message data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _requeue_message(self, message: IntegrationMessage):
        """
        Requeue message for retry
        """
        try:
            # Add delay for retry
            retry_delay = min(2 ** message.retry_count, 60)  # Exponential backoff, max 60 seconds
            
            def requeue_later():
                time.sleep(retry_delay)
                self.enqueue_message(message)
            
            # Schedule requeue
            threading.Thread(target=requeue_later, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error requeuing message {message.id}: {e}")
    
    def enqueue_message(self, message: IntegrationMessage) -> bool:
        """
        Enqueue message in appropriate priority queue
        """
        try:
            if message.status != MessageStatus.PENDING:
                logger.error(f"Cannot enqueue message with status: {message.status}")
                return False
            
            queue = self.queues[message.priority]
            
            try:
                queue.put(message, timeout=1)
                self.queue_stats['total_messages'] += 1
                
                # Update queue size stats
                self._update_queue_sizes()
                
                logger.debug(f"Enqueued message {message.id} with priority {message.priority.name}")
                return True
                
            except Full:
                logger.error(f"Queue full for priority {message.priority.name}")
                return False
                
        except Exception as e:
            logger.error(f"Error enqueuing message {message.id}: {e}")
            return False
    
    def create_message(self, message_type: str, data: Dict[str, Any], 
                      priority: MessagePriority = MessagePriority.MEDIUM,
                      max_retries: int = 3, timeout: int = 30) -> str:
        """
        Create and enqueue new message
        """
        try:
            import uuid
            
            message_id = str(uuid.uuid4())
            
            message = IntegrationMessage(
                id=message_id,
                message_type=message_type,
                data=data,
                priority=priority,
                status=MessageStatus.PENDING,
                created_at=django_tz.now(),
                max_retries=max_retries,
                timeout=timeout
            )
            
            if self.enqueue_message(message):
                return message_id
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None
    
    def register_handler(self, message_type: str, handler: Callable):
        """
        Register message handler
        """
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")
    
    def unregister_handler(self, message_type: str):
        """
        Unregister message handler
        """
        if message_type in self.message_handlers:
            del self.message_handlers[message_type]
            logger.info(f"Unregistered handler for message type: {message_type}")
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get queue statistics
        """
        try:
            self._update_queue_sizes()
            
            total_messages = self.queue_stats['total_messages']
            processed_messages = self.queue_stats['processed_messages']
            failed_messages = self.queue_stats['failed_messages']
            
            # Calculate rates
            processing_rate = (processed_messages / max(total_messages, 1)) * 100
            failure_rate = (failed_messages / max(total_messages, 1)) * 100
            
            return {
                'is_running': self.is_running,
                'total_messages': total_messages,
                'processed_messages': processed_messages,
                'failed_messages': failed_messages,
                'processing_rate': processing_rate,
                'failure_rate': failure_rate,
                'queue_sizes': self.queue_stats['queue_sizes'],
                'registered_handlers': list(self.message_handlers.keys()),
                'last_activity': self.queue_stats['last_activity'],
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }
    
    def _update_queue_sizes(self):
        """
        Update queue size statistics
        """
        try:
            self.queue_stats['queue_sizes'] = {
                priority.name: queue.qsize()
                for priority, queue in self.queues.items()
            }
        except Exception as e:
            logger.error(f"Error updating queue sizes: {e}")
    
    def clear_queue(self, priority: MessagePriority = None) -> int:
        """
        Clear queue(s)
        """
        try:
            cleared_count = 0
            
            if priority:
                queue = self.queues[priority]
                cleared_count = queue.qsize()
                
                # Clear queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except Empty:
                        break
            else:
                # Clear all queues
                for queue in self.queues.values():
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                            cleared_count += 1
                        except Empty:
                            break
            
            logger.info(f"Cleared {cleared_count} messages from queue(s)")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return 0
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get message status (simplified - in production would use persistent storage)
        """
        # This is a simplified implementation
        # In production, you would store message status in database or cache
        return {
            'message_id': message_id,
            'status': 'unknown',
            'note': 'Message status tracking not implemented in this simplified version'
        }


# Global message queue instance
import sys as _sys
_running_tests = 'pytest' in _sys.modules or 'test' in _sys.argv or 'test_coverage' in _sys.argv
integration_message_queue = IntegrationMessageQueue(start_workers=not _running_tests)


# Default message handlers
def handle_integration_alert_message(message: IntegrationMessage) -> Dict[str, Any]:
    """
    Handle integration alert message
    """
    try:
        data = message.data
        alert_data = data.get('alert_data', {})
        integration_data = data.get('integration_data', {})
        
        # Combine data
        combined_data = {**alert_data, **integration_data}
        
        # Process through integration handler
        result = integration_handler.process_alert_data(combined_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling integration alert message: {e}")
        return {
            'success': False,
            'error': 'Operation failed'
        }


def handle_webhook_message(message: IntegrationMessage) -> Dict[str, Any]:
    """
    Handle webhook message
    """
    try:
        data = message.data
        webhook_url = data.get('webhook_url')
        webhook_data = data.get('webhook_data', {})
        
        # Send webhook
        from api.alerts.integration.webhooks_integration import integration_webhook_manager
        result = integration_webhook_manager.send_webhook('default', webhook_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling webhook message: {e}")
        return {
            'success': False,
            'error': 'Operation failed'
        }


def handle_notification_message(message: IntegrationMessage) -> Dict[str, Any]:
    """
    Handle notification message
    """
    try:
        data = message.data
        notification_type = data.get('notification_type', 'email')
        notification_data = data.get('notification_data', {})
        
        # Process notification
        from api.alerts.services import NotificationService
        
        if notification_type == 'email':
            result = NotificationService.send_email_notification(
                to_email=notification_data.get('to_email'),
                subject=notification_data.get('subject'),
                message=notification_data.get('message')
            )
        elif notification_type == 'sms':
            result = NotificationService.send_sms_notification(
                phone_number=notification_data.get('phone_number'),
                message=notification_data.get('message')
            )
        else:
            result = {'success': False, 'error': f'Unknown notification type: {notification_type}'}
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling notification message: {e}")
        return {
            'success': False,
            'error': 'Operation failed'
        }


# Register default handlers
integration_message_queue.register_handler('integration_alert', handle_integration_alert_message)
integration_message_queue.register_handler('webhook', handle_webhook_message)
integration_message_queue.register_handler('notification', handle_notification_message)


# Utility functions
def enqueue_integration_message(message_type: str, payload: Dict[str, Any] = None,
                            priority: Union[str, MessagePriority] = MessagePriority.MEDIUM,
                            data: Dict[str, Any] = None) -> str:
    """
    Enqueue integration message.
    Accepts `payload` (used by MessageQueueViewSet.enqueue) or `data` (legacy
    alias) for the message body, and `priority` as a MessagePriority member
    or its name as a string (e.g. 'MEDIUM', as sent from request JSON).
    """
    message_data = payload if payload is not None else (data or {})

    if isinstance(priority, str):
        try:
            priority = MessagePriority[priority.upper()]
        except KeyError:
            priority = MessagePriority.MEDIUM

    return integration_message_queue.create_message(message_type, message_data, priority)


def get_queue_statistics() -> Dict[str, Any]:
    """
    Get queue statistics
    """
    return integration_message_queue.get_queue_statistics()


def shutdown_message_queue():
    """
    Shutdown message queue
    """
    integration_message_queue.stop_workers()


# Backward-compatible alias: alerts/integration/__init__.py imports
# `InMemoryQueue` and instantiates it directly.
InMemoryQueue = IntegrationMessageQueue
