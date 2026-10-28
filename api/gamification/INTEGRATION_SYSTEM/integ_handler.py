"""
Integration Handler — Core handler for managing integration operations.

This module provides the main integration handler that orchestrates
all integration operations including connection management, message routing,
and error handling.
"""

from __future__ import annotations

import logging
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum

from .integ_constants import (
    IntegrationType, IntegrationStatus, Priority, MessageType,
    DEFAULT_TIMEOUT, DEFAULT_RETRY_ATTEMPTS, DEFAULT_RETRY_DELAY
)
from .integ_exceptions import (
    IntegrationError, IntegrationNotFoundError, TimeoutError,
    ValidationError, CircuitBreakerOpenError
)
from .integ_registry import IntegrationRegistry, IntegrationConfig, IntegrationInstance
from .integ_adapter import BaseIntegrationAdapter, IntegrationMessage
from .integ_signals import (
    integration_connected, integration_disconnected, integration_connection_failed,
    data_received, data_sent, integration_error, error_recovery_attempted
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler States
# ---------------------------------------------------------------------------

class HandlerState(Enum):
    """Handler state enumeration."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Operation Result Classes
# ---------------------------------------------------------------------------

@dataclass
class OperationResult:
    """Result of an integration operation."""
    
    success: bool
    operation_id: str
    integration_id: str
    operation_type: str
    data: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "integration_id": self.integration_id,
            "operation_type": self.operation_type,
            "data": self.data,
            "error": str(self.error) if self.error else None,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class BatchOperationResult:
    """Result of a batch operation."""
    
    operation_id: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    results: List[OperationResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    total_execution_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": self.success_rate,
            "results": [result.to_dict() for result in self.results],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_execution_time": self.total_execution_time
        }


# ---------------------------------------------------------------------------
# Main Integration Handler
# ---------------------------------------------------------------------------

class IntegrationHandler:
    """Main handler for integration operations."""
    
    def __init__(self, registry: Optional[IntegrationRegistry] = None):
        self.registry = registry or IntegrationRegistry()
        self.state = HandlerState.INITIALIZING
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running_operations: Dict[str, Future] = {}
        self.operation_results: Dict[str, OperationResult] = {}
        self.metrics: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Initialize metrics
        self.metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "average_execution_time": 0.0,
            "active_integrations": 0,
            "error_rate": 0.0
        }
        
        self.state = HandlerState.READY
        self.logger.info("Integration handler initialized")
    
    def register_integration(self, config: IntegrationConfig) -> IntegrationInstance:
        """Register a new integration."""
        try:
            instance = self.registry.register_integration(config)
            self._update_metric("active_integrations", len(self.registry.list_integrations()))
            self.logger.info(f"Registered integration: {config.id}")
            return instance
        except Exception as e:
            self.logger.error(f"Failed to register integration {config.id}: {e}")
            raise
    
    def unregister_integration(self, integration_id: str) -> bool:
        """Unregister an integration."""
        try:
            success = self.registry.unregister_integration(integration_id)
            if success:
                self._update_metric("active_integrations", len(self.registry.list_integrations()))
                self.logger.info(f"Unregistered integration: {integration_id}")
            return success
        except Exception as e:
            self.logger.error(f"Failed to unregister integration {integration_id}: {e}")
            return False
    
    def activate_integration(self, integration_id: str) -> OperationResult:
        """Activate an integration."""
        import uuid
        operation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        try:
            self.registry.activate_integration(integration_id)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=True,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="activate",
                execution_time=execution_time
            )
            
            self._update_metrics(True, execution_time)
            self.operation_results[operation_id] = result
            
            # Emit signal
            integration_connected.send(
                sender=self,
                integration_id=integration_id,
                integration_type="unknown",  # Would get from config
                connection_info={}
            )
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=False,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="activate",
                error=e,
                execution_time=execution_time
            )
            
            self._update_metrics(False, execution_time)
            self.operation_results[operation_id] = result
            
            # Emit signal
            integration_connection_failed.send(
                sender=self,
                integration_id=integration_id,
                integration_type="unknown",
                error=e,
                attempt_count=1
            )
            
            return result
    
    def deactivate_integration(self, integration_id: str) -> OperationResult:
        """Deactivate an integration."""
        import uuid
        operation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        try:
            self.registry.deactivate_integration(integration_id)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=True,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="deactivate",
                execution_time=execution_time
            )
            
            self._update_metrics(True, execution_time)
            self.operation_results[operation_id] = result
            
            # Emit signal
            integration_disconnected.send(
                sender=self,
                integration_id=integration_id,
                integration_type="unknown",
                error=None,
                connection_info={}
            )
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=False,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="deactivate",
                error=e,
                execution_time=execution_time
            )
            
            self._update_metrics(False, execution_time)
            self.operation_results[operation_id] = result
            
            return result
    
    def send_message(
        self,
        integration_id: str,
        message: IntegrationMessage,
        timeout: Optional[float] = None
    ) -> OperationResult:
        """Send a message to an integration."""
        import uuid
        operation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get integration
            integration = self.registry.get_integration(integration_id)
            if not integration:
                raise IntegrationNotFoundError(
                    f"Integration '{integration_id}' not found",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            if not integration.is_active:
                raise IntegrationError(
                    f"Integration '{integration_id}' is not active",
                    ErrorCode.INTEGRATION_DISABLED
                )
            
            # Send message
            adapter = integration.instance
            if not isinstance(adapter, BaseIntegrationAdapter):
                raise IntegrationError(
                    f"Integration '{integration_id}' does not have a valid adapter",
                    ErrorCode.INTEGRATION_FAILED
                )
            
            result_data = adapter.send_message(message)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=True,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="send_message",
                data=result_data,
                execution_time=execution_time
            )
            
            self._update_metrics(True, execution_time)
            self.operation_results[operation_id] = result
            
            # Emit signal
            data_sent.send(
                sender=self,
                integration_id=integration_id,
                data=message.payload,
                data_type=message.type.value,
                timestamp=message.timestamp
            )
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = OperationResult(
                success=False,
                operation_id=operation_id,
                integration_id=integration_id,
                operation_type="send_message",
                error=e,
                execution_time=execution_time
            )
            
            self._update_metrics(False, execution_time)
            self.operation_results[operation_id] = result
            
            # Emit signal
            integration_error.send(
                sender=self,
                integration_id=integration_id,
                error_type=type(e).__name__,
                error=e,
                context={"operation": "send_message", "message_id": message.id}
            )
            
            return result
    
    def send_message_async(
        self,
        integration_id: str,
        message: IntegrationMessage,
        timeout: Optional[float] = None,
        callback: Optional[Callable[[OperationResult], None]] = None
    ) -> Future:
        """Send a message asynchronously."""
        def _send_message():
            result = self.send_message(integration_id, message, timeout)
            if callback:
                callback(result)
            return result
        
        future = self.executor.submit(_send_message)
        return future
    
    def send_batch_messages(
        self,
        messages: List[tuple[str, IntegrationMessage]],
        timeout: Optional[float] = None,
        max_concurrent: int = 10
    ) -> BatchOperationResult:
        """Send multiple messages in batch."""
        import uuid
        operation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        batch_result = BatchOperationResult(
            operation_id=operation_id,
            total_operations=len(messages)
        )
        
        # Process messages with concurrency control
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = []
            
            for integration_id, message in messages:
                future = executor.submit(self.send_message, integration_id, message, timeout)
                futures.append(future)
            
            # Collect results
            for future in futures:
                try:
                    result = future.result()
                    batch_result.results.append(result)
                    
                    if result.success:
                        batch_result.successful_operations += 1
                    else:
                        batch_result.failed_operations += 1
                        
                except Exception as e:
                    error_result = OperationResult(
                        success=False,
                        operation_id=str(uuid.uuid4()),
                        integration_id="unknown",
                        operation_type="send_message",
                        error=e
                    )
                    batch_result.results.append(error_result)
                    batch_result.failed_operations += 1
        
        batch_result.end_time = datetime.now(timezone.utc)
        batch_result.total_execution_time = (batch_result.end_time - start_time).total_seconds()
        
        return batch_result
    
    def get_operation_result(self, operation_id: str) -> Optional[OperationResult]:
        """Get result of an operation."""
        return self.operation_results.get(operation_id)
    
    def get_integration_status(self, integration_id: str) -> Dict[str, Any]:
        """Get status of an integration."""
        integration = self.registry.get_integration(integration_id)
        if not integration:
            raise IntegrationNotFoundError(
                f"Integration '{integration_id}' not found",
                ErrorCode.INTEGRATION_NOT_FOUND
            )
        
        return integration.to_dict()
    
    def get_all_integrations_status(self) -> Dict[str, Any]:
        """Get status of all integrations."""
        integrations = self.registry.list_integrations()
        
        return {
            "total_integrations": len(integrations),
            "integrations": [integration.to_dict() for integration in integrations],
            "handler_metrics": self.metrics.copy(),
            "handler_state": self.state.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def perform_health_check(self, integration_id: Optional[str] = None) -> Dict[str, Any]:
        """Perform health check on integrations."""
        health_results = {}
        
        if integration_id:
            # Check specific integration
            integration = self.registry.get_integration(integration_id)
            if integration:
                adapter = integration.instance
                if isinstance(adapter, BaseIntegrationAdapter):
                    health_results[integration_id] = adapter.health_check()
        else:
            # Check all integrations
            integrations = self.registry.list_integrations()
            for integration in integrations:
                adapter = integration.instance
                if isinstance(adapter, BaseIntegrationAdapter):
                    health_results[integration.config.id] = adapter.health_check()
        
        return {
            "health_check_results": health_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": self._calculate_overall_health(health_results)
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        return {
            "handler_metrics": self.metrics.copy(),
            "registry_stats": self.registry.get_registry_stats(),
            "active_operations": len(self.running_operations),
            "completed_operations": len(self.operation_results),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def shutdown(self, timeout: float = 30.0) -> None:
        """Shutdown the handler gracefully."""
        self.state = HandlerState.STOPPING
        self.logger.info("Shutting down integration handler")
        
        # Shutdown all integrations
        integrations = self.registry.list_integrations()
        for integration in integrations:
            try:
                if integration.is_active:
                    self.registry.deactivate_integration(integration.config.id)
            except Exception as e:
                self.logger.error(f"Error deactivating integration {integration.config.id}: {e}")
        
        # Wait for running operations to complete
        self._shutdown_event.wait(timeout)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.state = HandlerState.STOPPED
        self.logger.info("Integration handler shutdown complete")
    
    # ---------------------------------------------------------------------------
    # Private Methods
    # ---------------------------------------------------------------------------
    
    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update handler metrics."""
        with self._lock:
            self.metrics["total_operations"] += 1
            
            if success:
                self.metrics["successful_operations"] += 1
            else:
                self.metrics["failed_operations"] += 1
            
            # Update average execution time
            total_ops = self.metrics["total_operations"]
            current_avg = self.metrics["average_execution_time"]
            self.metrics["average_execution_time"] = (
                (current_avg * (total_ops - 1) + execution_time) / total_ops
            )
            
            # Update error rate
            self.metrics["error_rate"] = (
                self.metrics["failed_operations"] / total_ops
            )
    
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


# ---------------------------------------------------------------------------
# Global Handler Instance
# ---------------------------------------------------------------------------

# Global handler instance
integration_handler = IntegrationHandler()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def get_handler() -> IntegrationHandler:
    """Get the global integration handler."""
    return integration_handler


def send_message(
    integration_id: str,
    message: IntegrationMessage,
    timeout: Optional[float] = None
) -> OperationResult:
    """Send a message using the global handler."""
    return integration_handler.send_message(integration_id, message, timeout)


def activate_integration(integration_id: str) -> OperationResult:
    """Activate an integration using the global handler."""
    return integration_handler.activate_integration(integration_id)


def deactivate_integration(integration_id: str) -> OperationResult:
    """Deactivate an integration using the global handler."""
    return integration_handler.deactivate_integration(integration_id)


# Initialize logging
logger.info("Integration handler module initialized")
