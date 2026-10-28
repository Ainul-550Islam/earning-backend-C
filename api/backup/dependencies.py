"""
Backup Module Dependencies
Dependency injection and service container for backup operations
"""

from typing import Dict, Any, Optional, Type, Callable, Union
from abc import ABC, abstractmethod
import importlib
import inspect
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)


class DependencyContainer:
    """
    Dependency injection container for backup services
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._instances: Dict[str, Any] = {}
    
    def register(self, name: str, service: Any, singleton: bool = False):
        """
        Register a service
        
        Args:
            name: Service name
            service: Service instance or class
            singleton: Whether to treat as singleton
        """
        self._services[name] = service
        if singleton:
            self._singletons[name] = None
    
    def register_factory(self, name: str, factory: Callable):
        """
        Register a factory function
        
        Args:
            name: Service name
            factory: Factory function
        """
        self._factories[name] = factory
    
    def get(self, name: str) -> Any:
        """
        Get a service instance
        
        Args:
            name: Service name
            
        Returns:
            Service instance
        """
        # Check if it's a singleton and already instantiated
        if name in self._singletons and self._singletons[name] is not None:
            return self._singletons[name]
        
        # Check factories first
        if name in self._factories:
            instance = self._factories[name]()
            if name in self._singletons:
                self._singletons[name] = instance
            return instance
        
        # Check registered services
        if name in self._services:
            service = self._services[name]
            
            # If it's a class, instantiate it
            if inspect.isclass(service):
                instance = service()
            else:
                instance = service
            
            # Store singleton if needed
            if name in self._singletons:
                self._singletons[name] = instance
            
            return instance
        
        raise ValueError(f"Service '{name}' not found in container")
    
    def has(self, name: str) -> bool:
        """
        Check if service is registered
        
        Args:
            name: Service name
            
        Returns:
            True if service exists
        """
        return name in self._services or name in self._factories
    
    def clear(self):
        """
        Clear all registered services
        """
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._instances.clear()


class BackupServiceProvider(ABC):
    """
    Abstract base class for backup service providers
    """
    
    @abstractmethod
    def register_services(self, container: DependencyContainer):
        """
        Register services with the container
        
        Args:
            container: Dependency container
        """
        pass


class CoreBackupServiceProvider(BackupServiceProvider):
    """
    Core backup service provider
    """
    
    def register_services(self, container: DependencyContainer):
        """
        Register core backup services
        """
        from .services import BackupService
        from .services.DatabaseBackup import DatabaseBackupService
        from .services.factory import BackupServiceFactory
        from .services.BaseBackup import BaseBackupService
        from .services.S3Backup import S3BackupService
        from .services.LocalBackup import LocalBackupService
        
        # Register core services
        container.register('backup_service', BackupService, singleton=True)
        container.register('database_backup_service', DatabaseBackupService, singleton=True)
        container.register('backup_service_factory', BackupServiceFactory, singleton=True)
        container.register('base_backup_service', BaseBackupService)
        
        # Register storage services
        container.register('s3_backup_service', S3BackupService)
        container.register('local_backup_service', LocalBackupService)
        
        # Register validators
        from .services.BackupValidator import BackupValidator
        container.register('backup_validator', BackupValidator, singleton=True)
        
        # Register managers
        from .managers import BackupManager, BackupStorageManager
        container.register('backup_manager', BackupManager, singleton=True)
        container.register('backup_storage_manager', BackupStorageManager, singleton=True)


class StorageServiceProvider(BackupServiceProvider):
    """
    Storage service provider
    """
    
    def register_services(self, container: DependencyContainer):
        """
        Register storage services
        """
        # Register storage adapters
        try:
            from .services.storage_adapters import (
                S3StorageAdapter,
                AzureStorageAdapter,
                GCSStorageAdapter,
                FTPStorageAdapter
            )
            
            container.register('s3_storage_adapter', S3StorageAdapter)
            container.register('azure_storage_adapter', AzureStorageAdapter)
            container.register('gcs_storage_adapter', GCSStorageAdapter)
            container.register('ftp_storage_adapter', FTPStorageAdapter)
            
        except ImportError as e:
            logger.warning(f"Could not register storage adapters: {e}")
        
        # Register storage factory
        from .services.storage_factory import StorageAdapterFactory
        container.register('storage_adapter_factory', StorageAdapterFactory, singleton=True)


class NotificationServiceProvider(BackupServiceProvider):
    """
    Notification service provider
    """
    
    def register_services(self, container: DependencyContainer):
        """
        Register notification services
        """
        try:
            from .services.notification_services import (
                EmailNotificationService,
                SlackNotificationService,
                WebhookNotificationService
            )
            
            container.register('email_notification_service', EmailNotificationService, singleton=True)
            container.register('slack_notification_service', SlackNotificationService, singleton=True)
            container.register('webhook_notification_service', WebhookNotificationService, singleton=True)
            
            # Register notification manager
            from .services.notification_manager import NotificationManager
            container.register('notification_manager', NotificationManager, singleton=True)
            
        except ImportError as e:
            logger.warning(f"Could not register notification services: {e}")


class AnalyticsServiceProvider(BackupServiceProvider):
    """
    Analytics service provider
    """
    
    def register_services(self, container: DependencyContainer):
        """
        Register analytics services
        """
        try:
            from .services.analytics_services import (
                BackupAnalyticsService,
                PerformanceAnalyticsService,
                StorageAnalyticsService
            )
            
            container.register('backup_analytics_service', BackupAnalyticsService, singleton=True)
            container.register('performance_analytics_service', PerformanceAnalyticsService, singleton=True)
            container.register('storage_analytics_service', StorageAnalyticsService, singleton=True)
            
        except ImportError as e:
            logger.warning(f"Could not register analytics services: {e}")


class SecurityServiceProvider(BackupServiceProvider):
    """
    Security service provider
    """
    
    def register_services(self, container: DependencyContainer):
        """
        Register security services
        """
        try:
            from .services.security_services import (
                EncryptionService,
                KeyManagementService,
                AccessControlService
            )
            
            container.register('encryption_service', EncryptionService, singleton=True)
            container.register('key_management_service', KeyManagementService, singleton=True)
            container.register('access_control_service', AccessControlService, singleton=True)
            
        except ImportError as e:
            logger.warning(f"Could not register security services: {e}")


class BackupDependencyManager:
    """
    Main dependency manager for backup module
    """
    
    def __init__(self):
        self._container = DependencyContainer()
        self._providers: Dict[str, BackupServiceProvider] = {}
        self._initialized = False
    
    def register_provider(self, name: str, provider: BackupServiceProvider):
        """
        Register a service provider
        
        Args:
            name: Provider name
            provider: Service provider instance
        """
        self._providers[name] = provider
    
    def initialize(self):
        """
        Initialize all registered providers
        """
        if self._initialized:
            return
        
        # Register default providers
        self._register_default_providers()
        
        # Initialize all providers
        for name, provider in self._providers.items():
            try:
                provider.register_services(self._container)
                logger.info(f"Initialized provider: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {name}: {e}")
        
        self._initialized = True
        logger.info("Backup dependency manager initialized")
    
    def get_service(self, name: str) -> Any:
        """
        Get a service by name
        
        Args:
            name: Service name
            
        Returns:
            Service instance
        """
        if not self._initialized:
            self.initialize()
        
        return self._container.get(name)
    
    def has_service(self, name: str) -> bool:
        """
        Check if service exists
        
        Args:
            name: Service name
            
        Returns:
            True if service exists
        """
        if not self._initialized:
            self.initialize()
        
        return self._container.has(name)
    
    def _register_default_providers(self):
        """
        Register default service providers
        """
        # Core provider is always registered
        self.register_provider('core', CoreBackupServiceProvider())
        
        # Register other providers based on settings
        if getattr(settings, 'BACKUP_ENABLE_STORAGE_SERVICES', True):
            self.register_provider('storage', StorageServiceProvider())
        
        if getattr(settings, 'BACKUP_ENABLE_NOTIFICATIONS', True):
            self.register_provider('notification', NotificationServiceProvider())
        
        if getattr(settings, 'BACKUP_ENABLE_ANALYTICS', False):
            self.register_provider('analytics', AnalyticsServiceProvider())
        
        if getattr(settings, 'BACKUP_ENABLE_SECURITY_SERVICES', True):
            self.register_provider('security', SecurityServiceProvider())
        
        # Register custom providers from settings
        custom_providers = getattr(settings, 'BACKUP_CUSTOM_PROVIDERS', [])
        for provider_config in custom_providers:
            try:
                provider_class = self._load_provider_class(provider_config['class'])
                provider_instance = provider_class()
                self.register_provider(provider_config['name'], provider_instance)
            except Exception as e:
                logger.error(f"Failed to register custom provider {provider_config.get('name', 'unknown')}: {e}")
    
    def _load_provider_class(self, class_path: str) -> Type[BackupServiceProvider]:
        """
        Load provider class from string path
        
        Args:
            class_path: Class path (e.g., 'myapp.backup.CustomProvider')
            
        Returns:
            Provider class
        """
        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    
    def get_container(self) -> DependencyContainer:
        """
        Get the dependency container
        
        Returns:
            Dependency container
        """
        if not self._initialized:
            self.initialize()
        
        return self._container


# Global dependency manager instance
_dependency_manager = None


def get_dependency_manager() -> BackupDependencyManager:
    """
    Get the global dependency manager instance
    
    Returns:
        Backup dependency manager
    """
    global _dependency_manager
    if _dependency_manager is None:
        _dependency_manager = BackupDependencyManager()
    return _dependency_manager


def get_service(service_name: str) -> Any:
    """
    Get a service by name (convenience function)
    
    Args:
        service_name: Service name
        
    Returns:
        Service instance
    """
    return get_dependency_manager().get_service(service_name)


def inject_service(service_name: str):
    """
    Decorator for injecting services into functions/methods
    
    Args:
        service_name: Service name to inject
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Inject service into kwargs if not already present
            if service_name not in kwargs:
                kwargs[service_name] = get_service(service_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ServiceRegistry:
    """
    Registry for service metadata and configurations
    """
    
    def __init__(self):
        self._services: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, **metadata):
        """
        Register service metadata
        
        Args:
            name: Service name
            **metadata: Service metadata
        """
        self._services[name] = metadata
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get service metadata
        
        Args:
            name: Service name
            
        Returns:
            Service metadata
        """
        return self._services.get(name)
    
    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered services
        
        Returns:
            Dictionary of service metadata
        """
        return self._services.copy()
    
    def get_services_by_tag(self, tag: str) -> Dict[str, Dict[str, Any]]:
        """
        Get services by tag
        
        Args:
            tag: Tag to filter by
            
        Returns:
            Dictionary of services with the tag
        """
        return {
            name: metadata
            for name, metadata in self._services.items()
            if tag in metadata.get('tags', [])
        }


# Global service registry
_service_registry = ServiceRegistry()


def get_service_registry() -> ServiceRegistry:
    """
    Get the global service registry
    
    Returns:
        Service registry
    """
    return _service_registry


class ServiceDependency:
    """
    Service dependency descriptor
    """
    
    def __init__(self, service_name: str, optional: bool = False, default: Any = None):
        self.service_name = service_name
        self.optional = optional
        self.default = default
    
    def resolve(self) -> Any:
        """
        Resolve the dependency
        
        Returns:
            Service instance or default value
        """
        try:
            return get_service(self.service_name)
        except ValueError:
            if self.optional:
                return self.default
            raise


class ServiceDependencies:
    """
    Collection of service dependencies
    """
    
    def __init__(self):
        self._dependencies: Dict[str, ServiceDependency] = {}
    
    def add(self, name: str, service_name: str, optional: bool = False, default: Any = None):
        """
        Add a dependency
        
        Args:
            name: Dependency name
            service_name: Service name
            optional: Whether dependency is optional
            default: Default value if optional
        """
        self._dependencies[name] = ServiceDependency(service_name, optional, default)
    
    def resolve_all(self) -> Dict[str, Any]:
        """
        Resolve all dependencies
        
        Returns:
            Dictionary of resolved dependencies
        """
        return {
            name: dependency.resolve()
            for name, dependency in self._dependencies.items()
        }
    
    def inject_into(self, obj: Any):
        """
        Inject dependencies into object
        
        Args:
            obj: Object to inject into
        """
        for name, dependency in self._dependencies.items():
            try:
                setattr(obj, name, dependency.resolve())
            except ValueError as e:
                if not dependency.optional:
                    raise AttributeError(f"Failed to inject dependency '{name}': {e}")


def service_dependencies(**deps):
    """
    Decorator for injecting multiple dependencies
    
    Args:
        **deps: Dependency specifications
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            dependencies = ServiceDependencies()
            
            for name, config in deps.items():
                if isinstance(config, str):
                    dependencies.add(name, config)
                elif isinstance(config, dict):
                    dependencies.add(
                        name,
                        config['service'],
                        optional=config.get('optional', False),
                        default=config.get('default')
                    )
            
            # Resolve dependencies and inject into kwargs
            resolved = dependencies.resolve_all()
            kwargs.update(resolved)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Initialize service registry with default services
def initialize_service_registry():
    """
    Initialize the service registry with default services
    """
    registry = get_service_registry()
    
    # Register core services
    registry.register('backup_service', tags=['core'], singleton=True)
    registry.register('database_backup_service', tags=['core', 'database'], singleton=True)
    registry.register('backup_service_factory', tags=['core', 'factory'], singleton=True)
    registry.register('backup_validator', tags=['core', 'validation'], singleton=True)
    
    # Register storage services
    registry.register('s3_backup_service', tags=['storage', 'cloud'])
    registry.register('local_backup_service', tags=['storage', 'local'])
    registry.register('azure_storage_adapter', tags=['storage', 'cloud'])
    registry.register('gcs_storage_adapter', tags=['storage', 'cloud'])
    
    # Register notification services
    registry.register('email_notification_service', tags=['notification'], singleton=True)
    registry.register('slack_notification_service', tags=['notification'], singleton=True)
    registry.register('webhook_notification_service', tags=['notification'], singleton=True)
    
    # Register analytics services
    registry.register('backup_analytics_service', tags=['analytics'], singleton=True)
    registry.register('performance_analytics_service', tags=['analytics'], singleton=True)
    
    # Register security services
    registry.register('encryption_service', tags=['security'], singleton=True)
    registry.register('key_management_service', tags=['security'], singleton=True)
    registry.register('access_control_service', tags=['security'], singleton=True)


# Initialize on module import
initialize_service_registry()


# Export main classes and functions
__all__ = [
    'DependencyContainer',
    'BackupServiceProvider',
    'BackupDependencyManager',
    'get_dependency_manager',
    'get_service',
    'inject_service',
    'ServiceRegistry',
    'get_service_registry',
    'ServiceDependency',
    'ServiceDependencies',
    'service_dependencies',
    # Service providers
    'CoreBackupServiceProvider',
    'StorageServiceProvider',
    'NotificationServiceProvider',
    'AnalyticsServiceProvider',
    'SecurityServiceProvider',
]
