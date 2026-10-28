"""
Integration Registry — Registry system for managing integrations.

This module provides a comprehensive registry system for managing
integration configurations, instances, and metadata.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum

from .integ_constants import IntegrationType, IntegrationStatus, ErrorCode
from .integ_exceptions import (
    IntegrationError, IntegrationNotFoundError, ConfigurationError,
    ValidationError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry Data Classes
# ---------------------------------------------------------------------------

@dataclass
class IntegrationConfig:
    """Configuration data for an integration."""
    
    id: str
    name: str
    type: IntegrationType
    status: IntegrationStatus = IntegrationStatus.INACTIVE
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "config": self.config,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "enabled": self.enabled,
            "tags": self.tags
        }
    
    def validate(self) -> List[str]:
        """Validate configuration."""
        errors = []
        
        if not self.id:
            errors.append("Integration ID is required")
        
        if not self.name:
            errors.append("Integration name is required")
        
        if not self.type:
            errors.append("Integration type is required")
        
        # Validate config based on type
        if self.type == IntegrationType.WEBHOOK:
            errors.extend(self._validate_webhook_config())
        elif self.type == IntegrationType.API:
            errors.extend(self._validate_api_config())
        elif self.type == IntegrationType.DATABASE:
            errors.extend(self._validate_database_config())
        elif self.type == IntegrationType.MESSAGE_QUEUE:
            errors.extend(self._validate_message_queue_config())
        
        return errors
    
    def _validate_webhook_config(self) -> List[str]:
        """Validate webhook configuration."""
        errors = []
        config = self.config
        
        if not config.get("url"):
            errors.append("Webhook URL is required")
        
        method = config.get("method", "POST")
        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            errors.append(f"Invalid HTTP method: {method}")
        
        timeout = config.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("Timeout must be a positive number")
        
        return errors
    
    def _validate_api_config(self) -> List[str]:
        """Validate API configuration."""
        errors = []
        config = self.config
        
        if not config.get("base_url"):
            errors.append("Base URL is required")
        
        timeout = config.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("Timeout must be a positive number")
        
        return errors
    
    def _validate_database_config(self) -> List[str]:
        """Validate database configuration."""
        errors = []
        config = self.config
        
        if not config.get("connection_string"):
            errors.append("Connection string is required")
        
        pool_size = config.get("pool_size", 10)
        if not isinstance(pool_size, int) or pool_size <= 0:
            errors.append("Pool size must be a positive integer")
        
        return errors
    
    def _validate_message_queue_config(self) -> List[str]:
        """Validate message queue configuration."""
        errors = []
        config = self.config
        
        if not config.get("broker_url"):
            errors.append("Broker URL is required")
        
        if not config.get("queue"):
            errors.append("Queue name is required")
        
        return errors


@dataclass
class IntegrationInstance:
    """Instance of an integration with runtime information."""
    
    config: IntegrationConfig
    instance: Any = None
    is_active: bool = False
    last_activity: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config": self.config.to_dict(),
            "is_active": self.is_active,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "metrics": self.metrics
        }


# ---------------------------------------------------------------------------
# Abstract Integration Factory
# ---------------------------------------------------------------------------

class IntegrationFactory(ABC):
    """Abstract factory for creating integration instances."""
    
    @abstractmethod
    def create_instance(self, config: IntegrationConfig) -> Any:
        """Create an integration instance from configuration."""
        pass
    
    @abstractmethod
    def validate_config(self, config: IntegrationConfig) -> List[str]:
        """Validate integration configuration."""
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[IntegrationType]:
        """Get list of supported integration types."""
        pass


# ---------------------------------------------------------------------------
# Registry Implementation
# ---------------------------------------------------------------------------

class IntegrationRegistry:
    """Registry for managing integrations."""
    
    def __init__(self):
        self._integrations: Dict[str, IntegrationInstance] = {}
        self._factories: Dict[IntegrationType, IntegrationFactory] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def register_factory(self, integration_type: IntegrationType, factory: IntegrationFactory) -> None:
        """Register a factory for an integration type."""
        with self._lock:
            self._factories[integration_type] = factory
            self.logger.info(f"Registered factory for {integration_type.value}")
    
    def unregister_factory(self, integration_type: IntegrationType) -> None:
        """Unregister a factory for an integration type."""
        with self._lock:
            if integration_type in self._factories:
                del self._factories[integration_type]
                self.logger.info(f"Unregistered factory for {integration_type.value}")
    
    def get_factory(self, integration_type: IntegrationType) -> Optional[IntegrationFactory]:
        """Get factory for an integration type."""
        with self._lock:
            return self._factories.get(integration_type)
    
    def register_integration(self, config: IntegrationConfig) -> IntegrationInstance:
        """Register an integration."""
        with self._lock:
            # Validate configuration
            errors = config.validate()
            if errors:
                raise ValidationError(f"Configuration validation failed: {', '.join(errors)}")
            
            # Check if integration already exists
            if config.id in self._integrations:
                raise IntegrationError(
                    f"Integration with ID '{config.id}' already exists",
                    ErrorCode.INTEGRATION_FAILED
                )
            
            # Get factory and create instance
            factory = self.get_factory(config.type)
            if not factory:
                raise IntegrationError(
                    f"No factory registered for integration type '{config.type.value}'",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            try:
                instance = factory.create_instance(config)
                integration_instance = IntegrationInstance(config=config, instance=instance)
                
                self._integrations[config.id] = integration_instance
                self.logger.info(f"Registered integration: {config.id}")
                
                return integration_instance
                
            except Exception as e:
                raise IntegrationError(
                    f"Failed to create integration instance: {str(e)}",
                    ErrorCode.INTEGRATION_FAILED,
                    cause=e
                )
    
    def unregister_integration(self, integration_id: str) -> bool:
        """Unregister an integration."""
        with self._lock:
            if integration_id in self._integrations:
                integration = self._integrations[integration_id]
                
                # Cleanup if active
                if integration.is_active:
                    self._cleanup_integration(integration)
                
                del self._integrations[integration_id]
                self.logger.info(f"Unregistered integration: {integration_id}")
                return True
            
            return False
    
    def get_integration(self, integration_id: str) -> Optional[IntegrationInstance]:
        """Get an integration by ID."""
        with self._lock:
            return self._integrations.get(integration_id)
    
    def list_integrations(
        self,
        integration_type: Optional[IntegrationType] = None,
        status: Optional[IntegrationStatus] = None,
        enabled_only: bool = False
    ) -> List[IntegrationInstance]:
        """List integrations with optional filtering."""
        with self._lock:
            integrations = list(self._integrations.values())
            
            if integration_type:
                integrations = [i for i in integrations if i.config.type == integration_type]
            
            if status:
                integrations = [i for i in integrations if i.config.status == status]
            
            if enabled_only:
                integrations = [i for i in integrations if i.config.enabled]
            
            return integrations
    
    def update_integration(self, integration_id: str, updates: Dict[str, Any]) -> IntegrationInstance:
        """Update an integration configuration."""
        with self._lock:
            integration = self.get_integration(integration_id)
            if not integration:
                raise IntegrationNotFoundError(
                    f"Integration '{integration_id}' not found",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            # Create new config with updates
            old_config = integration.config
            new_config_data = old_config.to_dict()
            new_config_data.update(updates)
            new_config_data["updated_at"] = datetime.now(timezone.utc)
            
            # Reconstruct config
            new_config = IntegrationConfig(
                id=new_config_data["id"],
                name=new_config_data["name"],
                type=IntegrationType(new_config_data["type"]),
                status=IntegrationStatus(new_config_data["status"]),
                config=new_config_data["config"],
                metadata=new_config_data["metadata"],
                created_at=datetime.fromisoformat(new_config_data["created_at"]),
                updated_at=new_config_data["updated_at"],
                version=new_config_data["version"],
                enabled=new_config_data["enabled"],
                tags=new_config_data["tags"]
            )
            
            # Validate new config
            errors = new_config.validate()
            if errors:
                raise ValidationError(f"Configuration validation failed: {', '.join(errors)}")
            
            # If integration is active, cleanup first
            if integration.is_active:
                self._cleanup_integration(integration)
            
            # Create new instance
            factory = self.get_factory(new_config.type)
            if not factory:
                raise IntegrationError(
                    f"No factory registered for integration type '{new_config.type.value}'",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            try:
                instance = factory.create_instance(new_config)
                new_integration_instance = IntegrationInstance(
                    config=new_config,
                    instance=instance,
                    is_active=False,  # Start inactive
                    error_count=integration.error_count,
                    last_error=integration.last_error,
                    metrics=integration.metrics.copy()
                )
                
                self._integrations[integration_id] = new_integration_instance
                self.logger.info(f"Updated integration: {integration_id}")
                
                return new_integration_instance
                
            except Exception as e:
                # Restore old integration on failure
                self._integrations[integration_id] = integration
                raise IntegrationError(
                    f"Failed to update integration instance: {str(e)}",
                    ErrorCode.INTEGRATION_FAILED,
                    cause=e
                )
    
    def activate_integration(self, integration_id: str) -> bool:
        """Activate an integration."""
        with self._lock:
            integration = self.get_integration(integration_id)
            if not integration:
                raise IntegrationNotFoundError(
                    f"Integration '{integration_id}' not found",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            if not integration.config.enabled:
                raise IntegrationError(
                    f"Integration '{integration_id}' is disabled",
                    ErrorCode.INTEGRATION_DISABLED
                )
            
            if integration.is_active:
                self.logger.warning(f"Integration '{integration_id}' is already active")
                return True
            
            try:
                self._initialize_integration(integration)
                integration.is_active = True
                integration.last_activity = datetime.now(timezone.utc)
                integration.config.status = IntegrationStatus.ACTIVE
                
                self.logger.info(f"Activated integration: {integration_id}")
                return True
                
            except Exception as e:
                integration.error_count += 1
                integration.last_error = str(e)
                integration.config.status = IntegrationStatus.FAILED
                
                raise IntegrationError(
                    f"Failed to activate integration '{integration_id}': {str(e)}",
                    ErrorCode.INTEGRATION_FAILED,
                    cause=e
                )
    
    def deactivate_integration(self, integration_id: str) -> bool:
        """Deactivate an integration."""
        with self._lock:
            integration = self.get_integration(integration_id)
            if not integration:
                raise IntegrationNotFoundError(
                    f"Integration '{integration_id}' not found",
                    ErrorCode.INTEGRATION_NOT_FOUND
                )
            
            if not integration.is_active:
                self.logger.warning(f"Integration '{integration_id}' is already inactive")
                return True
            
            try:
                self._cleanup_integration(integration)
                integration.is_active = False
                integration.config.status = IntegrationStatus.INACTIVE
                
                self.logger.info(f"Deactivated integration: {integration_id}")
                return True
                
            except Exception as e:
                integration.error_count += 1
                integration.last_error = str(e)
                
                raise IntegrationError(
                    f"Failed to deactivate integration '{integration_id}': {str(e)}",
                    ErrorCode.INTEGRATION_FAILED,
                    cause=e
                )
    
    def get_integration_metrics(self, integration_id: str) -> Dict[str, Any]:
        """Get metrics for an integration."""
        integration = self.get_integration(integration_id)
        if not integration:
            raise IntegrationNotFoundError(
                f"Integration '{integration_id}' not found",
                ErrorCode.INTEGRATION_NOT_FOUND
            )
        
        return {
            "integration_id": integration_id,
            "is_active": integration.is_active,
            "error_count": integration.error_count,
            "last_error": integration.last_error,
            "last_activity": integration.last_activity.isoformat() if integration.last_activity else None,
            "status": integration.config.status.value,
            "type": integration.config.type.value,
            "version": integration.config.version,
            "custom_metrics": integration.metrics
        }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            total_integrations = len(self._integrations)
            active_integrations = len([i for i in self._integrations.values() if i.is_active])
            enabled_integrations = len([i for i in self._integrations.values() if i.config.enabled])
            
            type_counts = {}
            for integration in self._integrations.values():
                type_name = integration.config.type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            
            status_counts = {}
            for integration in self._integrations.values():
                status_name = integration.config.status.value
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            return {
                "total_integrations": total_integrations,
                "active_integrations": active_integrations,
                "enabled_integrations": enabled_integrations,
                "registered_factories": list(self._factories.keys()),
                "type_distribution": type_counts,
                "status_distribution": status_counts,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _initialize_integration(self, integration: IntegrationInstance) -> None:
        """Initialize an integration instance."""
        # This would be implemented based on the specific integration type
        # For now, we'll just log the initialization
        self.logger.info(f"Initializing integration: {integration.config.id}")
    
    def _cleanup_integration(self, integration: IntegrationInstance) -> None:
        """Cleanup an integration instance."""
        # This would be implemented based on the specific integration type
        # For now, we'll just log the cleanup
        self.logger.info(f"Cleaning up integration: {integration.config.id}")
        integration.is_active = False


# ---------------------------------------------------------------------------
# Global Registry Instance
# ---------------------------------------------------------------------------

# Global registry instance
integration_registry = IntegrationRegistry()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def get_registry() -> IntegrationRegistry:
    """Get the global integration registry."""
    return integration_registry


def register_integration_factory(integration_type: IntegrationType, factory: IntegrationFactory) -> None:
    """Register a factory with the global registry."""
    integration_registry.register_factory(integration_type, factory)


def register_integration(config: IntegrationConfig) -> IntegrationInstance:
    """Register an integration with the global registry."""
    return integration_registry.register_integration(config)


def get_integration(integration_id: str) -> Optional[IntegrationInstance]:
    """Get an integration from the global registry."""
    return integration_registry.get_integration(integration_id)


def activate_integration(integration_id: str) -> bool:
    """Activate an integration using the global registry."""
    return integration_registry.activate_integration(integration_id)


def deactivate_integration(integration_id: str) -> bool:
    """Deactivate an integration using the global registry."""
    return integration_registry.deactivate_integration(integration_id)


# Initialize logging
logger.info("Integration registry module initialized")
