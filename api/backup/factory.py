"""
🏭 Backup Service Factory Module

This module provides a comprehensive factory pattern for creating and managing
backup services, storage adapters, and related components. It implements the
Factory pattern to decouple service creation from service usage.

Features:
- Service factory pattern implementation
- Dynamic service registration
- Configuration-based service creation
- Service lifecycle management
- Dependency injection support
- Service health monitoring
"""
import time

import logging
from typing import Dict, Any, Type, Optional, Union, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import importlib
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Import backup services
from .services.BaseBackup import BaseBackupService
from .services.DatabaseBackup import DatabaseBackupService
from .services.storage import StorageAdapterFactory, StorageAdapterInterface
from .services.BackupValidator import BackupValidator
from .services.BackupEncryptionService import BackupEncryptionService
from .services.BackupCompressionService import BackupCompressionService
from .services.BackupNotificationService import BackupNotificationService

# Import integration system components
from .INTEGRATION_SYSTEM.integ_registry import get_integration_registry
from .INTEGRATION_SYSTEM.integ_adapter import BaseIntegrationAdapter
from .INTEGRATION_SYSTEM.data_validator import get_data_validator
from .INTEGRATION_SYSTEM.performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Enumeration of available service types."""
    
    # Storage services
    STORAGE_LOCAL = "local"
    STORAGE_S3 = "s3"
    STORAGE_AZURE = "azure"
    STORAGE_GCS = "gcs"
    
    # Database services
    DATABASE_POSTGRESQL = "postgresql"
    DATABASE_MYSQL = "mysql"
    DATABASE_SQLITE = "sqlite"
    DATABASE_DJANGO = "django"
    
    # Utility services
    VALIDATOR = "validator"
    ENCRYPTION = "encryption"
    COMPRESSION = "compression"
    NOTIFICATION = "notification"
    
    # Integration services
    INTEGRATION_ADAPTER = "integration_adapter"
    DATA_VALIDATOR = "data_validator"
    PERFORMANCE_MONITOR = "performance_monitor"


@dataclass
class ServiceConfig:
    """Configuration class for service creation."""
    
    service_type: ServiceType
    service_class: Type
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    health_check_enabled: bool = True
    auto_register: bool = True
    
    def __post_init__(self):
        """Validate service configuration."""
        if not self.service_class:
            raise ValueError("service_class is required")
        
        if not isinstance(self.service_type, ServiceType):
            self.service_type = ServiceType(self.service_type)


@dataclass
class ServiceInstance:
    """Represents a created service instance."""
    
    service_id: str
    service_type: ServiceType
    instance: Any
    config: ServiceConfig
    created_at: float
    health_status: str = "healthy"
    last_health_check: Optional[float] = None
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.health_status == "healthy"


class ServiceRegistry:
    """Registry for managing service configurations and instances."""
    
    def __init__(self):
        self._services: Dict[str, ServiceConfig] = {}
        self._instances: Dict[str, ServiceInstance] = {}
        self._service_types: Dict[ServiceType, List[str]] = {}
        
    def register_service(self, service_id: str, config: ServiceConfig) -> None:
        """Register a service configuration."""
        if service_id in self._services:
            logger.warning(f"Service {service_id} already registered, updating...")
        
        self._services[service_id] = config
        
        # Update service type mapping
        if config.service_type not in self._service_types:
            self._service_types[config.service_type] = []
        if service_id not in self._service_types[config.service_type]:
            self._service_types[config.service_type].append(service_id)
        
        logger.info(f"Registered service: {service_id} ({config.service_type.value})")
    
    def get_service_config(self, service_id: str) -> Optional[ServiceConfig]:
        """Get service configuration by ID."""
        return self._services.get(service_id)
    
    def get_services_by_type(self, service_type: ServiceType) -> List[str]:
        """Get all service IDs of a specific type."""
        return self._service_types.get(service_type, [])
    
    def list_services(self) -> Dict[str, ServiceConfig]:
        """List all registered services."""
        return self._services.copy()
    
    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        if service_id not in self._services:
            return False
        
        config = self._services[service_id]
        
        # Remove from service type mapping
        if config.service_type in self._service_types:
            if service_id in self._service_types[config.service_type]:
                self._service_types[config.service_type].remove(service_id)
        
        # Remove instance if exists
        if service_id in self._instances:
            del self._instances[service_id]
        
        del self._services[service_id]
        logger.info(f"Unregistered service: {service_id}")
        return True
    
    def register_instance(self, service_id: str, instance: Any) -> None:
        """Register a service instance."""
        if service_id not in self._services:
            raise ValueError(f"Service {service_id} not registered")
        
        config = self._services[service_id]
        
        import time
        service_instance = ServiceInstance(
            service_id=service_id,
            service_type=config.service_type,
            instance=instance,
            config=config,
            created_at=time.time()
        )
        
        self._instances[service_id] = service_instance
        logger.info(f"Registered instance for service: {service_id}")
    
    def get_instance(self, service_id: str) -> Optional[Any]:
        """Get service instance by ID."""
        instance_info = self._instances.get(service_id)
        return instance_info.instance if instance_info else None
    
    def get_instance_info(self, service_id: str) -> Optional[ServiceInstance]:
        """Get service instance information."""
        return self._instances.get(service_id)
    
    def list_instances(self) -> Dict[str, ServiceInstance]:
        """List all service instances."""
        return self._instances.copy()


class BaseServiceFactory(ABC):
    """Abstract base class for service factories."""
    
    @abstractmethod
    def create_service(self, config: ServiceConfig) -> Any:
        """Create a service instance."""
        pass
    
    @abstractmethod
    def validate_config(self, config: ServiceConfig) -> bool:
        """Validate service configuration."""
        pass


class StorageServiceFactory(BaseServiceFactory):
    """Factory for creating storage service instances."""
    
    def __init__(self):
        self._service_map = {
            ServiceType.STORAGE_LOCAL: LocalBackupService,
            ServiceType.STORAGE_S3: S3BackupService,
            ServiceType.STORAGE_AZURE: AzureBackupService,
            ServiceType.STORAGE_GCS: GCSBackupService,
        }
    
    def create_service(self, config: ServiceConfig) -> BaseBackupService:
        """Create a storage service instance."""
        if not self.validate_config(config):
            raise ValueError(f"Invalid configuration for {config.service_type}")
        
        service_class = self._service_map.get(config.service_type)
        if not service_class:
            raise ValueError(f"Unsupported storage service: {config.service_type}")
        
        try:
            instance = service_class(config.config)
            logger.info(f"Created storage service: {config.service_type.value}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create storage service {config.service_type}: {e}")
            raise
    
    def validate_config(self, config: ServiceConfig) -> bool:
        """Validate storage service configuration."""
        if config.service_type not in self._service_map:
            return False
        
        # Type-specific validation
        if config.service_type == ServiceType.STORAGE_S3:
            required_keys = ['bucket_name', 'aws_access_key_id', 'aws_secret_access_key']
            return all(key in config.config for key in required_keys)
        
        elif config.service_type == ServiceType.STORAGE_AZURE:
            required_keys = ['account_name', 'account_key', 'container_name']
            return all(key in config.config for key in required_keys)
        
        elif config.service_type == ServiceType.STORAGE_GCS:
            required_keys = ['bucket_name', 'credentials_path']
            return all(key in config.config for key in required_keys)
        
        return True


class DatabaseServiceFactory(BaseServiceFactory):
    """Factory for creating database service instances."""
    
    def __init__(self):
        self._service_map = {
            ServiceType.DATABASE_POSTGRESQL: DatabaseBackupService,
            ServiceType.DATABASE_MYSQL: DatabaseBackupService,
            ServiceType.DATABASE_SQLITE: DatabaseBackupService,
            ServiceType.DATABASE_DJANGO: DatabaseBackupService,
        }
    
    def create_service(self, config: ServiceConfig) -> DatabaseBackupService:
        """Create a database service instance."""
        if not self.validate_config(config):
            raise ValueError(f"Invalid configuration for {config.service_type}")
        
        try:
            instance = DatabaseBackupService(config.config)
            logger.info(f"Created database service: {config.service_type.value}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create database service {config.service_type}: {e}")
            raise
    
    def validate_config(self, config: ServiceConfig) -> bool:
        """Validate database service configuration."""
        return config.service_type in self._service_map


class UtilityServiceFactory(BaseServiceFactory):
    """Factory for creating utility service instances."""
    
    def __init__(self):
        self._service_map = {
            ServiceType.VALIDATOR: BackupValidator,
            ServiceType.ENCRYPTION: BackupEncryptionService,
            ServiceType.COMPRESSION: BackupCompressionService,
            ServiceType.NOTIFICATION: BackupNotificationService,
        }
    
    def create_service(self, config: ServiceConfig) -> Any:
        """Create a utility service instance."""
        if not self.validate_config(config):
            raise ValueError(f"Invalid configuration for {config.service_type}")
        
        service_class = self._service_map.get(config.service_type)
        if not service_class:
            raise ValueError(f"Unsupported utility service: {config.service_type}")
        
        try:
            if config.service_type == ServiceType.VALIDATOR:
                instance = service_class()
            else:
                instance = service_class(config.config)
            
            logger.info(f"Created utility service: {config.service_type.value}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create utility service {config.service_type}: {e}")
            raise
    
    def validate_config(self, config: ServiceConfig) -> bool:
        """Validate utility service configuration."""
        if config.service_type not in self._service_map:
            return False
        
        # Validator doesn't need config
        if config.service_type == ServiceType.VALIDATOR:
            return True
        
        # Notification service requires notification config
        if config.service_type == ServiceType.NOTIFICATION:
            return 'notification_config' in config.config
        
        return True


class IntegrationServiceFactory(BaseServiceFactory):
    """Factory for creating integration service instances."""
    
    def create_service(self, config: ServiceConfig) -> Any:
        """Create an integration service instance."""
        if not self.validate_config(config):
            raise ValueError(f"Invalid configuration for {config.service_type}")
        
        try:
            if config.service_type == ServiceType.INTEGRATION_ADAPTER:
                registry = get_integration_registry()
                adapter_name = config.config.get('adapter_name')
                if not adapter_name:
                    raise ValueError("adapter_name required for integration adapter")
                
                instance = registry.get_adapter(adapter_name)
            
            elif config.service_type == ServiceType.DATA_VALIDATOR:
                instance = get_data_validator()
            
            elif config.service_type == ServiceType.PERFORMANCE_MONITOR:
                instance = get_performance_monitor()
            
            else:
                raise ValueError(f"Unsupported integration service: {config.service_type}")
            
            logger.info(f"Created integration service: {config.service_type.value}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create integration service {config.service_type}: {e}")
            raise
    
    def validate_config(self, config: ServiceConfig) -> bool:
        """Validate integration service configuration."""
        return config.service_type in [
            ServiceType.INTEGRATION_ADAPTER,
            ServiceType.DATA_VALIDATOR,
            ServiceType.PERFORMANCE_MONITOR
        ]


class BackupServiceFactory:
    """
    Main factory class for creating and managing backup services.
    
    This factory provides a unified interface for creating all types of backup
    services, managing their lifecycle, and handling dependencies.
    """
    
    def __init__(self):
        self._registry = ServiceRegistry()
        self._factories = {
            'storage': StorageServiceFactory(),
            'database': DatabaseServiceFactory(),
            'utility': UtilityServiceFactory(),
            'integration': IntegrationServiceFactory(),
        }
        
        # Register default services
        self._register_default_services()
        
        # Load custom services from settings
        self._load_custom_services()
    
    def _register_default_services(self) -> None:
        """Register default service configurations."""
        import time
        
        # Default storage services
        default_storage_configs = {
            'local_storage': ServiceConfig(
                service_type=ServiceType.STORAGE_LOCAL,
                service_class=LocalBackupService,
                config={'backup_dir': getattr(settings, 'BACKUP_DIR', '/tmp/backups')},
                priority=1
            ),
            's3_storage': ServiceConfig(
                service_type=ServiceType.STORAGE_S3,
                service_class=S3BackupService,
                config={
                    'bucket_name': getattr(settings, 'AWS_S3_BUCKET', ''),
                    'aws_access_key_id': getattr(settings, 'AWS_ACCESS_KEY_ID', ''),
                    'aws_secret_access_key': getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''),
                    'region': getattr(settings, 'AWS_S3_REGION', 'us-east-1'),
                },
                enabled=bool(getattr(settings, 'AWS_S3_BUCKET', '')),
                priority=2
            ),
            'azure_storage': ServiceConfig(
                service_type=ServiceType.STORAGE_AZURE,
                service_class=AzureBackupService,
                config={
                    'account_name': getattr(settings, 'AZURE_ACCOUNT_NAME', ''),
                    'account_key': getattr(settings, 'AZURE_ACCOUNT_KEY', ''),
                    'container_name': getattr(settings, 'AZURE_CONTAINER', ''),
                },
                enabled=bool(getattr(settings, 'AZURE_ACCOUNT_NAME', '')),
                priority=3
            ),
            'gcs_storage': ServiceConfig(
                service_type=ServiceType.STORAGE_GCS,
                service_class=GCSBackupService,
                config={
                    'bucket_name': getattr(settings, 'GCS_BUCKET', ''),
                    'credentials_path': getattr(settings, 'GCS_CREDENTIALS_PATH', ''),
                },
                enabled=bool(getattr(settings, 'GCS_BUCKET', '')),
                priority=4
            ),
        }
        
        # Default utility services
        default_utility_configs = {
            'validator': ServiceConfig(
                service_type=ServiceType.VALIDATOR,
                service_class=BackupValidator,
                priority=1
            ),
            'encryption': ServiceConfig(
                service_type=ServiceType.ENCRYPTION,
                service_class=BackupEncryptionService,
                config={'default_algorithm': 'AES-256-GCM'},
                priority=2
            ),
            'compression': ServiceConfig(
                service_type=ServiceType.COMPRESSION,
                service_class=BackupCompressionService,
                config={'default_format': 'zip', 'default_level': 6},
                priority=3
            ),
            'notification': ServiceConfig(
                service_type=ServiceType.NOTIFICATION,
                service_class=BackupNotificationService,
                config={
                    'notification_config': getattr(settings, 'BACKUP_NOTIFICATION_CONFIG', {})
                },
                enabled=bool(getattr(settings, 'BACKUP_NOTIFICATION_CONFIG', {})),
                priority=4
            ),
        }
        
        # Register all default services
        for service_id, config in default_storage_configs.items():
            if config.enabled:
                self._registry.register_service(service_id, config)
        
        for service_id, config in default_utility_configs.items():
            if config.enabled:
                self._registry.register_service(service_id, config)
    
    def _load_custom_services(self) -> None:
        """Load custom service configurations from Django settings."""
        custom_services = getattr(settings, 'BACKUP_CUSTOM_SERVICES', {})
        
        for service_id, service_config in custom_services.items():
            try:
                # Convert string service type to enum
                if 'service_type' in service_config:
                    service_type = ServiceType(service_config['service_type'])
                else:
                    continue
                
                # Load service class dynamically
                if 'service_class_path' in service_config:
                    module_path, class_name = service_config['service_class_path'].rsplit('.', 1)
                    module = importlib.import_module(module_path)
                    service_class = getattr(module, class_name)
                else:
                    continue
                
                config = ServiceConfig(
                    service_type=service_type,
                    service_class=service_class,
                    config=service_config.get('config', {}),
                    enabled=service_config.get('enabled', True),
                    priority=service_config.get('priority', 0),
                    dependencies=service_config.get('dependencies', []),
                    health_check_enabled=service_config.get('health_check_enabled', True),
                    auto_register=service_config.get('auto_register', True)
                )
                
                self._registry.register_service(service_id, config)
                logger.info(f"Loaded custom service: {service_id}")
                
            except Exception as e:
                logger.error(f"Failed to load custom service {service_id}: {e}")
    
    def create_service(self, service_id: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create a service instance.
        
        Args:
            service_id: ID of the service to create
            config: Optional configuration overrides
            
        Returns:
            Created service instance
            
        Raises:
            ValueError: If service is not registered or configuration is invalid
        """
        service_config = self._registry.get_service_config(service_id)
        if not service_config:
            raise ValueError(f"Service {service_id} not registered")
        
        # Apply configuration overrides
        if config:
            service_config.config.update(config)
        
        # Determine factory type based on service type
        factory = None
        if service_config.service_type in [
            ServiceType.STORAGE_LOCAL, ServiceType.STORAGE_S3, 
            ServiceType.STORAGE_AZURE, ServiceType.STORAGE_GCS
        ]:
            factory = self._factories['storage']
        elif service_config.service_type in [
            ServiceType.DATABASE_POSTGRESQL, ServiceType.DATABASE_MYSQL,
            ServiceType.DATABASE_SQLITE, ServiceType.DATABASE_DJANGO
        ]:
            factory = self._factories['database']
        elif service_config.service_type in [
            ServiceType.VALIDATOR, ServiceType.ENCRYPTION,
            ServiceType.COMPRESSION, ServiceType.NOTIFICATION
        ]:
            factory = self._factories['utility']
        elif service_config.service_type in [
            ServiceType.INTEGRATION_ADAPTER, ServiceType.DATA_VALIDATOR,
            ServiceType.PERFORMANCE_MONITOR
        ]:
            factory = self._factories['integration']
        
        if not factory:
            raise ValueError(f"No factory found for service type: {service_config.service_type}")
        
        # Create service instance
        instance = factory.create_service(service_config)
        
        # Register instance
        self._registry.register_instance(service_id, instance)
        
        return instance
    
    def get_service(self, service_id: str) -> Any:
        """Get a service instance, creating it if necessary."""
        instance = self._registry.get_instance(service_id)
        if instance:
            return instance
        
        # Create instance if not exists
        return self.create_service(service_id)
    
    def get_storage_service(self, storage_type: str) -> BaseBackupService:
        """Get a storage service by type."""
        # Find service ID for the given storage type
        service_type = ServiceType(f"storage_{storage_type}")
        service_ids = self._registry.get_services_by_type(service_type)
        
        if not service_ids:
            raise ValueError(f"No storage service found for type: {storage_type}")
        
        # Get the highest priority service
        service_id = min(service_ids, key=lambda sid: self._registry.get_service_config(sid).priority)
        
        return self.get_service(service_id)
    
    def get_utility_service(self, utility_type: str) -> Any:
        """Get a utility service by type."""
        service_type = ServiceType(utility_type)
        service_ids = self._registry.get_services_by_type(service_type)
        
        if not service_ids:
            raise ValueError(f"No utility service found for type: {utility_type}")
        
        service_id = service_ids[0]  # Get first available
        return self.get_service(service_id)
    
    def register_service(self, service_id: str, config: ServiceConfig) -> None:
        """Register a new service."""
        self._registry.register_service(service_id, config)
        
        # Auto-create instance if enabled
        if config.auto_register:
            self.create_service(service_id)
    
    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        return self._registry.unregister_service(service_id)
    
    def list_services(self) -> Dict[str, ServiceConfig]:
        """List all registered services."""
        return self._registry.list_services()
    
    def list_instances(self) -> Dict[str, ServiceInstance]:
        """List all service instances."""
        return self._registry.list_instances()
    
    def check_service_health(self, service_id: str) -> bool:
        """Check the health of a service instance."""
        instance_info = self._registry.get_instance_info(service_id)
        if not instance_info:
            return False
        
        try:
            # Basic health check - try to access the instance
            if hasattr(instance_info.instance, 'health_check'):
                healthy = instance_info.instance.health_check()
            else:
                # Default health check - just ensure instance exists
                healthy = instance_info.instance is not None
            
            instance_info.health_status = "healthy" if healthy else "unhealthy"
            instance_info.last_health_check = time.time()
            
            return healthy
            
        except Exception as e:
            logger.error(f"Health check failed for service {service_id}: {e}")
            instance_info.health_status = "unhealthy"
            instance_info.last_health_check = time.time()
            return False
    
    def check_all_services_health(self) -> Dict[str, bool]:
        """Check health of all service instances."""
        results = {}
        for service_id in self._registry.list_instances():
            results[service_id] = self.check_service_health(service_id)
        return results
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered services."""
        services = self._registry.list_services()
        instances = self._registry.list_instances()
        
        stats = {
            'total_services': len(services),
            'total_instances': len(instances),
            'services_by_type': {},
            'enabled_services': 0,
            'healthy_services': 0,
        }
        
        # Count services by type
        for service_config in services.values():
            service_type = service_config.service_type.value
            if service_type not in stats['services_by_type']:
                stats['services_by_type'][service_type] = 0
            stats['services_by_type'][service_type] += 1
            
            if service_config.enabled:
                stats['enabled_services'] += 1
        
        # Count healthy instances
        for instance_info in instances.values():
            if instance_info.is_healthy():
                stats['healthy_services'] += 1
        
        return stats


# Global factory instance
_factory_instance: Optional[BackupServiceFactory] = None


def get_backup_service_factory() -> BackupServiceFactory:
    """Get the global backup service factory instance."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = BackupServiceFactory()
    return _factory_instance


def create_backup_service(service_id: str, config: Optional[Dict[str, Any]] = None) -> Any:
    """Convenience function to create a backup service."""
    factory = get_backup_service_factory()
    return factory.create_service(service_id, config)


def get_backup_service(service_id: str) -> Any:
    """Convenience function to get a backup service."""
    factory = get_backup_service_factory()
    return factory.get_service(service_id)


def get_storage_service(storage_type: str = 'local') -> BaseBackupService:
    """Convenience function to get a storage service."""
    factory = get_backup_service_factory()
    return factory.get_storage_service(storage_type)


def get_validator_service() -> BackupValidator:
    """Convenience function to get the validator service."""
    factory = get_backup_service_factory()
    return factory.get_utility_service('validator')


def get_encryption_service() -> BackupEncryptionService:
    """Convenience function to get the encryption service."""
    factory = get_backup_service_factory()
    return factory.get_utility_service('encryption')


def get_compression_service() -> BackupCompressionService:
    """Convenience function to get the compression service."""
    factory = get_backup_service_factory()
    return factory.get_utility_service('compression')


def get_notification_service() -> BackupNotificationService:
    """Convenience function to get the notification service."""
    factory = get_backup_service_factory()
    return factory.get_utility_service('notification')
