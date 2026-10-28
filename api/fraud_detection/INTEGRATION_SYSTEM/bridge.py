# =============================================================================
# INTEGRATION_SYSTEM/bridge.py
# =============================================================================
"""
Core Bridge System for Module Communication.

Provides centralized communication bridge between different modules
and integration systems. Handles message routing, transformation,
and protocol translation.
"""

from __future__ import annotations

import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Type
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from contextlib import asynccontextmanager
from abc import abstractmethod
from abc import ABC

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .integ_constants import IntegrationStatus, Priority, DataFormat
from .integ_exceptions import BridgeError, BridgeConnectionError, BridgeTimeoutError
from .transformer import JSONTransformer
from .circuit_breaker import CircuitBreaker
from .integ_signals import IntegrationSignalManager, SignalType

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BridgeMessageType(Enum):
    """Types of bridge messages."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    COMMAND = "command"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class BridgeProtocol(Enum):
    """Bridge communication protocols."""
    HTTP = "http"
    WEBSOCKET = "websocket"
    MESSAGE_QUEUE = "message_queue"
    RPC = "rpc"
    EVENT_STREAM = "event_stream"
    GRPC = "grpc"


@dataclass
class BridgeMessage:
    """Bridge message structure."""
    message_id: str
    message_type: BridgeMessageType
    source_module: str
    target_module: str
    protocol: BridgeProtocol
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    timestamp: datetime = field(default_factory=timezone.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timeout: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())


@dataclass
class BridgeRoute:
    """Bridge route configuration."""
    source_pattern: str
    target_pattern: str
    protocol: BridgeProtocol
    transformer: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    rate_limit: Optional[int] = None
    circuit_breaker: bool = True
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeConnection:
    """Bridge connection information."""
    connection_id: str
    module_name: str
    protocol: BridgeProtocol
    endpoint: str
    status: IntegrationStatus = IntegrationStatus.INACTIVE
    last_heartbeat: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BridgeRouter:
    """
    Router for bridge messages.
    
    Handles message routing, pattern matching,
    and protocol selection.
    """
    
    def __init__(self):
        """Initialize bridge router."""
        self.routes: List[BridgeRoute] = []
        self.connections: Dict[str, BridgeConnection] = {}
        self.pattern_cache: Dict[str, List[BridgeRoute]] = {}
        
        logger.info("BridgeRouter initialized")
    
    def add_route(self, route: BridgeRoute) -> None:
        """
        Add a new route.
        
        Args:
            route: Route configuration
        """
        self.routes.append(route)
        self._clear_pattern_cache()
        logger.info(f"Added route: {route.source_pattern} -> {route.target_pattern}")
    
    def remove_route(self, source_pattern: str, target_pattern: str) -> bool:
        """
        Remove a route.
        
        Args:
            source_pattern: Source pattern
            target_pattern: Target pattern
            
        Returns:
            True if route removed
        """
        for i, route in enumerate(self.routes):
            if route.source_pattern == source_pattern and route.target_pattern == target_pattern:
                del self.routes[i]
                self._clear_pattern_cache()
                logger.info(f"Removed route: {source_pattern} -> {target_pattern}")
                return True
        return False
    
    def find_routes(self, source_module: str, target_module: str) -> List[BridgeRoute]:
        """
        Find routes for module communication.
        
        Args:
            source_module: Source module name
            target_module: Target module name
            
        Returns:
            List of matching routes
        """
        cache_key = f"{source_module}->{target_module}"
        
        if cache_key in self.pattern_cache:
            return self.pattern_cache[cache_key]
        
        matching_routes = []
        
        for route in self.routes:
            if not route.enabled:
                continue
            
            if self._match_pattern(route.source_pattern, source_module) and \
               self._match_pattern(route.target_pattern, target_module):
                matching_routes.append(route)
        
        # Sort by priority (could be added to route config)
        self.pattern_cache[cache_key] = matching_routes
        return matching_routes
    
    def _match_pattern(self, pattern: str, value: str) -> bool:
        """
        Match pattern against value.
        
        Args:
            pattern: Pattern to match
            value: Value to test
            
        Returns:
            True if pattern matches
        """
        if pattern == "*":
            return True
        
        if pattern == value:
            return True
        
        # Support wildcards (e.g., "api.*")
        if "*" in pattern:
            import re
            regex_pattern = pattern.replace("*", ".*")
            return re.match(f"^{regex_pattern}$", value) is not None
        
        return False
    
    def _clear_pattern_cache(self) -> None:
        """Clear pattern matching cache."""
        self.pattern_cache.clear()
    
    def add_connection(self, connection: BridgeConnection) -> None:
        """
        Add a connection.
        
        Args:
            connection: Connection information
        """
        self.connections[connection.connection_id] = connection
        logger.info(f"Added connection: {connection.connection_id}")
    
    def remove_connection(self, connection_id: str) -> bool:
        """
        Remove a connection.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            True if connection removed
        """
        if connection_id in self.connections:
            del self.connections[connection_id]
            logger.info(f"Removed connection: {connection_id}")
            return True
        return False
    
    def get_connection(self, module_name: str) -> Optional[BridgeConnection]:
        """
        Get connection for module.
        
        Args:
            module_name: Module name
            
        Returns:
            Connection information or None
        """
        for connection in self.connections.values():
            if connection.module_name == module_name and connection.status == IntegrationStatus.ACTIVE:
                return connection
        return None
    
    def get_all_connections(self) -> List[BridgeConnection]:
        """Get all connections."""
        return list(self.connections.values())


class BridgeProtocolHandler(ABC):
    """
    Abstract base class for bridge protocol handlers.
    """
    
    @abstractmethod
    async def send_message(self, message: BridgeMessage, connection: BridgeConnection) -> Dict[str, Any]:
        """Send message using specific protocol."""
        pass
    
    @abstractmethod
    async def receive_message(self, connection: BridgeConnection) -> Optional[BridgeMessage]:
        """Receive message using specific protocol."""
        pass
    
    @abstractmethod
    async def establish_connection(self, connection: BridgeConnection) -> bool:
        """Establish connection using specific protocol."""
        pass
    
    @abstractmethod
    async def close_connection(self, connection: BridgeConnection) -> None:
        """Close connection using specific protocol."""
        pass


class HTTPBridgeHandler(BridgeProtocolHandler):
    """HTTP protocol handler for bridge communication."""
    
    def __init__(self):
        """Initialize HTTP bridge handler."""
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def send_message(self, message: BridgeMessage, connection: BridgeConnection) -> Dict[str, Any]:
        """Send message via HTTP."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = connection.endpoint
        headers = {
            'Content-Type': 'application/json',
            'X-Message-Type': message.message_type.value,
            'X-Source-Module': message.source_module,
            'X-Target-Module': message.target_module,
            'X-Correlation-ID': message.correlation_id,
            **message.headers
        }
        
        try:
            async with self.session.post(
                url,
                json=message.payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=message.timeout or 30)
            ) as response:
                
                if response.status >= 400:
                    error_text = await response.text()
                    raise BridgeError(f"HTTP {response.status}: {error_text}")
                
                result = await response.json()
                return result
                
        except asyncio.TimeoutError:
            raise BridgeTimeoutError(f"HTTP request timeout for {connection.connection_id}")
        except Exception as e:
            raise BridgeConnectionError(f"HTTP connection error: {e}")
    
    async def receive_message(self, connection: BridgeConnection) -> Optional[BridgeMessage]:
        """Receive message via HTTP (not typically used for HTTP)."""
        # HTTP is typically request/response, not streaming
        return None
    
    async def establish_connection(self, connection: BridgeConnection) -> bool:
        """Establish HTTP connection."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Test connection with health check
            health_url = f"{connection.endpoint}/health"
            async with self.session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status < 400:
                    connection.status = IntegrationStatus.ACTIVE
                    connection.last_heartbeat = timezone.now()
                    return True
                else:
                    connection.status = IntegrationStatus.ERROR
                    return False
                    
        except Exception as e:
            connection.status = IntegrationStatus.ERROR
            logger.error(f"HTTP connection failed for {connection.connection_id}: {e}")
            return False
    
    async def close_connection(self, connection: BridgeConnection) -> None:
        """Close HTTP connection."""
        connection.status = IntegrationStatus.INACTIVE


class WebSocketBridgeHandler(BridgeProtocolHandler):
    """WebSocket protocol handler for bridge communication."""
    
    def __init__(self):
        """Initialize WebSocket bridge handler."""
        self.connections: Dict[str, aiohttp.ClientWebSocketResponse] = {}
    
    async def send_message(self, message: BridgeMessage, connection: BridgeConnection) -> Dict[str, Any]:
        """Send message via WebSocket."""
        ws_connection = self.connections.get(connection.connection_id)
        if not ws_connection:
            raise BridgeConnectionError(f"WebSocket connection not found: {connection.connection_id}")
        
        try:
            message_data = {
                'message_id': message.message_id,
                'message_type': message.message_type.value,
                'source_module': message.source_module,
                'target_module': message.target_module,
                'payload': message.payload,
                'headers': message.headers,
                'correlation_id': message.correlation_id,
                'timestamp': message.timestamp.isoformat()
            }
            
            await ws_connection.send_json(message_data)
            return {'status': 'sent'}
            
        except Exception as e:
            raise BridgeConnectionError(f"WebSocket send error: {e}")
    
    async def receive_message(self, connection: BridgeConnection) -> Optional[BridgeMessage]:
        """Receive message via WebSocket."""
        ws_connection = self.connections.get(connection.connection_id)
        if not ws_connection:
            return None
        
        try:
            message_data = await ws_connection.receive_json()
            
            return BridgeMessage(
                message_id=message_data['message_id'],
                message_type=BridgeMessageType(message_data['message_type']),
                source_module=message_data['source_module'],
                target_module=message_data['target_module'],
                protocol=BridgeProtocol.WEBSOCKET,
                payload=message_data['payload'],
                headers=message_data.get('headers', {}),
                correlation_id=message_data.get('correlation_id'),
                timestamp=datetime.fromisoformat(message_data['timestamp'])
            )
            
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            return None
    
    async def establish_connection(self, connection: BridgeConnection) -> bool:
        """Establish WebSocket connection."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            ws_connection = await self.session.ws_connect(connection.endpoint)
            self.connections[connection.connection_id] = ws_connection
            
            connection.status = IntegrationStatus.ACTIVE
            connection.last_heartbeat = timezone.now()
            
            logger.info(f"WebSocket connection established: {connection.connection_id}")
            return True
            
        except Exception as e:
            connection.status = IntegrationStatus.ERROR
            logger.error(f"WebSocket connection failed for {connection.connection_id}: {e}")
            return False
    
    async def close_connection(self, connection: BridgeConnection) -> None:
        """Close WebSocket connection."""
        ws_connection = self.connections.pop(connection.connection_id, None)
        if ws_connection:
            await ws_connection.close()
        
        connection.status = IntegrationStatus.INACTIVE


class MessageQueueBridgeHandler(BridgeProtocolHandler):
    """Message Queue protocol handler for bridge communication."""
    
    def __init__(self):
        """Initialize Message Queue bridge handler."""
        self.connections: Dict[str, Any] = {}  # Would be actual queue connections
    
    async def send_message(self, message: BridgeMessage, connection: BridgeConnection) -> Dict[str, Any]:
        """Send message via message queue."""
        # This would implement actual message queue sending
        queue_connection = self.connections.get(connection.connection_id)
        if not queue_connection:
            raise BridgeConnectionError(f"Queue connection not found: {connection.connection_id}")
        
        try:
            # Send message to queue
            message_data = {
                'message_id': message.message_id,
                'message_type': message.message_type.value,
                'source_module': message.source_module,
                'target_module': message.target_module,
                'payload': message.payload,
                'headers': message.headers,
                'correlation_id': message.correlation_id,
                'timestamp': message.timestamp.isoformat()
            }
            
            # This would use actual queue client (RabbitMQ, Redis, etc.)
            # await queue_connection.publish(connection.endpoint, message_data)
            
            return {'status': 'queued'}
            
        except Exception as e:
            raise BridgeConnectionError(f"Message queue send error: {e}")
    
    async def receive_message(self, connection: BridgeConnection) -> Optional[BridgeMessage]:
        """Receive message via message queue."""
        queue_connection = self.connections.get(connection.connection_id)
        if not queue_connection:
            return None
        
        try:
            # This would use actual queue client to receive message
            # message_data = await queue_connection.consume(connection.endpoint)
            
            # For now, return None
            return None
            
        except Exception as e:
            logger.error(f"Message queue receive error: {e}")
            return None
    
    async def establish_connection(self, connection: BridgeConnection) -> bool:
        """Establish message queue connection."""
        try:
            # This would establish actual queue connection
            # queue_connection = await connect_to_queue(connection.endpoint)
            # self.connections[connection.connection_id] = queue_connection
            
            connection.status = IntegrationStatus.ACTIVE
            connection.last_heartbeat = timezone.now()
            
            logger.info(f"Message queue connection established: {connection.connection_id}")
            return True
            
        except Exception as e:
            connection.status = IntegrationStatus.ERROR
            logger.error(f"Message queue connection failed for {connection.connection_id}: {e}")
            return False
    
    async def close_connection(self, connection: BridgeConnection) -> None:
        """Close message queue connection."""
        queue_connection = self.connections.pop(connection.connection_id, None)
        if queue_connection:
            # await queue_connection.close()
            pass
        
        connection.status = IntegrationStatus.INACTIVE


class BridgeSystem:
    """
    Core bridge system for module communication.
    
    Provides centralized message routing, protocol handling,
    and communication management between modules.
    """
    
    def __init__(self):
        """Initialize bridge system."""
        self.router = BridgeRouter()
        self.transformer = JSONTransformer()
        self.signal_manager = IntegrationSignalManager()
        
        # Protocol handlers
        self.protocol_handlers: Dict[BridgeProtocol, BridgeProtocolHandler] = {
            BridgeProtocol.HTTP: HTTPBridgeHandler(),
            BridgeProtocol.WEBSOCKET: WebSocketBridgeHandler(),
            BridgeProtocol.MESSAGE_QUEUE: MessageQueueBridgeHandler(),
        }
        
        # Circuit breakers for connections
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Message tracking
        self.pending_messages: Dict[str, BridgeMessage] = {}
        self.message_history: List[BridgeMessage] = []
        
        # Statistics
        self.message_count = 0
        self.success_count = 0
        self.error_count = 0
        
        # Configuration
        self.max_pending_messages = getattr(settings, 'BRIDGE_MAX_PENDING_MESSAGES', 10000)
        self.message_history_size = getattr(settings, 'BRIDGE_MESSAGE_HISTORY_SIZE', 1000)
        self.default_timeout = getattr(settings, 'BRIDGE_DEFAULT_TIMEOUT', 30)
        
        logger.info("BridgeSystem initialized")
    
    async def send_message(self, message: BridgeMessage) -> Dict[str, Any]:
        """
        Send message through bridge.
        
        Args:
            message: Message to send
            
        Returns:
            Send result
        """
        try:
            # Find routes
            routes = self.router.find_routes(message.source_module, message.target_module)
            if not routes:
                raise BridgeError(f"No route found for {message.source_module} -> {message.target_module}")
            
            # Use first matching route
            route = routes[0]
            
            # Get connection
            connection = self.router.get_connection(message.target_module)
            if not connection:
                raise BridgeError(f"No active connection for module: {message.target_module}")
            
            # Check circuit breaker
            circuit_breaker = self._get_circuit_breaker(connection.connection_id)
            if not circuit_breaker.can_execute():
                raise BridgeError(f"Circuit breaker open for connection: {connection.connection_id}")
            
            # Transform message if needed
            if route.transformer:
                message.payload = await self.transformer.transform(
                    message.payload, route.transformer, 'outbound'
                )
            
            # Add to pending
            self.pending_messages[message.message_id] = message
            self.message_count += 1
            
            # Get protocol handler
            handler = self.protocol_handlers.get(route.protocol)
            if not handler:
                raise BridgeError(f"No handler for protocol: {route.protocol}")
            
            # Send message
            try:
                result = await handler.send_message(message, connection)
                circuit_breaker.record_success()
                self.success_count += 1
                
                # Remove from pending
                self.pending_messages.pop(message.message_id, None)
                
                # Add to history
                self._add_to_history(message)
                
                # Emit signal
                await self.signal_manager.emit_signal_async(
                    self.signal_manager.IntegrationSignalData(
                        signal_type=SignalType.INTEGRATION_COMPLETED,
                        integration_name=f"bridge_{connection.connection_id}",
                        integration_type=None,  # Bridge doesn't have integration type
                        timestamp=timezone.now(),
                        data={'message_id': message.message_id, 'target': message.target_module}
                    )
                )
                
                return result
                
            except Exception as e:
                circuit_breaker.record_failure()
                self.error_count += 1
                raise
                
        except Exception as e:
            logger.error(f"Failed to send message {message.message_id}: {e}")
            raise
    
    async def receive_message(self, connection_id: str) -> Optional[BridgeMessage]:
        """
        Receive message from connection.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Received message or None
        """
        try:
            connection = self.router.connections.get(connection_id)
            if not connection:
                return None
            
            handler = self.protocol_handlers.get(connection.protocol)
            if not handler:
                return None
            
            message = await handler.receive_message(connection)
            if message:
                self.message_count += 1
                self._add_to_history(message)
                connection.message_count += 1
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to receive message from {connection_id}: {e}")
            return None
    
    async def establish_connection(self, connection: BridgeConnection) -> bool:
        """
        Establish connection.
        
        Args:
            connection: Connection to establish
            
        Returns:
            True if connection established
        """
        try:
            handler = self.protocol_handlers.get(connection.protocol)
            if not handler:
                raise BridgeError(f"No handler for protocol: {connection.protocol}")
            
            success = await handler.establish_connection(connection)
            if success:
                self.router.add_connection(connection)
                logger.info(f"Connection established: {connection.connection_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to establish connection {connection.connection_id}: {e}")
            return False
    
    async def close_connection(self, connection_id: str) -> None:
        """
        Close connection.
        
        Args:
            connection_id: Connection ID
        """
        try:
            connection = self.router.connections.get(connection_id)
            if not connection:
                return
            
            handler = self.protocol_handlers.get(connection.protocol)
            if handler:
                await handler.close_connection(connection)
            
            self.router.remove_connection(connection_id)
            
            # Remove circuit breaker
            self.circuit_breakers.pop(connection_id, None)
            
            logger.info(f"Connection closed: {connection_id}")
            
        except Exception as e:
            logger.error(f"Failed to close connection {connection_id}: {e}")
    
    def _get_circuit_breaker(self, connection_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for connection."""
        if connection_id not in self.circuit_breakers:
            self.circuit_breakers[connection_id] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=BridgeConnectionError
            )
        return self.circuit_breakers[connection_id]
    
    def _add_to_history(self, message: BridgeMessage) -> None:
        """Add message to history."""
        self.message_history.append(message)
        
        # Trim history if needed
        if len(self.message_history) > self.message_history_size:
            self.message_history = self.message_history[-self.message_history_size:]
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get bridge system statistics."""
        return {
            'total_messages': self.message_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': (self.success_count / max(self.message_count, 1)) * 100,
            'pending_messages': len(self.pending_messages),
            'active_connections': len([
                c for c in self.router.connections.values() 
                if c.status == IntegrationStatus.ACTIVE
            ]),
            'total_routes': len(self.router.routes),
            'circuit_breakers': {
                conn_id: cb.state.value 
                for conn_id, cb in self.circuit_breakers.items()
            }
        }
    
    async def cleanup(self) -> None:
        """Cleanup bridge system resources."""
        # Close all connections
        for connection_id in list(self.router.connections.keys()):
            await self.close_connection(connection_id)
        
        # Clear data structures
        self.pending_messages.clear()
        self.message_history.clear()
        self.circuit_breakers.clear()
        
        logger.info("BridgeSystem cleanup completed")


# Global bridge system instance
_bridge_system = None


def get_bridge_system() -> BridgeSystem:
    """Get global bridge system instance."""
    global _bridge_system
    if _bridge_system is None:
        _bridge_system = BridgeSystem()
    return _bridge_system


# Convenience functions
async def send_bridge_message(source_module: str, target_module: str, 
                           payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Convenience function for sending bridge messages.
    
    Args:
        source_module: Source module name
        target_module: Target module name
        payload: Message payload
        **kwargs: Additional message parameters
        
    Returns:
        Send result
    """
    bridge = get_bridge_system()
    
    message = BridgeMessage(
        message_id=str(uuid.uuid4()),
        message_type=BridgeMessageType.REQUEST,
        source_module=source_module,
        target_module=target_module,
        protocol=BridgeProtocol.HTTP,  # Default
        payload=payload,
        **kwargs
    )
    
    return await bridge.send_message(message)


async def establish_bridge_connection(module_name: str, protocol: BridgeProtocol,
                                   endpoint: str, **kwargs) -> bool:
    """
    Convenience function for establishing bridge connections.
    
    Args:
        module_name: Module name
        protocol: Communication protocol
        endpoint: Connection endpoint
        **kwargs: Additional connection parameters
        
    Returns:
        True if connection established
    """
    bridge = get_bridge_system()
    
    connection = BridgeConnection(
        connection_id=str(uuid.uuid4()),
        module_name=module_name,
        protocol=protocol,
        endpoint=endpoint,
        **kwargs
    )
    
    return await bridge.establish_connection(connection)
