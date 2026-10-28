"""
hooks.py – Hook system for postback module.

Provides comprehensive hook system for extending and customizing
postback processing with pluggable architecture and event-driven
workflows.
"""
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import importlib
import inspect

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class HookPriority(Enum):
    """Hook execution priority levels."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class HookStatus(Enum):
    """Hook execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DISABLED = "disabled"


@dataclass
class HookContext:
    """
    Hook execution context containing data and metadata.
    
    Provides a unified interface for passing data between
    hooks and tracking execution state.
    """
    hook_name: str
    hook_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    execution_id: str = field(default="")
    status: HookStatus = HookStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    
    def __post_init__(self):
        """Initialize execution ID if not provided."""
        if not self.execution_id:
            import uuid
            self.execution_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'hook_name': self.hook_name,
            'hook_type': self.hook_type,
            'data': self.data,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'execution_id': self.execution_id,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'execution_time': self.execution_time,
            'retry_count': self.retry_count,
        }


class Hook:
    """
    Base hook class for postback processing extensions.
    
    Provides a framework for creating pluggable hooks that can
    intercept and modify postback processing at various stages.
    """
    
    def __init__(self, name: str, hook_type: str, priority: HookPriority = HookPriority.NORMAL):
        self.name = name
        self.hook_type = hook_type
        self.priority = priority
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_execution_time = 0.0
        self.last_execution = None
        self.config = {}
    
    def execute(self, context: HookContext) -> HookContext:
        """
        Execute the hook with the given context.
        
        Args:
            context: Hook execution context
            
        Returns:
            Updated context after hook execution
        """
        if not self.enabled:
            context.status = HookStatus.DISABLED
            return context
        
        start_time = timezone.now()
        context.status = HookStatus.RUNNING
        
        try:
            logger.debug(f"Executing hook: {self.name} ({self.hook_type})")
            
            # Call the hook implementation
            result = self._execute_hook(context)
            
            # Update context with result
            context.result = result
            context.status = HookStatus.SUCCESS
            
            # Update statistics
            self._update_statistics(True, (timezone.now() - start_time).total_seconds())
            
            logger.debug(f"Hook {self.name} executed successfully")
            
            return context
            
        except Exception as e:
            context.status = HookStatus.FAILURE
            context.error = str(e)
            
            # Update statistics
            self._update_statistics(False, (timezone.now() - start_time).total_seconds())
            
            logger.error(f"Hook {self.name} failed: {str(e)}")
            
            return context
    
    def _execute_hook(self, context: HookContext) -> Any:
        """
        Hook implementation method to be overridden by subclasses.
        
        Args:
            context: Hook execution context
            
        Returns:
            Hook execution result
        """
        raise NotImplementedError("Hook implementation must override _execute_hook method")
    
    def _update_statistics(self, success: bool, execution_time: float):
        """Update hook execution statistics."""
        self.execution_count += 1
        self.total_execution_time += execution_time
        self.last_execution = timezone.now()
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def configure(self, config: Dict[str, Any]):
        """Configure the hook with settings."""
        self.config.update(config)
        self._apply_configuration()
    
    def _apply_configuration(self):
        """Apply configuration to the hook."""
        # Override in subclasses as needed
        pass
    
    def enable(self):
        """Enable the hook."""
        self.enabled = True
        logger.info(f"Hook {self.name} enabled")
    
    def disable(self):
        """Disable the hook."""
        self.enabled = False
        logger.info(f"Hook {self.name} disabled")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hook execution statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        avg_execution_time = (self.total_execution_time / self.execution_count) if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'type': self.hook_type,
            'priority': self.priority.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': f"{success_rate:.2f}%",
            'avg_execution_time': f"{avg_execution_time:.3f}s",
            'total_execution_time': f"{self.total_execution_time:.3f}s",
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
        }


class HookRegistry:
    """
    Registry for managing hooks and their execution.
    
    Provides centralized management of hooks including registration,
    execution ordering, and lifecycle management.
    """
    
    def __init__(self):
        self.hooks: Dict[str, Hook] = {}
        self.hooks_by_type: Dict[str, List[Hook]] = {}
        self.execution_history = []
        self.enabled = True
    
    def register(self, hook: Hook):
        """
        Register a hook in the registry.
        
        Args:
            hook: Hook instance to register
        """
        if hook.name in self.hooks:
            logger.warning(f"Hook {hook.name} already registered, replacing")
        
        self.hooks[hook.name] = hook
        
        # Add to type-based grouping
        if hook.hook_type not in self.hooks_by_type:
            self.hooks_by_type[hook.hook_type] = []
        
        # Remove existing hook with same name from type group
        self.hooks_by_type[hook.hook_type] = [
            h for h in self.hooks_by_type[hook.hook_type]
            if h.name != hook.name
        ]
        
        # Add new hook
        self.hooks_by_type[hook.hook_type].append(hook)
        
        # Sort by priority (highest first)
        self.hooks_by_type[hook.hook_type].sort(key=lambda h: h.priority.value, reverse=True)
        
        logger.info(f"Registered hook: {hook.name} ({hook.hook_type})")
    
    def unregister(self, hook_name: str):
        """
        Unregister a hook from the registry.
        
        Args:
            hook_name: Name of hook to unregister
        """
        if hook_name not in self.hooks:
            logger.warning(f"Hook {hook_name} not found in registry")
            return
        
        hook = self.hooks[hook_name]
        
        # Remove from type grouping
        if hook.hook_type in self.hooks_by_type:
            self.hooks_by_type[hook.hook_type] = [
                h for h in self.hooks_by_type[hook.hook_type]
                if h.name != hook_name
            ]
        
        # Remove from registry
        del self.hooks[hook_name]
        
        logger.info(f"Unregistered hook: {hook_name}")
    
    def execute_hooks(self, hook_type: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute all hooks of a specific type.
        
        Args:
            hook_type: Type of hooks to execute
            context_data: Initial context data
            
        Returns:
            Execution results
        """
        if not self.enabled:
            return {'status': 'disabled', 'message': 'Hook registry disabled'}
        
        if hook_type not in self.hooks_by_type:
            return {'status': 'no_hooks', 'message': f'No hooks registered for type: {hook_type}'}
        
        hooks = self.hooks_by_type[hook_type]
        
        if not hooks:
            return {'status': 'no_hooks', 'message': f'No hooks available for type: {hook_type}'}
        
        start_time = timezone.now()
        execution_id = self._generate_execution_id()
        
        try:
            # Initialize context
            context = HookContext(
                hook_name=f"chain_{hook_type}",
                hook_type=hook_type,
                data=context_data or {},
                metadata={'execution_id': execution_id}
            )
            
            # Execute hooks in priority order
            results = []
            
            for hook in hooks:
                # Create hook-specific context
                hook_context = HookContext(
                    hook_name=hook.name,
                    hook_type=hook.hook_type,
                    data=context.data.copy(),
                    metadata=context.metadata.copy()
                )
                
                # Execute hook
                hook_context = hook.execute(hook_context)
                
                # Update main context with hook result
                context.data.update(hook_context.data)
                context.metadata.update(hook_context.metadata)
                
                # Store hook result
                results.append({
                    'hook_name': hook.name,
                    'status': hook_context.status.value,
                    'result': hook_context.result,
                    'error': hook_context.error,
                    'execution_time': hook_context.execution_time,
                })
                
                # Stop execution if hook failed and is critical
                if hook_context.status == HookStatus.FAILURE and hook.priority == HookPriority.HIGHEST:
                    logger.error(f"Critical hook {hook.name} failed, stopping execution")
                    break
            
            execution_time = (timezone.now() - start_time).total_seconds()
            
            # Record execution
            self._record_execution(execution_id, hook_type, results, execution_time)
            
            return {
                'execution_id': execution_id,
                'hook_type': hook_type,
                'status': 'completed',
                'execution_time': execution_time,
                'hooks_executed': len(results),
                'results': results,
                'final_context': context.to_dict(),
            }
            
        except Exception as e:
            execution_time = (timezone.now() - start_time).total_seconds()
            
            logger.error(f"Error executing hooks for {hook_type}: {str(e)}")
            
            return {
                'execution_id': execution_id,
                'hook_type': hook_type,
                'status': 'failed',
                'execution_time': execution_time,
                'error': str(e),
            }
    
    def get_hook(self, hook_name: str) -> Optional[Hook]:
        """Get a hook by name."""
        return self.hooks.get(hook_name)
    
    def get_hooks_by_type(self, hook_type: str) -> List[Hook]:
        """Get all hooks of a specific type."""
        return self.hooks_by_type.get(hook_type, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'total_hooks': len(self.hooks),
            'hooks_by_type': {
                hook_type: len(hooks)
                for hook_type, hooks in self.hooks_by_type.items()
            },
            'hook_details': {
                hook_name: hook.get_statistics()
                for hook_name, hook in self.hooks.items()
            },
            'execution_history_count': len(self.execution_history),
            'enabled': self.enabled,
        }
    
    def enable_all(self):
        """Enable all hooks."""
        for hook in self.hooks.values():
            hook.enable()
        
        self.enabled = True
        logger.info("All hooks enabled")
    
    def disable_all(self):
        """Disable all hooks."""
        for hook in self.hooks.values():
            hook.disable()
        
        self.enabled = False
        logger.info("All hooks disabled")
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _record_execution(self, execution_id: str, hook_type: str, results: List[Dict], execution_time: float):
        """Record hook execution details."""
        execution_record = {
            'execution_id': execution_id,
            'hook_type': hook_type,
            'results': results,
            'execution_time': execution_time,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.execution_history.append(execution_record)
        
        # Keep only last 100 executions
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
        
        # Cache execution record
        cache_key = f"hook_execution_{execution_id}"
        cache.set(cache_key, execution_record, timeout=3600)  # 1 hour


# Built-in hook types
class PostbackHookTypes:
    """Standard postback hook types."""
    PRE_PROCESSING = "pre_processing"
    POST_PROCESSING = "post_processing"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RATE_LIMITING = "rate_limiting"
    FRAUD_DETECTION = "fraud_detection"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    ERROR_HANDLING = "error_handling"
    CLEANUP = "cleanup"


# Built-in hook implementations
class ValidationHook(Hook):
    """Built-in validation hook."""
    
    def __init__(self, name: str = "validation_hook"):
        super().__init__(name, PostbackHookTypes.VALIDATION)
    
    def _execute_hook(self, context: HookContext) -> Any:
        """Execute validation logic."""
        data = context.data
        
        # Basic validation example
        required_fields = ['postback_id', 'network_key']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            raise PostbackException(f"Missing required fields: {missing_fields}")
        
        # Add validation result to context
        context.data['validation_passed'] = True
        context.data['validated_at'] = timezone.now().isoformat()
        
        return {'validated': True, 'missing_fields': []}


class AnalyticsHook(Hook):
    """Built-in analytics hook."""
    
    def __init__(self, name: str = "analytics_hook"):
        super().__init__(name, PostbackHookTypes.ANALYTICS)
    
    def _execute_hook(self, context: HookContext) -> Any:
        """Execute analytics logic."""
        data = context.data
        
        # Add analytics metadata
        analytics_data = {
            'processed_at': timezone.now().isoformat(),
            'hook_name': context.hook_name,
            'data_size': len(str(data)),
        }
        
        # Update context with analytics data
        context.data.setdefault('analytics', {}).update(analytics_data)
        
        return {'analytics_recorded': True}


class NotificationHook(Hook):
    """Built-in notification hook."""
    
    def __init__(self, name: str = "notification_hook"):
        super().__init__(name, PostbackHookTypes.NOTIFICATION)
    
    def _execute_hook(self, context: HookContext) -> Any:
        """Execute notification logic."""
        data = context.data
        
        # Example notification logic
        if data.get('status') == 'FAILED':
            # Send failure notification
            notification_data = {
                'type': 'failure',
                'postback_id': data.get('postback_id'),
                'error': data.get('error'),
                'timestamp': timezone.now().isoformat(),
            }
            
            context.data.setdefault('notifications', []).append(notification_data)
        
        return {'notifications_processed': True}


# Global hook registry instance
hook_registry = HookRegistry()


# Decorator for creating hooks
def hook(hook_type: str, name: str = None, priority: HookPriority = HookPriority.NORMAL):
    """
    Decorator for creating hook functions.
    
    Args:
        hook_type: Type of hook
        name: Hook name (defaults to function name)
        priority: Hook execution priority
    """
    def decorator(func):
        hook_name = name or func.__name__
        
        class FunctionHook(Hook):
            def __init__(self):
                super().__init__(hook_name, hook_type, priority)
            
            def _execute_hook(self, context: HookContext) -> Any:
                return func(context)
        
        # Create and register hook
        hook_instance = FunctionHook()
        hook_registry.register(hook_instance)
        
        return func
    return decorator


# Convenience functions for hook registration
def register_hook(hook: Hook):
    """Register a hook instance."""
    hook_registry.register(hook)


def unregister_hook(hook_name: str):
    """Unregister a hook by name."""
    hook_registry.unregister(hook_name)


def execute_hooks(hook_type: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute hooks of a specific type."""
    return hook_registry.execute_hooks(hook_type, context_data)


# Hook discovery and auto-loading
def discover_hooks():
    """Discover and auto-load hooks from configured modules."""
    hook_modules = getattr(settings, 'POSTBACK_HOOK_MODULES', [])
    
    for module_path in hook_modules:
        try:
            module = importlib.import_module(module_path)
            
            # Look for hook classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Hook) and obj != Hook:
                    # Instantiate and register the hook
                    hook_instance = obj()
                    hook_registry.register(hook_instance)
                    logger.info(f"Auto-registered hook: {hook_instance.name}")
            
        except ImportError as e:
            logger.error(f"Failed to import hook module {module_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading hooks from {module_path}: {str(e)}")


# Initialize built-in hooks
def initialize_builtin_hooks():
    """Initialize built-in hooks."""
    try:
        # Register built-in hooks
        hook_registry.register(ValidationHook())
        hook_registry.register(AnalyticsHook())
        hook_registry.register(NotificationHook())
        
        logger.info("Built-in hooks initialized")
        
    except Exception as e:
        logger.error(f"Error initializing built-in hooks: {str(e)}")


# Hook system initialization
def initialize_hook_system():
    """Initialize the hook system."""
    try:
        initialize_builtin_hooks()
        discover_hooks()
        
        logger.info("Hook system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing hook system: {str(e)}")


# Get system statistics
def get_hook_system_statistics() -> Dict[str, Any]:
    """Get comprehensive hook system statistics."""
    return {
        'registry_stats': hook_registry.get_statistics(),
        'system_enabled': hook_registry.enabled,
    }


# Hook configuration management
def configure_hook(hook_name: str, config: Dict[str, Any]):
    """Configure a specific hook."""
    hook = hook_registry.get_hook(hook_name)
    if hook:
        hook.configure(config)
        logger.info(f"Configured hook: {hook_name}")
    else:
        logger.warning(f"Hook {hook_name} not found for configuration")


# Hook lifecycle management
def enable_hook(hook_name: str):
    """Enable a specific hook."""
    hook = hook_registry.get_hook(hook_name)
    if hook:
        hook.enable()
    else:
        logger.warning(f"Hook {hook_name} not found")


def disable_hook(hook_name: str):
    """Disable a specific hook."""
    hook = hook_registry.get_hook(hook_name)
    if hook:
        hook.disable()
    else:
        logger.warning(f"Hook {hook_name} not found")
