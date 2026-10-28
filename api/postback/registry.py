"""
registry.py – Registry system for postback module.

Provides comprehensive registry functionality including:
- Component registration and discovery
- Service registry
- Plugin registry
- Configuration registry
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from django.utils import timezone
from django.core.cache import cache

from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Registry type enumeration."""
    SERVICE = "service"
    PLUGIN = "plugin"
    PROCESSOR = "processor"
    VALIDATOR = "validator"
    HOOK = "hook"
    MIDDLEWARE = "middleware"
    TASK = "task"


@dataclass
class RegistryEntry:
    """Registry entry containing component information."""
    name: str
    component_type: RegistryType
    component_class: type
    instance: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=timezone.now)
    enabled: bool = True
    priority: int = 50
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert registry entry to dictionary."""
        return {
            'name': self.name,
            'component_type': self.component_type.value,
            'component_class': self.component_class.__name__ if self.component_class else None,
            'instance': str(self.instance) if self.instance else None,
            'metadata': self.metadata,
            'registered_at': self.registered_at.isoformat(),
            'enabled': self.enabled,
            'priority': self.priority,
            'dependencies': self.dependencies,
        }


class BaseRegistry:
    """
    Base registry class for component management.
    
    Provides common registry functionality including registration,
    discovery, dependency resolution, and lifecycle management.
    """
    
    def __init__(self, registry_type: RegistryType):
        self.registry_type = registry_type
        self.entries: Dict[str, RegistryEntry] = {}
        self.registration_history = []
        self.enabled = True
    
    def register(self, name: str, component_class: type, **kwargs) -> RegistryEntry:
        """
        Register a component in the registry.
        
        Args:
            name: Component name
            component_class: Component class
            **kwargs: Additional registration options
            
        Returns:
            Registry entry
        """
        if name in self.entries:
            logger.warning(f"Component {name} already registered in {self.registry_type.value} registry")
            return self.entries[name]
        
        # Create registry entry
        entry = RegistryEntry(
            name=name,
            component_type=self.registry_type,
            component_class=component_class,
            metadata=kwargs.get('metadata', {}),
            enabled=kwargs.get('enabled', True),
            priority=kwargs.get('priority', 50),
            dependencies=kwargs.get('dependencies', []),
        )
        
        # Instantiate component if requested
        if kwargs.get('instantiate', False):
            try:
                entry.instance = component_class(**kwargs.get('init_kwargs', {}))
            except Exception as e:
                logger.error(f"Error instantiating component {name}: {str(e)}")
                raise PostbackException(f"Failed to instantiate component {name}: {str(e)}")
        
        # Add to registry
        self.entries[name] = entry
        
        # Record registration
        self._record_registration(entry)
        
        logger.info(f"Registered {self.registry_type.value} component: {name}")
        
        return entry
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a component from the registry.
        
        Args:
            name: Component name
            
        Returns:
            True if component was unregistered
        """
        if name not in self.entries:
            logger.warning(f"Component {name} not found in {self.registry_type.value} registry")
            return False
        
        entry = self.entries[name]
        
        # Cleanup component instance
        if entry.instance and hasattr(entry.instance, 'cleanup'):
            try:
                entry.instance.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up component {name}: {str(e)}")
        
        # Remove from registry
        del self.entries[name]
        
        logger.info(f"Unregistered {self.registry_type.value} component: {name}")
        
        return True
    
    def get(self, name: str) -> Optional[RegistryEntry]:
        """
        Get a registry entry by name.
        
        Args:
            name: Component name
            
        Returns:
            Registry entry or None
        """
        return self.entries.get(name)
    
    def get_instance(self, name: str) -> Optional[Any]:
        """
        Get component instance by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None
        """
        entry = self.get(name)
        return entry.instance if entry else None
    
    def list_all(self) -> List[RegistryEntry]:
        """List all registry entries."""
        return list(self.entries.values())
    
    def list_enabled(self) -> List[RegistryEntry]:
        """List enabled registry entries."""
        return [entry for entry in self.entries.values() if entry.enabled]
    
    def list_by_type(self, component_type: RegistryType) -> List[RegistryEntry]:
        """List entries by component type."""
        return [entry for entry in self.entries.values() if entry.component_type == component_type]
    
    def enable(self, name: str) -> bool:
        """
        Enable a component.
        
        Args:
            name: Component name
            
        Returns:
            True if component was enabled
        """
        entry = self.get(name)
        if entry:
            entry.enabled = True
            logger.info(f"Enabled {self.registry_type.value} component: {name}")
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """
        Disable a component.
        
        Args:
            name: Component name
            
        Returns:
            True if component was disabled
        """
        entry = self.get(name)
        if entry:
            entry.enabled = False
            logger.info(f"Disabled {self.registry_type.value} component: {name}")
            return True
        return False
    
    def resolve_dependencies(self, name: str) -> List[str]:
        """
        Resolve dependencies for a component.
        
        Args:
            name: Component name
            
        Returns:
            Ordered list of dependencies
        """
        entry = self.get(name)
        if not entry:
            return []
        
        resolved = []
        visited = set()
        
        def resolve_dep(dep_name: str):
            if dep_name in visited:
                return
            if dep_name not in self.entries:
                raise PostbackException(f"Dependency {dep_name} not found for component {name}")
            
            dep_entry = self.entries[dep_name]
            visited.add(dep_name)
            
            # Resolve dependencies of dependency
            for dep_dep in dep_entry.dependencies:
                resolve_dep(dep_dep)
            
            if dep_name not in resolved:
                resolved.append(dep_name)
        
        for dep in entry.dependencies:
            resolve_dep(dep)
        
        return resolved
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_entries = len(self.entries)
        enabled_entries = len([e for e in self.entries.values() if e.enabled])
        
        type_counts = {}
        for entry in self.entries.values():
            type_name = entry.component_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            'registry_type': self.registry_type.value,
            'total_entries': total_entries,
            'enabled_entries': enabled_entries,
            'disabled_entries': total_entries - enabled_entries,
            'type_distribution': type_counts,
            'registration_history_count': len(self.registration_history),
            'enabled': self.enabled,
        }
    
    def _record_registration(self, entry: RegistryEntry):
        """Record registration in history."""
        registration_record = {
            'action': 'register',
            'entry': entry.to_dict(),
            'timestamp': timezone.now().isoformat(),
        }
        
        self.registration_history.append(registration_record)
        
        # Keep only last 100 registrations
        if len(self.registration_history) > 100:
            self.registration_history = self.registration_history[-100]
        
        # Cache registration record
        cache_key = f"registry_{self.registry_type.value}_{entry.name}"
        cache.set(cache_key, registration_record, timeout=3600)  # 1 hour


class ServiceRegistry(BaseRegistry):
    """
    Registry for service components.
    
    Provides specialized functionality for service registration
    and management.
    """
    
    def __init__(self):
        super().__init__(RegistryType.SERVICE)
    
    def register_service(self, name: str, service_class: type, **kwargs) -> RegistryEntry:
        """
        Register a service component.
        
        Args:
            name: Service name
            service_class: Service class
            **kwargs: Additional registration options
            
        Returns:
            Registry entry
        """
        return self.register(name, service_class, instantiate=True, **kwargs)
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get service instance by name."""
        return self.get_instance(name)
    
    def call_service(self, name: str, method: str, *args, **kwargs) -> Any:
        """
        Call a method on a service.
        
        Args:
            name: Service name
            method: Method name
            *args: Method arguments
            **kwargs: Method keyword arguments
            
        Returns:
            Method result
        """
        service = self.get_service(name)
        if not service:
            raise PostbackException(f"Service {name} not found")
        
        if not hasattr(service, method):
            raise PostbackException(f"Service {name} does not have method {method}")
        
        return getattr(service, method)(*args, **kwargs)


class PluginRegistry(BaseRegistry):
    """
    Registry for plugin components.
    
    Provides specialized functionality for plugin registration
    and management.
    """
    
    def __init__(self):
        super().__init__(RegistryType.PLUGIN)
    
    def register_plugin(self, name: str, plugin_class: type, **kwargs) -> RegistryEntry:
        """
        Register a plugin component.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class
            **kwargs: Additional registration options
            
        Returns:
            Registry entry
        """
        return self.register(name, plugin_class, **kwargs)
    
    def activate_plugin(self, name: str) -> bool:
        """
        Activate a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin was activated
        """
        plugin = self.get_instance(name)
        if plugin and hasattr(plugin, 'activate'):
            try:
                plugin.activate()
                self.enable(name)
                return True
            except Exception as e:
                logger.error(f"Error activating plugin {name}: {str(e)}")
                return False
        return False
    
    def deactivate_plugin(self, name: str) -> bool:
        """
        Deactivate a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin was deactivated
        """
        plugin = self.get_instance(name)
        if plugin and hasattr(plugin, 'deactivate'):
            try:
                plugin.deactivate()
                self.disable(name)
                return True
            except Exception as e:
                logger.error(f"Error deactivating plugin {name}: {str(e)}")
                return False
        return False


class ProcessorRegistry(BaseRegistry):
    """
    Registry for processor components.
    
    Provides specialized functionality for processor registration
    and management.
    """
    
    def __init__(self):
        super().__init__(RegistryType.PROCESSOR)
    
    def register_processor(self, name: str, processor_class: type, **kwargs) -> RegistryEntry:
        """
        Register a processor component.
        
        Args:
            name: Processor name
            processor_class: Processor class
            **kwargs: Additional registration options
            
        Returns:
            Registry entry
        """
        return self.register(name, processor_class, **kwargs)
    
    def execute_processor(self, name: str, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        Execute a processor.
        
        Args:
            name: Processor name
            data: Data to process
            context: Processing context
            
        Returns:
            Processing result
        """
        processor = self.get_instance(name)
        if not processor:
            raise PostbackException(f"Processor {name} not found")
        
        if not hasattr(processor, 'process'):
            raise PostbackException(f"Processor {name} does not have process method")
        
        return processor.process(data, context or {})


# Global registry instances
service_registry = ServiceRegistry()
plugin_registry = PluginRegistry()
processor_registry = ProcessorRegistry()

# Additional registries
validator_registry = BaseRegistry(RegistryType.VALIDATOR)
hook_registry = BaseRegistry(RegistryType.HOOK)
middleware_registry = BaseRegistry(RegistryType.MIDDLEWARE)
task_registry = BaseRegistry(RegistryType.TASK)

# Registry collection
REGISTRIES = {
    RegistryType.SERVICE: service_registry,
    RegistryType.PLUGIN: plugin_registry,
    RegistryType.PROCESSOR: processor_registry,
    RegistryType.VALIDATOR: validator_registry,
    RegistryType.HOOK: hook_registry,
    RegistryType.MIDDLEWARE: middleware_registry,
    RegistryType.TASK: task_registry,
}


# Convenience functions
def get_registry(registry_type: Union[RegistryType, str]) -> BaseRegistry:
    """
    Get registry by type.
    
    Args:
        registry_type: Registry type
        
    Returns:
        Registry instance
    """
    if isinstance(registry_type, str):
        registry_type = RegistryType(registry_type)
    
    return REGISTRIES.get(registry_type)


def register_component(registry_type: Union[RegistryType, str], name: str, component_class: type, **kwargs) -> RegistryEntry:
    """
    Register a component in the appropriate registry.
    
    Args:
        registry_type: Registry type
        name: Component name
        component_class: Component class
        **kwargs: Additional registration options
        
    Returns:
        Registry entry
    """
    registry = get_registry(registry_type)
    return registry.register(name, component_class, **kwargs)


def get_component(registry_type: Union[RegistryType, str], name: str) -> Optional[Any]:
    """
    Get component instance by type and name.
    
    Args:
        registry_type: Registry type
        name: Component name
        
    Returns:
        Component instance or None
    """
    registry = get_registry(registry_type)
    return registry.get_instance(name)


def get_all_registries_statistics() -> Dict[str, Any]:
    """Get statistics for all registries."""
    return {
        registry_type.value: registry.get_statistics()
        for registry_type, registry in REGISTRIES.items()
    }


# Registry management functions
def enable_all_registries():
    """Enable all registries."""
    for registry in REGISTRIES.values():
        registry.enabled = True


def disable_all_registries():
    """Disable all registries."""
    for registry in REGISTRIES.values():
        registry.enabled = False


def clear_all_registries():
    """Clear all registries."""
    for registry in REGISTRIES.values():
        registry.entries.clear()
        registry.registration_history.clear()


# Service-specific convenience functions
def register_service(name: str, service_class: type, **kwargs) -> RegistryEntry:
    """Register a service."""
    return service_registry.register_service(name, service_class, **kwargs)


def get_service(name: str) -> Optional[Any]:
    """Get service instance."""
    return service_registry.get_service(name)


def call_service(name: str, method: str, *args, **kwargs) -> Any:
    """Call service method."""
    return service_registry.call_service(name, method, *args, **kwargs)


# Plugin-specific convenience functions
def register_plugin(name: str, plugin_class: type, **kwargs) -> RegistryEntry:
    """Register a plugin."""
    return plugin_registry.register_plugin(name, plugin_class, **kwargs)


def activate_plugin(name: str) -> bool:
    """Activate a plugin."""
    return plugin_registry.activate_plugin(name)


def deactivate_plugin(name: str) -> bool:
    """Deactivate a plugin."""
    return plugin_registry.deactivate_plugin(name)


# Processor-specific convenience functions
def register_processor(name: str, processor_class: type, **kwargs) -> RegistryEntry:
    """Register a processor."""
    return processor_registry.register_processor(name, processor_class, **kwargs)


def execute_processor(name: str, data: Any, context: Dict[str, Any] = None) -> Any:
    """Execute a processor."""
    return processor_registry.execute_processor(name, data, context)


# Registry initialization
def initialize_registries():
    """Initialize all registries."""
    try:
        logger.info("Registry system initialized")
        
        # Initialize any built-in components here
        # (Components are registered on-demand)
        
    except Exception as e:
        logger.error(f"Error initializing registries: {str(e)}")


# Registry discovery and auto-loading
def discover_and_register_components():
    """Discover and auto-register components from configured modules."""
    from django.conf import settings
    
    component_modules = getattr(settings, 'POSTBACK_COMPONENT_MODULES', [])
    
    for module_path in component_modules:
        try:
            import importlib
            module = importlib.import_module(module_path)
            
            # Look for component registration functions
            if hasattr(module, 'register_components'):
                module.register_components()
                logger.info(f"Auto-registered components from {module_path}")
            
        except ImportError as e:
            logger.error(f"Failed to import component module {module_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading components from {module_path}: {str(e)}")


# Registry health check
def check_registry_health() -> Dict[str, Any]:
    """Check health of all registries."""
    health_status = {
        'overall': 'healthy',
        'registries': {},
        'issues': [],
    }
    
    for registry_type, registry in REGISTRIES.items():
        try:
            stats = registry.get_statistics()
            
            # Check for issues
            issues = []
            if not registry.enabled:
                issues.append('Registry disabled')
            
            if stats['total_entries'] == 0:
                issues.append('No components registered')
            
            if stats['enabled_entries'] == 0:
                issues.append('No enabled components')
            
            registry_health = {
                'status': 'healthy' if not issues else 'warning',
                'statistics': stats,
                'issues': issues,
            }
            
            health_status['registries'][registry_type.value] = registry_health
            
            if issues:
                health_status['issues'].extend([f"{registry_type.value}: {issue}" for issue in issues])
            
        except Exception as e:
            health_status['registries'][registry_type.value] = {
                'status': 'error',
                'error': str(e),
            }
            health_status['issues'].append(f"{registry_type.value}: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
