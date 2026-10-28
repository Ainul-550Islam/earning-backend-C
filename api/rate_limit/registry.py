# api/rate_limit/registry.py
"""
Registry system for rate limit module.

Provides centralized registration and management of rate limiting components.
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Type
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class RateLimitRegistry:
    """
    Central registry for rate limiting components.
    """
    
    def __init__(self):
        self._algorithms: Dict[str, Type] = {}
        self._strategies: Dict[str, Type] = {}
        self._storage_backends: Dict[str, Type] = {}
        self._middleware: Dict[str, Type] = {}
        self._views: Dict[str, Type] = {}
        self._serializers: Dict[str, Type] = {}
        self._permissions: Dict[str, Type] = {}
        self._hooks: Dict[str, Type] = {}
        self._plugins: Dict[str, Type] = {}
        self._tasks: Dict[str, Type] = {}
        self._validators: Dict[str, Type] = {}
        self._filters: Dict[str, Type] = {}
        self._managers: Dict[str, Type] = {}
        self._services: Dict[str, Type] = {}
        
        self._load_default_registrations()
    
    def _load_default_registrations(self):
        """Load default component registrations."""
        try:
            # Register default algorithms
            from api.rate_limit.logic import RateLimitAlgorithm
            self.register_algorithm('token_bucket', RateLimitAlgorithm)
            self.register_algorithm('sliding_window', RateLimitAlgorithm)
            self.register_algorithm('fixed_window', RateLimitAlgorithm)
            
            # Register default services
            from api.rate_limit.services import RateLimitService
            self.register_service('default', RateLimitService)
            
            logger.info("Default rate limit components registered")
            
        except ImportError as e:
            logger.warning(f"Failed to load default registrations: {str(e)}")
    
    def register_algorithm(self, name: str, algorithm_class: Type):
        """
        Register a rate limiting algorithm.
        
        Args:
            name: Algorithm name
            algorithm_class: Algorithm class
        """
        self._algorithms[name] = algorithm_class
        logger.info(f"Registered algorithm: {name}")
    
    def register_strategy(self, name: str, strategy_class: Type):
        """
        Register a rate limiting strategy.
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
        """
        self._strategies[name] = strategy_class
        logger.info(f"Registered strategy: {name}")
    
    def register_storage_backend(self, name: str, backend_class: Type):
        """
        Register a storage backend.
        
        Args:
            name: Backend name
            backend_class: Backend class
        """
        self._storage_backends[name] = backend_class
        logger.info(f"Registered storage backend: {name}")
    
    def register_middleware(self, name: str, middleware_class: Type):
        """
        Register middleware class.
        
        Args:
            name: Middleware name
            middleware_class: Middleware class
        """
        self._middleware[name] = middleware_class
        logger.info(f"Registered middleware: {name}")
    
    def register_view(self, name: str, view_class: Type):
        """
        Register view class.
        
        Args:
            name: View name
            view_class: View class
        """
        self._views[name] = view_class
        logger.info(f"Registered view: {name}")
    
    def register_serializer(self, name: str, serializer_class: Type):
        """
        Register serializer class.
        
        Args:
            name: Serializer name
            serializer_class: Serializer class
        """
        self._serializers[name] = serializer_class
        logger.info(f"Registered serializer: {name}")
    
    def register_permission(self, name: str, permission_class: Type):
        """
        Register permission class.
        
        Args:
            name: Permission name
            permission_class: Permission class
        """
        self._permissions[name] = permission_class
        logger.info(f"Registered permission: {name}")
    
    def register_hook(self, name: str, hook_class: Type):
        """
        Register hook class.
        
        Args:
            name: Hook name
            hook_class: Hook class
        """
        self._hooks[name] = hook_class
        logger.info(f"Registered hook: {name}")
    
    def register_plugin(self, name: str, plugin_class: Type):
        """
        Register plugin class.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class
        """
        self._plugins[name] = plugin_class
        logger.info(f"Registered plugin: {name}")
    
    def register_task(self, name: str, task_class: Type):
        """
        Register task class.
        
        Args:
            name: Task name
            task_class: Task class
        """
        self._tasks[name] = task_class
        logger.info(f"Registered task: {name}")
    
    def register_validator(self, name: str, validator_class: Type):
        """
        Register validator class.
        
        Args:
            name: Validator name
            validator_class: Validator class
        """
        self._validators[name] = validator_class
        logger.info(f"Registered validator: {name}")
    
    def register_filter(self, name: str, filter_class: Type):
        """
        Register filter class.
        
        Args:
            name: Filter name
            filter_class: Filter class
        """
        self._filters[name] = filter_class
        logger.info(f"Registered filter: {name}")
    
    def register_manager(self, name: str, manager_class: Type):
        """
        Register manager class.
        
        Args:
            name: Manager name
            manager_class: Manager class
        """
        self._managers[name] = manager_class
        logger.info(f"Registered manager: {name}")
    
    def register_service(self, name: str, service_class: Type):
        """
        Register service class.
        
        Args:
            name: Service name
            service_class: Service class
        """
        self._services[name] = service_class
        logger.info(f"Registered service: {name}")
    
    def get_algorithm(self, name: str) -> Optional[Type]:
        """Get registered algorithm class."""
        return self._algorithms.get(name)
    
    def get_strategy(self, name: str) -> Optional[Type]:
        """Get registered strategy class."""
        return self._strategies.get(name)
    
    def get_storage_backend(self, name: str) -> Optional[Type]:
        """Get registered storage backend class."""
        return self._storage_backends.get(name)
    
    def get_middleware(self, name: str) -> Optional[Type]:
        """Get registered middleware class."""
        return self._middleware.get(name)
    
    def get_view(self, name: str) -> Optional[Type]:
        """Get registered view class."""
        return self._views.get(name)
    
    def get_serializer(self, name: str) -> Optional[Type]:
        """Get registered serializer class."""
        return self._serializers.get(name)
    
    def get_permission(self, name: str) -> Optional[Type]:
        """Get registered permission class."""
        return self._permissions.get(name)
    
    def get_hook(self, name: str) -> Optional[Type]:
        """Get registered hook class."""
        return self._hooks.get(name)
    
    def get_plugin(self, name: str) -> Optional[Type]:
        """Get registered plugin class."""
        return self._plugins.get(name)
    
    def get_task(self, name: str) -> Optional[Type]:
        """Get registered task class."""
        return self._tasks.get(name)
    
    def get_validator(self, name: str) -> Optional[Type]:
        """Get registered validator class."""
        return self._validators.get(name)
    
    def get_filter(self, name: str) -> Optional[Type]:
        """Get registered filter class."""
        return self._filters.get(name)
    
    def get_manager(self, name: str) -> Optional[Type]:
        """Get registered manager class."""
        return self._managers.get(name)
    
    def get_service(self, name: str) -> Optional[Type]:
        """Get registered service class."""
        return self._services.get(name)
    
    def list_algorithms(self) -> List[str]:
        """List all registered algorithms."""
        return list(self._algorithms.keys())
    
    def list_strategies(self) -> List[str]:
        """List all registered strategies."""
        return list(self._strategies.keys())
    
    def list_storage_backends(self) -> List[str]:
        """List all registered storage backends."""
        return list(self._storage_backends.keys())
    
    def list_middleware(self) -> List[str]:
        """List all registered middleware."""
        return list(self._middleware.keys())
    
    def list_views(self) -> List[str]:
        """List all registered views."""
        return list(self._views.keys())
    
    def list_serializers(self) -> List[str]:
        """List all registered serializers."""
        return list(self._serializers.keys())
    
    def list_permissions(self) -> List[str]:
        """List all registered permissions."""
        return list(self._permissions.keys())
    
    def list_hooks(self) -> List[str]:
        """List all registered hooks."""
        return list(self._hooks.keys())
    
    def list_plugins(self) -> List[str]:
        """List all registered plugins."""
        return list(self._plugins.keys())
    
    def list_tasks(self) -> List[str]:
        """List all registered tasks."""
        return list(self._tasks.keys())
    
    def list_validators(self) -> List[str]:
        """List all registered validators."""
        return list(self._validators.keys())
    
    def list_filters(self) -> List[str]:
        """List all registered filters."""
        return list(self._filters.keys())
    
    def list_managers(self) -> List[str]:
        """List all registered managers."""
        return list(self._managers.keys())
    
    def list_services(self) -> List[str]:
        """List all registered services."""
        return list(self._services.keys())
    
    def get_registry_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        return {
            'algorithms': len(self._algorithms),
            'strategies': len(self._strategies),
            'storage_backends': len(self._storage_backends),
            'middleware': len(self._middleware),
            'views': len(self._views),
            'serializers': len(self._serializers),
            'permissions': len(self._permissions),
            'hooks': len(self._hooks),
            'plugins': len(self._plugins),
            'tasks': len(self._tasks),
            'validators': len(self._validators),
            'filters': len(self._filters),
            'managers': len(self._managers),
            'services': len(self._services),
        }
    
    def validate_registrations(self) -> Dict[str, List[str]]:
        """
        Validate all registered components.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': [],
            'invalid': [],
            'missing': []
        }
        
        # Check required components
        required_components = {
            'algorithms': ['token_bucket', 'sliding_window', 'fixed_window'],
            'services': ['default'],
        }
        
        for component_type, required_names in required_components.items():
            registry = getattr(self, f'_{component_type}')
            
            for name in required_names:
                if name in registry:
                    results['valid'].append(f"{component_type}.{name}")
                else:
                    results['missing'].append(f"{component_type}.{name}")
        
        return results
    
    def unregister(self, component_type: str, name: str):
        """
        Unregister a component.
        
        Args:
            component_type: Type of component
            name: Component name
        """
        registry = getattr(self, f'_{component_type}', None)
        if registry and name in registry:
            del registry[name]
            logger.info(f"Unregistered {component_type}: {name}")
        else:
            logger.warning(f"Component not found: {component_type}.{name}")


class ComponentFactory:
    """
    Factory for creating registered components.
    """
    
    def __init__(self, registry: RateLimitRegistry):
        self.registry = registry
    
    def create_algorithm(self, name: str, **kwargs) -> Any:
        """Create algorithm instance."""
        algorithm_class = self.registry.get_algorithm(name)
        if not algorithm_class:
            raise ValueError(f"Algorithm '{name}' not registered")
        
        return algorithm_class(**kwargs)
    
    def create_strategy(self, name: str, **kwargs) -> Any:
        """Create strategy instance."""
        strategy_class = self.registry.get_strategy(name)
        if not strategy_class:
            raise ValueError(f"Strategy '{name}' not registered")
        
        return strategy_class(**kwargs)
    
    def create_storage_backend(self, name: str, **kwargs) -> Any:
        """Create storage backend instance."""
        backend_class = self.registry.get_storage_backend(name)
        if not backend_class:
            raise ValueError(f"Storage backend '{name}' not registered")
        
        return backend_class(**kwargs)
    
    def create_middleware(self, name: str, **kwargs) -> Any:
        """Create middleware instance."""
        middleware_class = self.registry.get_middleware(name)
        if not middleware_class:
            raise ValueError(f"Middleware '{name}' not registered")
        
        return middleware_class(**kwargs)
    
    def create_service(self, name: str, **kwargs) -> Any:
        """Create service instance."""
        service_class = self.registry.get_service(name)
        if not service_class:
            raise ValueError(f"Service '{name}' not registered")
        
        return service_class(**kwargs)
    
    def create_plugin(self, name: str, **kwargs) -> Any:
        """Create plugin instance."""
        plugin_class = self.registry.get_plugin(name)
        if not plugin_class:
            raise ValueError(f"Plugin '{name}' not registered")
        
        return plugin_class(**kwargs)


# Global registry instance
rate_limit_registry = RateLimitRegistry()
component_factory = ComponentFactory(rate_limit_registry)


def register_component(component_type: str, name: str, component_class: Type):
    """
    Convenience function to register a component.
    
    Args:
        component_type: Type of component
        name: Component name
        component_class: Component class
    """
    getattr(rate_limit_registry, f'register_{component_type}')(name, component_class)


def get_component(component_type: str, name: str) -> Optional[Type]:
    """
    Convenience function to get a registered component.
    
    Args:
        component_type: Type of component
        name: Component name
        
    Returns:
        Component class or None
    """
    return getattr(rate_limit_registry, f'get_{component_type}')(name)


def create_component(component_type: str, name: str, **kwargs) -> Any:
    """
    Convenience function to create a component instance.
    
    Args:
        component_type: Type of component
        name: Component name
        **kwargs: Component initialization arguments
        
    Returns:
        Component instance
    """
    return getattr(component_factory, f'create_{component_type}')(name, **kwargs)


# Auto-load components from settings
def load_components_from_settings():
    """Load components from Django settings."""
    try:
        component_configs = getattr(settings, 'RATE_LIMIT_COMPONENTS', {})
        
        for component_type, components in component_configs.items():
            for name, config in components.items():
                if isinstance(config, str):
                    # Simple string path
                    module_path, class_name = config.rsplit('.', 1)
                    module = __import__(module_path, fromlist=[class_name])
                    component_class = getattr(module, class_name)
                    
                    register_component(component_type, name, component_class)
                
                elif isinstance(config, dict):
                    # Dictionary with class path and config
                    class_path = config.get('class')
                    if class_path:
                        module_path, class_name = class_path.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        component_class = getattr(module, class_name)
                        
                        register_component(component_type, name, component_class)
        
        logger.info("Components loaded from settings")
        
    except Exception as e:
        logger.error(f"Failed to load components from settings: {str(e)}")


# Auto-load on import
try:
    load_components_from_settings()
except Exception as e:
    logger.error(f"Failed to auto-load components: {str(e)}")


# Export functions and classes
__all__ = [
    'RateLimitRegistry',
    'ComponentFactory',
    'rate_limit_registry',
    'component_factory',
    'register_component',
    'get_component',
    'create_component',
    'load_components_from_settings'
]
