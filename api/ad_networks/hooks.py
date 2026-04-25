"""
api/ad_networks/hooks.py
Hook system for ad networks module
SaaS-ready with tenant support
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)


class HookType(Enum):
    """Hook types for ad networks"""
    
    # Offer hooks
    OFFER_BEFORE_CREATE = "offer_before_create"
    OFFER_AFTER_CREATE = "offer_after_create"
    OFFER_BEFORE_UPDATE = "offer_before_update"
    OFFER_AFTER_UPDATE = "offer_after_update"
    OFFER_BEFORE_DELETE = "offer_before_delete"
    OFFER_AFTER_DELETE = "offer_after_delete"
    
    # Conversion hooks
    CONVERSION_BEFORE_CREATE = "conversion_before_create"
    CONVERSION_AFTER_CREATE = "conversion_after_create"
    CONVERSION_BEFORE_APPROVE = "conversion_before_approve"
    CONVERSION_AFTER_APPROVE = "conversion_after_approve"
    CONVERSION_BEFORE_REJECT = "conversion_before_reject"
    CONVERSION_AFTER_REJECT = "conversion_after_reject"
    
    # Reward hooks
    REWARD_BEFORE_CREATE = "reward_before_create"
    REWARD_AFTER_CREATE = "reward_after_create"
    REWARD_BEFORE_APPROVE = "reward_before_approve"
    REWARD_AFTER_APPROVE = "reward_after_approve"
    REWARD_BEFORE_PAY = "reward_before_pay"
    REWARD_AFTER_PAY = "reward_after_pay"
    
    # User hooks
    USER_BEFORE_ENGAGEMENT = "user_before_engagement"
    USER_AFTER_ENGAGEMENT = "user_after_engagement"
    USER_BEFORE_CONVERSION = "user_before_conversion"
    USER_AFTER_CONVERSION = "user_after_conversion"
    USER_BEFORE_REWARD = "user_before_reward"
    USER_AFTER_REWARD = "user_after_reward"
    
    # Network hooks
    NETWORK_BEFORE_SYNC = "network_before_sync"
    NETWORK_AFTER_SYNC = "network_after_sync"
    NETWORK_BEFORE_HEALTH_CHECK = "network_before_health_check"
    NETWORK_AFTER_HEALTH_CHECK = "network_after_health_check"
    
    # Fraud hooks
    FRAUD_BEFORE_DETECTION = "fraud_before_detection"
    FRAUD_AFTER_DETECTION = "fraud_after_detection"
    FRAUD_BEFORE_FLAG = "fraud_before_flag"
    FRAUD_AFTER_FLAG = "fraud_after_flag"
    
    # System hooks
    CACHE_BEFORE_CLEAR = "cache_before_clear"
    CACHE_AFTER_CLEAR = "cache_after_clear"
    EXPORT_BEFORE_START = "export_before_start"
    EXPORT_AFTER_COMPLETE = "export_after_complete"
    NOTIFICATION_BEFORE_SEND = "notification_before_send"
    NOTIFICATION_AFTER_SEND = "notification_after_send"


class HookPriority(Enum):
    """Hook priority levels"""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class HookResult:
    """Result of hook execution"""
    
    def __init__(self, success: bool = True, data: Any = None, 
                 error: str = None, stop_execution: bool = False):
        self.success = success
        self.data = data
        self.error = error
        self.stop_execution = stop_execution
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'stop_execution': self.stop_execution
        }


class Hook(ABC):
    """Abstract base class for hooks"""
    
    def __init__(self, name: str, hook_type: HookType, 
                 priority: HookPriority = HookPriority.NORMAL):
        self.name = name
        self.hook_type = hook_type
        self.priority = priority
        self.enabled = True
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique hook ID"""
        import uuid
        return str(uuid.uuid4())
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute hook logic"""
        pass
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if hook can be executed"""
        return self.enabled
    
    def enable(self):
        """Enable hook"""
        self.enabled = True
    
    def disable(self):
        """Disable hook"""
        self.enabled = False


class FunctionHook(Hook):
    """Hook that executes a function"""
    
    def __init__(self, name: str, hook_type: HookType, 
                 func: Callable, priority: HookPriority = HookPriority.NORMAL):
        super().__init__(name, hook_type, priority)
        self.func = func
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute function"""
        try:
            if not self.can_execute(context):
                return HookResult(success=False, error="Hook cannot execute")
            
            result = self.func(context)
            
            if isinstance(result, HookResult):
                return result
            elif isinstance(result, dict):
                return HookResult(success=True, data=result)
            else:
                return HookResult(success=True, data=result)
                
        except Exception as e:
            logger.error(f"Error executing hook {self.name}: {str(e)}")
            return HookResult(success=False, error=str(e))


class ConditionalHook(Hook):
    """Hook that executes conditionally"""
    
    def __init__(self, name: str, hook_type: HookType,
                 condition: Callable, hook: Hook, 
                 priority: HookPriority = HookPriority.NORMAL):
        super().__init__(name, hook_type, priority)
        self.condition = condition
        self.hook = hook
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if condition is met"""
        return super().can_execute(context) and self.condition(context)
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute hook if condition is met"""
        if self.can_execute(context):
            return self.hook.execute(context)
        else:
            return HookResult(success=True, data="Condition not met, hook skipped")


class ChainedHook(Hook):
    """Hook that chains multiple hooks"""
    
    def __init__(self, name: str, hook_type: HookType,
                 hooks: List[Hook], priority: HookPriority = HookPriority.NORMAL,
                 stop_on_first_error: bool = False):
        super().__init__(name, hook_type, priority)
        self.hooks = sorted(hooks, key=lambda h: h.priority.value, reverse=True)
        self.stop_on_first_error = stop_on_first_error
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute all hooks in chain"""
        results = []
        
        for hook in self.hooks:
            if not hook.can_execute(context):
                continue
            
            result = hook.execute(context)
            results.append(result)
            
            # Stop on first error if configured
            if self.stop_on_first_error and not result.success:
                return HookResult(
                    success=False,
                    error=f"Hook {hook.name} failed: {result.error}",
                    data=results
                )
            
            # Stop execution if requested
            if result.stop_execution:
                return HookResult(
                    success=True,
                    data=results,
                    stop_execution=True
                )
        
        return HookResult(success=True, data=results)


class HookRegistry:
    """Registry for managing hooks"""
    
    def __init__(self):
        self.hooks: Dict[HookType, List[Hook]] = {}
        self.hook_names: Dict[str, Hook] = {}
    
    def register(self, hook: Hook) -> bool:
        """Register a hook"""
        try:
            if hook.hook_type not in self.hooks:
                self.hooks[hook.hook_type] = []
            
            # Check for duplicate names
            if hook.name in self.hook_names:
                logger.warning(f"Hook name {hook.name} already exists, skipping registration")
                return False
            
            # Add to registry
            self.hooks[hook.hook_type].append(hook)
            self.hook_names[hook.name] = hook
            
            # Sort by priority
            self.hooks[hook.hook_type].sort(key=lambda h: h.priority.value, reverse=True)
            
            logger.info(f"Registered hook {hook.name} for {hook.hook_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering hook {hook.name}: {str(e)}")
            return False
    
    def unregister(self, hook_name: str) -> bool:
        """Unregister a hook"""
        try:
            if hook_name not in self.hook_names:
                logger.warning(f"Hook {hook_name} not found")
                return False
            
            hook = self.hook_names[hook_name]
            
            # Remove from type registry
            if hook.hook_type in self.hooks:
                self.hooks[hook.hook_type].remove(hook)
            
            # Remove from name registry
            del self.hook_names[hook_name]
            
            logger.info(f"Unregistered hook {hook_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering hook {hook_name}: {str(e)}")
            return False
    
    def get_hooks(self, hook_type: HookType) -> List[Hook]:
        """Get hooks for a specific type"""
        return self.hooks.get(hook_type, [])
    
    def get_hook(self, hook_name: str) -> Optional[Hook]:
        """Get hook by name"""
        return self.hook_names.get(hook_name)
    
    def enable_hook(self, hook_name: str) -> bool:
        """Enable a hook"""
        hook = self.get_hook(hook_name)
        if hook:
            hook.enable()
            return True
        return False
    
    def disable_hook(self, hook_name: str) -> bool:
        """Disable a hook"""
        hook = self.get_hook(hook_name)
        if hook:
            hook.disable()
            return True
        return False
    
    def list_hooks(self) -> List[Dict[str, Any]]:
        """List all hooks"""
        hooks = []
        
        for hook in self.hook_names.values():
            hooks.append({
                'id': hook.id,
                'name': hook.name,
                'type': hook.hook_type.value,
                'priority': hook.priority.value,
                'enabled': hook.enabled
            })
        
        return hooks


class HookExecutor:
    """Executor for running hooks"""
    
    def __init__(self, registry: HookRegistry):
        self.registry = registry
        self.execution_history = []
        self.max_history = 1000
    
    def execute_hooks(self, hook_type: HookType, context: Dict[str, Any]) -> HookResult:
        """Execute all hooks for a type"""
        hooks = self.registry.get_hooks(hook_type)
        
        if not hooks:
            return HookResult(success=True, data="No hooks found")
        
        results = []
        
        for hook in hooks:
            if not hook.can_execute(context):
                continue
            
            start_time = timezone.now()
            
            try:
                result = hook.execute(context)
                
                # Record execution
                execution_record = {
                    'hook_name': hook.name,
                    'hook_type': hook_type.value,
                    'success': result.success,
                    'duration_ms': (timezone.now() - start_time).total_seconds() * 1000,
                    'timestamp': start_time.isoformat()
                }
                
                self._add_to_history(execution_record)
                
                results.append(result)
                
                # Stop execution if requested
                if result.stop_execution:
                    break
                
            except Exception as e:
                logger.error(f"Error executing hook {hook.name}: {str(e)}")
                
                # Record failed execution
                execution_record = {
                    'hook_name': hook.name,
                    'hook_type': hook_type.value,
                    'success': False,
                    'error': str(e),
                    'duration_ms': (timezone.now() - start_time).total_seconds() * 1000,
                    'timestamp': start_time.isoformat()
                }
                
                self._add_to_history(execution_record)
                
                results.append(HookResult(success=False, error=str(e)))
        
        return HookResult(success=True, data=results)
    
    def execute_hook(self, hook_name: str, context: Dict[str, Any]) -> HookResult:
        """Execute a specific hook"""
        hook = self.registry.get_hook(hook_name)
        
        if not hook:
            return HookResult(success=False, error=f"Hook {hook_name} not found")
        
        if not hook.can_execute(context):
            return HookResult(success=False, error="Hook cannot execute")
        
        start_time = timezone.now()
        
        try:
            result = hook.execute(context)
            
            # Record execution
            execution_record = {
                'hook_name': hook_name,
                'success': result.success,
                'duration_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': start_time.isoformat()
            }
            
            self._add_to_history(execution_record)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing hook {hook_name}: {str(e)}")
            
            # Record failed execution
            execution_record = {
                'hook_name': hook_name,
                'success': False,
                'error': str(e),
                'duration_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': start_time.isoformat()
            }
            
            self._add_to_history(execution_record)
            
            return HookResult(success=False, error=str(e))
    
    def _add_to_history(self, execution_record: Dict[str, Any]):
        """Add execution record to history"""
        self.execution_history.append(execution_record)
        
        # Trim history if too long
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_execution_history(self, hook_name: str = None, 
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history"""
        history = self.execution_history
        
        if hook_name:
            history = [r for r in history if r['hook_name'] == hook_name]
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda r: r['timestamp'], reverse=True)
        
        return history[:limit]
    
    def get_hook_stats(self) -> Dict[str, Any]:
        """Get hook execution statistics"""
        if not self.execution_history:
            return {}
        
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for r in self.execution_history if r['success'])
        failed_executions = total_executions - successful_executions
        
        avg_duration = sum(r.get('duration_ms', 0) for r in self.execution_history) / total_executions
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'success_rate': (successful_executions / total_executions) * 100,
            'average_duration_ms': avg_duration
        }


# Global hook registry and executor
hook_registry = HookRegistry()
hook_executor = HookExecutor(hook_registry)


# Hook decorators
def hook(hook_type: HookType, priority: HookPriority = HookPriority.NORMAL):
    """Decorator to register a function as a hook"""
    def decorator(func):
        hook_name = f"{func.__module__}.{func.__name__}"
        function_hook = FunctionHook(hook_name, hook_type, func, priority)
        hook_registry.register(function_hook)
        return func
    return decorator


def conditional_hook(hook_type: HookType, condition: Callable, 
                   priority: HookPriority = HookPriority.NORMAL):
    """Decorator to register a conditional hook"""
    def decorator(func):
        hook_name = f"{func.__module__}.{func.__name__}"
        function_hook = FunctionHook(hook_name, hook_type, func, priority)
        conditional_hook_obj = ConditionalHook(
            f"conditional_{hook_name}", hook_type, condition, function_hook, priority
        )
        hook_registry.register(conditional_hook_obj)
        return func
    return decorator


# Built-in hooks
@hook(HookType.OFFER_BEFORE_CREATE)
def validate_offer_data(context: Dict[str, Any]) -> HookResult:
    """Validate offer data before creation"""
    offer_data = context.get('offer_data', {})
    
    # Basic validation
    if not offer_data.get('title'):
        return HookResult(success=False, error="Offer title is required")
    
    if not offer_data.get('reward_amount') or offer_data['reward_amount'] <= 0:
        return HookResult(success=False, error="Reward amount must be positive")
    
    return HookResult(success=True, data="Offer data validated")


@hook(HookType.CONVERSION_BEFORE_APPROVE)
def check_fraud_score(context: Dict[str, Any]) -> HookResult:
    """Check fraud score before approval"""
    conversion = context.get('conversion')
    
    if conversion and conversion.fraud_score >= 70:
        return HookResult(
            success=False,
            error="High fraud score detected",
            stop_execution=True
        )
    
    return HookResult(success=True, data="Fraud score checked")


@hook(HookType.REWARD_BEFORE_APPROVE)
def check_user_balance(context: Dict[str, Any]) -> HookResult:
    """Check user balance before reward approval"""
    reward = context.get('reward')
    
    if reward:
        # This would check user's wallet balance
        # For now, just return success
        pass
    
    return HookResult(success=True, data="User balance checked")


@hook(HookType.FRAUD_BEFORE_DETECTION)
def log_fraud_detection(context: Dict[str, Any]) -> HookResult:
    """Log fraud detection attempt"""
    conversion_id = context.get('conversion_id')
    tenant_id = context.get('tenant_id')
    
    logger.info(f"Starting fraud detection for conversion {conversion_id} in tenant {tenant_id}")
    
    return HookResult(success=True, data="Fraud detection logged")


@hook(HookType.CACHE_AFTER_CLEAR)
def log_cache_clear(context: Dict[str, Any]) -> HookResult:
    """Log cache clearing"""
    cache_keys = context.get('cache_keys', [])
    tenant_id = context.get('tenant_id')
    
    logger.info(f"Cleared {len(cache_keys)} cache keys for tenant {tenant_id}")
    
    return HookResult(success=True, data="Cache clear logged")


# Hook helper functions
def execute_offer_hooks(hook_type: HookType, offer_data: Dict[str, Any], 
                       tenant_id: str = None) -> HookResult:
    """Execute offer-related hooks"""
    context = {
        'offer_data': offer_data,
        'tenant_id': tenant_id,
        'timestamp': timezone.now().isoformat()
    }
    
    return hook_executor.execute_hooks(hook_type, context)


def execute_conversion_hooks(hook_type: HookType, conversion, 
                           tenant_id: str = None) -> HookResult:
    """Execute conversion-related hooks"""
    context = {
        'conversion': conversion,
        'tenant_id': tenant_id,
        'timestamp': timezone.now().isoformat()
    }
    
    return hook_executor.execute_hooks(hook_type, context)


def execute_reward_hooks(hook_type: HookType, reward, 
                       tenant_id: str = None) -> HookResult:
    """Execute reward-related hooks"""
    context = {
        'reward': reward,
        'tenant_id': tenant_id,
        'timestamp': timezone.now().isoformat()
    }
    
    return hook_executor.execute_hooks(hook_type, context)


def execute_user_hooks(hook_type: HookType, user, 
                     tenant_id: str = None, **kwargs) -> HookResult:
    """Execute user-related hooks"""
    context = {
        'user': user,
        'tenant_id': tenant_id,
        'timestamp': timezone.now().isoformat()
    }
    context.update(kwargs)
    
    return hook_executor.execute_hooks(hook_type, context)


def execute_network_hooks(hook_type: HookType, network, 
                        tenant_id: str = None, **kwargs) -> HookResult:
    """Execute network-related hooks"""
    context = {
        'network': network,
        'tenant_id': tenant_id,
        'timestamp': timezone.now().isoformat()
    }
    context.update(kwargs)
    
    return hook_executor.execute_hooks(hook_type, context)


# Export all classes and functions
__all__ = [
    # Enums
    'HookType',
    'HookPriority',
    
    # Classes
    'HookResult',
    'Hook',
    'FunctionHook',
    'ConditionalHook',
    'ChainedHook',
    'HookRegistry',
    'HookExecutor',
    
    # Global instances
    'hook_registry',
    'hook_executor',
    
    # Decorators
    'hook',
    'conditional_hook',
    
    # Helper functions
    'execute_offer_hooks',
    'execute_conversion_hooks',
    'execute_reward_hooks',
    'execute_user_hooks',
    'execute_network_hooks'
]
