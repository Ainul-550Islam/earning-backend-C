"""
Bridge System - Cross-Module Communication Bridge

Bridge pattern implementation for connecting different modules and services
within the rate limiting system and external integrations.
"""

import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union, Type
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, BridgeError, BridgeTimeoutError
from .integ_registry import integration_registry
from .event_bus import EventBus, Event

logger = logging.getLogger(__name__)


class BridgeType(Enum):
    """Types of bridges."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    BATCH = "batch"
    STREAMING = "streaming"
    REQUEST_RESPONSE = "request_response"
    PUBLISH_SUBSCRIBE = "publish_subscribe"


class BridgeState(Enum):
    """Bridge states."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class BridgeMessage:
    """Message sent through bridge."""
    message_id: str
    source: str
    destination: str
    message_type: str
    payload: Dict[str, Any]
    headers: Dict[str, Any] = field(default_factory=dict)
    priority: IntegrationPriority = IntegrationPriority.NORMAL
    timestamp: datetime = field(default_factory=timezone.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class BridgeConfig:
    """Bridge configuration."""
    name: str
    bridge_type: BridgeType
    source_module: str
    target_module: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_size: int = 100
    buffer_size: int = 1000
    compression: bool = False
    encryption: bool = False


class Bridge:
    """Base bridge implementation for module communication."""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.state = BridgeState.ACTIVE
        self.message_queue = Queue(maxsize=config.buffer_size)
        self.response_queue = Queue(maxsize=config.buffer_size)
        self.event_bus = EventBus()
        self.handlers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
        self.statistics = {
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0,
            'last_message_time': None,
            'average_processing_time': 0.0
        }
        self._lock = threading.RLock()
        
        # Register event handlers
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Register event handlers for the bridge."""
        self.event_bus.subscribe(f"bridge.{self.config.name}.message_received", self._handle_message_received)
        self.event_bus.subscribe(f"bridge.{self.config.name}.message_sent", self._handle_message_sent)
        self.event_bus.subscribe(f"bridge.{self.config.name}.error", self._handle_error)
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register message handler."""
        self.handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")
    
    def add_middleware(self, middleware: Callable):
        """Add middleware to the bridge."""
        self.middleware.append(middleware)
        logger.info(f"Added middleware: {middleware.__name__}")
    
    async def send_message(self, message: BridgeMessage) -> bool:
        """Send message through bridge."""
        try:
            if self.state != BridgeState.ACTIVE:
                raise BridgeError(f"Bridge is not active: {self.state}")
            
            # Apply middleware
            processed_message = await self._apply_middleware(message)
            
            # Send based on bridge type
            if self.config.bridge_type == BridgeType.SYNCHRONOUS:
                success = await self._send_synchronous(processed_message)
            elif self.config.bridge_type == BridgeType.ASYNCHRONOUS:
                success = await self._send_asynchronous(processed_message)
            elif self.config.bridge_type == BridgeType.BATCH:
                success = await self._send_batch(processed_message)
            elif self.config.bridge_type == BridgeType.STREAMING:
                success = await self._send_streaming(processed_message)
            else:
                success = await self._send_request_response(processed_message)
            
            if success:
                self.statistics['messages_sent'] += 1
                self.statistics['last_message_time'] = timezone.now()
                
                # Publish event
                await self.event_bus.publish(
                    Event(f"bridge.{self.config.name}.message_sent", {
                        'message_id': message.message_id,
                        'source': message.source,
                        'destination': message.destination
                    })
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            self.statistics['errors'] += 1
            await self.event_bus.publish(
                Event(f"bridge.{self.config.name}.error", {
                    'error': str(e),
                    'message_id': message.message_id
                })
            )
            return False
    
    async def _apply_middleware(self, message: BridgeMessage) -> BridgeMessage:
        """Apply middleware to message."""
        processed_message = message
        
        for middleware in self.middleware:
            try:
                if asyncio.iscoroutinefunction(middleware):
                    processed_message = await middleware(processed_message)
                else:
                    processed_message = middleware(processed_message)
            except Exception as e:
                logger.error(f"Middleware failed: {middleware.__name__} - {str(e)}")
                raise BridgeError(f"Middleware error: {str(e)}")
        
        return processed_message
    
    async def _send_synchronous(self, message: BridgeMessage) -> bool:
        """Send message synchronously."""
        try:
            # Get handler for message type
            handler = self.handlers.get(message.message_type)
            if not handler:
                raise BridgeError(f"No handler for message type: {message.message_type}")
            
            # Execute handler
            start_time = timezone.now()
            
            if asyncio.iscoroutinefunction(handler):
                response = await handler(message)
            else:
                response = handler(message)
            
            # Update processing time
            processing_time = (timezone.now() - start_time).total_seconds()
            self._update_processing_time(processing_time)
            
            # Send response if reply_to is specified
            if message.reply_to:
                response_message = BridgeMessage(
                    message_id=f"response_{message.message_id}",
                    source=self.config.target_module,
                    destination=message.source,
                    message_type="response",
                    payload=response if isinstance(response, dict) else {'result': response},
                    correlation_id=message.correlation_id or message.message_id,
                    reply_to=message.message_id
                )
                await self._send_response(response_message)
            
            return True
            
        except Exception as e:
            logger.error(f"Synchronous send failed: {str(e)}")
            return False
    
    async def _send_asynchronous(self, message: BridgeMessage) -> bool:
        """Send message asynchronously."""
        try:
            # Add to queue
            self.message_queue.put(message)
            
            # Process in background
            asyncio.create_task(self._process_async_message(message))
            
            return True
            
        except Exception as e:
            logger.error(f"Asynchronous send failed: {str(e)}")
            return False
    
    async def _send_batch(self, message: BridgeMessage) -> bool:
        """Send message in batch."""
        try:
            # Add to batch queue
            self.message_queue.put(message)
            
            # Check if batch is ready to send
            if self.message_queue.qsize() >= self.config.batch_size:
                await self._process_batch()
            
            return True
            
        except Exception as e:
            logger.error(f"Batch send failed: {str(e)}")
            return False
    
    async def _send_streaming(self, message: BridgeMessage) -> bool:
        """Send message as stream."""
        try:
            # Add to stream queue
            self.message_queue.put(message)
            
            # Process immediately for streaming
            asyncio.create_task(self._process_stream_message(message))
            
            return True
            
        except Exception as e:
            logger.error(f"Streaming send failed: {str(e)}")
            return False
    
    async def _send_request_response(self, message: BridgeMessage) -> bool:
        """Send request-response message."""
        try:
            # Get handler for message type
            handler = self.handlers.get(message.message_type)
            if not handler:
                raise BridgeError(f"No handler for message type: {message.message_type}")
            
            # Execute handler with timeout
            start_time = timezone.now()
            
            try:
                if asyncio.iscoroutinefunction(handler):
                    response = await asyncio.wait_for(handler(message), timeout=message.timeout)
                else:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(handler, message), 
                        timeout=message.timeout
                    )
            except asyncio.TimeoutError:
                raise BridgeTimeoutError(f"Handler timeout: {message.timeout}s")
            
            # Update processing time
            processing_time = (timezone.now() - start_time).total_seconds()
            self._update_processing_time(processing_time)
            
            # Send response
            response_message = BridgeMessage(
                message_id=f"response_{message.message_id}",
                source=self.config.target_module,
                destination=message.source,
                message_type="response",
                payload=response if isinstance(response, dict) else {'result': response},
                correlation_id=message.correlation_id or message.message_id,
                reply_to=message.message_id
            )
            
            await self._send_response(response_message)
            return True
            
        except Exception as e:
            logger.error(f"Request-response send failed: {str(e)}")
            return False
    
    async def _send_response(self, message: BridgeMessage) -> bool:
        """Send response message."""
        try:
            self.response_queue.put(message)
            
            # Publish response event
            await self.event_bus.publish(
                Event(f"bridge.{self.config.name}.response_sent", {
                    'message_id': message.message_id,
                    'correlation_id': message.correlation_id
                })
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Response send failed: {str(e)}")
            return False
    
    async def _process_async_message(self, message: BridgeMessage):
        """Process asynchronous message."""
        try:
            handler = self.handlers.get(message.message_type)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    await asyncio.to_thread(handler, message)
            
            self.statistics['messages_received'] += 1
            
        except Exception as e:
            logger.error(f"Async message processing failed: {str(e)}")
            self.statistics['errors'] += 1
    
    async def _process_batch(self):
        """Process batch of messages."""
        try:
            messages = []
            
            # Collect batch
            while len(messages) < self.config.batch_size and not self.message_queue.empty():
                try:
                    message = self.message_queue.get_nowait()
                    messages.append(message)
                except Empty:
                    break
            
            if messages:
                # Process batch
                handler = self.handlers.get("batch")
                if handler:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(messages)
                    else:
                        await asyncio.to_thread(handler, messages)
                
                self.statistics['messages_received'] += len(messages)
        
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            self.statistics['errors'] += 1
    
    async def _process_stream_message(self, message: BridgeMessage):
        """Process streaming message."""
        try:
            handler = self.handlers.get("stream")
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    await asyncio.to_thread(handler, message)
            
            self.statistics['messages_received'] += 1
        
        except Exception as e:
            logger.error(f"Stream message processing failed: {str(e)}")
            self.statistics['errors'] += 1
    
    def _update_processing_time(self, processing_time: float):
        """Update average processing time."""
        current_avg = self.statistics['average_processing_time']
        total_messages = self.statistics['messages_sent'] + self.statistics['messages_received']
        
        if total_messages == 1:
            self.statistics['average_processing_time'] = processing_time
        else:
            self.statistics['average_processing_time'] = (
                (current_avg * (total_messages - 1) + processing_time) / total_messages
            )
    
    async def _handle_message_received(self, event: Event):
        """Handle message received event."""
        logger.debug(f"Message received: {event.data}")
    
    async def _handle_message_sent(self, event: Event):
        """Handle message sent event."""
        logger.debug(f"Message sent: {event.data}")
    
    async def _handle_error(self, event: Event):
        """Handle error event."""
        logger.error(f"Bridge error: {event.data}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'state': self.state.value,
            'queue_size': self.message_queue.qsize(),
            'response_queue_size': self.response_queue.qsize(),
            'handlers_count': len(self.handlers),
            'middleware_count': len(self.middleware),
            **self.statistics
        }
    
    def set_state(self, state: BridgeState):
        """Set bridge state."""
        with self._lock:
            old_state = self.state
            self.state = state
            logger.info(f"Bridge state changed: {old_state.value} -> {state.value}")


class BridgeManager:
    """Manager for multiple bridges."""
    
    def __init__(self):
        self.bridges: Dict[str, Bridge] = {}
        self.bridge_configs: Dict[str, BridgeConfig] = {}
        self._lock = threading.RLock()
    
    def create_bridge(self, config: BridgeConfig) -> Bridge:
        """Create a new bridge."""
        with self._lock:
            if config.name in self.bridges:
                raise BridgeError(f"Bridge already exists: {config.name}")
            
            bridge = Bridge(config)
            self.bridges[config.name] = bridge
            self.bridge_configs[config.name] = config
            
            logger.info(f"Created bridge: {config.name}")
            return bridge
    
    def get_bridge(self, name: str) -> Optional[Bridge]:
        """Get bridge by name."""
        return self.bridges.get(name)
    
    def remove_bridge(self, name: str) -> bool:
        """Remove bridge."""
        with self._lock:
            if name in self.bridges:
                bridge = self.bridges[name]
                bridge.set_state(BridgeState.INACTIVE)
                del self.bridges[name]
                del self.bridge_configs[name]
                logger.info(f"Removed bridge: {name}")
                return True
            return False
    
    def get_all_bridges(self) -> Dict[str, Bridge]:
        """Get all bridges."""
        return self.bridges.copy()
    
    def get_bridges_by_type(self, bridge_type: BridgeType) -> List[Bridge]:
        """Get bridges by type."""
        return [
            bridge for bridge in self.bridges.values()
            if bridge.config.bridge_type == bridge_type
        ]
    
    def get_bridges_by_module(self, module_name: str) -> List[Bridge]:
        """Get bridges by module."""
        return [
            bridge for bridge in self.bridges.values()
            if (bridge.config.source_module == module_name or 
                bridge.config.target_module == module_name)
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all bridges."""
        stats = {
            'total_bridges': len(self.bridges),
            'active_bridges': len([b for b in self.bridges.values() if b.state == BridgeState.ACTIVE]),
            'total_messages_sent': 0,
            'total_messages_received': 0,
            'total_errors': 0,
            'bridges': {}
        }
        
        for name, bridge in self.bridges.items():
            bridge_stats = bridge.get_statistics()
            stats['bridges'][name] = bridge_stats
            stats['total_messages_sent'] += bridge_stats['messages_sent']
            stats['total_messages_received'] += bridge_stats['messages_received']
            stats['total_errors'] += bridge_stats['errors']
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all bridges."""
        health_status = {
            'total_bridges': len(self.bridges),
            'healthy_bridges': 0,
            'unhealthy_bridges': 0,
            'bridges': {}
        }
        
        for name, bridge in self.bridges.items():
            is_healthy = (
                bridge.state == BridgeState.ACTIVE and
                bridge.statistics['errors'] < 10 and
                bridge.message_queue.qsize() < bridge.config.buffer_size * 0.8
            )
            
            if is_healthy:
                health_status['healthy_bridges'] += 1
            else:
                health_status['unhealthy_bridges'] += 1
            
            health_status['bridges'][name] = {
                'state': bridge.state.value,
                'healthy': is_healthy,
                'queue_size': bridge.message_queue.qsize(),
                'errors': bridge.statistics['errors']
            }
        
        return health_status


# Global bridge manager
bridge_manager = BridgeManager()


# Bridge factory functions
def create_synchronous_bridge(name: str, source_module: str, target_module: str, 
                             config: Dict[str, Any] = None) -> Bridge:
    """Create synchronous bridge."""
    bridge_config = BridgeConfig(
        name=name,
        bridge_type=BridgeType.SYNCHRONOUS,
        source_module=source_module,
        target_module=target_module,
        config=config or {}
    )
    
    return bridge_manager.create_bridge(bridge_config)


def create_asynchronous_bridge(name: str, source_module: str, target_module: str,
                             config: Dict[str, Any] = None) -> Bridge:
    """Create asynchronous bridge."""
    bridge_config = BridgeConfig(
        name=name,
        bridge_type=BridgeType.ASYNCHRONOUS,
        source_module=source_module,
        target_module=target_module,
        config=config or {}
    )
    
    return bridge_manager.create_bridge(bridge_config)


def create_batch_bridge(name: str, source_module: str, target_module: str,
                       config: Dict[str, Any] = None) -> Bridge:
    """Create batch bridge."""
    bridge_config = BridgeConfig(
        name=name,
        bridge_type=BridgeType.BATCH,
        source_module=source_module,
        target_module=target_module,
        config=config or {}
    )
    
    return bridge_manager.create_bridge(bridge_config)


def create_streaming_bridge(name: str, source_module: str, target_module: str,
                           config: Dict[str, Any] = None) -> Bridge:
    """Create streaming bridge."""
    bridge_config = BridgeConfig(
        name=name,
        bridge_type=BridgeType.STREAMING,
        source_module=source_module,
        target_module=target_module,
        config=config or {}
    )
    
    return bridge_manager.create_bridge(bridge_config)
