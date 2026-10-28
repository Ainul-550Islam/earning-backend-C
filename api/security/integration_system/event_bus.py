"""
Integration Event Bus Module
Event bus for integration system communication
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import *

User = get_user_model()
logger = logging.getLogger('security.integration.event_bus')


class EventBusMessage:
    """Event bus message"""
    
    def __init__(self, event_type: str, data: Dict[str, Any], 
                 source: str = None, target: str = None, 
                 priority: int = 2, ttl: int = None):
        self.id = SecurityUtils.generate_uuid()
        self.event_type = event_type
        self.data = data
        self.source = source
        self.target = target
        self.priority = priority
        self.ttl = ttl
        self.created_at = timezone.now()
        self.expires_at = None
        self.attempts = 0
        self.max_attempts = 3
        self.status = 'pending'
        
        if ttl:
            self.expires_at = self.created_at + timedelta(seconds=ttl)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            'id': str(self.id),
            'event_type': self.event_type,
            'data': self.data,
            'source': self.source,
            'target': self.target,
            'priority': self.priority,
            'ttl': self.ttl,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'status': self.status
        }
    
    def is_expired(self) -> bool:
        """Check if message is expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.attempts < self.max_attempts and not self.is_expired()


class EventSubscriber:
    """Event subscriber"""
    
    def __init__(self, name: str, event_types: List[str], handler: Callable,
                 filter_func: Callable = None, async_handler: bool = False):
        self.name = name
        self.event_types = event_types
        self.handler = handler
        self.filter_func = filter_func
        self.async_handler = async_handler
        self.enabled = True
        self.statistics = {
            'messages_received': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'last_activity': None
        }
    
    def can_handle(self, message: EventBusMessage) -> bool:
        """Check if subscriber can handle message"""
        if not self.enabled:
            return False
        
        if message.event_type not in self.event_types:
            return False
        
        if self.filter_func and not self.filter_func(message):
            return False
        
        return True
    
    async def handle_message(self, message: EventBusMessage) -> Dict[str, Any]:
        """Handle message"""
        try:
            self.statistics['messages_received'] += 1
            self.statistics['last_activity'] = timezone.now()
            
            if self.async_handler:
                result = await self.handler(message)
            else:
                result = self.handler(message)
            
            self.statistics['messages_processed'] += 1
            message.status = 'processed'
            
            return {
                'status': 'success',
                'subscriber': self.name,
                'result': result
            }
            
        except Exception as e:
            self.statistics['messages_failed'] += 1
            logger.error(f"Error in subscriber {self.name}: {e}")
            message.status = 'failed'
            
            return {
                'status': 'error',
                'subscriber': self.name,
                'error': str(e)
            }
    
    def enable(self):
        """Enable subscriber"""
        self.enabled = True
    
    def disable(self):
        """Disable subscriber"""
        self.enabled = False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get subscriber statistics"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'event_types': self.event_types,
            'async_handler': self.async_handler,
            'statistics': self.statistics
        }


class EventBus:
    """Event bus for integration system"""
    
    def __init__(self, name: str, max_queue_size: int = 10000):
        self.name = name
        self.max_queue_size = max_queue_size
        self.subscribers = {}
        self.message_queue = []
        self.processing_queue = []
        self.dead_letter_queue = []
        self.enabled = True
        self.statistics = {
            'messages_published': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'messages_expired': 0,
            'queue_size': 0,
            'dead_letter_size': 0
        }
        self.processing = False
        self.batch_size = 100
        self.processing_interval = 1.0  # seconds
    
    def subscribe(self, subscriber: EventSubscriber):
        """Subscribe to event types"""
        for event_type in subscriber.event_types:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            self.subscribers[event_type].append(subscriber)
        
        logger.info(f"Subscriber {subscriber.name} subscribed to {subscriber.event_types}")
    
    def unsubscribe(self, subscriber_name: str):
        """Unsubscribe subscriber"""
        for event_type, subscribers in self.subscribers.items():
            self.subscribers[event_type] = [
                s for s in subscribers if s.name != subscriber_name
            ]
        
        logger.info(f"Unsubscribed: {subscriber_name}")
    
    def publish(self, message: EventBusMessage) -> bool:
        """Publish message to event bus"""
        if not self.enabled:
            return False
        
        if len(self.message_queue) >= self.max_queue_size:
            logger.warning(f"Event bus {self.name} queue full, dropping message")
            return False
        
        self.message_queue.append(message)
        self.statistics['messages_published'] += 1
        self.statistics['queue_size'] = len(self.message_queue)
        
        logger.debug(f"Published message to event bus {self.name}: {message.event_type}")
        return True
    
    def publish_event(self, event_type: str, data: Dict[str, Any], 
                      source: str = None, target: str = None, 
                      priority: int = 2, ttl: int = None) -> bool:
        """Publish event to event bus"""
        message = EventBusMessage(event_type, data, source, target, priority, ttl)
        return self.publish(message)
    
    async def start_processing(self):
        """Start processing messages"""
        if self.processing:
            return
        
        self.processing = True
        logger.info(f"Started processing event bus: {self.name}")
        
        while self.processing:
            await self._process_messages()
            await asyncio.sleep(self.processing_interval)
    
    def stop_processing(self):
        """Stop processing messages"""
        self.processing = False
        logger.info(f"Stopped processing event bus: {self.name}")
    
    async def _process_messages(self):
        """Process messages from queue"""
        if not self.message_queue:
            return
        
        # Get batch of messages
        batch_size = min(self.batch_size, len(self.message_queue))
        batch = self.message_queue[:batch_size]
        
        # Remove from queue
        self.message_queue = self.message_queue[batch_size:]
        self.statistics['queue_size'] = len(self.message_queue)
        
        # Process each message
        tasks = []
        for message in batch:
            if message.is_expired():
                self.statistics['messages_expired'] += 1
                self._move_to_dead_letter(message, 'expired')
                continue
            
            task = asyncio.create_task(self._process_message(message))
            tasks.append(task)
        
        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_message(self, message: EventBusMessage):
        """Process single message"""
        try:
            # Get subscribers for this event type
            subscribers = self.subscribers.get(message.event_type, [])
            
            if not subscribers:
                # No subscribers, move to dead letter
                self._move_to_dead_letter(message, 'no_subscribers')
                return
            
            # Find subscribers that can handle this message
            eligible_subscribers = [s for s in subscribers if s.can_handle(message)]
            
            if not eligible_subscribers:
                # No eligible subscribers
                self._move_to_dead_letter(message, 'no_eligible_subscribers')
                return
            
            # Process with all eligible subscribers
            tasks = []
            for subscriber in eligible_subscribers:
                task = asyncio.create_task(subscriber.handle_message(message))
                tasks.append(task)
            
            # Wait for all subscribers to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
            
            if success_count > 0:
                self.statistics['messages_processed'] += 1
                message.status = 'processed'
            else:
                self.statistics['messages_failed'] += 1
                message.attempts += 1
                
                if not message.can_retry():
                    self._move_to_dead_letter(message, 'processing_failed')
                else:
                    # Re-queue for retry
                    self.message_queue.append(message)
            
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            self.statistics['messages_failed'] += 1
            message.attempts += 1
            
            if not message.can_retry():
                self._move_to_dead_letter(message, 'processing_error')
    
    def _move_to_dead_letter(self, message: EventBusMessage, reason: str):
        """Move message to dead letter queue"""
        message.status = 'dead_letter'
        message.metadata = message.metadata or {}
        message.metadata['dead_letter_reason'] = reason
        message.metadata['dead_letter_timestamp'] = timezone.now().isoformat()
        
        self.dead_letter_queue.append(message)
        self.statistics['dead_letter_size'] = len(self.dead_letter_queue)
        
        logger.warning(f"Message {message.id} moved to dead letter: {reason}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'processing': self.processing,
            'statistics': self.statistics,
            'subscriber_count': sum(len(subs) for subs in self.subscribers.values()),
            'event_types': list(self.subscribers.keys())
        }
    
    def get_subscriber_statistics(self) -> Dict[str, Any]:
        """Get subscriber statistics"""
        stats = {}
        
        for event_type, subscribers in self.subscribers.items():
            stats[event_type] = [sub.get_statistics() for sub in subscribers]
        
        return stats
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status"""
        return {
            'queue_size': len(self.message_queue),
            'max_queue_size': self.max_queue_size,
            'processing_queue_size': len(self.processing_queue),
            'dead_letter_size': len(self.dead_letter_queue),
            'queue_utilization': len(self.message_queue) / self.max_queue_size
        }
    
    def clear_dead_letter_queue(self):
        """Clear dead letter queue"""
        self.dead_letter_queue.clear()
        self.statistics['dead_letter_size'] = 0
        logger.info(f"Cleared dead letter queue for event bus: {self.name}")
    
    def retry_dead_letter_messages(self, max_retries: int = 3):
        """Retry messages from dead letter queue"""
        retry_count = 0
        
        for message in self.dead_letter_queue[:]:
            if message.attempts < max_retries:
                message.status = 'pending'
                message.attempts = 0
                self.message_queue.append(message)
                self.dead_letter_queue.remove(message)
                retry_count += 1
        
        self.statistics['queue_size'] = len(self.message_queue)
        self.statistics['dead_letter_size'] = len(self.dead_letter_queue)
        
        logger.info(f"Retried {retry_count} messages from dead letter queue")
        return retry_count
    
    def enable(self):
        """Enable event bus"""
        self.enabled = True
        logger.info(f"Event bus {self.name} enabled")
    
    def disable(self):
        """Disable event bus"""
        self.enabled = False
        logger.info(f"Event bus {self.name} disabled")
    
    def clear_queue(self):
        """Clear message queue"""
        self.message_queue.clear()
        self.statistics['queue_size'] = 0
        logger.info(f"Cleared message queue for event bus: {self.name}")


class EventBusManager:
    """Manager for multiple event buses"""
    
    def __init__(self):
        self.event_buses = {}
        self.global_subscribers = []
        self.enabled = True
    
    def create_event_bus(self, bus_name: str, max_queue_size: int = 10000) -> EventBus:
        """Create event bus"""
        bus = EventBus(bus_name, max_queue_size)
        self.event_buses[bus_name] = bus
        logger.info(f"Created event bus: {bus_name}")
        return bus
    
    def remove_event_bus(self, bus_name: str) -> bool:
        """Remove event bus"""
        if bus_name in self.event_buses:
            bus = self.event_buses[bus_name]
            bus.stop_processing()
            del self.event_buses[bus_name]
            logger.info(f"Removed event bus: {bus_name}")
            return True
        return False
    
    def get_event_bus(self, bus_name: str) -> Optional[EventBus]:
        """Get event bus by name"""
        return self.event_buses.get(bus_name)
    
    def publish_to_bus(self, bus_name: str, message: EventBusMessage) -> bool:
        """Publish message to specific bus"""
        bus = self.get_event_bus(bus_name)
        if bus:
            return bus.publish(message)
        return False
    
    def publish_to_all_buses(self, message: EventBusMessage) -> List[bool]:
        """Publish message to all buses"""
        results = []
        for bus in self.event_buses.values():
            results.append(bus.publish(message))
        return results
    
    def add_global_subscriber(self, subscriber: EventSubscriber):
        """Add global subscriber to all buses"""
        self.global_subscribers.append(subscriber)
        
        for bus in self.event_buses.values():
            bus.subscribe(subscriber)
        
        logger.info(f"Added global subscriber: {subscriber.name}")
    
    def remove_global_subscriber(self, subscriber_name: str):
        """Remove global subscriber from all buses"""
        self.global_subscribers = [
            s for s in self.global_subscribers if s.name != subscriber_name
        ]
        
        for bus in self.event_buses.values():
            bus.unsubscribe(subscriber_name)
        
        logger.info(f"Removed global subscriber: {subscriber_name}")
    
    async def start_all_processing(self):
        """Start processing for all buses"""
        tasks = []
        for bus in self.event_buses.values():
            task = asyncio.create_task(bus.start_processing())
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks)
    
    def stop_all_processing(self):
        """Stop processing for all buses"""
        for bus in self.event_buses.values():
            bus.stop_processing()
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all buses"""
        return {
            'enabled': self.enabled,
            'total_buses': len(self.event_buses),
            'global_subscribers': len(self.global_subscribers),
            'buses': {
                name: bus.get_statistics()
                for name, bus in self.event_buses.items()
            }
        }
    
    def enable_all_buses(self):
        """Enable all buses"""
        for bus in self.event_buses.values():
            bus.enable()
    
    def disable_all_buses(self):
        """Disable all buses"""
        for bus in self.event_buses.values():
            bus.disable()
    
    def enable(self):
        """Enable event bus manager"""
        self.enabled = True
        logger.info("Event bus manager enabled")
    
    def disable(self):
        """Disable event bus manager"""
        self.enabled = False
        logger.info("Event bus manager disabled")


# Global event bus manager
event_bus_manager = EventBusManager()

# Create default event bus
default_event_bus = event_bus_manager.create_event_bus('default')


# Export symbols
__all__ = [
    'EventBusMessage',
    'EventSubscriber',
    'EventBus',
    'EventBusManager',
    'event_bus_manager',
    'default_event_bus'
]