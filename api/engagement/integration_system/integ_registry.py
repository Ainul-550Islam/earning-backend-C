# engagement/integration_system/integ_registry.py
"""
Integration registry system.
Manages registration, discovery, and lifecycle of integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from .integ_constants import (
    IntegrationType, IntegrationStatus, EventPriority,
    DEFAULT_CONFIG, CACHE_KEYS, ERROR_CODES
)

logger = logging.getLogger(__name__)


class RegistrationStatus(Enum):
    """Registration status for integrations."""
    PENDING = "pending"
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNREGISTERED = "unregistered"


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""
    id: str
    name: str
    type: IntegrationType
    description: str = ""
    version: str = "1.0.0"
    status: RegistrationStatus = RegistrationStatus.PENDING
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    last_active: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'description': self.description,
            'version': self.version,
            'status': self.status.value,
            'config': self.config,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'error_count': self.error_count,
            'success_count': self.success_count,
            'tags': self.tags,
        }


class BaseIntegration(ABC):
    """Base class for all integrations."""
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._is_initialized = False
        self._lock = threading.Lock()
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the integration."""
        pass
    
    @abstractmethod
    def execute(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """Execute the integration."""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate integration configuration."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Cleanup resources."""
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with fallback to defaults."""
        return self.config.config.get(key, default)
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration."""
        with self._lock:
            self.config.config.update(updates)
            self.config.updated_at = timezone.now()
    
    def increment_success(self):
        """Increment success count."""
        self.config.success_count += 1
        self.config.last_active = timezone.now()
    
    def increment_error(self):
        """Increment error count."""
        self.config.error_count += 1
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.config.success_count + self.config.error_count
        if total == 0:
            return 0.0
        return (self.config.success_count / total) * 100


class IntegrationRegistry:
    """Registry for managing integrations."""
    
    def __init__(self):
        self._integrations: Dict[str, BaseIntegration] = {}
        self._configs: Dict[str, IntegrationConfig] = {}
        self._lock = threading.RLock()
        self._health_cache = {}
        self._stats_cache = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def register(self, integration: BaseIntegration, config: IntegrationConfig) -> bool:
        """Register an integration."""
        try:
            with self._lock:
                # Validate configuration
                if not integration.validate_config():
                    self.logger.error(f"Invalid configuration for integration {config.id}")
                    return False
                
                # Check if integration already exists
                if config.id in self._integrations:
                    self.logger.warning(f"Integration {config.id} already registered, updating...")
                    self.unregister(config.id)
                
                # Initialize integration
                if not integration.initialize():
                    self.logger.error(f"Failed to initialize integration {config.id}")
                    config.status = RegistrationStatus.ERROR
                    return False
                
                # Register integration
                self._integrations[config.id] = integration
                self._configs[config.id] = config
                config.status = RegistrationStatus.REGISTERED
                
                # Cache configuration
                self._cache_config(config)
                
                self.logger.info(f"Successfully registered integration {config.id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to register integration {config.id}: {exc}")
            config.status = RegistrationStatus.ERROR
            return False
    
    def unregister(self, integration_id: str) -> bool:
        """Unregister an integration."""
        try:
            with self._lock:
                if integration_id not in self._integrations:
                    self.logger.warning(f"Integration {integration_id} not found")
                    return False
                
                integration = self._integrations[integration_id]
                config = self._configs[integration_id]
                
                # Cleanup integration
                integration.cleanup()
                
                # Remove from registry
                del self._integrations[integration_id]
                del self._configs[integration_id]
                config.status = RegistrationStatus.UNREGISTERED
                
                # Clear cache
                self._clear_config_cache(integration_id)
                
                self.logger.info(f"Successfully unregistered integration {integration_id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to unregister integration {integration_id}: {exc}")
            return False
    
    def get_integration(self, integration_id: str) -> Optional[BaseIntegration]:
        """Get integration by ID."""
        return self._integrations.get(integration_id)
    
    def get_config(self, integration_id: str) -> Optional[IntegrationConfig]:
        """Get integration configuration by ID."""
        config = self._configs.get(integration_id)
        if not config:
            # Try to get from cache
            config = self._get_cached_config(integration_id)
            if config:
                self._configs[integration_id] = config
        
        return config
    
    def list_integrations(self, status: RegistrationStatus = None, 
                         integration_type: IntegrationType = None,
                         tags: List[str] = None) -> List[IntegrationConfig]:
        """List integrations with optional filtering."""
        configs = list(self._configs.values())
        
        if status:
            configs = [c for c in configs if c.status == status]
        
        if integration_type:
            configs = [c for c in configs if c.type == integration_type]
        
        if tags:
            configs = [c for c in configs if any(tag in c.tags for tag in tags)]
        
        return configs
    
    def execute_integration(self, integration_id: str, data: Any, 
                           context: Dict[str, Any] = None) -> Any:
        """Execute an integration."""
        integration = self.get_integration(integration_id)
        if not integration:
            raise ValueError(f"Integration {integration_id} not found")
        
        config = self.get_config(integration_id)
        if config.status != RegistrationStatus.REGISTERED:
            raise ValueError(f"Integration {integration_id} is not active")
        
        try:
            result = integration.execute(data, context or {})
            integration.increment_success()
            return result
            
        except Exception as exc:
            integration.increment_error()
            self.logger.error(f"Failed to execute integration {integration_id}: {exc}")
            raise
    
    def health_check(self, integration_id: str = None) -> Dict[str, Any]:
        """Perform health check on integrations."""
        if integration_id:
            return self._check_integration_health(integration_id)
        else:
            return self._check_all_integrations_health()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            total_integrations = len(self._integrations)
            status_counts = {}
            type_counts = {}
            total_success = 0
            total_errors = 0
            
            for config in self._configs.values():
                # Count by status
                status = config.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Count by type
                integration_type = config.type.value
                type_counts[integration_type] = type_counts.get(integration_type, 0) + 1
                
                # Count successes and errors
                total_success += config.success_count
                total_errors += config.error_count
            
            success_rate = (total_success / (total_success + total_errors) * 100) if (total_success + total_errors) > 0 else 0
            
            return {
                'total_integrations': total_integrations,
                'status_counts': status_counts,
                'type_counts': type_counts,
                'total_success': total_success,
                'total_errors': total_errors,
                'success_rate': success_rate,
                'last_updated': timezone.now().isoformat(),
            }
    
    def update_integration_status(self, integration_id: str, status: RegistrationStatus) -> bool:
        """Update integration status."""
        config = self.get_config(integration_id)
        if not config:
            return False
        
        config.status = status
        config.updated_at = timezone.now()
        self._cache_config(config)
        return True
    
    def find_integrations_by_tag(self, tag: str) -> List[IntegrationConfig]:
        """Find integrations by tag."""
        return [config for config in self._configs.values() if tag in config.tags]
    
    def get_integrations_by_type(self, integration_type: IntegrationType) -> List[IntegrationConfig]:
        """Get integrations by type."""
        return [config for config in self._configs.values() if config.type == integration_type]
    
    def cleanup_inactive_integrations(self, inactive_hours: int = 24) -> int:
        """Clean up inactive integrations."""
        cutoff_time = timezone.now() - timedelta(hours=inactive_hours)
        cleaned_count = 0
        
        for integration_id, config in list(self._configs.items()):
            if config.last_active and config.last_active < cutoff_time:
                if config.status == RegistrationStatus.REGISTERED:
                    self.update_integration_status(integration_id, RegistrationStatus.INACTIVE)
                    cleaned_count += 1
        
        return cleaned_count
    
    def _cache_config(self, config: IntegrationConfig):
        """Cache integration configuration."""
        cache_key = CACHE_KEYS['INTEGRATION_CONFIG'].format(integration_id=config.id)
        cache.set(cache_key, config.to_dict(), timeout=3600)  # 1 hour
    
    def _get_cached_config(self, integration_id: str) -> Optional[IntegrationConfig]:
        """Get cached integration configuration."""
        cache_key = CACHE_KEYS['INTEGRATION_CONFIG'].format(integration_id=integration_id)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return IntegrationConfig(
                id=cached_data['id'],
                name=cached_data['name'],
                type=IntegrationType(cached_data['type']),
                description=cached_data['description'],
                version=cached_data['version'],
                status=RegistrationStatus(cached_data['status']),
                config=cached_data['config'],
                metadata=cached_data['metadata'],
                created_at=datetime.fromisoformat(cached_data['created_at']),
                updated_at=datetime.fromisoformat(cached_data['updated_at']),
                last_active=datetime.fromisoformat(cached_data['last_active']) if cached_data['last_active'] else None,
                error_count=cached_data['error_count'],
                success_count=cached_data['success_count'],
                tags=cached_data['tags'],
            )
        
        return None
    
    def _clear_config_cache(self, integration_id: str):
        """Clear cached configuration."""
        cache_key = CACHE_KEYS['INTEGRATION_CONFIG'].format(integration_id=integration_id)
        cache.delete(cache_key)
    
    def _check_integration_health(self, integration_id: str) -> Dict[str, Any]:
        """Check health of a specific integration."""
        integration = self.get_integration(integration_id)
        if not integration:
            return {
                'integration_id': integration_id,
                'status': 'not_found',
                'healthy': False,
            }
        
        try:
            health_data = integration.health_check()
            health_data['integration_id'] = integration_id
            health_data['healthy'] = health_data.get('status') == 'healthy'
            health_data['checked_at'] = timezone.now().isoformat()
            
            # Cache health data
            cache_key = CACHE_KEYS['HEALTH_CHECK'].format(integration_id=integration_id)
            cache.set(cache_key, health_data, timeout=300)  # 5 minutes
            
            return health_data
            
        except Exception as exc:
            self.logger.error(f"Health check failed for integration {integration_id}: {exc}")
            return {
                'integration_id': integration_id,
                'status': 'error',
                'healthy': False,
                'error': str(exc),
                'checked_at': timezone.now().isoformat(),
            }
    
    def _check_all_integrations_health(self) -> Dict[str, Any]:
        """Check health of all integrations."""
        health_results = {}
        healthy_count = 0
        unhealthy_count = 0
        
        for integration_id in self._integrations.keys():
            health = self._check_integration_health(integration_id)
            health_results[integration_id] = health
            
            if health.get('healthy', False):
                healthy_count += 1
            else:
                unhealthy_count += 1
        
        return {
            'total_integrations': len(self._integrations),
            'healthy_count': healthy_count,
            'unhealthy_count': unhealthy_count,
            'health_results': health_results,
            'checked_at': timezone.now().isoformat(),
        }


class IntegrationFactory:
    """Factory for creating integrations."""
    
    _integration_classes: Dict[str, Type[BaseIntegration]] = {}
    
    @classmethod
    def register_integration_class(cls, integration_type: str, integration_class: Type[BaseIntegration]):
        """Register an integration class."""
        cls._integration_classes[integration_type] = integration_class
    
    @classmethod
    def create_integration(cls, integration_type: str, config: IntegrationConfig) -> BaseIntegration:
        """Create an integration instance."""
        integration_class = cls._integration_classes.get(integration_type)
        if not integration_class:
            raise ValueError(f"Unknown integration type: {integration_type}")
        
        return integration_class(config)
    
    @classmethod
    def list_supported_types(cls) -> List[str]:
        """List supported integration types."""
        return list(cls._integration_classes.keys())


# Global registry instance
integration_registry = IntegrationRegistry()


# Decorator for registering integration classes
def register_integration(integration_type: str):
    """Decorator to register an integration class."""
    def decorator(cls):
        IntegrationFactory.register_integration_class(integration_type, cls)
        return cls
    return decorator


# Integration discovery utilities
class IntegrationDiscovery:
    """Utilities for discovering integrations."""
    
    @staticmethod
    def discover_from_settings() -> List[Dict[str, Any]]:
        """Discover integrations from Django settings."""
        integrations = []
        
        settings_integrations = getattr(settings, 'ENGAGEMENT_INTEGRATIONS', [])
        
        for integration_config in settings_integrations:
            integrations.append({
                'id': integration_config.get('id'),
                'name': integration_config.get('name'),
                'type': integration_config.get('type'),
                'config': integration_config.get('config', {}),
                'enabled': integration_config.get('enabled', True),
            })
        
        return integrations
    
    @staticmethod
    def discover_from_database() -> List[Dict[str, Any]]:
        """Discover integrations from database."""
        # This would query a database table for integration configurations
        # For now, return empty list
        return []
    
    @staticmethod
    def discover_from_file(file_path: str) -> List[Dict[str, Any]]:
        """Discover integrations from configuration file."""
        import json
        import os
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get('integrations', [])
        except Exception as exc:
            logger.error(f"Failed to load integrations from {file_path}: {exc}")
            return []


# Auto-registration utilities
class AutoRegistration:
    """Utilities for automatic integration registration."""
    
    @staticmethod
    def register_all_discovered():
        """Register all discovered integrations."""
        # Discover from different sources
        settings_integrations = IntegrationDiscovery.discover_from_settings()
        db_integrations = IntegrationDiscovery.discover_from_database()
        
        all_integrations = settings_integrations + db_integrations
        
        registered_count = 0
        for integration_data in all_integrations:
            try:
                # Create configuration
                config = IntegrationConfig(
                    id=integration_data['id'],
                    name=integration_data['name'],
                    type=IntegrationType(integration_data['type']),
                    config=integration_data.get('config', {}),
                    metadata=integration_data.get('metadata', {}),
                    tags=integration_data.get('tags', []),
                )
                
                # Create integration
                integration = IntegrationFactory.create_integration(
                    integration_data['type'],
                    config
                )
                
                # Register
                if integration_registry.register(integration, config):
                    registered_count += 1
                    
            except Exception as exc:
                logger.error(f"Failed to auto-register integration {integration_data.get('id', 'unknown')}: {exc}")
        
        logger.info(f"Auto-registered {registered_count} integrations")
        return registered_count
