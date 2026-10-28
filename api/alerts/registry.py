"""
Registry system for alerts app - manages registration and discovery of components
"""
from typing import Dict, List, Any, Optional, Callable, Type
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class AlertRegistry:
    """Central registry for alert system components"""
    
    def __init__(self):
        self._processors: Dict[str, Type] = {}
        self._channels: Dict[str, Type] = {}
        self._filters: Dict[str, Type] = {}
        self._analytics: Dict[str, Type] = {}
        self._reporters: Dict[str, Type] = {}
        self._validators: Dict[str, Type] = {}
        self._transformers: Dict[str, Type] = {}
        self._middleware: Dict[str, Type] = {}
        self._tasks: Dict[str, Callable] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._permissions: Dict[str, Type] = {}
        self._serializers: Dict[str, Type] = {}
        self._views: Dict[str, Type] = {}
    
    # Processor registration
    def register_processor(self, name: str, processor_class: Type):
        """Register an alert processor"""
        self._processors[name] = processor_class
        logger.info(f"Registered processor: {name}")
    
    def get_processor(self, name: str) -> Optional[Type]:
        """Get processor by name"""
        return self._processors.get(name)
    
    def get_all_processors(self) -> Dict[str, Type]:
        """Get all registered processors"""
        return self._processors.copy()
    
    # Channel registration
    def register_channel(self, name: str, channel_class: Type):
        """Register a notification channel"""
        self._channels[name] = channel_class
        logger.info(f"Registered channel: {name}")
    
    def get_channel(self, name: str) -> Optional[Type]:
        """Get channel by name"""
        return self._channels.get(name)
    
    def get_all_channels(self) -> Dict[str, Type]:
        """Get all registered channels"""
        return self._channels.copy()
    
    # Filter registration
    def register_filter(self, name: str, filter_class: Type):
        """Register an alert filter"""
        self._filters[name] = filter_class
        logger.info(f"Registered filter: {name}")
    
    def get_filter(self, name: str) -> Optional[Type]:
        """Get filter by name"""
        return self._filters.get(name)
    
    def get_all_filters(self) -> Dict[str, Type]:
        """Get all registered filters"""
        return self._filters.copy()
    
    # Analytics registration
    def register_analytics(self, name: str, analytics_class: Type):
        """Register an analytics processor"""
        self._analytics[name] = analytics_class
        logger.info(f"Registered analytics: {name}")
    
    def get_analytics(self, name: str) -> Optional[Type]:
        """Get analytics by name"""
        return self._analytics.get(name)
    
    def get_all_analytics(self) -> Dict[str, Type]:
        """Get all registered analytics"""
        return self._analytics.copy()
    
    # Reporter registration
    def register_reporter(self, name: str, reporter_class: Type):
        """Register a reporter"""
        self._reporters[name] = reporter_class
        logger.info(f"Registered reporter: {name}")
    
    def get_reporter(self, name: str) -> Optional[Type]:
        """Get reporter by name"""
        return self._reporters.get(name)
    
    def get_all_reporters(self) -> Dict[str, Type]:
        """Get all registered reporters"""
        return self._reporters.copy()
    
    # Validator registration
    def register_validator(self, name: str, validator_class: Type):
        """Register a validator"""
        self._validators[name] = validator_class
        logger.info(f"Registered validator: {name}")
    
    def get_validator(self, name: str) -> Optional[Type]:
        """Get validator by name"""
        return self._validators.get(name)
    
    def get_all_validators(self) -> Dict[str, Type]:
        """Get all registered validators"""
        return self._validators.copy()
    
    # Transformer registration
    def register_transformer(self, name: str, transformer_class: Type):
        """Register a transformer"""
        self._transformers[name] = transformer_class
        logger.info(f"Registered transformer: {name}")
    
    def get_transformer(self, name: str) -> Optional[Type]:
        """Get transformer by name"""
        return self._transformers.get(name)
    
    def get_all_transformers(self) -> Dict[str, Type]:
        """Get all registered transformers"""
        return self._transformers.copy()
    
    # Middleware registration
    def register_middleware(self, name: str, middleware_class: Type):
        """Register middleware"""
        self._middleware[name] = middleware_class
        logger.info(f"Registered middleware: {name}")
    
    def get_middleware(self, name: str) -> Optional[Type]:
        """Get middleware by name"""
        return self._middleware.get(name)
    
    def get_all_middleware(self) -> Dict[str, Type]:
        """Get all registered middleware"""
        return self._middleware.copy()
    
    # Task registration
    def register_task(self, name: str, task_func: Callable):
        """Register a task"""
        self._tasks[name] = task_func
        logger.info(f"Registered task: {name}")
    
    def get_task(self, name: str) -> Optional[Callable]:
        """Get task by name"""
        return self._tasks.get(name)
    
    def get_all_tasks(self) -> Dict[str, Callable]:
        """Get all registered tasks"""
        return self._tasks.copy()
    
    # Hook registration
    def register_hook(self, hook_name: str, hook_func: Callable):
        """Register a hook function"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        self._hooks[hook_name].append(hook_func)
        logger.info(f"Registered hook: {hook_name}")
    
    def get_hooks(self, hook_name: str) -> List[Callable]:
        """Get all hooks for a name"""
        return self._hooks.get(hook_name, [])
    
    def execute_hooks(self, hook_name: str, *args, **kwargs):
        """Execute all hooks for a name"""
        results = []
        for hook_func in self.get_hooks(hook_name):
            try:
                result = hook_func(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Error executing hook {hook_name}: {e}")
        return results
    
    # Permission registration
    def register_permission(self, name: str, permission_class: Type):
        """Register a permission"""
        self._permissions[name] = permission_class
        logger.info(f"Registered permission: {name}")
    
    def get_permission(self, name: str) -> Optional[Type]:
        """Get permission by name"""
        return self._permissions.get(name)
    
    def get_all_permissions(self) -> Dict[str, Type]:
        """Get all registered permissions"""
        return self._permissions.copy()
    
    # Serializer registration
    def register_serializer(self, name: str, serializer_class: Type):
        """Register a serializer"""
        self._serializers[name] = serializer_class
        logger.info(f"Registered serializer: {name}")
    
    def get_serializer(self, name: str) -> Optional[Type]:
        """Get serializer by name"""
        return self._serializers.get(name)
    
    def get_all_serializers(self) -> Dict[str, Type]:
        """Get all registered serializers"""
        return self._serializers.copy()
    
    # View registration
    def register_view(self, name: str, view_class: Type):
        """Register a view"""
        self._views[name] = view_class
        logger.info(f"Registered view: {name}")
    
    def get_view(self, name: str) -> Optional[Type]:
        """Get view by name"""
        return self._views.get(name)
    
    def get_all_views(self) -> Dict[str, Type]:
        """Get all registered views"""
        return self._views.copy()
    
    # Registry statistics
    def get_registry_stats(self) -> Dict[str, int]:
        """Get statistics about registered components"""
        return {
            'processors': len(self._processors),
            'channels': len(self._channels),
            'filters': len(self._filters),
            'analytics': len(self._analytics),
            'reporters': len(self._reporters),
            'validators': len(self._validators),
            'transformers': len(self._transformers),
            'middleware': len(self._middleware),
            'tasks': len(self._tasks),
            'hooks': sum(len(hooks) for hooks in self._hooks.values()),
            'permissions': len(self._permissions),
            'serializers': len(self._serializers),
            'views': len(self._views),
        }
    
    def clear_registry(self):
        """Clear all registered components"""
        self._processors.clear()
        self._channels.clear()
        self._filters.clear()
        self._analytics.clear()
        self._reporters.clear()
        self._validators.clear()
        self._transformers.clear()
        self._middleware.clear()
        self._tasks.clear()
        self._hooks.clear()
        self._permissions.clear()
        self._serializers.clear()
        self._views.clear()
        logger.info("Registry cleared")


class ComponentDiscovery:
    """Discovers and auto-registers components"""
    
    def __init__(self, registry: AlertRegistry):
        self.registry = registry
        self.discovered_modules = []
    
    def discover_components(self):
        """Discover and register components"""
        self._discover_processors()
        self._discover_channels()
        self._discover_filters()
        self._discover_analytics()
        self._discover_reporters()
        self._discover_validators()
        self._discover_transformers()
        self._discover_middleware()
        self._discover_tasks()
        self._discover_permissions()
        self._discover_serializers()
        self._discover_views()
        
        logger.info(f"Component discovery completed. Found {len(self.discovered_modules)} modules")
    
    def _discover_processors(self):
        """Discover alert processors"""
        processor_modules = getattr(settings, 'ALERT_PROCESSOR_MODULES', [])
        for module_path in processor_modules:
            try:
                self._register_module_components(module_path, 'processor')
            except Exception as e:
                logger.error(f"Error discovering processors in {module_path}: {e}")
    
    def _discover_channels(self):
        """Discover notification channels"""
        channel_modules = getattr(settings, 'ALERT_CHANNEL_MODULES', [])
        for module_path in channel_modules:
            try:
                self._register_module_components(module_path, 'channel')
            except Exception as e:
                logger.error(f"Error discovering channels in {module_path}: {e}")
    
    def _discover_filters(self):
        """Discover alert filters"""
        filter_modules = getattr(settings, 'ALERT_FILTER_MODULES', [])
        for module_path in filter_modules:
            try:
                self._register_module_components(module_path, 'filter')
            except Exception as e:
                logger.error(f"Error discovering filters in {module_path}: {e}")
    
    def _discover_analytics(self):
        """Discover analytics processors"""
        analytics_modules = getattr(settings, 'ALERT_ANALYTICS_MODULES', [])
        for module_path in analytics_modules:
            try:
                self._register_module_components(module_path, 'analytics')
            except Exception as e:
                logger.error(f"Error discovering analytics in {module_path}: {e}")
    
    def _discover_reporters(self):
        """Discover reporters"""
        reporter_modules = getattr(settings, 'ALERT_REPORTER_MODULES', [])
        for module_path in reporter_modules:
            try:
                self._register_module_components(module_path, 'reporter')
            except Exception as e:
                logger.error(f"Error discovering reporters in {module_path}: {e}")
    
    def _discover_validators(self):
        """Discover validators"""
        validator_modules = getattr(settings, 'ALERT_VALIDATOR_MODULES', [])
        for module_path in validator_modules:
            try:
                self._register_module_components(module_path, 'validator')
            except Exception as e:
                logger.error(f"Error discovering validators in {module_path}: {e}")
    
    def _discover_transformers(self):
        """Discover transformers"""
        transformer_modules = getattr(settings, 'ALERT_TRANSFORMER_MODULES', [])
        for module_path in transformer_modules:
            try:
                self._register_module_components(module_path, 'transformer')
            except Exception as e:
                logger.error(f"Error discovering transformers in {module_path}: {e}")
    
    def _discover_middleware(self):
        """Discover middleware"""
        middleware_modules = getattr(settings, 'ALERT_MIDDLEWARE_MODULES', [])
        for module_path in middleware_modules:
            try:
                self._register_module_components(module_path, 'middleware')
            except Exception as e:
                logger.error(f"Error discovering middleware in {module_path}: {e}")
    
    def _discover_tasks(self):
        """Discover tasks"""
        task_modules = getattr(settings, 'ALERT_TASK_MODULES', [])
        for module_path in task_modules:
            try:
                self._register_module_components(module_path, 'task')
            except Exception as e:
                logger.error(f"Error discovering tasks in {module_path}: {e}")
    
    def _discover_permissions(self):
        """Discover permissions"""
        permission_modules = getattr(settings, 'ALERT_PERMISSION_MODULES', [])
        for module_path in permission_modules:
            try:
                self._register_module_components(module_path, 'permission')
            except Exception as e:
                logger.error(f"Error discovering permissions in {module_path}: {e}")
    
    def _discover_serializers(self):
        """Discover serializers"""
        serializer_modules = getattr(settings, 'ALERT_SERIALIZER_MODULES', [])
        for module_path in serializer_modules:
            try:
                self._register_module_components(module_path, 'serializer')
            except Exception as e:
                logger.error(f"Error discovering serializers in {module_path}: {e}")
    
    def _discover_views(self):
        """Discover views"""
        view_modules = getattr(settings, 'ALERT_VIEW_MODULES', [])
        for module_path in view_modules:
            try:
                self._register_module_components(module_path, 'view')
            except Exception as e:
                logger.error(f"Error discovering views in {module_path}: {e}")
    
    def _register_module_components(self, module_path: str, component_type: str):
        """Register components from a module"""
        import importlib
        import inspect
        
        try:
            module = importlib.import_module(module_path)
            self.discovered_modules.append(module_path)
            
            # Find all classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Skip imported classes
                if obj.__module__ != module_path:
                    continue
                
                # Register based on component type
                if component_type == 'processor':
                    if hasattr(obj, 'process_alert'):
                        self.registry.register_processor(name, obj)
                
                elif component_type == 'channel':
                    if hasattr(obj, 'send'):
                        self.registry.register_channel(name, obj)
                
                elif component_type == 'filter':
                    if hasattr(obj, 'should_suppress'):
                        self.registry.register_filter(name, obj)
                
                elif component_type == 'analytics':
                    if hasattr(obj, 'analyze_alerts'):
                        self.registry.register_analytics(name, obj)
                
                elif component_type == 'reporter':
                    if hasattr(obj, 'generate_report'):
                        self.registry.register_reporter(name, obj)
                
                elif component_type == 'validator':
                    if hasattr(obj, 'validate'):
                        self.registry.register_validator(name, obj)
                
                elif component_type == 'transformer':
                    if hasattr(obj, 'transform'):
                        self.registry.register_transformer(name, obj)
                
                elif component_type == 'middleware':
                    if hasattr(obj, '__call__'):
                        self.registry.register_middleware(name, obj)
                
                elif component_type == 'task':
                    if hasattr(obj, 'delay') or hasattr(obj, 'apply_async'):
                        self.registry.register_task(name, obj)
                
                elif component_type == 'permission':
                    if hasattr(obj, 'has_permission'):
                        self.registry.register_permission(name, obj)
                
                elif component_type == 'serializer':
                    if hasattr(obj, 'data') or hasattr(obj, 'is_valid'):
                        self.registry.register_serializer(name, obj)
                
                elif component_type == 'view':
                    if hasattr(obj, 'as_view') or hasattr(obj, 'dispatch'):
                        self.registry.register_view(name, obj)
        
        except ImportError as e:
            logger.error(f"Could not import module {module_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing module {module_path}: {e}")


# Global registry instance
alert_registry = AlertRegistry()
component_discovery = ComponentDiscovery(alert_registry)


def get_registry() -> AlertRegistry:
    """Get the global alert registry"""
    return alert_registry


def initialize_registry():
    """Initialize the registry and discover components"""
    component_discovery.discover_components()
    logger.info("Alert registry initialized")


# Decorators for easy registration
def register_processor(name: str):
    """Decorator to register a processor"""
    def decorator(cls):
        alert_registry.register_processor(name, cls)
        return cls
    return decorator


def register_channel(name: str):
    """Decorator to register a channel"""
    def decorator(cls):
        alert_registry.register_channel(name, cls)
        return cls
    return decorator


def register_filter(name: str):
    """Decorator to register a filter"""
    def decorator(cls):
        alert_registry.register_filter(name, cls)
        return cls
    return decorator


def register_analytics(name: str):
    """Decorator to register analytics"""
    def decorator(cls):
        alert_registry.register_analytics(name, cls)
        return cls
    return decorator


def register_reporter(name: str):
    """Decorator to register a reporter"""
    def decorator(cls):
        alert_registry.register_reporter(name, cls)
        return cls
    return decorator


def register_validator(name: str):
    """Decorator to register a validator"""
    def decorator(cls):
        alert_registry.register_validator(name, cls)
        return cls
    return decorator


def register_transformer(name: str):
    """Decorator to register a transformer"""
    def decorator(cls):
        alert_registry.register_transformer(name, cls)
        return cls
    return decorator


def register_middleware(name: str):
    """Decorator to register middleware"""
    def decorator(cls):
        alert_registry.register_middleware(name, cls)
        return cls
    return decorator


def register_task(name: str):
    """Decorator to register a task"""
    def decorator(func):
        alert_registry.register_task(name, func)
        return func
    return decorator


def register_permission(name: str):
    """Decorator to register a permission"""
    def decorator(cls):
        alert_registry.register_permission(name, cls)
        return cls
    return decorator


def register_serializer(name: str):
    """Decorator to register a serializer"""
    def decorator(cls):
        alert_registry.register_serializer(name, cls)
        return cls
    return decorator


def register_view(name: str):
    """Decorator to register a view"""
    def decorator(cls):
        alert_registry.register_view(name, cls)
        return cls
    return decorator


def register_hook(hook_name: str):
    """Decorator to register a hook"""
    def decorator(func):
        alert_registry.register_hook(hook_name, func)
        return func
    return decorator
