"""
Bridge System — Bridge components for connecting different systems.

This module provides bridge components that facilitate communication
between different systems, protocols, and data formats.
"""

from __future__ import annotations

import logging
import asyncio
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum

from .integ_constants import IntegrationType, ErrorCode
from .integ_exceptions import (
    IntegrationError, ConnectionError, DataFormatError,
    ValidationError, TimeoutError
)
from .integ_signals import (
    data_received, data_sent, integration_connected, integration_disconnected
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bridge Types
# ---------------------------------------------------------------------------

class BridgeType(Enum):
    """Bridge type enumeration."""
    PROTOCOL_BRIDGE = "protocol_bridge"
    DATA_FORMAT_BRIDGE = "data_format_bridge"
    SYSTEM_BRIDGE = "system_bridge"
    AUTHENTICATION_BRIDGE = "authentication_bridge"
    EVENT_BRIDGE = "event_bridge"
    MESSAGE_BRIDGE = "message_bridge"


class BridgeDirection(Enum):
    """Bridge direction enumeration."""
    BIDIRECTIONAL = "bidirectional"
    UNIDIRECTIONAL = "unidirectional"
    REQUEST_ONLY = "request_only"
    RESPONSE_ONLY = "response_only"


class BridgeState(Enum):
    """Bridge state enumeration."""
    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Bridge Data Classes
# ---------------------------------------------------------------------------

@dataclass
class BridgeConfig:
    """Configuration for a bridge."""
    
    id: str
    name: str
    bridge_type: BridgeType
    direction: BridgeDirection
    source_config: Dict[str, Any]
    target_config: Dict[str, Any]
    transformation_rules: List[Dict[str, Any]] = field(default_factory=list)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "bridge_type": self.bridge_type.value,
            "direction": self.direction.value,
            "source_config": self.source_config,
            "target_config": self.target_config,
            "transformation_rules": self.transformation_rules,
            "filters": self.filters,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class BridgeMessage:
    """Message passed through a bridge."""
    
    id: str
    source_system: str
    target_system: str
    payload: Any
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_system": self.source_system,
            "target_system": self.target_system,
            "payload": self.payload,
            "headers": self.headers,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id
        }


@dataclass
class BridgeMetrics:
    """Metrics for a bridge."""
    
    bridge_id: str
    messages_processed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    average_processing_time: float = 0.0
    last_activity: Optional[datetime] = None
    uptime_percentage: float = 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bridge_id": self.bridge_id,
            "messages_processed": self.messages_processed,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors": self.errors,
            "average_processing_time": self.average_processing_time,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "uptime_percentage": self.uptime_percentage
        }


# ---------------------------------------------------------------------------
# Abstract Bridge Base Class
# ---------------------------------------------------------------------------

class BaseBridge(ABC):
    """Abstract base class for all bridges."""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.state = BridgeState.INACTIVE
        self.metrics = BridgeMetrics(bridge_id=config.id)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    @property
    @abstractmethod
    def bridge_type(self) -> BridgeType:
        """Get the bridge type."""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the bridge."""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Start the bridge."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the bridge."""
        pass
    
    @abstractmethod
    def process_message(self, message: BridgeMessage) -> Optional[BridgeMessage]:
        """Process a message through the bridge."""
        pass
    
    @abstractmethod
    def validate_config(self) -> List[str]:
        """Validate bridge configuration."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        pass
    
    # ---------------------------------------------------------------------------
    # Common Bridge Methods
    # ---------------------------------------------------------------------------
    
    def is_active(self) -> bool:
        """Check if bridge is active."""
        return self.state == BridgeState.ACTIVE
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "bridge_id": self.config.id,
            "bridge_type": self.bridge_type.value,
            "direction": self.config.direction.value,
            "state": self.state.value,
            "enabled": self.config.enabled,
            "metrics": self.metrics.to_dict(),
            "last_activity": self.metrics.last_activity.isoformat() if self.metrics.last_activity else None
        }
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add an event handler."""
        with self._lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable) -> None:
        """Remove an event handler."""
        with self._lock:
            if event_type in self._event_handlers:
                try:
                    self._event_handlers[event_type].remove(handler)
                except ValueError:
                    pass
    
    def emit_event(self, event_type: str, **kwargs: Any) -> None:
        """Emit an event to all handlers."""
        with self._lock:
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        handler(self, **kwargs)
                    except Exception as e:
                        self.logger.error(f"Error in event handler for {event_type}: {e}")
    
    def update_metrics(self, **updates: Any) -> None:
        """Update bridge metrics."""
        for key, value in updates.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
        
        self.metrics.last_activity = datetime.now(timezone.utc)
    
    def record_error(self, error: Exception) -> None:
        """Record an error."""
        self.metrics.errors += 1
        self.logger.error(f"Bridge error: {error}")
        self.emit_event("error_occurred", error=error)
    
    def apply_filters(self, message: BridgeMessage) -> bool:
        """Apply filters to determine if message should be processed."""
        if not self.config.filters:
            return True
        
        for filter_rule in self.config.filters:
            if not self._apply_filter(message, filter_rule):
                return False
        
        return True
    
    def _apply_filter(self, message: BridgeMessage, filter_rule: Dict[str, Any]) -> bool:
        """Apply a single filter rule."""
        filter_type = filter_rule.get("type")
        
        if filter_type == "header":
            header_name = filter_rule.get("header")
            expected_value = filter_rule.get("value")
            actual_value = message.headers.get(header_name)
            
            if expected_value is not None:
                return actual_value == expected_value
            else:
                return actual_value is not None
        
        elif filter_type == "metadata":
            metadata_key = filter_rule.get("key")
            expected_value = filter_rule.get("value")
            actual_value = message.metadata.get(metadata_key)
            
            if expected_value is not None:
                return actual_value == expected_value
            else:
                return actual_value is not None
        
        elif filter_type == "source_system":
            allowed_systems = filter_rule.get("systems", [])
            return message.source_system in allowed_systems
        
        elif filter_type == "target_system":
            allowed_systems = filter_rule.get("systems", [])
            return message.target_system in allowed_systems
        
        return True
    
    def transform_message(self, message: BridgeMessage) -> BridgeMessage:
        """Apply transformation rules to message."""
        if not self.config.transformation_rules:
            return message
        
        transformed_message = BridgeMessage(
            id=message.id,
            source_system=message.source_system,
            target_system=message.target_system,
            payload=message.payload,
            headers=message.headers.copy(),
            metadata=message.metadata.copy(),
            timestamp=message.timestamp,
            correlation_id=message.correlation_id
        )
        
        for rule in self.config.transformation_rules:
            transformed_message = self._apply_transformation(transformed_message, rule)
        
        return transformed_message
    
    def _apply_transformation(self, message: BridgeMessage, rule: Dict[str, Any]) -> BridgeMessage:
        """Apply a single transformation rule."""
        transformation_type = rule.get("type")
        
        if transformation_type == "add_header":
            header_name = rule.get("header")
            header_value = rule.get("value")
            message.headers[header_name] = header_value
        
        elif transformation_type == "remove_header":
            header_name = rule.get("header")
            message.headers.pop(header_name, None)
        
        elif transformation_type == "add_metadata":
            metadata_key = rule.get("key")
            metadata_value = rule.get("value")
            message.metadata[metadata_key] = metadata_value
        
        elif transformation_type == "remove_metadata":
            metadata_key = rule.get("key")
            message.metadata.pop(metadata_key, None)
        
        elif transformation_type == "map_field":
            source_field = rule.get("source")
            target_field = rule.get("target")
            
            if isinstance(message.payload, dict):
                if source_field in message.payload:
                    message.payload[target_field] = message.payload[source_field]
                    if source_field != target_field:
                        del message.payload[source_field]
        
        elif transformation_type == "rename_system":
            new_source = rule.get("source")
            new_target = rule.get("target")
            if new_source:
                message.source_system = new_source
            if new_target:
                message.target_system = new_target
        
        return message


# ---------------------------------------------------------------------------
# Protocol Bridge
# ---------------------------------------------------------------------------

class ProtocolBridge(BaseBridge):
    """Bridge for protocol conversion (HTTP to WebSocket, etc.)."""
    
    @property
    def bridge_type(self) -> BridgeType:
        return BridgeType.PROTOCOL_BRIDGE
    
    def initialize(self) -> None:
        """Initialize protocol bridge."""
        self.state = BridgeState.INITIALIZING
        
        try:
            self.validate_config()
            
            # Initialize protocol adapters
            self.source_adapter = self._create_protocol_adapter(self.config.source_config)
            self.target_adapter = self._create_protocol_adapter(self.config.target_config)
            
            self.state = BridgeState.ACTIVE
            self.emit_event("initialized")
            self.logger.info("Protocol bridge initialized")
            
        except Exception as e:
            self.record_error(e)
            self.state = BridgeState.ERROR
            raise IntegrationError(f"Failed to initialize protocol bridge: {e}")
    
    def start(self) -> None:
        """Start the protocol bridge."""
        if self.state != BridgeState.ACTIVE:
            raise IntegrationError("Bridge must be active to start")
        
        try:
            # Start adapters
            self.source_adapter.start()
            self.target_adapter.start()
            
            self.emit_event("started")
            self.logger.info("Protocol bridge started")
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to start protocol bridge: {e}")
    
    def stop(self) -> None:
        """Stop the protocol bridge."""
        self.state = BridgeState.TERMINATING
        
        try:
            # Stop adapters
            if hasattr(self, 'source_adapter'):
                self.source_adapter.stop()
            if hasattr(self, 'target_adapter'):
                self.target_adapter.stop()
            
            self.state = BridgeState.TERMINATED
            self.emit_event("stopped")
            self.logger.info("Protocol bridge stopped")
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to stop protocol bridge: {e}")
    
    def process_message(self, message: BridgeMessage) -> Optional[BridgeMessage]:
        """Process a message through the protocol bridge."""
        if not self.is_active():
            raise IntegrationError("Bridge is not active")
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Apply filters
            if not self.apply_filters(message):
                return None
            
            # Transform message
            transformed_message = self.transform_message(message)
            
            # Convert protocol
            if self.config.direction in [BridgeDirection.BIDIRECTIONAL, BridgeDirection.UNIDIRECTIONAL]:
                # Convert from source to target protocol
                converted_message = self._convert_protocol(transformed_message)
                self.update_metrics(messages_processed=1, messages_sent=1)
            else:
                converted_message = None
            
            # Update metrics
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.update_metrics(average_processing_time=processing_time)
            
            return converted_message
            
        except Exception as e:
            self.record_error(e)
            self.update_metrics(errors=1)
            raise IntegrationError(f"Failed to process message: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate protocol bridge configuration."""
        errors = []
        
        if not self.config.source_config.get("protocol"):
            errors.append("Source protocol is required")
        
        if not self.config.target_config.get("protocol"):
            errors.append("Target protocol is required")
        
        source_protocol = self.config.source_config.get("protocol")
        target_protocol = self.config.target_config.get("protocol")
        
        # Validate protocol compatibility
        if not self._are_protocols_compatible(source_protocol, target_protocol):
            errors.append(f"Protocols {source_protocol} and {target_protocol} are not compatible")
        
        return errors
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {}
        }
        
        try:
            # Check source adapter
            if hasattr(self, 'source_adapter'):
                health_status["checks"]["source_adapter"] = {
                    "status": "pass",
                    "protocol": self.config.source_config.get("protocol")
                }
            else:
                health_status["checks"]["source_adapter"] = {
                    "status": "fail",
                    "error": "Source adapter not initialized"
                }
                health_status["status"] = "unhealthy"
            
            # Check target adapter
            if hasattr(self, 'target_adapter'):
                health_status["checks"]["target_adapter"] = {
                    "status": "pass",
                    "protocol": self.config.target_config.get("protocol")
                }
            else:
                health_status["checks"]["target_adapter"] = {
                    "status": "fail",
                    "error": "Target adapter not initialized"
                }
                health_status["status"] = "unhealthy"
            
            # Check metrics
            health_status["checks"]["metrics"] = {
                "status": "pass" if self.metrics.errors < 10 else "fail",
                "error_count": self.metrics.errors,
                "messages_processed": self.metrics.messages_processed
            }
            
        except Exception as e:
            health_status["checks"]["general"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        return health_status
    
    def _create_protocol_adapter(self, config: Dict[str, Any]) -> Any:
        """Create a protocol adapter."""
        protocol = config.get("protocol")
        
        # This would create actual protocol adapters
        # For now, we'll return a mock adapter
        class MockAdapter:
            def start(self):
                pass
            
            def stop(self):
                pass
            
            def convert(self, data):
                return data
        
        return MockAdapter()
    
    def _are_protocols_compatible(self, source: str, target: str) -> bool:
        """Check if protocols are compatible."""
        # This would implement actual compatibility checking
        # For now, we'll assume all protocols are compatible
        return True
    
    def _convert_protocol(self, message: BridgeMessage) -> BridgeMessage:
        """Convert message between protocols."""
        # This would implement actual protocol conversion
        # For now, we'll return the message as-is
        return message


# ---------------------------------------------------------------------------
# Data Format Bridge
# ---------------------------------------------------------------------------

class DataFormatBridge(BaseBridge):
    """Bridge for data format conversion (JSON to XML, etc.)."""
    
    @property
    def bridge_type(self) -> BridgeType:
        return BridgeType.DATA_FORMAT_BRIDGE
    
    def initialize(self) -> None:
        """Initialize data format bridge."""
        self.state = BridgeState.INITIALIZING
        
        try:
            self.validate_config()
            
            # Initialize format converters
            self.source_converter = self._create_format_converter(self.config.source_config)
            self.target_converter = self._create_format_converter(self.config.target_config)
            
            self.state = BridgeState.ACTIVE
            self.emit_event("initialized")
            self.logger.info("Data format bridge initialized")
            
        except Exception as e:
            self.record_error(e)
            self.state = BridgeState.ERROR
            raise IntegrationError(f"Failed to initialize data format bridge: {e}")
    
    def start(self) -> None:
        """Start the data format bridge."""
        if self.state != BridgeState.ACTIVE:
            raise IntegrationError("Bridge must be active to start")
        
        self.emit_event("started")
        self.logger.info("Data format bridge started")
    
    def stop(self) -> None:
        """Stop the data format bridge."""
        self.state = BridgeState.TERMINATING
        
        self.state = BridgeState.TERMINATED
        self.emit_event("stopped")
        self.logger.info("Data format bridge stopped")
    
    def process_message(self, message: BridgeMessage) -> Optional[BridgeMessage]:
        """Process a message through the data format bridge."""
        if not self.is_active():
            raise IntegrationError("Bridge is not active")
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Apply filters
            if not self.apply_filters(message):
                return None
            
            # Transform message
            transformed_message = self.transform_message(message)
            
            # Convert data format
            if self.config.direction in [BridgeDirection.BIDIRECTIONAL, BridgeDirection.UNIDIRECTIONAL]:
                converted_message = self._convert_data_format(transformed_message)
                self.update_metrics(messages_processed=1, messages_sent=1)
            else:
                converted_message = None
            
            # Update metrics
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.update_metrics(average_processing_time=processing_time)
            
            return converted_message
            
        except Exception as e:
            self.record_error(e)
            self.update_metrics(errors=1)
            raise IntegrationError(f"Failed to process message: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate data format bridge configuration."""
        errors = []
        
        if not self.config.source_config.get("format"):
            errors.append("Source format is required")
        
        if not self.config.target_config.get("format"):
            errors.append("Target format is required")
        
        source_format = self.config.source_config.get("format")
        target_format = self.config.target_config.get("format")
        
        # Validate format compatibility
        if not self._are_formats_compatible(source_format, target_format):
            errors.append(f"Formats {source_format} and {target_format} are not compatible")
        
        return errors
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {}
        }
        
        try:
            # Check converters
            health_status["checks"]["source_converter"] = {
                "status": "pass" if hasattr(self, 'source_converter') else "fail",
                "format": self.config.source_config.get("format")
            }
            
            health_status["checks"]["target_converter"] = {
                "status": "pass" if hasattr(self, 'target_converter') else "fail",
                "format": self.config.target_config.get("format")
            }
            
            # Check metrics
            health_status["checks"]["metrics"] = {
                "status": "pass" if self.metrics.errors < 10 else "fail",
                "error_count": self.metrics.errors,
                "messages_processed": self.metrics.messages_processed
            }
            
        except Exception as e:
            health_status["checks"]["general"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        return health_status
    
    def _create_format_converter(self, config: Dict[str, Any]) -> Any:
        """Create a format converter."""
        format_type = config.get("format")
        
        # This would create actual format converters
        # For now, we'll return a mock converter
        class MockConverter:
            def convert(self, data):
                return data
        
        return MockConverter()
    
    def _are_formats_compatible(self, source: str, target: str) -> bool:
        """Check if formats are compatible."""
        # This would implement actual compatibility checking
        # For now, we'll assume all formats are compatible
        return True
    
    def _convert_data_format(self, message: BridgeMessage) -> BridgeMessage:
        """Convert message data format."""
        # This would implement actual format conversion
        # For now, we'll return the message as-is
        return message


# ---------------------------------------------------------------------------
# Bridge Manager
# ---------------------------------------------------------------------------

class BridgeManager:
    """Manager for all bridges."""
    
    def __init__(self):
        self.bridges: Dict[str, BaseBridge] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def register_bridge(self, bridge: BaseBridge) -> None:
        """Register a bridge."""
        with self._lock:
            if bridge.config.id in self.bridges:
                raise IntegrationError(f"Bridge with ID '{bridge.config.id}' already exists")
            
            self.bridges[bridge.config.id] = bridge
            self.logger.info(f"Registered bridge: {bridge.config.id}")
    
    def unregister_bridge(self, bridge_id: str) -> bool:
        """Unregister a bridge."""
        with self._lock:
            if bridge_id in self.bridges:
                bridge = self.bridges[bridge_id]
                if bridge.is_active():
                    bridge.stop()
                del self.bridges[bridge_id]
                self.logger.info(f"Unregistered bridge: {bridge_id}")
                return True
            return False
    
    def get_bridge(self, bridge_id: str) -> Optional[BaseBridge]:
        """Get a bridge by ID."""
        with self._lock:
            return self.bridges.get(bridge_id)
    
    def list_bridges(self, bridge_type: Optional[BridgeType] = None) -> List[BaseBridge]:
        """List bridges with optional filtering."""
        with self._lock:
            bridges = list(self.bridges.values())
            
            if bridge_type:
                bridges = [b for b in bridges if b.bridge_type == bridge_type]
            
            return bridges
    
    def start_bridge(self, bridge_id: str) -> bool:
        """Start a bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Bridge '{bridge_id}' not found")
        
        try:
            bridge.start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start bridge {bridge_id}: {e}")
            return False
    
    def stop_bridge(self, bridge_id: str) -> bool:
        """Stop a bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Bridge '{bridge_id}' not found")
        
        try:
            bridge.stop()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop bridge {bridge_id}: {e}")
            return False
    
    def process_message_through_bridge(self, bridge_id: str, message: BridgeMessage) -> Optional[BridgeMessage]:
        """Process a message through a specific bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Bridge '{bridge_id}' not found")
        
        return bridge.process_message(message)
    
    def get_all_bridge_status(self) -> Dict[str, Any]:
        """Get status of all bridges."""
        with self._lock:
            return {
                "total_bridges": len(self.bridges),
                "bridges": {bridge_id: bridge.get_status() for bridge_id, bridge in self.bridges.items()},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def perform_health_checks(self) -> Dict[str, Any]:
        """Perform health checks on all bridges."""
        health_results = {}
        
        for bridge_id, bridge in self.bridges.items():
            try:
                health_results[bridge_id] = bridge.health_check()
            except Exception as e:
                health_results[bridge_id] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "health_check_results": health_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": self._calculate_overall_health(health_results)
        }
    
    def _calculate_overall_health(self, health_results: Dict[str, Any]) -> str:
        """Calculate overall health status."""
        if not health_results:
            return "unknown"
        
        healthy_count = 0
        total_count = len(health_results)
        
        for result in health_results.values():
            if isinstance(result, dict) and result.get("status") == "healthy":
                healthy_count += 1
        
        if healthy_count == total_count:
            return "healthy"
        elif healthy_count > 0:
            return "degraded"
        else:
            return "unhealthy"


# Global bridge manager instance
bridge_manager = BridgeManager()


# Initialize logging
logger.info("Bridge system module initialized")
