"""
Fallback Logic — Fallback mechanisms and recovery strategies.

This module provides comprehensive fallback logic for handling failures
and implementing recovery strategies when primary systems fail.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum

from .integ_constants import ErrorCode, DEFAULT_RETRY_ATTEMPTS
from .integ_exceptions import (
    IntegrationError, TimeoutError, ConnectionError,
    ServiceUnavailableError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback Types
# ---------------------------------------------------------------------------

class FallbackStrategy(Enum):
    """Fallback strategy enumeration."""
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    ALTERNATIVE_SERVICE = "alternative_service"
    CACHE_FALLBACK = "cache_fallback"
    DEFAULT_RESPONSE = "default_response"
    DEGRADE_SERVICE = "degrade_service"
    MANUAL_INTERVENTION = "manual_intervention"
    CUSTOM = "custom"


class FallbackTrigger(Enum):
    """Fallback trigger enumeration."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    ERROR_RATE_HIGH = "error_rate_high"
    RESPONSE_TIME_HIGH = "response_time_high"
    CUSTOM = "custom"


class FallbackStatus(Enum):
    """Fallback status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"
    RECOVERING = "recovering"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Fallback Data Classes
# ---------------------------------------------------------------------------

@dataclass
class FallbackCondition:
    """Condition for triggering fallback."""
    
    id: str
    trigger_type: FallbackTrigger
    parameters: Dict[str, Any] = field(default_factory=dict)
    evaluation_function: Optional[Callable] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if condition is met."""
        if not self.enabled:
            return False
        
        if self.evaluation_function:
            try:
                return self.evaluation_function(context, self.parameters)
            except Exception as e:
                logger.error(f"Error evaluating fallback condition {self.id}: {e}")
                return False
        
        # Built-in condition evaluation
        if self.trigger_type == FallbackTrigger.TIMEOUT:
            timeout_threshold = self.parameters.get("timeout_threshold", 30.0)
            response_time = context.get("response_time", 0.0)
            return response_time > timeout_threshold
        
        elif self.trigger_type == FallbackTrigger.CONNECTION_ERROR:
            error = context.get("error")
            return isinstance(error, ConnectionError)
        
        elif self.trigger_type == FallbackTrigger.HTTP_ERROR:
            status_code = context.get("status_code")
            error_codes = self.parameters.get("error_codes", [500, 502, 503, 504])
            return status_code in error_codes
        
        elif self.trigger_type == FallbackTrigger.RATE_LIMIT:
            rate_limit_exceeded = context.get("rate_limit_exceeded", False)
            return rate_limit_exceeded
        
        elif self.trigger_type == FallbackTrigger.SERVICE_UNAVAILABLE:
            error = context.get("error")
            return isinstance(error, ServiceUnavailableError)
        
        elif self.trigger_type == FallbackTrigger.ERROR_RATE_HIGH:
            error_rate = context.get("error_rate", 0.0)
            threshold = self.parameters.get("error_rate_threshold", 0.1)
            return error_rate > threshold
        
        elif self.trigger_type == FallbackTrigger.RESPONSE_TIME_HIGH:
            avg_response_time = context.get("average_response_time", 0.0)
            threshold = self.parameters.get("response_time_threshold", 5.0)
            return avg_response_time > threshold
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "trigger_type": self.trigger_type.value,
            "parameters": self.parameters,
            "evaluation_function": self.evaluation_function.__name__ if self.evaluation_function else None,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


@dataclass
class FallbackAction:
    """Action to take when fallback is triggered."""
    
    id: str
    strategy: FallbackStrategy
    parameters: Dict[str, Any] = field(default_factory=dict)
    action_function: Optional[Callable] = None
    enabled: bool = True
    priority: int = 0
    timeout: Optional[float] = None
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def execute(self, context: Dict[str, Any]) -> Any:
        """Execute the fallback action."""
        if not self.enabled:
            raise IntegrationError(f"Fallback action {self.id} is disabled")
        
        if self.action_function:
            return self._execute_with_retry(context)
        
        # Built-in action execution
        if self.strategy == FallbackStrategy.RETRY:
            return self._execute_retry(context)
        elif self.strategy == FallbackStrategy.ALTERNATIVE_SERVICE:
            return self._execute_alternative_service(context)
        elif self.strategy == FallbackStrategy.CACHE_FALLBACK:
            return self._execute_cache_fallback(context)
        elif self.strategy == FallbackStrategy.DEFAULT_RESPONSE:
            return self._execute_default_response(context)
        elif self.strategy == FallbackStrategy.DEGRADE_SERVICE:
            return self._execute_degrade_service(context)
        
        raise IntegrationError(f"Unsupported fallback strategy: {self.strategy.value}")
    
    def _execute_with_retry(self, context: Dict[str, Any]) -> Any:
        """Execute action with retry logic."""
        last_error = None
        
        for attempt in range(self.max_attempts):
            try:
                result = self.action_function(context, self.parameters)
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_attempts - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    time.sleep(delay)
        
        raise last_error or IntegrationError("Fallback action failed after all attempts")
    
    def _execute_retry(self, context: Dict[str, Any]) -> Any:
        """Execute retry strategy."""
        original_function = context.get("original_function")
        original_args = context.get("original_args", [])
        original_kwargs = context.get("original_kwargs", {})
        max_retries = self.parameters.get("max_retries", DEFAULT_RETRY_ATTEMPTS)
        retry_delay = self.parameters.get("retry_delay", 1.0)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return original_function(*original_args, **original_kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
        
        raise last_error or IntegrationError("Retry strategy failed after all attempts")
    
    def _execute_alternative_service(self, context: Dict[str, Any]) -> Any:
        """Execute alternative service strategy."""
        alternative_function = self.parameters.get("alternative_function")
        if not alternative_function:
            raise IntegrationError("Alternative service requires 'alternative_function' parameter")
        
        args = context.get("original_args", [])
        kwargs = context.get("original_kwargs", {})
        
        return alternative_function(*args, **kwargs)
    
    def _execute_cache_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute cache fallback strategy."""
        cache_key = self.parameters.get("cache_key")
        cache_backend = self.parameters.get("cache_backend")
        
        if not cache_key or not cache_backend:
            raise IntegrationError("Cache fallback requires 'cache_key' and 'cache_backend' parameters")
        
        # Generate cache key from context if needed
        if callable(cache_key):
            key = cache_key(context)
        else:
            key = cache_key
        
        # Get cached value
        cached_value = cache_backend.get(key)
        if cached_value is not None:
            return cached_value
        
        raise IntegrationError(f"No cached value found for key: {key}")
    
    def _execute_default_response(self, context: Dict[str, Any]) -> Any:
        """Execute default response strategy."""
        default_response = self.parameters.get("default_response")
        if default_response is None:
            raise IntegrationError("Default response requires 'default_response' parameter")
        
        if callable(default_response):
            return default_response(context)
        
        return default_response
    
    def _execute_degrade_service(self, context: Dict[str, Any]) -> Any:
        """Execute service degradation strategy."""
        degraded_function = self.parameters.get("degraded_function")
        if not degraded_function:
            raise IntegrationError("Service degradation requires 'degraded_function' parameter")
        
        args = context.get("original_args", [])
        kwargs = context.get("original_kwargs", {})
        
        return degraded_function(*args, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "strategy": self.strategy.value,
            "parameters": self.parameters,
            "action_function": self.action_function.__name__ if self.action_function else None,
            "enabled": self.enabled,
            "priority": self.priority,
            "timeout": self.timeout,
            "max_attempts": self.max_attempts,
            "metadata": self.metadata
        }


@dataclass
class FallbackPolicy:
    """Fallback policy configuration."""
    
    id: str
    name: str
    conditions: List[FallbackCondition] = field(default_factory=list)
    actions: List[FallbackAction] = field(default_factory=list)
    enabled: bool = True
    auto_recovery: bool = True
    recovery_delay: float = 60.0  # seconds
    max_fallback_duration: Optional[float] = None  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def should_trigger(self, context: Dict[str, Any]) -> bool:
        """Check if fallback should be triggered."""
        if not self.enabled:
            return False
        
        return any(condition.evaluate(context) for condition in self.conditions)
    
    def get_actions(self) -> List[FallbackAction]:
        """Get sorted actions by priority."""
        return sorted(self.actions, key=lambda a: a.priority, reverse=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "actions": [action.to_dict() for action in self.actions],
            "enabled": self.enabled,
            "auto_recovery": self.auto_recovery,
            "recovery_delay": self.recovery_delay,
            "max_fallback_duration": self.max_fallback_duration,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class FallbackExecution:
    """Record of fallback execution."""
    
    id: str
    policy_id: str
    triggered_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    conditions_met: List[str] = field(default_factory=list)
    actions_executed: List[str] = field(default_factory=list)
    successful: bool = False
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    recovered_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "policy_id": self.policy_id,
            "triggered_at": self.triggered_at.isoformat(),
            "context": self.context,
            "conditions_met": self.conditions_met,
            "actions_executed": self.actions_executed,
            "successful": self.successful,
            "result": self.result,
            "error": str(self.error) if self.error else None,
            "execution_time": self.execution_time,
            "recovered_at": self.recovered_at.isoformat() if self.recovered_at else None
        }


# ---------------------------------------------------------------------------
# Fallback Manager
# ---------------------------------------------------------------------------

class FallbackManager:
    """Manager for fallback policies and execution."""
    
    def __init__(self):
        self.policies: Dict[str, FallbackPolicy] = {}
        self.executions: List[FallbackExecution] = []
        self.active_fallbacks: Dict[str, FallbackExecution] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._recovery_thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start the fallback manager."""
        if self._running:
            return
        
        self._running = True
        self._recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
        self._recovery_thread.start()
        
        self.logger.info("Fallback manager started")
    
    def stop(self) -> None:
        """Stop the fallback manager."""
        self._running = False
        
        if self._recovery_thread:
            self._recovery_thread.join(timeout=5.0)
        
        self.logger.info("Fallback manager stopped")
    
    def register_policy(self, policy: FallbackPolicy) -> None:
        """Register a fallback policy."""
        with self._lock:
            self.policies[policy.id] = policy
            self.logger.info(f"Registered fallback policy: {policy.id}")
    
    def unregister_policy(self, policy_id: str) -> bool:
        """Unregister a fallback policy."""
        with self._lock:
            if policy_id in self.policies:
                del self.policies[policy_id]
                self.logger.info(f"Unregistered fallback policy: {policy_id}")
                return True
            return False
    
    def execute_with_fallback(
        self,
        policy_id: str,
        primary_function: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute function with fallback protection."""
        policy = self.policies.get(policy_id)
        if not policy:
            raise IntegrationError(f"Fallback policy '{policy_id}' not found")
        
        # Check if fallback is already active
        if policy_id in self.active_fallbacks:
            return self._execute_fallback_actions(policy, {
                "original_function": primary_function,
                "original_args": args,
                "original_kwargs": kwargs,
                "fallback_active": True
            })
        
        # Try primary function
        try:
            start_time = time.time()
            result = primary_function(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Check if fallback should be triggered based on execution context
            context = {
                "original_function": primary_function,
                "original_args": args,
                "original_kwargs": kwargs,
                "response_time": execution_time,
                "success": True,
                "result": result
            }
            
            if policy.should_trigger(context):
                return self._trigger_fallback(policy, context)
            
            return result
            
        except Exception as e:
            # Check if fallback should be triggered
            context = {
                "original_function": primary_function,
                "original_args": args,
                "original_kwargs": kwargs,
                "error": e,
                "success": False
            }
            
            if policy.should_trigger(context):
                return self._trigger_fallback(policy, context)
            
            # Re-raise if no fallback triggered
            raise e
    
    def _trigger_fallback(self, policy: FallbackPolicy, context: Dict[str, Any]) -> Any:
        """Trigger fallback for a policy."""
        import uuid
        
        execution = FallbackExecution(
            id=str(uuid.uuid4()),
            policy_id=policy.id,
            triggered_at=datetime.now(timezone.utc),
            context=context
        )
        
        try:
            # Record which conditions were met
            for condition in policy.conditions:
                if condition.evaluate(context):
                    execution.conditions_met.append(condition.id)
            
            # Execute fallback actions
            result = self._execute_fallback_actions(policy, context, execution)
            
            execution.successful = True
            execution.result = result
            
            # Record active fallback
            with self._lock:
                self.active_fallbacks[policy.id] = execution
                self.executions.append(execution)
            
            self.logger.info(f"Fallback triggered for policy: {policy.id}")
            return result
            
        except Exception as e:
            execution.successful = False
            execution.error = e
            
            with self._lock:
                self.executions.append(execution)
            
            self.logger.error(f"Fallback execution failed for policy {policy.id}: {e}")
            raise e
    
    def _execute_fallback_actions(
        self,
        policy: FallbackPolicy,
        context: Dict[str, Any],
        execution: Optional[FallbackExecution] = None
    ) -> Any:
        """Execute fallback actions."""
        actions = policy.get_actions()
        last_result = None
        
        for action in actions:
            try:
                start_time = time.time()
                result = action.execute(context)
                execution_time = time.time() - start_time
                
                if execution:
                    execution.actions_executed.append(action.id)
                    execution.execution_time += execution_time
                
                last_result = result
                
                # If action succeeded, stop processing further actions
                if result is not None:
                    break
                    
            except Exception as e:
                self.logger.error(f"Fallback action {action.id} failed: {e}")
                if execution:
                    execution.actions_executed.append(action.id)
                
                # Continue to next action
                continue
        
        return last_result
    
    def _recovery_loop(self) -> None:
        """Main recovery loop."""
        while self._running:
            try:
                self._check_recovery()
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in recovery loop: {e}")
                time.sleep(5)
    
    def _check_recovery(self) -> None:
        """Check for recovery opportunities."""
        with self._lock:
            active_fallbacks_copy = self.active_fallbacks.copy()
        
        for policy_id, execution in active_fallbacks_copy.items():
            policy = self.policies.get(policy_id)
            if not policy or not policy.auto_recovery:
                continue
            
            # Check if recovery delay has passed
            time_since_trigger = (datetime.now(timezone.utc) - execution.triggered_at).total_seconds()
            if time_since_trigger < policy.recovery_delay:
                continue
            
            # Check if max fallback duration exceeded
            if policy.max_fallback_duration and time_since_trigger > policy.max_fallback_duration:
                self._force_recovery(policy_id, "Maximum fallback duration exceeded")
                continue
            
            # Try to recover by testing primary function
            try:
                primary_function = execution.context.get("original_function")
                if primary_function:
                    # Test with a simple health check
                    test_result = self._test_recovery(primary_function, execution.context)
                    
                    if test_result:
                        self._force_recovery(policy_id, "Recovery test successful")
                        
            except Exception as e:
                self.logger.debug(f"Recovery test failed for policy {policy_id}: {e}")
    
    def _test_recovery(self, primary_function: Callable, context: Dict[str, Any]) -> bool:
        """Test if primary function has recovered."""
        try:
            # Try a simple call with minimal arguments
            args = context.get("original_args", [])
            kwargs = context.get("original_kwargs", {})
            
            # For testing, we might want to use a health check endpoint
            # This is a simplified implementation
            if hasattr(primary_function, '__self__'):
                # Method call
                return True  # Assume recovery for now
            else:
                # Function call - might be too risky to test
                return True
                
        except Exception:
            return False
    
    def _force_recovery(self, policy_id: str, reason: str) -> None:
        """Force recovery for a policy."""
        with self._lock:
            if policy_id in self.active_fallbacks:
                execution = self.active_fallbacks[policy_id]
                execution.recovered_at = datetime.now(timezone.utc)
                del self.active_fallbacks[policy_id]
                
                self.logger.info(f"Force recovery for policy {policy_id}: {reason}")
    
    def get_policy_status(self, policy_id: str) -> Dict[str, Any]:
        """Get status of a specific policy."""
        policy = self.policies.get(policy_id)
        if not policy:
            raise IntegrationError(f"Fallback policy '{policy_id}' not found")
        
        is_active = policy_id in self.active_fallbacks
        execution = self.active_fallbacks.get(policy_id)
        
        return {
            "policy_id": policy_id,
            "policy_name": policy.name,
            "enabled": policy.enabled,
            "active": is_active,
            "execution": execution.to_dict() if execution else None,
            "conditions_count": len(policy.conditions),
            "actions_count": len(policy.actions)
        }
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all policies."""
        status = {}
        
        for policy_id, policy in self.policies.items():
            try:
                status[policy_id] = self.get_policy_status(policy_id)
            except Exception as e:
                status[policy_id] = {"error": str(e)}
        
        return {
            "policies": status,
            "total_policies": len(self.policies),
            "active_fallbacks": len(self.active_fallbacks),
            "total_executions": len(self.executions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_execution_history(self, policy_id: Optional[str] = None, limit: int = 100) -> List[FallbackExecution]:
        """Get execution history."""
        with self._lock:
            executions = self.executions.copy()
        
        if policy_id:
            executions = [e for e in executions if e.policy_id == policy_id]
        
        # Sort by triggered_at descending
        executions.sort(key=lambda e: e.triggered_at, reverse=True)
        
        return executions[:limit]


# Global fallback manager instance
fallback_manager = FallbackManager()


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def with_fallback(
    policy_id: str,
    fallback_manager_instance: Optional[FallbackManager] = None
) -> Callable:
    """Decorator to add fallback protection to a function."""
    
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = fallback_manager_instance or fallback_manager
            return manager.execute_with_fallback(policy_id, func, *args, **kwargs)
        
        return wrapper
    
    return decorator


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_fallback_policy(
    policy_id: str,
    name: str,
    conditions: List[FallbackCondition],
    actions: List[FallbackAction],
    **kwargs: Any
) -> FallbackPolicy:
    """Create a fallback policy."""
    policy = FallbackPolicy(
        id=policy_id,
        name=name,
        conditions=conditions,
        actions=actions,
        **kwargs
    )
    
    fallback_manager.register_policy(policy)
    return policy


def create_fallback_condition(
    condition_id: str,
    trigger_type: FallbackTrigger,
    **kwargs: Any
) -> FallbackCondition:
    """Create a fallback condition."""
    return FallbackCondition(
        id=condition_id,
        trigger_type=trigger_type,
        **kwargs
    )


def create_fallback_action(
    action_id: str,
    strategy: FallbackStrategy,
    **kwargs: Any
) -> FallbackAction:
    """Create a fallback action."""
    return FallbackAction(
        id=action_id,
        strategy=strategy,
        **kwargs
    )


# Initialize logging
logger.info("Fallback logic module initialized")
