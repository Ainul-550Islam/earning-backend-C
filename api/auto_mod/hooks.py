# =============================================================================
# auto_mod/hooks.py
# =============================================================================

"""
Hook system for auto moderation system.
Provides extensible hook points for customizing moderation behavior.
"""
import time

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class HookPriority(Enum):
    """Hook execution priority."""
    LOWEST = 1
    LOW = 2
    NORMAL = 3
    HIGH = 4
    HIGHEST = 5


class HookResult(Enum):
    """Hook execution result."""
    SUCCESS = "success"
    FAILURE = "failure"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class HookContext:
    """Hook execution context."""
    hook_name: str
    trigger_event: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: timezone.datetime = field(default_factory=timezone.now)
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value with default."""
        return self.data.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """Set data value."""
        self.data[key] = value
    
    def has_data(self, key: str) -> bool:
        """Check if data key exists."""
        return key in self.data


class BaseHook(ABC):
    """Base class for all hooks."""
    
    def __init__(self, name: str, priority: HookPriority = HookPriority.NORMAL, **kwargs):
        self.name = name
        self.priority = priority
        self.enabled = kwargs.get('enabled', True)
        self.async_hook = kwargs.get('async', False)
        self.timeout = kwargs.get('timeout', 300)
        self.conditions: List[Callable] = kwargs.get('conditions', [])
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.skip_count = 0
        self.abort_count = 0
        self.last_execution = None
        self.average_execution_time = 0.0
        self.execution_times: List[float] = []
        self.max_execution_times = 100
        self._lock = threading.Lock()
    
    def can_execute(self, context: HookContext) -> bool:
        """Check if hook can be executed."""
        if not self.enabled:
            return False
        
        # Check conditions
        for condition in self.conditions:
            try:
                if not condition(context):
                    return False
            except Exception as exc:
                logger.error(f"Hook {self.name}: condition error: {exc}")
                return False
        
        return True
    
    @abstractmethod
    def execute(self, context: HookContext) -> HookResult:
        """Execute the hook logic."""
        pass
    
    def _record_execution(self, result: HookResult, execution_time: float) -> None:
        """Record execution statistics."""
        with self._lock:
            self.execution_count += 1
            self.last_execution = timezone.now()
            
            # Update result counters
            if result == HookResult.SUCCESS:
                self.success_count += 1
            elif result == HookResult.FAILURE:
                self.failure_count += 1
            elif result == HookResult.SKIP:
                self.skip_count += 1
            elif result == HookResult.ABORT:
                self.abort_count += 1
            
            # Update execution time
            self.execution_times.append(execution_time)
            if len(self.execution_times) > self.max_execution_times:
                self.execution_times = self.execution_times[-self.max_execution_times:]
            
            if self.execution_times:
                self.average_execution_time = sum(self.execution_times) / len(self.execution_times)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hook statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'priority': self.priority.value,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'skip_count': self.skip_count,
            'abort_count': self.abort_count,
            'success_rate': round(success_rate, 2),
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'average_execution_time': round(self.average_execution_time, 3),
            'async_hook': self.async_hook
        }


class HookRegistry:
    """
    Registry for managing hooks and hook points.
    """
    
    def __init__(self):
        self.hooks: Dict[str, List[BaseHook]] = {}
        self.global_hooks: List[BaseHook] = []
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history_size = 10000
        self._lock = threading.Lock()
    
    def register_hook(self, hook_point: str, hook: BaseHook) -> None:
        """Register a hook for a specific hook point."""
        with self._lock:
            if hook_point not in self.hooks:
                self.hooks[hook_point] = []
            
            self.hooks[hook_point].append(hook)
            
            # Sort by priority (highest first)
            self.hooks[hook_point].sort(key=lambda h: h.priority.value, reverse=True)
            
            logger.info(f"HookRegistry: registered hook {hook.name} for {hook_point}")
    
    def register_global_hook(self, hook: BaseHook) -> None:
        """Register a global hook for all hook points."""
        with self._lock:
            self.global_hooks.append(hook)
            
            # Sort by priority
            self.global_hooks.sort(key=lambda h: h.priority.value, reverse=True)
            
            logger.info(f"HookRegistry: registered global hook {hook.name}")
    
    def unregister_hook(self, hook_point: str, hook_name: str) -> None:
        """Unregister a hook."""
        with self._lock:
            if hook_point in self.hooks:
                self.hooks[hook_point] = [
                    h for h in self.hooks[hook_point] if h.name != hook_name
                ]
                logger.info(f"HookRegistry: unregistered hook {hook_name} for {hook_point}")
    
    def unregister_global_hook(self, hook_name: str) -> None:
        """Unregister a global hook."""
        with self._lock:
            self.global_hooks = [
                h for h in self.global_hooks if h.name != hook_name
            ]
            logger.info(f"HookRegistry: unregistered global hook {hook_name}")
    
    def execute_hooks(self, hook_point: str, context: HookContext) -> HookResult:
        """
        Execute all hooks for a hook point.
        
        Args:
            hook_point: Hook point name
            context: Hook execution context
            
        Returns:
            Final hook result
        """
        start_time = timezone.now()
        
        try:
            # Get applicable hooks
            applicable_hooks = []
            
            # Hook point specific hooks
            if hook_point in self.hooks:
                applicable_hooks.extend([
                    h for h in self.hooks[hook_point] if h.can_execute(context)
                ])
            
            # Global hooks
            applicable_hooks.extend([
                h for h in self.global_hooks if h.can_execute(context)
            ])
            
            if not applicable_hooks:
                logger.debug(f"HookRegistry: no hooks for {hook_point}")
                return HookResult.SKIP
            
            # Execute hooks
            final_result = HookResult.SUCCESS
            
            for hook in applicable_hooks:
                hook_start = time.time()
                
                try:
                    result = hook.execute(context)
                    hook_execution_time = time.time() - hook_start
                    hook._record_execution(result, hook_execution_time)
                    
                    # Handle abort result
                    if result == HookResult.ABORT:
                        final_result = HookResult.ABORT
                        logger.warning(f"HookRegistry: hook {hook.name} aborted execution for {hook_point}")
                        break
                    
                    # Handle failure result
                    elif result == HookResult.FAILURE:
                        final_result = HookResult.FAILURE
                        logger.error(f"HookRegistry: hook {hook.name} failed for {hook_point}")
                    
                except Exception as exc:
                    hook_execution_time = time.time() - hook_start
                    hook._record_execution(HookResult.FAILURE, hook_execution_time)
                    logger.error(f"HookRegistry: hook {hook.name} exception for {hook_point}: {exc}")
                    final_result = HookResult.FAILURE
            
            # Record execution
            execution_time = (timezone.now() - start_time).total_seconds()
            self._record_execution(hook_point, context, final_result, execution_time)
            
            return final_result
            
        except Exception as exc:
            logger.error(f"HookRegistry: execution error for {hook_point}: {exc}")
            return HookResult.FAILURE
    
    async def execute_hooks_async(self, hook_point: str, context: HookContext) -> HookResult:
        """
        Execute all hooks for a hook point asynchronously.
        
        Args:
            hook_point: Hook point name
            context: Hook execution context
            
        Returns:
            Final hook result
        """
        start_time = timezone.now()
        
        try:
            # Get applicable hooks
            applicable_hooks = []
            
            # Hook point specific hooks
            if hook_point in self.hooks:
                applicable_hooks.extend([
                    h for h in self.hooks[hook_point] if h.can_execute(context)
                ])
            
            # Global hooks
            applicable_hooks.extend([
                h for h in self.global_hooks if h.can_execute(context)
            ])
            
            if not applicable_hooks:
                logger.debug(f"HookRegistry: no hooks for {hook_point}")
                return HookResult.SKIP
            
            # Execute hooks concurrently
            import asyncio
            
            tasks = []
            for hook in applicable_hooks:
                if hook.async_hook:
                    tasks.append(self._execute_hook_async(hook, context))
                else:
                    # Run sync hooks in thread pool
                    tasks.append(asyncio.get_event_loop().run_in_executor(
                        None, hook.execute, context
                    ))
            
            # Wait for all hooks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            final_result = HookResult.SUCCESS
            
            for i, result in enumerate(results):
                hook = applicable_hooks[i]
                hook_start = time.time()
                
                if isinstance(result, Exception):
                    hook_execution_time = time.time() - hook_start
                    hook._record_execution(HookResult.FAILURE, hook_execution_time)
                    logger.error(f"HookRegistry: hook {hook.name} exception for {hook_point}: {result}")
                    final_result = HookResult.FAILURE
                else:
                    hook_execution_time = time.time() - hook_start
                    hook._record_execution(result, hook_execution_time)
                    
                    if result == HookResult.ABORT:
                        final_result = HookResult.ABORT
                        logger.warning(f"HookRegistry: hook {hook.name} aborted execution for {hook_point}")
                        break
                    elif result == HookResult.FAILURE:
                        final_result = HookResult.FAILURE
                        logger.error(f"HookRegistry: hook {hook.name} failed for {hook_point}")
            
            # Record execution
            execution_time = (timezone.now() - start_time).total_seconds()
            self._record_execution(hook_point, context, final_result, execution_time)
            
            return final_result
            
        except Exception as exc:
            logger.error(f"HookRegistry: async execution error for {hook_point}: {exc}")
            return HookResult.FAILURE
    
    async def _execute_hook_async(self, hook: BaseHook, context: HookContext) -> HookResult:
        """Execute a single hook asynchronously."""
        return hook.execute(context)
    
    def _record_execution(self, hook_point: str, context: HookContext, 
                         result: HookResult, execution_time: float) -> None:
        """Record hook execution."""
        with self._lock:
            execution_record = {
                'hook_point': hook_point,
                'context': context,
                'result': result.value,
                'execution_time': execution_time,
                'timestamp': timezone.now().isoformat()
            }
            
            self.execution_history.append(execution_record)
            
            # Trim history if too large
            if len(self.execution_history) > self.max_history_size:
                self.execution_history = self.execution_history[-self.max_history_size:]
    
    def get_hook_stats(self) -> Dict[str, Any]:
        """Get hook statistics."""
        with self._lock:
            stats = {}
            
            for hook_point, hooks in self.hooks.items():
                for hook in hooks:
                    stats[hook.name] = hook.get_stats()
            
            for hook in self.global_hooks:
                stats[hook.name] = hook.get_stats()
            
            return stats
    
    def get_execution_history(self, hook_point: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history."""
        with self._lock:
            history = self.execution_history
            
            if hook_point:
                history = [h for h in history if h['hook_point'] == hook_point]
            
            return history[-limit:]


# Global hook registry
hook_registry = HookRegistry()


# Common hook points
class HookPoints:
    """Common hook point definitions."""
    
    # Submission hooks
    BEFORE_SUBMISSION_SCAN = "before_submission_scan"
    AFTER_SUBMISSION_SCAN = "after_submission_scan"
    BEFORE_SUBMISSION_APPROVE = "before_submission_approve"
    AFTER_SUBMISSION_APPROVE = "after_submission_approve"
    BEFORE_SUBMISSION_REJECT = "before_submission_reject"
    AFTER_SUBMISSION_REJECT = "after_submission_reject"
    
    # Rule hooks
    BEFORE_RULE_EVALUATION = "before_rule_evaluation"
    AFTER_RULE_EVALUATION = "after_rule_evaluation"
    BEFORE_RULE_EXECUTION = "before_rule_execution"
    AFTER_RULE_EXECUTION = "after_rule_execution"
    
    # Bot hooks
    BEFORE_BOT_START = "before_bot_start"
    AFTER_BOT_START = "after_bot_start"
    BEFORE_BOT_STOP = "before_bot_stop"
    AFTER_BOT_STOP = "after_bot_stop"
    BEFORE_BOT_PROCESS = "before_bot_process"
    AFTER_BOT_PROCESS = "after_bot_process"
    
    # Queue hooks
    BEFORE_QUEUE_ASSIGNMENT = "before_queue_assignment"
    AFTER_QUEUE_ASSIGNMENT = "after_queue_assignment"
    BEFORE_QUEUE_ESCALATION = "before_queue_escalation"
    AFTER_QUEUE_ESCALATION = "after_queue_escalation"
    
    # Decision hooks
    BEFORE_DECISION_CREATE = "before_decision_create"
    AFTER_DECISION_CREATE = "after_decision_create"
    BEFORE_DECISION_OVERRIDE = "before_decision_override"
    AFTER_DECISION_OVERRIDE = "after_decision_override"
    
    # Appeal hooks
    BEFORE_APPEAL_CREATE = "before_appeal_create"
    AFTER_APPEAL_CREATE = "after_appeal_create"
    BEFORE_APPEAL_RESOLVE = "before_appeal_resolve"
    AFTER_APPEAL_RESOLVE = "after_appeal_resolve"
    
    # Model hooks
    BEFORE_MODEL_TRAIN = "before_model_train"
    AFTER_MODEL_TRAIN = "after_model_train"
    BEFORE_MODEL_DEPLOY = "before_model_deploy"
    AFTER_MODEL_DEPLOY = "after_model_deploy"
    
    # System hooks
    BEFORE_SYSTEM_SHUTDOWN = "before_system_shutdown"
    AFTER_SYSTEM_STARTUP = "after_system_startup"
    BEFORE_CACHE_CLEAR = "before_cache_clear"
    AFTER_CACHE_CLEAR = "after_cache_clear"


# Hook decorators
def hook(hook_point: str, priority: HookPriority = HookPriority.NORMAL, **kwargs):
    """
    Decorator to register a hook.
    
    Args:
        hook_point: Hook point name
        priority: Hook execution priority
        **kwargs: Additional hook configuration
    """
    def decorator(cls: type) -> type:
        # Create hook instance
        hook_instance = cls(
            name=cls.__name__,
            priority=priority,
            **kwargs
        )
        
        # Register hook
        hook_registry.register_hook(hook_point, hook_instance)
        
        return cls
    return decorator


def global_hook(priority: HookPriority = HookPriority.NORMAL, **kwargs):
    """
    Decorator to register a global hook.
    
    Args:
        priority: Hook execution priority
        **kwargs: Additional hook configuration
    """
    def decorator(cls: type) -> type:
        # Create hook instance
        hook_instance = cls(
            name=cls.__name__,
            priority=priority,
            **kwargs
        )
        
        # Register global hook
        hook_registry.register_global_hook(hook_instance)
        
        return cls
    return decorator


# Hook utility functions
def execute_hooks(hook_point: str, trigger_event: str, data: Dict[str, Any] = None,
                 **kwargs) -> HookResult:
    """
    Execute hooks for a hook point.
    
    Args:
        hook_point: Hook point name
        trigger_event: Trigger event name
        data: Hook data
        **kwargs: Additional context parameters
        
    Returns:
        Final hook result
    """
    context = HookContext(
        hook_name=hook_point,
        trigger_event=trigger_event,
        data=data or {},
        **kwargs
    )
    
    return hook_registry.execute_hooks(hook_point, context)


async def execute_hooks_async(hook_point: str, trigger_event: str, data: Dict[str, Any] = None,
                             **kwargs) -> HookResult:
    """
    Execute hooks for a hook point asynchronously.
    
    Args:
        hook_point: Hook point name
        trigger_event: Trigger event name
        data: Hook data
        **kwargs: Additional context parameters
        
    Returns:
        Final hook result
    """
    context = HookContext(
        hook_name=hook_point,
        trigger_event=trigger_event,
        data=data or {},
        **kwargs
    )
    
    return await hook_registry.execute_hooks_async(hook_point, context)


# Hook condition utilities
class HookCondition:
    """Hook condition utilities."""
    
    @staticmethod
    def during_business_hours(start_hour: int = 9, end_hour: int = 17) -> Callable:
        """Condition: execute during business hours."""
        def condition_func(context: HookContext) -> bool:
            return start_hour <= context.timestamp.hour <= end_hour
        return condition_func
    
    @staticmethod
    def on_weekdays() -> Callable:
        """Condition: execute on weekdays."""
        def condition_func(context: HookContext) -> bool:
            return context.timestamp.weekday() < 5
        return condition_func
    
    @staticmethod
    def has_data_key(key: str) -> Callable:
        """Condition: context has specific data key."""
        def condition_func(context: HookContext) -> bool:
            return context.has_data(key)
        return condition_func
    
    @staticmethod
    def data_key_equals(key: str, value: Any) -> Callable:
        """Condition: context data key equals specific value."""
        def condition_func(context: HookContext) -> bool:
            return context.get_data(key) == value
        return condition_func
    
    @staticmethod
    def user_has_permission(permission: str) -> Callable:
        """Condition: user has specific permission."""
        def condition_func(context: HookContext) -> bool:
            if not context.user_id:
                return False
            
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(pk=context.user_id)
                return user.has_perm(permission)
            except Exception:
                return False
        return condition_func


# Common hook implementations
class LoggingHook(BaseHook):
    """Hook that logs execution."""
    
    def __init__(self, name: str = "LoggingHook", **kwargs):
        super().__init__(name, **kwargs)
        self.log_level = kwargs.get('log_level', 'INFO')
        self.log_message = kwargs.get('log_message', 'Hook executed: {hook_point}')
    
    def execute(self, context: HookContext) -> HookResult:
        """Log hook execution."""
        message = self.log_message.format(
            hook_point=context.hook_name,
            trigger_event=context.trigger_event,
            user_id=context.user_id,
            tenant_id=context.tenant_id
        )
        
        getattr(logger, self.log_level.lower())(message)
        
        return HookResult.SUCCESS


class MetricsHook(BaseHook):
    """Hook that records metrics."""
    
    def __init__(self, name: str = "MetricsHook", **kwargs):
        super().__init__(name, **kwargs)
        self.metric_name = kwargs.get('metric_name', 'hook_execution')
        self.metric_tags = kwargs.get('metric_tags', {})
    
    def execute(self, context: HookContext) -> HookResult:
        """Record hook execution metrics."""
        # This would integrate with your metrics system
        # For now, we'll just log the metric
        logger.info(f"Metric: {self.metric_name} tags={self.metric_tags} "
                   f"hook_point={context.hook_name} trigger={context.trigger_event}")
        
        return HookResult.SUCCESS


class ValidationHook(BaseHook):
    """Hook that validates context data."""
    
    def __init__(self, name: str = "ValidationHook", **kwargs):
        super().__init__(name, **kwargs)
        self.required_fields = kwargs.get('required_fields', [])
        self.validators = kwargs.get('validators', {})
    
    def execute(self, context: HookContext) -> HookResult:
        """Validate context data."""
        # Check required fields
        for field in self.required_fields:
            if not context.has_data(field):
                logger.error(f"ValidationHook: missing required field {field}")
                return HookResult.FAILURE
        
        # Run validators
        for field, validator in self.validators.items():
            value = context.get_data(field)
            try:
                if not validator(value):
                    logger.error(f"ValidationHook: validation failed for field {field}")
                    return HookResult.FAILURE
            except Exception as exc:
                logger.error(f"ValidationHook: validation error for field {field}: {exc}")
                return HookResult.FAILURE
        
        return HookResult.SUCCESS


class CacheHook(BaseHook):
    """Hook that manages cache operations."""
    
    def __init__(self, name: str = "CacheHook", **kwargs):
        super().__init__(name, **kwargs)
        self.cache_keys = kwargs.get('cache_keys', [])
        self.cache_action = kwargs.get('cache_action', 'clear')  # clear, warm, refresh
        self.cache_ttl = kwargs.get('cache_ttl', 3600)
    
    def execute(self, context: HookContext) -> HookResult:
        """Execute cache operations."""
        try:
            if self.cache_action == 'clear':
                for key in self.cache_keys:
                    cache.delete(key)
                    logger.debug(f"CacheHook: cleared cache key {key}")
            
            elif self.cache_action == 'warm':
                for key in self.cache_keys:
                    # This would implement cache warming logic
                    logger.debug(f"CacheHook: warmed cache key {key}")
            
            elif self.cache_action == 'refresh':
                for key in self.cache_keys:
                    # This would implement cache refresh logic
                    logger.debug(f"CacheHook: refreshed cache key {key}")
            
            return HookResult.SUCCESS
            
        except Exception as exc:
            logger.error(f"CacheHook: cache operation failed: {exc}")
            return HookResult.FAILURE


# Auto-registration of common hooks
def register_common_hooks():
    """Register common hooks."""
    # Register logging hooks for important hook points
    important_hooks = [
        HookPoints.BEFORE_SUBMISSION_SCAN,
        HookPoints.AFTER_SUBMISSION_SCAN,
        HookPoints.BEFORE_RULE_EXECUTION,
        HookPoints.AFTER_RULE_EXECUTION,
        HookPoints.BEFORE_BOT_START,
        HookPoints.AFTER_BOT_START,
        HookPoints.BEFORE_DECISION_CREATE,
        HookPoints.AFTER_DECISION_CREATE,
    ]
    
    for hook_point in important_hooks:
        logging_hook = LoggingHook(
            name=f"LoggingHook_{hook_point}",
            log_message=f"Hook executed: {hook_point}"
        )
        hook_registry.register_hook(hook_point, logging_hook)
    
    logger.info("HookRegistry: registered common hooks")


# Initialize common hooks on import
register_common_hooks()
