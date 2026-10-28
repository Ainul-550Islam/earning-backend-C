"""
Gamification Hooks — Hook system for gamification module.

This module provides a comprehensive hook system for extending gamification
functionality through custom hooks and callbacks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union, Callable
from functools import wraps
import inspect

from django.contrib.auth import get_user_model
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

User = get_user_model()
logger = logging.getLogger(__name__)


class HookType:
    """Hook type constants."""
    
    # Contest hooks
    BEFORE_CONTEST_CREATE = "before_contest_create"
    AFTER_CONTEST_CREATE = "after_contest_create"
    BEFORE_CONTEST_ACTIVATE = "before_contest_activate"
    AFTER_CONTEST_ACTIVATE = "after_contest_activate"
    BEFORE_CONTEST_COMPLETE = "before_contest_complete"
    AFTER_CONTEST_COMPLETE = "after_contest_complete"
    
    # Achievement hooks
    BEFORE_ACHIEVEMENT_AWARD = "before_achievement_award"
    AFTER_ACHIEVEMENT_AWARD = "after_achievement_award"
    BEFORE_ACHIEVEMENT_REVOKE = "before_achievement_revoke"
    AFTER_ACHIEVEMENT_REVOKE = "after_achievement_revoke"
    
    # Badge hooks
    BEFORE_BADGE_EARN = "before_badge_earn"
    AFTER_BADGE_EARN = "after_badge_earn"
    BEFORE_BADGE_PIN = "before_badge_pin"
    AFTER_BADGE_PIN = "after_badge_pin"
    
    # Points hooks
    BEFORE_POINTS_AWARD = "before_points_award"
    AFTER_POINTS_AWARD = "after_points_award"
    BEFORE_POINTS_DEDUCT = "before_points_deduct"
    AFTER_POINTS_DEDUCT = "after_points_deduct"
    
    # Challenge hooks
    BEFORE_CHALLENGE_CREATE = "before_challenge_create"
    AFTER_CHALLENGE_CREATE = "after_challenge_create"
    BEFORE_CHALLENGE_COMPLETE = "before_challenge_complete"
    AFTER_CHALLENGE_COMPLETE = "after_challenge_complete"
    
    # Streak hooks
    BEFORE_STREAK_UPDATE = "before_streak_update"
    AFTER_STREAK_UPDATE = "after_streak_update"
    BEFORE_STREAK_RESET = "before_streak_reset"
    AFTER_STREAK_RESET = "after_streak_reset"
    
    # Level hooks
    BEFORE_LEVEL_UP = "before_level_up"
    AFTER_LEVEL_UP = "after_level_up"
    
    # User hooks
    BEFORE_USER_REGISTER = "before_user_register"
    AFTER_USER_REGISTER = "after_user_register"
    BEFORE_USER_LOGIN = "before_user_login"
    AFTER_USER_LOGIN = "after_user_login"


@dataclass
class HookContext:
    """Context object passed to hook functions."""
    
    hook_name: str
    user_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: timezone.now())
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data from context."""
        return self.data.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """Set data in context."""
        self.data[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from context."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata in context."""
        self.metadata[key] = value


class Hook(ABC):
    """Abstract base class for hooks."""
    
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def execute(self, context: HookContext) -> Any:
        """Execute the hook."""
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, priority={self.priority})"
    
    def __lt__(self, other) -> bool:
        """Compare hooks by priority for sorting."""
        return self.priority < other.priority


class FunctionHook(Hook):
    """Hook that wraps a callable function."""
    
    def __init__(self, name: str, func: Callable, priority: int = 0):
        super().__init__(name, priority)
        self.func = func
    
    def execute(self, context: HookContext) -> Any:
        """Execute the wrapped function."""
        try:
            # Check function signature to determine what to pass
            sig = inspect.signature(self.func)
            
            if len(sig.parameters) == 1:
                # Function takes only context
                return self.func(context)
            elif len(sig.parameters) == 0:
                # Function takes no arguments
                return self.func()
            else:
                # Function takes context and additional args
                return self.func(context, **context.data)
                
        except Exception as e:
            self.logger.error(f"Error executing hook {self.name}: {e}")
            raise GamificationServiceError(f"Hook execution failed: {e}")


class ConditionalHook(Hook):
    """Hook that executes conditionally based on a predicate."""
    
    def __init__(self, name: str, condition: Callable[[HookContext], bool], 
                 hook: Hook, priority: int = 0):
        super().__init__(name, priority)
        self.condition = condition
        self.hook = hook
    
    def execute(self, context: HookContext) -> Any:
        """Execute the hook if condition is met."""
        try:
            if self.condition(context):
                return self.hook.execute(context)
            return None
        except Exception as e:
            self.logger.error(f"Error executing conditional hook {self.name}: {e}")
            raise GamificationServiceError(f"Conditional hook execution failed: {e}")


class AsyncHook(Hook):
    """Hook that executes asynchronously."""
    
    def __init__(self, name: str, func: Callable, priority: int = 0):
        super().__init__(name, priority)
        self.func = func
    
    def execute(self, context: HookContext) -> Any:
        """Execute the function asynchronously."""
        try:
            # In a real implementation, this would use a task queue
            # For now, we'll execute synchronously
            return self.func(context)
        except Exception as e:
            self.logger.error(f"Error executing async hook {self.name}: {e}")
            raise GamificationServiceError(f"Async hook execution failed: {e}")


class HookRegistry:
    """Registry for managing hooks."""
    
    def __init__(self):
        self.hooks: Dict[str, List[Hook]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_hook(self, hook_name: str, hook: Hook) -> None:
        """Register a hook."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        
        self.hooks[hook_name].append(hook)
        
        # Sort hooks by priority
        self.hooks[hook_name].sort()
        
        self.logger.info(f"Registered hook {hook.name} for {hook_name}")
    
    def unregister_hook(self, hook_name: str, hook_name_to_remove: str) -> None:
        """Unregister a hook."""
        if hook_name in self.hooks:
            self.hooks[hook_name] = [
                h for h in self.hooks[hook_name] 
                if h.name != hook_name_to_remove
            ]
            self.logger.info(f"Unregistered hook {hook_name_to_remove} from {hook_name}")
    
    def get_hooks(self, hook_name: str) -> List[Hook]:
        """Get all hooks for a specific hook name."""
        return self.hooks.get(hook_name, [])
    
    def execute_hooks(self, hook_name: str, context: HookContext) -> List[Any]:
        """Execute all hooks for a specific hook name."""
        hooks = self.get_hooks(hook_name)
        results = []
        
        for hook in hooks:
            try:
                result = hook.execute(context)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error executing hook {hook.name}: {e}")
                # Continue with other hooks even if one fails
        
        return results
    
    def clear_hooks(self, hook_name: Optional[str] = None) -> None:
        """Clear hooks."""
        if hook_name:
            if hook_name in self.hooks:
                del self.hooks[hook_name]
                self.logger.info(f"Cleared hooks for {hook_name}")
        else:
            self.hooks.clear()
            self.logger.info("Cleared all hooks")
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """List all registered hooks."""
        return {
            name: [hook.name for hook in hooks]
            for name, hooks in self.hooks.items()
        }
    
    def get_hook_count(self, hook_name: str) -> int:
        """Get the number of hooks for a specific hook name."""
        return len(self.hooks.get(hook_name, []))


# Global hook registry
hook_registry = HookRegistry()


# Decorators for hook registration
def hook(hook_name: str, priority: int = 0):
    """Decorator to register a function as a hook."""
    def decorator(func):
        hook_obj = FunctionHook(func.__name__, func, priority)
        hook_registry.register_hook(hook_name, hook_obj)
        return func
    return decorator


def conditional_hook(hook_name: str, condition: Callable[[HookContext], bool], priority: int = 0):
    """Decorator to register a conditional hook."""
    def decorator(func):
        hook_obj = FunctionHook(func.__name__, func, priority)
        conditional_hook_obj = ConditionalHook(
            f"conditional_{func.__name__}", condition, hook_obj, priority
        )
        hook_registry.register_hook(hook_name, conditional_hook_obj)
        return func
    return decorator


def async_hook(hook_name: str, priority: int = 0):
    """Decorator to register an async hook."""
    def decorator(func):
        hook_obj = AsyncHook(func.__name__, func, priority)
        hook_registry.register_hook(hook_name, hook_obj)
        return func
    return decorator


# Hook execution utilities
def execute_hook(hook_name: str, user_id: Optional[str] = None,
                data: Optional[Dict[str, Any]] = None,
                metadata: Optional[Dict[str, Any]] = None) -> List[Any]:
    """Execute hooks for a specific hook name."""
    context = HookContext(
        hook_name=hook_name,
        user_id=user_id,
        data=data or {},
        metadata=metadata or {}
    )
    
    return hook_registry.execute_hooks(hook_name, context)


def execute_hook_with_result(hook_name: str, user_id: Optional[str] = None,
                           data: Optional[Dict[str, Any]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Any:
    """Execute hooks and return the first non-None result."""
    results = execute_hook(hook_name, user_id, data, metadata)
    
    for result in results:
        if result is not None:
            return result
    
    return None


# Built-in hooks
@hook(HookType.BEFORE_POINTS_AWARD)
def validate_points_award(context: HookContext) -> Optional[Dict[str, Any]]:
    """Validate points before awarding."""
    points = context.get_data('points', 0)
    max_points = context.get_data('max_points', 10000)
    
    if points < 0:
        raise GamificationServiceError("Points cannot be negative")
    
    if points > max_points:
        raise GamificationServiceError(f"Points cannot exceed {max_points}")
    
    return {'validated': True}


@hook(HookType.AFTER_POINTS_AWARD)
def log_points_award(context: HookContext) -> None:
    """Log points award."""
    user_id = context.user_id
    points = context.get_data('points', 0)
    source = context.get_data('source', 'unknown')
    
    logger.info(f"Awarded {points} points to user {user_id} from {source}")


@hook(HookType.BEFORE_BADGE_EARN)
def validate_badge_earn(context: HookContext) -> Optional[Dict[str, Any]]:
    """Validate badge earning."""
    user_id = context.user_id
    badge_id = context.get_data('badge_id')
    
    if not user_id:
        raise GamificationServiceError("User ID is required")
    
    if not badge_id:
        raise GamificationServiceError("Badge ID is required")
    
    return {'validated': True}


@hook(HookType.AFTER_BADGE_EARN)
def notify_badge_earn(context: HookContext) -> None:
    """Notify badge earning."""
    user_id = context.user_id
    badge_id = context.get_data('badge_id')
    
    logger.info(f"User {user_id} earned badge {badge_id}")
    
    # In a real implementation, this would send notifications
    # For now, we just log it


@hook(HookType.BEFORE_CONTEST_ACTIVATE)
def validate_contest_activation(context: HookContext) -> Optional[Dict[str, Any]]:
    """Validate contest activation."""
    contest_id = context.get_data('contest_id')
    
    if not contest_id:
        raise GamificationServiceError("Contest ID is required")
    
    return {'validated': True}


@hook(HookType.AFTER_CONTEST_ACTIVATE)
def notify_contest_activation(context: HookContext) -> None:
    """Notify contest activation."""
    contest_id = context.get_data('contest_id')
    
    logger.info(f"Contest {contest_id} activated")
    
    # In a real implementation, this would send notifications
    # For now, we just log it


# Hook management utilities
class HookManager:
    """Manager for hook operations."""
    
    def __init__(self):
        self.registry = hook_registry
        self.logger = logging.getLogger(__name__)
    
    def register_function_hook(self, hook_name: str, func: Callable, priority: int = 0) -> None:
        """Register a function as a hook."""
        hook_obj = FunctionHook(func.__name__, func, priority)
        self.registry.register_hook(hook_name, hook_obj)
    
    def register_conditional_hook(self, hook_name: str, condition: Callable[[HookContext], bool],
                                 func: Callable, priority: int = 0) -> None:
        """Register a conditional hook."""
        hook_obj = FunctionHook(func.__name__, func, priority)
        conditional_hook_obj = ConditionalHook(
            f"conditional_{func.__name__}", condition, hook_obj, priority
        )
        self.registry.register_hook(hook_name, conditional_hook_obj)
    
    def register_async_hook(self, hook_name: str, func: Callable, priority: int = 0) -> None:
        """Register an async hook."""
        hook_obj = AsyncHook(func.__name__, func, priority)
        self.registry.register_hook(hook_name, hook_obj)
    
    def create_hook_from_config(self, hook_config: Dict[str, Any]) -> Hook:
        """Create a hook from configuration."""
        hook_type = hook_config.get('type', 'function')
        hook_name = hook_config.get('name')
        priority = hook_config.get('priority', 0)
        
        if hook_type == 'function':
            # This would need to import the function from the module
            func_name = hook_config.get('function')
            module_name = hook_config.get('module')
            # Implementation would depend on your specific requirements
            raise NotImplementedError("Function hook from config not implemented")
        else:
            raise ValueError(f"Unknown hook type: {hook_type}")
    
    def get_hook_stats(self) -> Dict[str, Any]:
        """Get hook statistics."""
        return {
            'total_hooks': sum(len(hooks) for hooks in self.registry.hooks.values()),
            'hook_types': list(self.registry.hooks.keys()),
            'hooks_by_type': {
                name: len(hooks) for name, hooks in self.registry.hooks.items()
            }
        }
    
    def validate_hook(self, hook: Hook) -> bool:
        """Validate a hook."""
        try:
            # Create a test context
            test_context = HookContext(hook_name="test", user_id="test")
            
            # Try to execute the hook
            hook.execute(test_context)
            
            return True
        except Exception as e:
            self.logger.error(f"Hook validation failed for {hook.name}: {e}")
            return False
    
    def test_all_hooks(self) -> Dict[str, bool]:
        """Test all registered hooks."""
        results = {}
        
        for hook_name, hooks in self.registry.hooks.items():
            for hook in hooks:
                results[hook.name] = self.validate_hook(hook)
        
        return results


# Global hook manager
hook_manager = HookManager()


# Hook monitoring
class HookMonitor:
    """Monitor hook execution for debugging and analytics."""
    
    def __init__(self):
        self.execution_counts: Dict[str, int] = {}
        self.execution_times: Dict[str, List[datetime]] = []
        self.execution_errors: Dict[str, List[Exception]] = {}
        self.logger = logging.getLogger(__name__)
    
    def record_execution(self, hook_name: str, success: bool = True, error: Optional[Exception] = None) -> None:
        """Record hook execution."""
        self.execution_counts[hook_name] = self.execution_counts.get(hook_name, 0) + 1
        self.execution_times.append(datetime.now())
        
        if not success and error:
            if hook_name not in self.execution_errors:
                self.execution_errors[hook_name] = []
            self.execution_errors[hook_name].append(error)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            'total_executions': sum(self.execution_counts.values()),
            'execution_counts': self.execution_counts.copy(),
            'error_counts': {
                name: len(errors) for name, errors in self.execution_errors.items()
            },
            'last_execution': self.execution_times[-1].isoformat() if self.execution_times else None
        }
    
    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_counts.clear()
        self.execution_times.clear()
        self.execution_errors.clear()
        self.logger.info("Hook monitor stats reset")


# Global hook monitor
hook_monitor = HookMonitor()


# Initialize built-in hooks
def initialize_built_in_hooks() -> None:
    """Initialize built-in hooks."""
    try:
        # Built-in hooks are already registered via decorators
        logger.info("Initialized built-in hooks")
        
    except Exception as e:
        logger.error(f"Error initializing built-in hooks: {e}")


# Initialize on module import
try:
    initialize_built_in_hooks()
    logger.info("Gamification hooks module initialized")
except Exception as e:
    logger.error(f"Error initializing hooks module: {e}")
