"""
Integration Adapter — Base adapter classes for integration implementations.

This module provides abstract base classes and common functionality
for implementing integration adapters.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum

from .integ_constants import IntegrationType, IntegrationStatus, Priority, MessageType
from .integ_exceptions import (
    IntegrationError, ConnectionError, TimeoutError, AuthenticationError,
    DataFormatError, ValidationError, ConfigurationError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter States
# ---------------------------------------------------------------------------

class AdapterState(Enum):
    """Adapter state enumeration."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Message and Data Classes
# ---------------------------------------------------------------------------

@dataclass
class IntegrationMessage:
    """Message for integration communication."""
    
    id: str
    type: MessageType
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "payload": self.payload,
            "headers": self.headers,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }


@dataclass
class ConnectionInfo:
    """Connection information for integrations."""
    
    endpoint: str
    protocol: str
    port: Optional[int] = None
    path: Optional[str] = None
    query_params: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "port": self.port,
            "path": self.path,
            "query_params": self.query_params,
            "headers": self.headers,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay
        }


# ---------------------------------------------------------------------------
# Abstract Base Adapter
# ---------------------------------------------------------------------------

class BaseIntegrationAdapter(ABC):
    """Abstract base class for integration adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.state = AdapterState.UNINITIALIZED
        self.connection_info: Optional[ConnectionInfo] = None
        self.last_activity: Optional[datetime] = None
        self.error_count: int = 0
        self.last_error: Optional[str] = None
        self.metrics: Dict[str, Any] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    @abstractmethod
    def integration_type(self) -> IntegrationType:
        """Get the integration type."""
        pass
    
    @property
    @abstractmethod
    def supported_message_types(self) -> List[MessageType]:
        """Get list of supported message types."""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the adapter."""
        pass
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    def send_message(self, message: IntegrationMessage) -> Any:
        """Send a message."""
        pass
    
    @abstractmethod
    def receive_message(self, timeout: Optional[float] = None) -> Optional[IntegrationMessage]:
        """Receive a message."""
        pass
    
    @abstractmethod
    def validate_config(self) -> List[str]:
        """Validate configuration."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        pass
    
    # ---------------------------------------------------------------------------
    # Common Adapter Methods
    # ---------------------------------------------------------------------------
    
    def is_healthy(self) -> bool:
        """Check if adapter is healthy."""
        if self.state in [AdapterState.ERROR, AdapterState.TERMINATED]:
            return False
        
        # Check error rate
        if self.error_count > 10:  # Configurable threshold
            return False
        
        # Check last activity
        if self.last_activity:
            time_since_activity = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
            if time_since_activity > 300:  # 5 minutes
                return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter status."""
        return {
            "state": self.state.value,
            "integration_type": self.integration_type.value,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "is_healthy": self.is_healthy(),
            "metrics": self.metrics.copy(),
            "connection_info": self.connection_info.to_dict() if self.connection_info else None
        }
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add an event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable) -> None:
        """Remove an event handler."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def emit_event(self, event_type: str, **kwargs: Any) -> None:
        """Emit an event to all handlers."""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    handler(self, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type}: {e}")
    
    def update_metrics(self, metric_name: str, value: Any) -> None:
        """Update adapter metrics."""
        self.metrics[metric_name] = value
        self.metrics[f"{metric_name}_updated_at"] = datetime.now(timezone.utc).isoformat()
    
    def record_error(self, error: Exception) -> None:
        """Record an error."""
        self.error_count += 1
        self.last_error = str(error)
        self.last_activity = datetime.now(timezone.utc)
        
        if self.state != AdapterState.ERROR:
            self.state = AdapterState.ERROR
        
        self.emit_event("error_occurred", error=error)
        self.logger.error(f"Adapter error: {error}")
    
    def reset_error_state(self) -> None:
        """Reset error state."""
        self.error_count = 0
        self.last_error = None
        if self.state == AdapterState.ERROR:
            self.state = AdapterState.READY
    
    def validate_message(self, message: IntegrationMessage) -> List[str]:
        """Validate a message."""
        errors = []
        
        if not message.id:
            errors.append("Message ID is required")
        
        if message.type not in self.supported_message_types:
            errors.append(f"Message type '{message.type.value}' not supported")
        
        if message.is_expired():
            errors.append("Message has expired")
        
        return errors
    
    def create_message(
        self,
        message_type: MessageType,
        payload: Dict[str, Any],
        **kwargs: Any
    ) -> IntegrationMessage:
        """Create a new message."""
        import uuid
        
        return IntegrationMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            payload=payload,
            headers=kwargs.get("headers", {}),
            priority=kwargs.get("priority", Priority.NORMAL),
            correlation_id=kwargs.get("correlation_id"),
            reply_to=kwargs.get("reply_to"),
            expires_at=kwargs.get("expires_at"),
            max_retries=kwargs.get("max_retries", 3)
        )


# ---------------------------------------------------------------------------
# HTTP/Webhook Adapter
# ---------------------------------------------------------------------------

class HTTPAdapter(BaseIntegrationAdapter):
    """Adapter for HTTP-based integrations including webhooks."""
    
    @property
    def integration_type(self) -> IntegrationType:
        return IntegrationType.WEBHOOK
    
    @property
    def supported_message_types(self) -> List[MessageType]:
        return [MessageType.REQUEST, MessageType.RESPONSE, MessageType.EVENT]
    
    def initialize(self) -> None:
        """Initialize HTTP adapter."""
        self.state = AdapterState.INITIALIZING
        
        try:
            self.validate_config()
            
            # Create connection info
            self.connection_info = ConnectionInfo(
                endpoint=self.config["url"],
                protocol="https" if self.config["url"].startswith("https") else "http",
                timeout=self.config.get("timeout", 30),
                retry_attempts=self.config.get("retry_attempts", 3),
                retry_delay=self.config.get("retry_delay", 1.0),
                headers=self.config.get("headers", {})
            )
            
            self.state = AdapterState.READY
            self.emit_event("initialized")
            self.logger.info("HTTP adapter initialized")
            
        except Exception as e:
            self.record_error(e)
            raise ConfigurationError(f"Failed to initialize HTTP adapter: {e}")
    
    def connect(self) -> None:
        """Establish HTTP connection (validation)."""
        if self.state != AdapterState.READY:
            raise IntegrationError("Adapter must be in READY state to connect")
        
        self.state = AdapterState.CONNECTING
        
        try:
            # Test connection with a HEAD request
            import requests
            
            response = requests.head(
                self.connection_info.endpoint,
                headers=self.connection_info.headers,
                timeout=self.connection_info.timeout
            )
            
            if response.status_code >= 400:
                raise ConnectionError(f"HTTP connection test failed: {response.status_code}")
            
            self.state = AdapterState.CONNECTED
            self.last_activity = datetime.now(timezone.utc)
            self.emit_event("connected")
            self.logger.info("HTTP adapter connected")
            
        except Exception as e:
            self.record_error(e)
            raise ConnectionError(f"Failed to connect: {e}")
    
    def disconnect(self) -> None:
        """Close HTTP connection."""
        self.state = AdapterState.DISCONNECTING
        
        try:
            # HTTP doesn't maintain persistent connections, so just update state
            self.state = AdapterState.DISCONNECTED
            self.emit_event("disconnected")
            self.logger.info("HTTP adapter disconnected")
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to disconnect: {e}")
    
    def send_message(self, message: IntegrationMessage) -> Any:
        """Send HTTP request."""
        if self.state != AdapterState.CONNECTED:
            raise IntegrationError("Adapter must be connected to send messages")
        
        errors = self.validate_message(message)
        if errors:
            raise ValidationError(f"Message validation failed: {', '.join(errors)}")
        
        try:
            import requests
            
            method = self.config.get("method", "POST")
            url = self.connection_info.endpoint
            
            # Merge message headers with default headers
            headers = self.connection_info.headers.copy()
            headers.update(message.headers)
            
            # Add correlation ID header
            if message.correlation_id:
                headers["X-Correlation-ID"] = message.correlation_id
            
            response = requests.request(
                method=method,
                url=url,
                json=message.payload,
                headers=headers,
                timeout=self.connection_info.timeout
            )
            
            self.last_activity = datetime.now(timezone.utc)
            self.update_metrics("last_request_status", response.status_code)
            self.update_metrics("last_request_time", self.last_activity.isoformat())
            
            # Handle response
            if response.status_code >= 400:
                raise IntegrationError(f"HTTP request failed: {response.status_code}")
            
            self.emit_event("message_sent", message=message, response=response)
            return response
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to send message: {e}")
    
    def receive_message(self, timeout: Optional[float] = None) -> Optional[IntegrationMessage]:
        """HTTP adapter doesn't support receiving messages."""
        raise NotImplementedError("HTTP adapter doesn't support receiving messages")
    
    def validate_config(self) -> List[str]:
        """Validate HTTP configuration."""
        errors = []
        
        if not self.config.get("url"):
            errors.append("URL is required")
        
        method = self.config.get("method", "POST")
        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            errors.append(f"Invalid HTTP method: {method}")
        
        timeout = self.config.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("Timeout must be a positive number")
        
        return errors
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {}
        }
        
        try:
            # Test connectivity
            import requests
            
            response = requests.head(
                self.connection_info.endpoint,
                headers=self.connection_info.headers,
                timeout=5  # Short timeout for health check
            )
            
            health_status["checks"]["connectivity"] = {
                "status": "pass" if response.status_code < 400 else "fail",
                "response_time": response.elapsed.total_seconds(),
                "status_code": response.status_code
            }
            
        except Exception as e:
            health_status["checks"]["connectivity"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Check error rate
        health_status["checks"]["error_rate"] = {
            "status": "pass" if self.error_count < 5 else "fail",
            "error_count": self.error_count
        }
        
        # Check state
        health_status["checks"]["state"] = {
            "status": "pass" if self.state == AdapterState.CONNECTED else "fail",
            "current_state": self.state.value
        }
        
        return health_status


# ---------------------------------------------------------------------------
# API Adapter
# ---------------------------------------------------------------------------

class APIAdapter(HTTPAdapter):
    """Adapter for REST API integrations."""
    
    @property
    def integration_type(self) -> IntegrationType:
        return IntegrationType.API
    
    def initialize(self) -> None:
        """Initialize API adapter."""
        self.state = AdapterState.INITIALIZING
        
        try:
            self.validate_config()
            
            # Create connection info with base URL
            base_url = self.config["base_url"]
            self.connection_info = ConnectionInfo(
                endpoint=base_url,
                protocol="https" if base_url.startswith("https") else "http",
                timeout=self.config.get("timeout", 30),
                retry_attempts=self.config.get("retry_attempts", 3),
                retry_delay=self.config.get("retry_delay", 1.0),
                headers=self.config.get("headers", {})
            )
            
            self.state = AdapterState.READY
            self.emit_event("initialized")
            self.logger.info("API adapter initialized")
            
        except Exception as e:
            self.record_error(e)
            raise ConfigurationError(f"Failed to initialize API adapter: {e}")
    
    def send_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        """Send API request."""
        if self.state != AdapterState.CONNECTED:
            raise IntegrationError("Adapter must be connected to send requests")
        
        try:
            import requests
            
            url = f"{self.connection_info.endpoint.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Merge headers
            request_headers = self.connection_info.headers.copy()
            if headers:
                request_headers.update(headers)
            
            response = requests.request(
                method=method.upper(),
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=self.connection_info.timeout
            )
            
            self.last_activity = datetime.now(timezone.utc)
            self.update_metrics("last_request_status", response.status_code)
            
            return response
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to send API request: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate API configuration."""
        errors = []
        
        if not self.config.get("base_url"):
            errors.append("Base URL is required")
        
        timeout = self.config.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("Timeout must be a positive number")
        
        return errors


# ---------------------------------------------------------------------------
# Database Adapter
# ---------------------------------------------------------------------------

class DatabaseAdapter(BaseIntegrationAdapter):
    """Adapter for database integrations."""
    
    @property
    def integration_type(self) -> IntegrationType:
        return IntegrationType.DATABASE
    
    @property
    def supported_message_types(self) -> List[MessageType]:
        return [MessageType.REQUEST, MessageType.RESPONSE]
    
    def initialize(self) -> None:
        """Initialize database adapter."""
        self.state = AdapterState.INITIALIZING
        
        try:
            self.validate_config()
            
            # Create connection info
            self.connection_info = ConnectionInfo(
                endpoint=self.config["connection_string"],
                protocol="database",
                timeout=self.config.get("pool_timeout", 30)
            )
            
            self.state = AdapterState.READY
            self.emit_event("initialized")
            self.logger.info("Database adapter initialized")
            
        except Exception as e:
            self.record_error(e)
            raise ConfigurationError(f"Failed to initialize database adapter: {e}")
    
    def connect(self) -> None:
        """Establish database connection."""
        if self.state != AdapterState.READY:
            raise IntegrationError("Adapter must be in READY state to connect")
        
        self.state = AdapterState.CONNECTING
        
        try:
            # This would implement actual database connection
            # For now, we'll simulate connection
            self.state = AdapterState.CONNECTED
            self.last_activity = datetime.now(timezone.utc)
            self.emit_event("connected")
            self.logger.info("Database adapter connected")
            
        except Exception as e:
            self.record_error(e)
            raise ConnectionError(f"Failed to connect to database: {e}")
    
    def disconnect(self) -> None:
        """Close database connection."""
        self.state = AdapterState.DISCONNECTING
        
        try:
            # This would implement actual database disconnection
            self.state = AdapterState.DISCONNECTED
            self.emit_event("disconnected")
            self.logger.info("Database adapter disconnected")
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to disconnect from database: {e}")
    
    def send_message(self, message: IntegrationMessage) -> Any:
        """Execute database operation."""
        if self.state != AdapterState.CONNECTED:
            raise IntegrationError("Adapter must be connected to send messages")
        
        errors = self.validate_message(message)
        if errors:
            raise ValidationError(f"Message validation failed: {', '.join(errors)}")
        
        try:
            # This would implement actual database operation
            result = {"status": "success", "message": "Database operation completed"}
            
            self.last_activity = datetime.now(timezone.utc)
            self.emit_event("message_sent", message=message, result=result)
            
            return result
            
        except Exception as e:
            self.record_error(e)
            raise IntegrationError(f"Failed to execute database operation: {e}")
    
    def receive_message(self, timeout: Optional[float] = None) -> Optional[IntegrationMessage]:
        """Database adapter doesn't support receiving messages."""
        raise NotImplementedError("Database adapter doesn't support receiving messages")
    
    def validate_config(self) -> List[str]:
        """Validate database configuration."""
        errors = []
        
        if not self.config.get("connection_string"):
            errors.append("Connection string is required")
        
        pool_size = self.config.get("pool_size", 10)
        if not isinstance(pool_size, int) or pool_size <= 0:
            errors.append("Pool size must be a positive integer")
        
        return errors
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {}
        }
        
        try:
            # Test database connection
            # This would implement actual database health check
            health_status["checks"]["database_connection"] = {
                "status": "pass",
                "response_time": 0.1
            }
            
        except Exception as e:
            health_status["checks"]["database_connection"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        return health_status


# Initialize logging
logger.info("Integration adapter module initialized")
