# api/cms/registry.py
"""Registry system for CMS - manages dynamic registration of components."""
import logging
from typing import Dict, Any, List, Type, Optional, Callable
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class CMSRegistry:
    """Central registry for CMS components and configurations."""
    
    def __init__(self):
        self._components: Dict[str, Dict[str, Any]] = {}
        self._services: Dict[str, Any] = {}
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._viewsets: Dict[str, Type] = {}
        self._serializers: Dict[str, Type] = {}
        self._permissions: Dict[str, Type] = {}
        self._middleware: Dict[str, Type] = {}
        self._tasks: Dict[str, Callable] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._filters: Dict[str, Type] = {}
        self._validators: Dict[str, Callable] = {}
        
    # ── Component Registration ──────────────────────────────────
    
    def register_component(self, name: str, component_class: Type, **metadata):
        """Register a component class with metadata."""
        self._components[name] = {
            'class': component_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered component: {name}")
    
    def get_component(self, name: str) -> Optional[Type]:
        """Get registered component class."""
        component = self._components.get(name)
        return component['class'] if component else None
    
    def get_component_metadata(self, name: str) -> Dict[str, Any]:
        """Get component metadata."""
        component = self._components.get(name)
        return component['metadata'] if component else {}
    
    def list_components(self, component_type: Optional[str] = None) -> List[str]:
        """List all registered components, optionally filtered by type."""
        if component_type:
            return [
                name for name, comp in self._components.items()
                if comp['metadata'].get('type') == component_type
            ]
        return list(self._components.keys())
    
    # ── Service Registration ───────────────────────────────────
    
    def register_service(self, name: str, service_instance: Any, **metadata):
        """Register a service instance."""
        self._services[name] = {
            'instance': service_instance,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered service: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get registered service instance."""
        service = self._services.get(name)
        return service['instance'] if service else None
    
    def list_services(self) -> List[str]:
        """List all registered services."""
        return list(self._services.keys())
    
    # ── Plugin Registration ────────────────────────────────────
    
    def register_plugin(self, name: str, plugin_class: Type, **metadata):
        """Register a plugin class."""
        self._plugins[name] = {
            'class': plugin_class,
            'metadata': metadata,
            'enabled': metadata.get('enabled', True),
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered plugin: {name}")
    
    def get_plugin(self, name: str) -> Optional[Type]:
        """Get registered plugin class."""
        plugin = self._plugins.get(name)
        return plugin['class'] if plugin and plugin['enabled'] else None
    
    def enable_plugin(self, name: str):
        """Enable a registered plugin."""
        if name in self._plugins:
            self._plugins[name]['enabled'] = True
            logger.info(f"[Registry] Enabled plugin: {name}")
    
    def disable_plugin(self, name: str):
        """Disable a registered plugin."""
        if name in self._plugins:
            self._plugins[name]['enabled'] = False
            logger.info(f"[Registry] Disabled plugin: {name}")
    
    def list_plugins(self, enabled_only: bool = True) -> List[str]:
        """List registered plugins."""
        if enabled_only:
            return [
                name for name, plugin in self._plugins.items()
                if plugin['enabled']
            ]
        return list(self._plugins.keys())
    
    # ── ViewSet Registration ───────────────────────────────────
    
    def register_viewset(self, name: str, viewset_class: Type, **metadata):
        """Register a ViewSet class."""
        self._viewsets[name] = {
            'class': viewset_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered ViewSet: {name}")
    
    def get_viewset(self, name: str) -> Optional[Type]:
        """Get registered ViewSet class."""
        viewset = self._viewsets.get(name)
        return viewset['class'] if viewset else None
    
    def list_viewsets(self) -> List[str]:
        """List all registered ViewSets."""
        return list(self._viewsets.keys())
    
    # ── Serializer Registration ─────────────────────────────────
    
    def register_serializer(self, name: str, serializer_class: Type, **metadata):
        """Register a serializer class."""
        self._serializers[name] = {
            'class': serializer_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered serializer: {name}")
    
    def get_serializer(self, name: str) -> Optional[Type]:
        """Get registered serializer class."""
        serializer = self._serializers.get(name)
        return serializer['class'] if serializer else None
    
    def list_serializers(self) -> List[str]:
        """List all registered serializers."""
        return list(self._serializers.keys())
    
    # ── Permission Registration ───────────────────────────────────
    
    def register_permission(self, name: str, permission_class: Type, **metadata):
        """Register a permission class."""
        self._permissions[name] = {
            'class': permission_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered permission: {name}")
    
    def get_permission(self, name: str) -> Optional[Type]:
        """Get registered permission class."""
        permission = self._permissions.get(name)
        return permission['class'] if permission else None
    
    def list_permissions(self) -> List[str]:
        """List all registered permissions."""
        return list(self._permissions.keys())
    
    # ── Middleware Registration ──────────────────────────────────
    
    def register_middleware(self, name: str, middleware_class: Type, **metadata):
        """Register a middleware class."""
        self._middleware[name] = {
            'class': middleware_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered middleware: {name}")
    
    def get_middleware(self, name: str) -> Optional[Type]:
        """Get registered middleware class."""
        middleware = self._middleware.get(name)
        return middleware['class'] if middleware else None
    
    def list_middleware(self) -> List[str]:
        """List all registered middleware."""
        return list(self._middleware.keys())
    
    # ── Task Registration ─────────────────────────────────────
    
    def register_task(self, name: str, task_func: Callable, **metadata):
        """Register a task function."""
        self._tasks[name] = {
            'function': task_func,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered task: {name}")
    
    def get_task(self, name: str) -> Optional[Callable]:
        """Get registered task function."""
        task = self._tasks.get(name)
        return task['function'] if task else None
    
    def list_tasks(self) -> List[str]:
        """List all registered tasks."""
        return list(self._tasks.keys())
    
    # ── Hook Registration ───────────────────────────────────────
    
    def register_hook(self, hook_name: str, hook_func: Callable, priority: int = 100):
        """Register a hook function."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        self._hooks[hook_name].append({
            'function': hook_func,
            'priority': priority,
            'registered_at': timezone.now()
        })
        
        # Sort by priority (lower number = higher priority)
        self._hooks[hook_name].sort(key=lambda h: h['priority'])
        logger.info(f"[Registry] Registered hook: {hook_name}")
    
    def get_hooks(self, hook_name: str) -> List[Callable]:
        """Get all registered hooks for a specific hook name."""
        hooks = self._hooks.get(hook_name, [])
        return [h['function'] for h in hooks]
    
    def execute_hooks(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute all registered hooks for a specific hook name."""
        results = []
        hooks = self._hooks.get(hook_name, [])
        
        for hook_info in hooks:
            try:
                result = hook_info['function'](*args, **kwargs)
                results.append(result)
                logger.debug(f"[Registry] Executed hook {hook_name}: {hook_info['function'].__name__}")
            except Exception as e:
                logger.error(f"[Registry] Hook execution error: {e}")
        
        return results
    
    def list_hooks(self) -> List[str]:
        """List all registered hook names."""
        return list(self._hooks.keys())
    
    # ── Filter Registration ────────────────────────────────────
    
    def register_filter(self, name: str, filter_class: Type, **metadata):
        """Register a filter class."""
        self._filters[name] = {
            'class': filter_class,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered filter: {name}")
    
    def get_filter(self, name: str) -> Optional[Type]:
        """Get registered filter class."""
        filter_obj = self._filters.get(name)
        return filter_obj['class'] if filter_obj else None
    
    def list_filters(self) -> List[str]:
        """List all registered filters."""
        return list(self._filters.keys())
    
    # ── Validator Registration ─────────────────────────────────
    
    def register_validator(self, name: str, validator_func: Callable, **metadata):
        """Register a validator function."""
        self._validators[name] = {
            'function': validator_func,
            'metadata': metadata,
            'registered_at': timezone.now()
        }
        logger.info(f"[Registry] Registered validator: {name}")
    
    def get_validator(self, name: str) -> Optional[Callable]:
        """Get registered validator function."""
        validator = self._validators.get(name)
        return validator['function'] if validator else None
    
    def list_validators(self) -> List[str]:
        """List all registered validators."""
        return list(self._validators.keys())
    
    # ── Registry Management ─────────────────────────────────────
    
    def unregister(self, category: str, name: str):
        """Unregister a component from any category."""
        registries = {
            'component': self._components,
            'service': self._services,
            'plugin': self._plugins,
            'viewset': self._viewsets,
            'serializer': self._serializers,
            'permission': self._permissions,
            'middleware': self._middleware,
            'task': self._tasks,
            'hook': self._hooks,
            'filter': self._filters,
            'validator': self._validators
        }
        
        if category in registries and name in registries[category]:
            del registries[category][name]
            logger.info(f"[Registry] Unregistered {category}: {name}")
    
    def clear_registry(self, category: Optional[str] = None):
        """Clear registry, optionally filtered by category."""
        if category:
            registries = {
                'component': self._components,
                'service': self._services,
                'plugin': self._plugins,
                'viewset': self._viewsets,
                'serializer': self._serializers,
                'permission': self._permissions,
                'middleware': self._middleware,
                'task': self._tasks,
                'hook': self._hooks,
                'filter': self._filters,
                'validator': self._validators
            }
            
            if category in registries:
                registries[category].clear()
                logger.info(f"[Registry] Cleared {category} registry")
        else:
            self._components.clear()
            self._services.clear()
            self._plugins.clear()
            self._viewsets.clear()
            self._serializers.clear()
            self._permissions.clear()
            self._middleware.clear()
            self._tasks.clear()
            self._hooks.clear()
            self._filters.clear()
            self._validators.clear()
            logger.info("[Registry] Cleared all registries")
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        return {
            'components': len(self._components),
            'services': len(self._services),
            'plugins': len(self._plugins),
            'enabled_plugins': len([p for p in self._plugins.values() if p['enabled']]),
            'viewsets': len(self._viewsets),
            'serializers': len(self._serializers),
            'permissions': len(self._permissions),
            'middleware': len(self._middleware),
            'tasks': len(self._tasks),
            'hooks': len(self._hooks),
            'filters': len(self._filters),
            'validators': len(self._validators)
        }
    
    def cache_registry_info(self, ttl: int = 300):
        """Cache registry information for performance."""
        stats = self.get_registry_stats()
        cache.set('cms_registry_stats', stats, ttl)
        return stats


# Global registry instance
registry = CMSRegistry()


# ── Registration Decorators ─────────────────────────────────────

def register_component(name: str, **metadata):
    """Decorator for registering components."""
    def decorator(cls):
        registry.register_component(name, cls, **metadata)
        return cls
    return decorator


def register_service(name: str, **metadata):
    """Decorator for registering services."""
    def decorator(instance):
        registry.register_service(name, instance, **metadata)
        return instance
    return decorator


def register_plugin(name: str, **metadata):
    """Decorator for registering plugins."""
    def decorator(cls):
        registry.register_plugin(name, cls, **metadata)
        return cls
    return decorator


def register_viewset(name: str, **metadata):
    """Decorator for registering ViewSets."""
    def decorator(cls):
        registry.register_viewset(name, cls, **metadata)
        return cls
    return decorator


def register_serializer(name: str, **metadata):
    """Decorator for registering serializers."""
    def decorator(cls):
        registry.register_serializer(name, cls, **metadata)
        return cls
    return decorator


def register_permission(name: str, **metadata):
    """Decorator for registering permissions."""
    def decorator(cls):
        registry.register_permission(name, cls, **metadata)
        return cls
    return decorator


def register_middleware(name: str, **metadata):
    """Decorator for registering middleware."""
    def decorator(cls):
        registry.register_middleware(name, cls, **metadata)
        return cls
    return decorator


def register_task(name: str, **metadata):
    """Decorator for registering tasks."""
    def decorator(func):
        registry.register_task(name, func, **metadata)
        return func
    return decorator


def register_hook(hook_name: str, priority: int = 100):
    """Decorator for registering hooks."""
    def decorator(func):
        registry.register_hook(hook_name, func, priority)
        return func
    return decorator


def register_filter(name: str, **metadata):
    """Decorator for registering filters."""
    def decorator(cls):
        registry.register_filter(name, cls, **metadata)
        return cls
    return decorator


def register_validator(name: str, **metadata):
    """Decorator for registering validators."""
    def decorator(func):
        registry.register_validator(name, func, **metadata)
        return func
    return decorator


# ── Built-in Registrations ─────────────────────────────────────

def register_builtin_components():
    """Register built-in CMS components."""
    
    # Register survey-related components
    try:
        from .models_new.profile_surveys import Survey, SurveyCompletion
        registry.register_component('survey', Survey, type='model', category='surveys')
        registry.register_component('survey_completion', SurveyCompletion, type='model', category='surveys')
    except ImportError:
        pass
    
    # Register reward-related components
    try:
        from .models_new.survey_rewards import RewardTransaction, RewardPool
        registry.register_component('reward_transaction', RewardTransaction, type='model', category='rewards')
        registry.register_component('reward_pool', RewardPool, type='model', category='rewards')
    except ImportError:
        pass
    
    # Register task-related components
    try:
        from .models_new.task_management import TaskSchedule, TaskExecution
        registry.register_component('task_schedule', TaskSchedule, type='model', category='tasks')
        registry.register_component('task_execution', TaskExecution, type='model', category='tasks')
    except ImportError:
        pass
    
    # Register user-related components
    try:
        from .models_new.user_profile import UserProfile, UserSegment
        registry.register_component('user_profile', UserProfile, type='model', category='users')
        registry.register_component('user_segment', UserSegment, type='model', category='users')
    except ImportError:
        pass
    
    logger.info("[Registry] Built-in components registered")


# Auto-register built-in components when module is imported
register_builtin_components()
