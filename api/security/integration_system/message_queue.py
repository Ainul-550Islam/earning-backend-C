"""
Message Queue Module
High traffic message queue manager for integration system
"""

import logging
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import QueueType
from .circuit_breaker import circuit_breaker_protected

User = get_user_model()
logger = logging.getLogger('security.integration.message_queue')


class Message:
    """Message for queue system"""
    
    def __init__(self, body: Any, priority: int = 5, ttl: int = None, 
                 delay: int = 0, max_retries: int = 3):
        self.id = SecurityUtils.generate_uuid()
        self.body = body
        self.priority = priority  # 1-10, lower number = higher priority
        self.ttl = ttl  # Time to live in seconds
        self.delay = delay  # Delay before processing
        self.max_retries = max_retries
        self.created_at = timezone.now()
        self.available_at = self.created_at + timedelta(seconds=delay)
        self.expires_at = self.created_at + timedelta(seconds=ttl) if ttl else None
        self.attempts = 0
        self.last_attempt = None
        self.status = 'pending'  # pending, processing, completed, failed, expired
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            'id': str(self.id),
            'body': self.body,
            'priority': self.priority,
            'ttl': self.ttl,
            'delay': self.delay,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat(),
            'available_at': self.available_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'attempts': self.attempts,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'status': self.status
        }
    
    def is_available(self) -> bool:
        """Check if message is available for processing"""
        return (self.status == 'pending' and 
                timezone.now() >= self.available_at and 
                (not self.expires_at or timezone.now() < self.expires_at))
    
    def is_expired(self) -> bool:
        """Check if message is expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.attempts < self.max_retries and not self.is_expired()
    
    def mark_processing(self):
        """Mark message as processing"""
        self.status = 'processing'
        self.last_attempt = timezone.now()
        self.attempts += 1
    
    def mark_completed(self):
        """Mark message as completed"""
        self.status = 'completed'
    
    def mark_failed(self):
        """Mark message as failed"""
        if self.can_retry():
            self.status = 'pending'
        else:
            self.status = 'failed'


class Queue:
    """Message queue"""
    
    def __init__(self, name: str, max_size: int = 10000, max_memory_mb: int = 100):
        self.name = name
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.messages = []
        self.processing_messages = set()
        self.completed_messages = []
        self.failed_messages = []
        self.dead_letter_messages = []
        self.subscribers = []
        self.enabled = True
        self.statistics = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'expired_messages': 0,
            'queue_size': 0,
            'processing_count': 0,
            'dead_letter_count': 0
        }
        self.lock = asyncio.Lock()
    
    async def enqueue(self, message: Message) -> bool:
        """Enqueue message"""
        async with self.lock:
            if not self.enabled:
                return False
            
            # Check queue size limit
            if len(self.messages) >= self.max_size:
                logger.warning(f"Queue {self.name} full, dropping message")
                return False
            
            # Check memory limit
            if self._get_memory_usage() > self.max_memory_mb:
                logger.warning(f"Queue {self.name} memory limit exceeded, dropping message")
                return False
            
            # Add message to queue
            self.messages.append(message)
            self.statistics['total_messages'] += 1
            self.statistics['queue_size'] = len(self.messages)
            
            logger.debug(f"Enqueued message {message.id} to queue {self.name}")
            return True
    
    async def dequeue(self) -> Optional[Message]:
        """Dequeue next available message"""
        async with self.lock:
            if not self.messages:
                return None
            
            # Find available message (highest priority first)
            available_messages = [msg for msg in self.messages if msg.is_available()]
            
            if not available_messages:
                return None
            
            # Sort by priority (lower number = higher priority)
            available_messages.sort(key=lambda m: (m.priority, m.created_at))
            message = available_messages[0]
            
            # Remove from queue
            self.messages.remove(message)
            self.processing_messages.add(message.id)
            message.mark_processing()
            
            self.statistics['queue_size'] = len(self.messages)
            self.statistics['processing_count'] = len(self.processing_messages)
            
            logger.debug(f"Dequeued message {message.id} from queue {self.name}")
            return message
    
    async def complete_message(self, message: Message):
        """Mark message as completed"""
        async with self.lock:
            message.mark_completed()
            
            if message.id in self.processing_messages:
                self.processing_messages.remove(message.id)
            
            self.completed_messages.append(message)
            self.statistics['processed_messages'] += 1
            self.statistics['processing_count'] = len(self.processing_messages)
            
            # Cleanup old completed messages
            self._cleanup_completed_messages()
            
            logger.debug(f"Completed message {message.id} in queue {self.name}")
    
    async def fail_message(self, message: Message):
        """Mark message as failed"""
        async with self.lock:
            message.mark_failed()
            
            if message.id in self.processing_messages:
                self.processing_messages.remove(message.id)
            
            if message.status == 'failed':
                self.failed_messages.append(message)
                self.statistics['failed_messages'] += 1
            elif message.status == 'expired':
                self.dead_letter_messages.append(message)
                self.statistics['expired_messages'] += 1
                self.statistics['dead_letter_count'] += 1
            else:
                # Retry - re-enqueue
                self.messages.append(message)
                self.statistics['queue_size'] = len(self.messages)
            
            self.statistics['processing_count'] = len(self.processing_messages)
            
            logger.debug(f"Failed message {message.id} in queue {self.name}")
    
    async def subscribe(self, callback: Callable[[Message], Any]):
        """Subscribe to queue messages"""
        self.subscribers.append(callback)
        logger.info(f"Added subscriber to queue {self.name}")
    
    async def unsubscribe(self, callback: Callable):
        """Unsubscribe from queue messages"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"Removed subscriber from queue {self.name}")
    
    async def process_messages(self):
        """Process messages with subscribers"""
        if not self.enabled or not self.subscribers:
            return
        
        while True:
            try:
                # Get next message
                message = await self.dequeue()
                if not message:
                    await asyncio.sleep(0.1)  # Small delay when no messages
                    continue
                
                # Process with all subscribers
                success_count = 0
                
                for callback in self.subscribers:
                    try:
                        result = callback(message)
                        if asyncio.iscoroutine(result):
                            result = await result
                        
                        if result is not False:
                            success_count += 1
                    
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")
                
                # Mark message based on results
                if success_count > 0:
                    await self.complete_message(message)
                else:
                    await self.fail_message(message)
            
            except Exception as e:
                logger.error(f"Error processing messages in queue {self.name}: {e}")
                await asyncio.sleep(1)
    
    def _get_memory_usage(self) -> float:
        """Get estimated memory usage in MB"""
        total_size = 0
        
        for message in self.messages:
            # Rough estimate of message size
            total_size += len(str(message.body)) * 2  # Assume 2 bytes per character
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def _cleanup_completed_messages(self):
        """Cleanup old completed messages"""
        # Keep only last 1000 completed messages
        if len(self.completed_messages) > 1000:
            self.completed_messages = self.completed_messages[-1000:]
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'queue_size': len(self.messages),
            'processing_count': len(self.processing_messages),
            'completed_count': len(self.completed_messages),
            'failed_count': len(self.failed_messages),
            'dead_letter_count': len(self.dead_letter_messages),
            'subscriber_count': len(self.subscribers),
            'max_size': self.max_size,
            'memory_usage_mb': self._get_memory_usage(),
            'statistics': self.statistics
        }
    
    def enable(self):
        """Enable queue"""
        self.enabled = True
        logger.info(f"Queue {self.name} enabled")
    
    def disable(self):
        """Disable queue"""
        self.enabled = False
        logger.info(f"Queue {self.name} disabled")
    
    def clear(self):
        """Clear queue"""
        self.messages.clear()
        self.processing_messages.clear()
        self.completed_messages.clear()
        self.failed_messages.clear()
        self.dead_letter_messages.clear()
        self.statistics = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'expired_messages': 0,
            'queue_size': 0,
            'processing_count': 0,
            'dead_letter_count': 0
        }
        logger.info(f"Cleared queue {self.name}")


class MessageQueueManager:
    """Manager for multiple message queues"""
    
    def __init__(self):
        self.queues = {}
        self.queue_configs = {}
        self.enabled = True
        self.default_config = {
            'max_size': 10000,
            'max_memory_mb': 100,
            'auto_process': True
        }
    
    def create_queue(self, queue_name: str, max_size: int = None, 
                    max_memory_mb: int = None, auto_process: bool = True) -> Queue:
        """Create message queue"""
        config = self.default_config.copy()
        
        if max_size is not None:
            config['max_size'] = max_size
        if max_memory_mb is not None:
            config['max_memory_mb'] = max_memory_mb
        if auto_process is not None:
            config['auto_process'] = auto_process
        
        queue = Queue(
            queue_name,
            config['max_size'],
            config['max_memory_mb']
        )
        
        self.queues[queue_name] = queue
        self.queue_configs[queue_name] = config
        
        # Start processing if auto_process is enabled
        if config['auto_process']:
            asyncio.create_task(queue.process_messages())
        
        logger.info(f"Created message queue: {queue_name}")
        return queue
    
    def remove_queue(self, queue_name: str) -> bool:
        """Remove message queue"""
        if queue_name in self.queues:
            queue = self.queues[queue_name]
            queue.disable()
            del self.queues[queue_name]
            del self.queue_configs[queue_name]
            logger.info(f"Removed message queue: {queue_name}")
            return True
        return False
    
    def get_queue(self, queue_name: str) -> Optional[Queue]:
        """Get queue by name"""
        return self.queues.get(queue_name)
    
    async def send_message(self, queue_name: str, body: Any, priority: int = 5, 
                          ttl: int = None, delay: int = 0, max_retries: int = 3) -> bool:
        """Send message to queue"""
        queue = self.get_queue(queue_name)
        if not queue:
            logger.error(f"Queue not found: {queue_name}")
            return False
        
        message = Message(body, priority, ttl, delay, max_retries)
        return await queue.enqueue(message)
    
    async def send_batch_messages(self, queue_name: str, messages: List[Dict[str, Any]]) -> int:
        """Send batch of messages to queue"""
        queue = self.get_queue(queue_name)
        if not queue:
            logger.error(f"Queue not found: {queue_name}")
            return 0
        
        sent_count = 0
        for msg_config in messages:
            message = Message(
                body=msg_config.get('body'),
                priority=msg_config.get('priority', 5),
                ttl=msg_config.get('ttl'),
                delay=msg_config.get('delay', 0),
                max_retries=msg_config.get('max_retries', 3)
            )
            
            if await queue.enqueue(message):
                sent_count += 1
        
        return sent_count
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all queues"""
        return {
            'enabled': self.enabled,
            'total_queues': len(self.queues),
            'queues': {
                name: queue.get_status()
                for name, queue in self.queues.items()
            }
        }
    
    def enable_all_queues(self):
        """Enable all queues"""
        for queue in self.queues.values():
            queue.enable()
    
    def disable_all_queues(self):
        """Disable all queues"""
        for queue in self.queues.values():
            queue.disable()
    
    def clear_all_queues(self):
        """Clear all queues"""
        for queue in self.queues.values():
            queue.clear()
    
    def enable(self):
        """Enable queue manager"""
        self.enabled = True
        logger.info("Message queue manager enabled")
    
    def disable(self):
        """Disable queue manager"""
        self.enabled = False
        logger.info("Message queue manager disabled")


class HighTrafficQueueManager(MessageQueueManager):
    """High traffic queue manager with additional features"""
    
    def __init__(self):
        super().__init__()
        self.rate_limiters = {}
        self.load_balancers = {}
        self.monitoring_enabled = True
        self.performance_metrics = {}
    
    def create_high_traffic_queue(self, queue_name: str, **kwargs) -> Queue:
        """Create high traffic optimized queue"""
        # Default high traffic settings
        high_traffic_config = {
            'max_size': kwargs.get('max_size', 50000),
            'max_memory_mb': kwargs.get('max_memory_mb', 500),
            'auto_process': True
        }
        
        queue = self.create_queue(queue_name, **high_traffic_config)
        
        # Add performance monitoring
        self.performance_metrics[queue_name] = {
            'throughput': 0,
            'latency': 0,
            'error_rate': 0,
            'last_updated': timezone.now()
        }
        
        # Add rate limiting if specified
        rate_limit = kwargs.get('rate_limit')
        if rate_limit:
            self.add_rate_limiter(queue_name, rate_limit)
        
        return queue
    
    def add_rate_limiter(self, queue_name: str, rate_limit: int):
        """Add rate limiter to queue"""
        self.rate_limiters[queue_name] = {
            'limit': rate_limit,
            'tokens': rate_limit,
            'last_refill': timezone.now()
        }
    
    def check_rate_limit(self, queue_name: str) -> bool:
        """Check if rate limit allows processing"""
        if queue_name not in self.rate_limiters:
            return True
        
        limiter = self.rate_limiters[queue_name]
        now = timezone.now()
        
        # Refill tokens based on time elapsed
        time_diff = (now - limiter['last_refill']).total_seconds()
        tokens_to_add = int(time_diff * limiter['limit'] / 60)  # Refill per minute
        
        limiter['tokens'] = min(limiter['limit'], limiter['tokens'] + tokens_to_add)
        limiter['last_refill'] = now
        
        # Check if token available
        if limiter['tokens'] > 0:
            limiter['tokens'] -= 1
            return True
        
        return False
    
    def update_performance_metrics(self, queue_name: str, throughput: float, 
                                  latency: float, error_rate: float):
        """Update performance metrics for queue"""
        if queue_name in self.performance_metrics:
            self.performance_metrics[queue_name].update({
                'throughput': throughput,
                'latency': latency,
                'error_rate': error_rate,
                'last_updated': timezone.now()
            })
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report for all queues"""
        return {
            'queue_count': len(self.queues),
            'total_messages': sum(q.statistics['total_messages'] for q in self.queues.values()),
            'total_processed': sum(q.statistics['processed_messages'] for q in self.queues.values()),
            'total_failed': sum(q.statistics['failed_messages'] for q in self.queues.values()),
            'performance_metrics': self.performance_metrics,
            'rate_limiters': {
                name: {
                    'limit': limiter['limit'],
                    'available_tokens': limiter['tokens']
                }
                for name, limiter in self.rate_limiters.items()
            }
        }


# Global queue manager
message_queue_manager = MessageQueueManager()
high_traffic_manager = HighTrafficQueueManager()

# Create default queues
default_queue = message_queue_manager.create_queue('default')
security_events_queue = message_queue_manager.create_queue('security_events')
high_priority_queue = message_queue_manager.create_queue('high_priority', max_size=1000)


# Export symbols
__all__ = [
    'Message',
    'Queue',
    'MessageQueueManager',
    'HighTrafficQueueManager',
    'message_queue_manager',
    'high_traffic_manager',
    'default_queue',
    'security_events_queue',
    'high_priority_queue'
]