# =============================================================================
# fraud_detection/hooks.py
# =============================================================================
"""
Hooks System for Fraud Detection System.

Provides extensible hook system for custom fraud detection
logic, third-party integrations, and workflow customization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from django.conf import settings
from django.utils import timezone

from api.fraud_detection.exceptions import HookError


logger = logging.getLogger(__name__)


class HookPoint(Enum):
    """Hook points in the fraud detection workflow."""
    PRE_FRAUD_DETECTION = "pre_fraud_detection"
    POST_FRAUD_DETECTION = "post_fraud_detection"
    PRE_CASE_CREATION = "pre_case_creation"
    POST_CASE_CREATION = "post_case_creation"
    PRE_ALERT_GENERATION = "pre_alert_generation"
    POST_ALERT_GENERATION = "post_alert_generation"
    PRE_SANCTIONS_CHECK = "pre_sanctions_check"
    POST_SANCTIONS_CHECK = "post_sanctions_check"
    PRE_COMPLIANCE_CHECK = "pre_compliance_check"
    POST_COMPLIANCE_CHECK = "post_compliance_check"
    PRE_RISK_UPDATE = "pre_risk_update"
    POST_RISK_UPDATE = "post_risk_update"
    PRE_USER_SUSPENSION = "pre_user_suspension"
    POST_USER_SUSPENSION = "post_user_suspension"
    PRE_TRANSACTION_BLOCK = "pre_transaction_block"
    POST_TRANSACTION_BLOCK = "post_transaction_block"


class HookPriority(Enum):
    """Hook execution priority."""
    HIGHEST = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    LOWEST = 0


@dataclass
class HookResult:
    """Data class for hook execution results."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: Optional[List[str]] = None
    should_continue: bool = True
    should_abort: bool = False
    metadata: Optional[Dict[str, Any]] = None


class Hook(ABC):
    """Abstract base class for fraud detection hooks."""
    
    def __init__(self, name: str, priority: HookPriority = HookPriority.NORMAL):
        """Initialize hook."""
        self.name = name
        self.priority = priority
        self.enabled = True
        self.execution_count = 0
        self.last_executed = None
        self.error_count = 0
        self.last_error = None
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute hook logic.
        
        Args:
            context: Hook execution context
            
        Returns:
            Hook execution result
        """
        pass
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if hook can execute in given context.
        
        Args:
            context: Hook execution context
            
        Returns:
            True if hook can execute
        """
        return self.enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hook execution statistics."""
        return {
            'name': self.name,
            'priority': self.priority.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'error_count': self.error_count,
            'last_error': self.last_error
        }


class HookRegistry:
    """Registry for managing fraud detection hooks."""
    
    def __init__(self):
        """Initialize hook registry."""
        self.hooks: Dict[HookPoint, List[Hook]] = {}
        self.global_hooks: List[Hook] = []
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history = getattr(settings, 'FRAUD_HOOK_MAX_HISTORY', 1000)
    
    def register_hook(self, hook_point: HookPoint, hook: Hook):
        """
        Register hook for specific hook point.
        
        Args:
            hook_point: Hook point to register for
            hook: Hook instance
        """
        if hook_point not in self.hooks:
            self.hooks[hook_point] = []
        
        self.hooks[hook_point].append(hook)
        
        # Sort by priority (highest first)
        self.hooks[hook_point].sort(key=lambda h: h.priority.value, reverse=True)
        
        logger.info(f"Registered hook '{hook.name}' for hook point '{hook_point.value}'")
    
    def register_global_hook(self, hook: Hook):
        """
        Register global hook (executed for all hook points).
        
        Args:
            hook: Hook instance
        """
        self.global_hooks.append(hook)
        
        # Sort by priority (highest first)
        self.global_hooks.sort(key=lambda h: h.priority.value, reverse=True)
        
        logger.info(f"Registered global hook '{hook.name}'")
    
    def unregister_hook(self, hook_point: HookPoint, hook_name: str):
        """
        Unregister hook by name.
        
        Args:
            hook_point: Hook point
            hook_name: Hook name
        """
        if hook_point in self.hooks:
            self.hooks[hook_point] = [
                hook for hook in self.hooks[hook_point]
                if hook.name != hook_name
            ]
            logger.info(f"Unregistered hook '{hook_name}' from hook point '{hook_point.value}'")
    
    def unregister_global_hook(self, hook_name: str):
        """
        Unregister global hook by name.
        
        Args:
            hook_name: Hook name
        """
        self.global_hooks = [
            hook for hook in self.global_hooks
            if hook.name != hook_name
        ]
        logger.info(f"Unregistered global hook '{hook_name}'")
    
    def execute_hooks(self, hook_point: HookPoint, context: Dict[str, Any]) -> List[HookResult]:
        """
        Execute all hooks for a hook point.
        
        Args:
            hook_point: Hook point to execute
            context: Execution context
            
        Returns:
            List of hook execution results
        """
        results = []
        
        # Execute global hooks first
        for hook in self.global_hooks:
            if hook.can_execute(context):
                result = self._execute_single_hook(hook, hook_point, context)
                results.append(result)
        
        # Execute hook-specific hooks
        if hook_point in self.hooks:
            for hook in self.hooks[hook_point]:
                if hook.can_execute(context):
                    result = self._execute_single_hook(hook, hook_point, context)
                    results.append(result)
        
        # Record execution
        self._record_execution(hook_point, context, results)
        
        return results
    
    def _execute_single_hook(self, hook: Hook, hook_point: HookPoint, context: Dict[str, Any]) -> HookResult:
        """Execute single hook."""
        start_time = timezone.now()
        
        try:
            hook.execution_count += 1
            hook.last_executed = start_time
            
            result = hook.execute(context)
            
            # Update error count if failed
            if not result.success:
                hook.error_count += 1
                hook.last_error = result.error
            
            # Record execution time
            execution_time = (timezone.now() - start_time).total_seconds()
            
            logger.debug(f"Hook '{hook.name}' executed in {execution_time:.3f}s - Success: {result.success}")
            
            return result
            
        except Exception as e:
            hook.error_count += 1
            hook.last_error = str(e)
            
            logger.error(f"Hook '{hook.name}' execution failed: {e}")
            
            return HookResult(
                success=False,
                error=str(e),
                should_continue=True
            )
    
    def _record_execution(self, hook_point: HookPoint, context: Dict[str, Any], results: List[HookResult]):
        """Record hook execution for audit."""
        execution_record = {
            'hook_point': hook_point.value,
            'timestamp': timezone.now().isoformat(),
            'context_keys': list(context.keys()),
            'hooks_executed': len(results),
            'successful_hooks': len([r for r in results if r.success]),
            'failed_hooks': len([r for r in results if not r.success]),
            'aborted_hooks': len([r for r in results if r.should_abort]),
            'results': [
                {
                    'hook_name': r.metadata.get('hook_name', 'unknown') if r.metadata else 'unknown',
                    'success': r.success,
                    'execution_time': r.metadata.get('execution_time', 0) if r.metadata else 0
                }
                for r in results
            ]
        }
        
        self.execution_history.append(execution_record)
        
        # Trim history if needed
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_hook_stats(self, hook_point: Optional[HookPoint] = None) -> Dict[str, Any]:
        """Get hook execution statistics."""
        stats = {
            'total_hooks': len(self.global_hooks),
            'global_hooks': [hook.get_stats() for hook in self.global_hooks],
            'hook_points': {}
        }
        
        for point, hooks in self.hooks.items():
            stats['hook_points'][point.value] = {
                'hook_count': len(hooks),
                'hooks': [hook.get_stats() for hook in hooks]
            }
        
        return stats
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get hook execution history."""
        return self.execution_history[-limit:] if self.execution_history else []


# Built-in hooks
class LoggingHook(Hook):
    """Hook for logging fraud detection events."""
    
    def __init__(self):
        super().__init__("logging_hook", HookPriority.LOWEST)
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute logging hook."""
        try:
            hook_point = context.get('hook_point', 'unknown')
            user_id = context.get('user_id')
            transaction_id = context.get('transaction_id')
            
            log_data = {
                'hook_point': hook_point,
                'user_id': user_id,
                'transaction_id': transaction_id,
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Fraud detection hook executed: {log_data}")
            
            return HookResult(
                success=True,
                data={'logged': True},
                metadata={'hook_name': self.name}
            )
            
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
                metadata={'hook_name': self.name}
            )
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if hook can execute."""
        return self.enabled and 'hook_point' in context


class MetricsHook(Hook):
    """Hook for collecting fraud detection metrics."""
    
    def __init__(self):
        super().__init__("metrics_hook", HookPriority.LOW)
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute metrics hook."""
        try:
            hook_point = context.get('hook_point', 'unknown')
            user_id = context.get('user_id')
            risk_score = context.get('risk_score', 0)
            
            # Record metric
            from api.fraud_detection.monitoring import record_fraud_metric
            record_fraud_metric('hook_execution', 1, {
                'hook_point': hook_point,
                'user_id': user_id,
                'risk_score': risk_score,
                'hook_name': self.name
            })
            
            return HookResult(
                success=True,
                data={'metric_recorded': True},
                metadata={'hook_name': self.name}
            )
            
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
                metadata={'hook_name': self.name}
            )


class ValidationHook(Hook):
    """Hook for validating fraud detection data."""
    
    def __init__(self):
        super().__init__("validation_hook", HookPriority.HIGHEST)
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute validation hook."""
        try:
            user_id = context.get('user_id')
            transaction_data = context.get('transaction_data', {})
            
            # Validate required fields
            if not user_id:
                return HookResult(
                    success=False,
                    error="User ID is required",
                    should_abort=True,
                    metadata={'hook_name': self.name}
                )
            
            # Validate transaction amount
            amount = transaction_data.get('amount', 0)
            if amount < 0:
                return HookResult(
                    success=False,
                    error="Transaction amount cannot be negative",
                    should_abort=True,
                    metadata={'hook_name': self.name}
                )
            
            return HookResult(
                success=True,
                data={'validation_passed': True},
                metadata={'hook_name': self.name}
            )
            
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
                should_abort=True,
                metadata={'hook_name': self.name}
            )


class ExternalIntegrationHook(Hook):
    """Hook for external system integrations."""
    
    def __init__(self, integration_name: str, webhook_url: str):
        super().__init__(f"external_integration_{integration_name}", HookPriority.NORMAL)
        self.integration_name = integration_name
        self.webhook_url = webhook_url
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute external integration hook."""
        try:
            # Prepare webhook payload
            payload = {
                'integration': self.integration_name,
                'hook_point': context.get('hook_point', 'unknown'),
                'timestamp': timezone.now().isoformat(),
                'data': context
            }
            
            # Send webhook (simplified)
            # In practice, this would use requests or similar
            logger.info(f"Would send webhook to {self.webhook_url}: {payload}")
            
            return HookResult(
                success=True,
                data={'webhook_sent': True},
                metadata={'hook_name': self.name}
            )
            
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
                metadata={'hook_name': self.name}
            )


class CustomLogicHook(Hook):
    """Hook for custom fraud detection logic."""
    
    def __init__(self, name: str, logic_function: Callable[[Dict[str, Any]], HookResult], 
                 priority: HookPriority = HookPriority.NORMAL):
        super().__init__(name, priority)
        self.logic_function = logic_function
    
    def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute custom logic hook."""
        try:
            return self.logic_function(context)
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
                metadata={'hook_name': self.name}
            )


# Global hook registry
hook_registry = HookRegistry()

# Register built-in hooks
hook_registry.register_global_hook(LoggingHook())
hook_registry.register_global_hook(MetricsHook())
hook_registry.register_hook(HookPoint.PRE_FRAUD_DETECTION, ValidationHook())


# Hook execution convenience functions
def execute_pre_fraud_detection_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-fraud detection hooks."""
    context['hook_point'] = HookPoint.PRE_FRAUD_DETECTION.value
    return hook_registry.execute_hooks(HookPoint.PRE_FRAUD_DETECTION, context)


def execute_post_fraud_detection_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-fraud detection hooks."""
    context['hook_point'] = HookPoint.POST_FRAUD_DETECTION.value
    return hook_registry.execute_hooks(HookPoint.POST_FRAUD_DETECTION, context)


def execute_pre_case_creation_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-case creation hooks."""
    context['hook_point'] = HookPoint.PRE_CASE_CREATION.value
    return hook_registry.execute_hooks(HookPoint.PRE_CASE_CREATION, context)


def execute_post_case_creation_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-case creation hooks."""
    context['hook_point'] = HookPoint.POST_CASE_CREATION.value
    return hook_registry.execute_hooks(HookPoint.POST_CASE_CREATION, context)


def execute_pre_alert_generation_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-alert generation hooks."""
    context['hook_point'] = HookPoint.PRE_ALERT_GENERATION.value
    return hook_registry.execute_hooks(HookPoint.PRE_ALERT_GENERATION, context)


def execute_post_alert_generation_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-alert generation hooks."""
    context['hook_point'] = HookPoint.POST_ALERT_GENERATION.value
    return hook_registry.execute_hooks(HookPoint.POST_ALERT_GENERATION, context)


def execute_pre_sanctions_check_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-sanctions check hooks."""
    context['hook_point'] = HookPoint.PRE_SANCTIONS_CHECK.value
    return hook_registry.execute_hooks(HookPoint.PRE_SANCTIONS_CHECK, context)


def execute_post_sanctions_check_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-sanctions check hooks."""
    context['hook_point'] = HookPoint.POST_SANCTIONS_CHECK.value
    return hook_registry.execute_hooks(HookPoint.POST_SANCTIONS_CHECK, context)


def execute_pre_compliance_check_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-compliance check hooks."""
    context['hook_point'] = HookPoint.PRE_COMPLIANCE_CHECK.value
    return hook_registry.execute_hooks(HookPoint.PRE_COMPLIANCE_CHECK, context)


def execute_post_compliance_check_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-compliance check hooks."""
    context['hook_point'] = HookPoint.POST_COMPLIANCE_CHECK.value
    return hook_registry.execute_hooks(HookPoint.POST_COMPLIANCE_CHECK, context)


def execute_pre_risk_update_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute pre-risk update hooks."""
    context['hook_point'] = HookPoint.PRE_RISK_UPDATE.value
    return hook_registry.execute_hooks(HookPoint.PRE_RISK_UPDATE, context)


def execute_post_risk_update_hooks(context: Dict[str, Any]) -> List[HookResult]:
    """Execute post-risk update hooks."""
    context['hook_point'] = HookPoint.POST_RISK_UPDATE.value
    return hook_registry.execute_hooks(HookPoint.POST_RISK_UPDATE, context)


# Hook management functions
def register_custom_hook(hook_point: HookPoint, hook: Hook):
    """Register custom hook."""
    hook_registry.register_hook(hook_point, hook)


def register_custom_global_hook(hook: Hook):
    """Register custom global hook."""
    hook_registry.register_global_hook(hook)


def create_external_integration_hook(integration_name: str, webhook_url: str) -> ExternalIntegrationHook:
    """Create external integration hook."""
    return ExternalIntegrationHook(integration_name, webhook_url)


def create_custom_logic_hook(name: str, logic_function: Callable[[Dict[str, Any]], HookResult],
                           priority: HookPriority = HookPriority.NORMAL) -> CustomLogicHook:
    """Create custom logic hook."""
    return CustomLogicHook(name, logic_function, priority)


# Hook statistics and monitoring
def get_hook_statistics() -> Dict[str, Any]:
    """Get hook execution statistics."""
    return hook_registry.get_hook_stats()


def get_hook_execution_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Get hook execution history."""
    return hook_registry.get_execution_history(limit)


# Hook configuration from settings
def load_hooks_from_settings():
    """Load hook configuration from Django settings."""
    try:
        hook_configs = getattr(settings, 'FRAUD_DETECTION_HOOKS', {})
        
        for hook_point_name, hooks in hook_configs.items():
            try:
                hook_point = HookPoint(hook_point_name)
                
                for hook_config in hooks:
                    hook_type = hook_config.get('type', 'custom')
                    
                    if hook_type == 'external_integration':
                        integration_name = hook_config.get('integration_name')
                        webhook_url = hook_config.get('webhook_url')
                        
                        if integration_name and webhook_url:
                            hook = create_external_integration_hook(integration_name, webhook_url)
                            hook_registry.register_hook(hook_point, hook)
                    
                    elif hook_type == 'custom':
                        # Custom hooks would need to be defined in settings
                        # This is a placeholder for that functionality
                        pass
                        
            except ValueError as e:
                logger.error(f"Invalid hook point '{hook_point_name}': {e}")
                
    except Exception as e:
        logger.error(f"Error loading hooks from settings: {e}")


# Load hooks from settings on module import
load_hooks_from_settings()


_hook_registry_instance: Optional[HookRegistry] = None


def get_hook_registry() -> HookRegistry:
    """Return the process-wide HookRegistry singleton."""
    global _hook_registry_instance
    if _hook_registry_instance is None:
        _hook_registry_instance = HookRegistry()
    return _hook_registry_instance
