# api/rate_limit/message_queue.py
"""
Message queue system for rate limit module.

Provides high-traffic message processing and queue management.
"""

import logging
import json
import threading
import time
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from collections import deque
import queue
import uuid

logger = logging.getLogger(__name__)


class MessagePriority:
    """Message priority constants."""
    
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    
    CHOICES = [
        (LOW, 'Low'),
        (NORMAL, 'Normal'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class MessageStatus:
    """Message status constants."""
    
    QUEUED = 'queued'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'
    
    CHOICES = [
        (QUEUED, 'Queued'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (CANCELLED, 'Cancelled'),
        (EXPIRED, 'Expired'),
    ]


class Message:
    """Represents a message in the queue."""
    
    def __init__(self, message_type: str, payload: Dict[str, Any], 
                 priority: int = MessagePriority.NORMAL, ttl: int = 3600,
                 retry_attempts: int = 3, delay: int = 0):
        self.message_id = str(uuid.uuid4())
        self.message_type = message_type
        self.payload = payload
        self.priority = priority
        self.ttl = ttl
        self.retry_attempts = retry_attempts
        self.delay = delay
        self.created_at = timezone.now()
        self.expires_at = self.created_at + timedelta(seconds=ttl)
        self.queued_at = None
        self.processed_at = None
        self.completed_at = None
        self.status = MessageStatus.QUEUED
        self.attempts = 0
        self.error_message = None
        self.result_data = None
        self.metadata = {}
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        return timezone.now() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.attempts < self.retry_attempts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            'message_id': self.message_id,
            'message_type': self.message_type,
            'payload': self.payload,
            'priority': self.priority,
            'ttl': self.ttl,
            'retry_attempts': self.retry_attempts,
            'delay': self.delay,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'queued_at': self.queued_at.isoformat() if self.queued_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'attempts': self.attempts,
            'error_message': self.error_message,
            'result_data': self.result_data,
            'metadata': self.metadata
        }


class PriorityQueue:
    """Priority-based message queue."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queues = {
            MessagePriority.CRITICAL: deque(),
            MessagePriority.HIGH: deque(),
            MessagePriority.NORMAL: deque(),
            MessagePriority.LOW: deque()
        }
        self.lock = threading.RLock()
        self.total_messages = 0
    
    def put(self, message: Message) -> bool:
        """
        Add message to queue.
        
        Args:
            message: Message to add
            
        Returns:
            True if added successfully
        """
        with self.lock:
            if self.total_messages >= self.max_size:
                return False
            
            self.queues[message.priority].append(message)
            message.queued_at = timezone.now()
            self.total_messages += 1
            return True
    
    def get(self) -> Optional[Message]:
        """
        Get next message from queue.
        
        Returns:
            Next message or None
        """
        with self.lock:
            # Check queues in priority order
            for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                            MessagePriority.NORMAL, MessagePriority.LOW]:
                if self.queues[priority]:
                    message = self.queues[priority].popleft()
                    self.total_messages -= 1
                    return message
            
            return None
    
    def size(self) -> int:
        """Get queue size."""
        return self.total_messages
    
    def size_by_priority(self) -> Dict[int, int]:
        """Get queue size by priority."""
        with self.lock:
            return {
                priority: len(queue)
                for priority, queue in self.queues.items()
            }
    
    def peek(self) -> Optional[Message]:
        """Peek at next message without removing it."""
        with self.lock:
            for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                            MessagePriority.NORMAL, MessagePriority.LOW]:
                if self.queues[priority]:
                    return self.queues[priority][0]
            
            return None
    
    def remove_expired(self) -> int:
        """Remove expired messages from queue."""
        with self.lock:
            removed_count = 0
            
            for priority, queue in self.queues.items():
                valid_messages = deque()
                
                for message in queue:
                    if not message.is_expired():
                        valid_messages.append(message)
                    else:
                        message.status = MessageStatus.EXPIRED
                        removed_count += 1
                
                self.queues[priority] = valid_messages
            
            self.total_messages -= removed_count
            return removed_count


class MessageHandler:
    """Base class for message handlers."""
    
    def __init__(self, name: str, message_types: List[str] = None,
                 max_concurrent: int = 10, timeout: int = 30):
        self.name = name
        self.message_types = message_types or []
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.active_tasks = 0
        self.total_processed = 0
        self.total_failed = 0
        self.last_activity = None
        self.lock = threading.Semaphore(max_concurrent)
    
    def can_handle(self, message_type: str) -> bool:
        """Check if handler can handle message type."""
        return message_type in self.message_types or '*' in self.message_types
    
    def handle(self, message: Message) -> Dict[str, Any]:
        """
        Handle a message.
        
        Args:
            message: Message to handle
            
        Returns:
            Handling result
        """
        if not self.can_handle(message.message_type):
            return {
                'success': False,
                'error': f'Handler {self.name} cannot handle message type: {message.message_type}'
            }
        
        with self.lock:
            self.active_tasks += 1
        
        try:
            result = self._handle_message(message)
            
            if result.get('success', False):
                self.total_processed += 1
            else:
                self.total_failed += 1
            
            self.last_activity = timezone.now()
            return result
            
        except Exception as e:
            self.total_failed += 1
            logger.error(f"Message handler {self.name} failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.active_tasks -= 1
    
    def _handle_message(self, message: Message) -> Dict[str, Any]:
        """Handle message implementation."""
        raise NotImplementedError("Subclasses must implement _handle_message()")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            'name': self.name,
            'message_types': self.message_types,
            'max_concurrent': self.max_concurrent,
            'active_tasks': self.active_tasks,
            'total_processed': self.total_processed,
            'total_failed': self.total_failed,
            'success_rate': (
                self.total_processed / max(self.total_processed + self.total_failed, 1)
            ) * 100,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }


class RateLimitMessageHandler(MessageHandler):
    """Handler for rate limit related messages."""
    
    def __init__(self):
        super().__init__(
            name='rate_limit_handler',
            message_types=[
                'rate_limit_exceeded',
                'rate_limit_allowed',
                'abuse_detected',
                'ip_blocked',
                'ip_unblocked',
                'config_updated',
                'user_profile_updated'
            ],
            max_concurrent=20
        )
    
    def _handle_message(self, message: Message) -> Dict[str, Any]:
        """Handle rate limit message."""
        try:
            message_type = message.message_type
            payload = message.payload
            
            # Process based on message type
            if message_type == 'rate_limit_exceeded':
                result = self._handle_rate_limit_exceeded(payload)
            elif message_type == 'rate_limit_allowed':
                result = self._handle_rate_limit_allowed(payload)
            elif message_type == 'abuse_detected':
                result = self._handle_abuse_detected(payload)
            elif message_type == 'ip_blocked':
                result = self._handle_ip_blocked(payload)
            elif message_type == 'ip_unblocked':
                result = self._handle_ip_unblocked(payload)
            elif message_type == 'config_updated':
                result = self._handle_config_updated(payload)
            elif message_type == 'user_profile_updated':
                result = self._handle_user_profile_updated(payload)
            else:
                result = {
                    'success': False,
                    'error': f'Unknown message type: {message_type}'
                }
            
            # Store result in cache
            cache_key = f"rate_limit_message_result:{message.message_id}"
            cache.set(cache_key, result, timeout=3600)  # 1 hour
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to handle rate limit message: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _handle_rate_limit_exceeded(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rate limit exceeded message."""
        # Update statistics
        cache_key = f"rate_limit_stats:{timezone.now().date()}"
        stats = cache.get(cache_key, {'exceeded_count': 0, 'allowed_count': 0})
        stats['exceeded_count'] += 1
        cache.set(cache_key, stats, timeout=86400)  # 24 hours
        
        # Trigger integrations
        from api.rate_limit.integ_handler import integration_handler
        
        for integration_id, integration_info in integration_handler.active_integrations.items():
            adapter = integration_info['adapter']
            
            if hasattr(adapter, 'handle_rate_limit_exceeded'):
                try:
                    adapter.handle_rate_limit_exceeded(payload)
                except Exception as e:
                    logger.error(f"Integration {integration_id} failed to handle rate limit exceeded: {str(e)}")
        
        return {
            'success': True,
            'action': 'rate_limit_exceeded_processed',
            'exceeded_count': stats['exceeded_count']
        }
    
    def _handle_rate_limit_allowed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rate limit allowed message."""
        # Update statistics
        cache_key = f"rate_limit_stats:{timezone.now().date()}"
        stats = cache.get(cache_key, {'exceeded_count': 0, 'allowed_count': 0})
        stats['allowed_count'] += 1
        cache.set(cache_key, stats, timeout=86400)  # 24 hours
        
        return {
            'success': True,
            'action': 'rate_limit_allowed_processed',
            'allowed_count': stats['allowed_count']
        }
    
    def _handle_abuse_detected(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle abuse detected message."""
        # Store abuse report
        cache_key = f"abuse_reports:{timezone.now().date()}"
        reports = cache.get(cache_key, [])
        reports.append({
            'timestamp': timezone.now().isoformat(),
            'payload': payload
        })
        cache.set(cache_key, reports, timeout=86400)  # 24 hours
        
        # Trigger security integrations
        from api.rate_limit.integ_handler import integration_handler
        
        for integration_id, integration_info in integration_handler.active_integrations.items():
            adapter = integration_info['adapter']
            
            if hasattr(adapter, 'handle_abuse_detected'):
                try:
                    adapter.handle_abuse_detected(payload)
                except Exception as e:
                    logger.error(f"Integration {integration_id} failed to handle abuse detected: {str(e)}")
        
        return {
            'success': True,
            'action': 'abuse_detected_processed',
            'reports_count': len(reports)
        }
    
    def _handle_ip_blocked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle IP blocked message."""
        # Update block statistics
        cache_key = f"ip_block_stats:{timezone.now().date()}"
        stats = cache.get(cache_key, {'blocked_count': 0, 'unblocked_count': 0})
        stats['blocked_count'] += 1
        cache.set(cache_key, stats, timeout=86400)  # 24 hours
        
        return {
            'success': True,
            'action': 'ip_blocked_processed',
            'blocked_count': stats['blocked_count']
        }
    
    def _handle_ip_unblocked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle IP unblocked message."""
        # Update block statistics
        cache_key = f"ip_block_stats:{timezone.now().date()}"
        stats = cache.get(cache_key, {'blocked_count': 0, 'unblocked_count': 0})
        stats['unblocked_count'] += 1
        cache.set(cache_key, stats, timeout=86400)  # 24 hours
        
        return {
            'success': True,
            'action': 'ip_unblocked_processed',
            'unblocked_count': stats['unblocked_count']
        }
    
    def _handle_config_updated(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle config updated message."""
        # Clear configuration cache
        cache.delete('rate_limit_config_cache')
        
        # Trigger integration updates
        from api.rate_limit.integ_handler import integration_handler
        
        for integration_id, integration_info in integration_handler.active_integrations.items():
            adapter = integration_info['adapter']
            
            if hasattr(adapter, 'handle_config_updated'):
                try:
                    adapter.handle_config_updated(payload)
                except Exception as e:
                    logger.error(f"Integration {integration_id} failed to handle config updated: {str(e)}")
        
        return {
            'success': True,
            'action': 'config_updated_processed'
        }
    
    def _handle_user_profile_updated(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user profile updated message."""
        # Update user profile cache
        user_id = payload.get('user_id')
        if user_id:
            cache_key = f"user_profile:{user_id}"
            cache.set(cache_key, payload, timeout=3600)  # 1 hour
        
        return {
            'success': True,
            'action': 'user_profile_updated_processed'
        }


class AnalyticsMessageHandler(MessageHandler):
    """Handler for analytics related messages."""
    
    def __init__(self):
        super().__init__(
            name='analytics_handler',
            message_types=[
                'analytics_event',
                'performance_metric',
                'user_behavior',
                'system_health'
            ],
            max_concurrent=10
        )
    
    def _handle_message(self, message: Message) -> Dict[str, Any]:
        """Handle analytics message."""
        try:
            message_type = message.message_type
            payload = message.payload
            
            # Store analytics data
            cache_key = f"analytics_{message_type}:{timezone.now().date()}"
            events = cache.get(cache_key, [])
            events.append({
                'timestamp': timezone.now().isoformat(),
                'payload': payload
            })
            
            # Keep only last 1000 events
            if len(events) > 1000:
                events = events[-1000:]
            
            cache.set(cache_key, events, timeout=86400 * 7)  # 7 days
            
            return {
                'success': True,
                'action': f'{message_type}_stored',
                'events_count': len(events)
            }
            
        except Exception as e:
            logger.error(f"Failed to handle analytics message: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class MessageQueueManager:
    """
    Manager for message queue system.
    """
    
    def __init__(self, max_queue_size: int = 10000, max_workers: int = 10):
        self.queue = PriorityQueue(max_queue_size)
        self.handlers: Dict[str, MessageHandler] = {}
        self.max_workers = max_workers
        self.workers: List[threading.Thread] = []
        self.is_running = False
        self.statistics = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'expired_messages': 0,
            'queue_size': 0
        }
        self._initialize_default_handlers()
    
    def _initialize_default_handlers(self):
        """Initialize default message handlers."""
        # Register rate limit handler
        rate_limit_handler = RateLimitMessageHandler()
        self.register_handler(rate_limit_handler)
        
        # Register analytics handler
        analytics_handler = AnalyticsMessageHandler()
        self.register_handler(analytics_handler)
    
    def register_handler(self, handler: MessageHandler):
        """
        Register a message handler.
        
        Args:
            handler: Message handler instance
        """
        for message_type in handler.message_types:
            self.handlers[message_type] = handler
        
        logger.info(f"Registered message handler: {handler.name}")
    
    def unregister_handler(self, handler_name: str):
        """
        Unregister a message handler.
        
        Args:
            handler_name: Handler name
        """
        handlers_to_remove = [
            message_type for message_type, handler in self.handlers.items()
            if handler.name == handler_name
        ]
        
        for message_type in handlers_to_remove:
            del self.handlers[message_type]
        
        logger.info(f"Unregistered message handler: {handler_name}")
    
    def publish_message(self, message_type: str, payload: Dict[str, Any],
                        priority: int = MessagePriority.NORMAL, ttl: int = 3600,
                        retry_attempts: int = 3, delay: int = 0) -> str:
        """
        Publish a message to the queue.
        
        Args:
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            ttl: Time to live in seconds
            retry_attempts: Number of retry attempts
            delay: Delay in seconds before processing
            
        Returns:
            Message ID
        """
        message = Message(
            message_type=message_type,
            payload=payload,
            priority=priority,
            ttl=ttl,
            retry_attempts=retry_attempts,
            delay=delay
        )
        
        success = self.queue.put(message)
        
        if success:
            self.statistics['total_messages'] += 1
            logger.debug(f"Published message: {message.message_id} ({message_type})")
            return message.message_id
        else:
            logger.error(f"Failed to publish message: queue is full")
            raise Exception("Message queue is full")
    
    def start_workers(self):
        """Start worker threads."""
        if self.is_running:
            logger.warning("Message queue workers are already running")
            return
        
        self.is_running = True
        
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"MQ-Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} message queue workers")
    
    def stop_workers(self):
        """Stop worker threads."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        logger.info("Stopped message queue workers")
    
    def _worker_loop(self):
        """Main worker loop for processing messages."""
        while self.is_running:
            try:
                # Get next message
                message = self.queue.get()
                
                if message is None:
                    time.sleep(0.1)
                    continue
                
                # Check if message is expired
                if message.is_expired():
                    message.status = MessageStatus.EXPIRED
                    self.statistics['expired_messages'] += 1
                    continue
                
                # Check delay
                if message.delay > 0:
                    time.sleep(message.delay)
                
                # Process message
                self._process_message(message)
                
            except Exception as e:
                logger.error(f"Error in message queue worker: {str(e)}")
                time.sleep(1)
    
    def _process_message(self, message: Message):
        """Process a single message."""
        try:
            message.status = MessageStatus.PROCESSING
            message.processed_at = timezone.now()
            
            # Get handler for message type
            handler = self.handlers.get(message.message_type)
            
            if not handler:
                message.status = MessageStatus.FAILED
                message.error_message = f"No handler for message type: {message.message_type}"
                self.statistics['failed_messages'] += 1
                return
            
            # Handle message
            result = handler.handle(message)
            
            if result.get('success', False):
                message.status = MessageStatus.COMPLETED
                message.completed_at = timezone.now()
                message.result_data = result
                self.statistics['processed_messages'] += 1
            else:
                message.status = MessageStatus.FAILED
                message.error_message = result.get('error', 'Unknown error')
                self.statistics['failed_messages'] += 1
                
                # Retry if possible
                if message.can_retry():
                    message.status = MessageStatus.QUEUED
                    message.attempts += 1
                    self.queue.put(message)
            
        except Exception as e:
            message.status = MessageStatus.FAILED
            message.error_message = str(e)
            self.statistics['failed_messages'] += 1
            logger.error(f"Failed to process message {message.message_id}: {str(e)}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status."""
        self.statistics['queue_size'] = self.queue.size()
        self.statistics['queue_size_by_priority'] = self.queue.size_by_priority()
        
        return {
            'is_running': self.is_running,
            'max_workers': self.max_workers,
            'active_workers': len(self.workers),
            'statistics': self.statistics.copy(),
            'handlers': {
                name: handler.get_statistics()
                for name, handler in self.handlers.items()
            }
        }
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message status by ID."""
        # Check cache for message result
        cache_key = f"rate_limit_message_result:{message_id}"
        result = cache.get(cache_key)
        
        if result:
            return result
        
        return None
    
    def cleanup_expired_messages(self) -> int:
        """Clean up expired messages."""
        removed_count = self.queue.remove_expired()
        self.statistics['expired_messages'] += removed_count
        
        logger.info(f"Cleaned up {removed_count} expired messages")
        return removed_count


# Global message queue manager instance
message_queue_manager = MessageQueueManager()

# Start workers
message_queue_manager.start_workers()


# Export classes and functions
__all__ = [
    'MessagePriority',
    'MessageStatus',
    'Message',
    'PriorityQueue',
    'MessageHandler',
    'RateLimitMessageHandler',
    'AnalyticsMessageHandler',
    'MessageQueueManager',
    'message_queue_manager'
]
