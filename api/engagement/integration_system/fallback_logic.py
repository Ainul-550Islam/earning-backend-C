# engagement/integration_system/fallback_logic.py
"""
Fallback logic system for integration resilience.
Provides graceful degradation and alternative strategies.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, DEFAULT_CONFIG, CACHE_KEYS
)
from .integ_exceptions import IntegrationException, ExceptionUtils

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategy types."""
    IGNORE = "ignore"
    RETRY = "retry"
    ALTERNATIVE = "alternative"
    CACHE = "cache"
    DEFAULT_VALUE = "default_value"
    SIMPLIFIED = "simplified"
    DEGRADED = "degraded"
    MANUAL = "manual"


class FallbackTrigger(Enum):
    """Fallback trigger conditions."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


@dataclass
class FallbackRule:
    """Fallback rule definition."""
    id: str
    name: str
    trigger: FallbackTrigger
    strategy: FallbackStrategy
    priority: int = 0
    enabled: bool = True
    max_attempts: int = 3
    delay_ms: int = 1000
    conditions: Dict[str, Any] = field(default_factory=dict)
    alternative_handler: Optional[Callable] = None
    default_value: Any = None
    cache_key: Optional[str] = None
    cache_timeout: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class FallbackResult:
    """Fallback execution result."""
    success: bool
    strategy_used: FallbackStrategy
    original_error: Optional[Exception] = None
    fallback_data: Any = None
    execution_time_ms: float = 0.0
    attempt_count: int = 0
    rule_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseFallbackHandler(ABC):
    """Base fallback handler class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute fallback logic."""
        pass
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return True


class RetryFallbackHandler(BaseFallbackHandler):
    """Retry fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute retry logic."""
        start_time = time.time()
        
        try:
            # Get the original function to retry
            func = context.get('function')
            if not func:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.RETRY,
                    original_error=original_error,
                    message="No function to retry",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Check if we should retry
            attempt_count = context.get('attempt_count', 0)
            if attempt_count >= rule.max_attempts:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.RETRY,
                    original_error=original_error,
                    attempt_count=attempt_count,
                    message=f"Max retries ({rule.max_attempts}) exceeded",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Add delay
            if rule.delay_ms > 0:
                time.sleep(rule.delay_ms / 1000)
            
            # Retry the function
            args = context.get('args', ())
            kwargs = context.get('kwargs', {})
            
            result = func(*args, **kwargs)
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.RETRY,
                fallback_data=result,
                attempt_count=attempt_count + 1,
                message=f"Retry successful after {attempt_count + 1} attempts",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.RETRY,
                original_error=exc,
                attempt_count=context.get('attempt_count', 0) + 1,
                message=f"Retry failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.RETRY


class CacheFallbackHandler(BaseFallbackHandler):
    """Cache fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute cache fallback logic."""
        start_time = time.time()
        
        try:
            if not rule.cache_key:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.CACHE,
                    original_error=original_error,
                    message="No cache key specified",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Try to get from cache
            cached_data = cache.get(rule.cache_key)
            
            if cached_data is not None:
                return FallbackResult(
                    success=True,
                    strategy_used=FallbackStrategy.CACHE,
                    fallback_data=cached_data,
                    message="Retrieved from cache",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.CACHE,
                    original_error=original_error,
                    message="No cached data available",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.CACHE,
                original_error=exc,
                message=f"Cache fallback failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.CACHE


class AlternativeFallbackHandler(BaseFallbackHandler):
    """Alternative fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute alternative logic."""
        start_time = time.time()
        
        try:
            if not rule.alternative_handler:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.ALTERNATIVE,
                    original_error=original_error,
                    message="No alternative handler specified",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Execute alternative handler
            result = rule.alternative_handler(context, original_error)
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.ALTERNATIVE,
                fallback_data=result,
                message="Alternative handler succeeded",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.ALTERNATIVE,
                original_error=exc,
                message=f"Alternative handler failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.ALTERNATIVE


class DefaultValueFallbackHandler(BaseFallbackHandler):
    """Default value fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute default value logic."""
        start_time = time.time()
        
        try:
            if rule.default_value is None:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.DEFAULT_VALUE,
                    original_error=original_error,
                    message="No default value specified",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.DEFAULT_VALUE,
                fallback_data=rule.default_value,
                message="Using default value",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.DEFAULT_VALUE,
                original_error=exc,
                message=f"Default value fallback failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.DEFAULT_VALUE


class SimplifiedFallbackHandler(BaseFallbackHandler):
    """Simplified fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute simplified logic."""
        start_time = time.time()
        
        try:
            # Get original data
            original_data = context.get('data', {})
            
            # Apply simplification
            simplified_data = self._simplify_data(original_data)
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.SIMPLIFIED,
                fallback_data=simplified_data,
                message="Data simplified",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.SIMPLIFIED,
                original_error=exc,
                message=f"Simplification failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.SIMPLIFIED
    
    def _simplify_data(self, data: Any) -> Any:
        """Simplify data structure."""
        if isinstance(data, dict):
            # Keep only essential fields
            essential_fields = ['id', 'name', 'status', 'created_at']
            simplified = {}
            
            for field in essential_fields:
                if field in data:
                    value = data[field]
                    if isinstance(value, (dict, list)):
                        # Simplify nested structures
                        simplified[field] = str(value)[:100]  # Truncate
                    else:
                        simplified[field] = value
            
            return simplified
        elif isinstance(data, list):
            # Limit list size
            return data[:10]  # Keep only first 10 items
        else:
            return str(data)[:100]  # Truncate to 100 characters


class DegradedFallbackHandler(BaseFallbackHandler):
    """Degraded service fallback handler."""
    
    def execute(self, rule: FallbackRule, context: Dict[str, Any], 
                 original_error: Exception = None) -> FallbackResult:
        """Execute degraded service logic."""
        start_time = time.time()
        
        try:
            # Return degraded response
            degraded_response = {
                'status': 'degraded',
                'message': 'Service is currently degraded',
                'timestamp': timezone.now().isoformat(),
                'original_error': str(original_error) if original_error else None
            }
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.DEGRADED,
                fallback_data=degraded_response,
                message="Service degraded gracefully",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.DEGRADED,
                original_error=exc,
                message=f"Degraded fallback failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def can_handle(self, rule: FallbackRule, context: Dict[str, Any]) -> bool:
        """Check if handler can handle rule."""
        return rule.strategy == FallbackStrategy.DEGRADED


class FallbackManager:
    """Manager for fallback logic."""
    
    def __init__(self):
        self.rules: List[FallbackRule] = []
        self.handlers: Dict[FallbackStrategy, BaseFallbackHandler] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.FallbackManager")
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default fallback handlers."""
        self.handlers[FallbackStrategy.RETRY] = RetryFallbackHandler('retry')
        self.handlers[FallbackStrategy.CACHE] = CacheFallbackHandler('cache')
        self.handlers[FallbackStrategy.ALTERNATIVE] = AlternativeFallbackHandler('alternative')
        self.handlers[FallbackStrategy.DEFAULT_VALUE] = DefaultValueFallbackHandler('default_value')
        self.handlers[FallbackStrategy.SIMPLIFIED] = SimplifiedFallbackHandler('simplified')
        self.handlers[FallbackStrategy.DEGRADED] = DegradedFallbackHandler('degraded')
    
    def add_rule(self, rule: FallbackRule) -> bool:
        """Add fallback rule."""
        try:
            with self._lock:
                self.rules.append(rule)
                self.rules.sort(key=lambda r: r.priority, reverse=True)
                self.logger.info(f"Added fallback rule: {rule.name}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to add fallback rule {rule.name}: {exc}")
            return False
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove fallback rule."""
        try:
            with self._lock:
                self.rules = [r for r in self.rules if r.id != rule_id]
                self.logger.info(f"Removed fallback rule: {rule_id}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to remove fallback rule {rule_id}: {exc}")
            return False
    
    def execute_fallback(self, exception: Exception, context: Dict[str, Any]) -> FallbackResult:
        """Execute fallback logic for exception."""
        start_time = time.time()
        
        try:
            # Determine trigger type from exception
            trigger = self._get_trigger_type(exception)
            
            # Find matching rules
            matching_rules = self._find_matching_rules(trigger, exception, context)
            
            if not matching_rules:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.IGNORE,
                    original_error=exception,
                    message="No matching fallback rules found",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Try rules in priority order
            for rule in matching_rules:
                handler = self.handlers.get(rule.strategy)
                if not handler:
                    self.logger.warning(f"No handler for strategy {rule.strategy}")
                    continue
                
                if not handler.can_handle(rule, context):
                    self.logger.warning(f"Handler cannot handle rule {rule.name}")
                    continue
                
                try:
                    # Update rule statistics
                    rule.usage_count += 1
                    
                    # Execute fallback
                    result = handler.execute(rule, context, exception)
                    result.rule_id = rule.id
                    
                    # Update rule statistics
                    if result.success:
                        rule.success_count += 1
                    else:
                        rule.failure_count += 1
                    
                    rule.updated_at = timezone.now()
                    
                    return result
                    
                except Exception as exc:
                    self.logger.error(f"Handler {handler.name} failed for rule {rule.name}: {exc}")
                    rule.failure_count += 1
                    rule.updated_at = timezone.now()
                    continue
            
            # No fallback succeeded
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.IGNORE,
                original_error=exception,
                message="All fallback attempts failed",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as exc:
            self.logger.error(f"Fallback execution failed: {exc}")
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.IGNORE,
                original_error=exc,
                message=f"Fallback execution failed: {str(exc)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _get_trigger_type(self, exception: Exception) -> FallbackTrigger:
        """Get trigger type from exception."""
        if isinstance(exception, IntegrationException):
            # Map integration exceptions to triggers
            exception_type_map = {
                TimeoutError: FallbackTrigger.TIMEOUT,
                ConnectionError: FallbackTrigger.CONNECTION_ERROR,
                AuthenticationError: FallbackTrigger.AUTHENTICATION_ERROR,
                AuthorizationError: FallbackTrigger.AUTHORIZATION_ERROR,
                DataValidationError: FallbackTrigger.VALIDATION_ERROR,
                RateLimitError: FallbackTrigger.RATE_LIMIT,
                SystemOverloadError: FallbackTrigger.SYSTEM_ERROR,
            }
            
            return exception_type_map.get(type(exception), FallbackTrigger.SYSTEM_ERROR)
        else:
            return FallbackTrigger.SYSTEM_ERROR
    
    def _find_matching_rules(self, trigger: FallbackTrigger, exception: Exception, 
                           context: Dict[str, Any]) -> List[FallbackRule]:
        """Find matching fallback rules."""
        matching_rules = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check trigger match
            if rule.trigger != trigger:
                continue
            
            # Check conditions
            if not self._check_conditions(rule.conditions, exception, context):
                continue
            
            matching_rules.append(rule)
        
        return matching_rules
    
    def _check_conditions(self, conditions: Dict[str, Any], exception: Exception, 
                         context: Dict[str, Any]) -> bool:
        """Check if conditions are met."""
        if not conditions:
            return True
        
        # Check integration type
        if 'integration_type' in conditions:
            integration_type = context.get('integration_type')
            if integration_type != conditions['integration_type']:
                return False
        
        # Check operation
        if 'operation' in conditions:
            operation = context.get('operation')
            if operation != conditions['operation']:
                return False
        
        # Check error type
        if 'error_type' in conditions:
            error_type = conditions['error_type']
            if type(exception).__name__ != error_type:
                return False
        
        # Check custom conditions
        if 'custom' in conditions:
            custom_condition = conditions['custom']
            if callable(custom_condition):
                return custom_condition(exception, context)
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        with self._lock:
            total_rules = len(self.rules)
            enabled_rules = sum(1 for r in self.rules if r.enabled)
            
            rule_stats = []
            for rule in self.rules:
                success_rate = (rule.success_count / rule.usage_count * 100) if rule.usage_count > 0 else 0
                rule_stats.append({
                    'id': rule.id,
                    'name': rule.name,
                    'trigger': rule.trigger.value,
                    'strategy': rule.strategy.value,
                    'enabled': rule.enabled,
                    'usage_count': rule.usage_count,
                    'success_count': rule.success_count,
                    'failure_count': rule.failure_count,
                    'success_rate': success_rate,
                    'last_updated': rule.updated_at.isoformat()
                })
            
            return {
                'total_rules': total_rules,
                'enabled_rules': enabled_rules,
                'rule_statistics': rule_stats,
                'last_updated': timezone.now().isoformat()
            }
    
    def reset_statistics(self):
        """Reset all statistics."""
        with self._lock:
            for rule in self.rules:
                rule.usage_count = 0
                rule.success_count = 0
                rule.failure_count = 0
                rule.updated_at = timezone.now()
    
    def add_handler(self, strategy: FallbackStrategy, handler: BaseFallbackHandler):
        """Add custom fallback handler."""
        self.handlers[strategy] = handler
        self.logger.info(f"Added custom handler for strategy: {strategy}")


# Fallback utilities
class FallbackUtils:
    """Utilities for fallback management."""
    
    @staticmethod
    def create_rule(rule_id: str, name: str, trigger: FallbackTrigger, 
                   strategy: FallbackStrategy, **kwargs) -> FallbackRule:
        """Create fallback rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=trigger,
            strategy=strategy,
            **kwargs
        )
    
    @staticmethod
    def retry_rule(rule_id: str, name: str, max_retries: int = 3, 
                  delay_ms: int = 1000, **kwargs) -> FallbackRule:
        """Create retry rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.CONNECTION_ERROR,
            strategy=FallbackStrategy.RETRY,
            max_attempts=max_retries,
            delay_ms=delay_ms,
            **kwargs
        )
    
    @staticmethod
    def cache_rule(rule_id: str, name: str, cache_key: str, 
                 cache_timeout: int = 300, **kwargs) -> FallbackRule:
        """Create cache rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.CONNECTION_ERROR,
            strategy=FallbackStrategy.CACHE,
            cache_key=cache_key,
            cache_timeout=cache_timeout,
            **kwargs
        )
    
    @staticmethod
    def alternative_rule(rule_id: str, name: str, alternative_handler: Callable,
                          **kwargs) -> FallbackRule:
        """Create alternative rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.CONNECTION_ERROR,
            strategy=FallbackStrategy.ALTERNATIVE,
            alternative_handler=alternative_handler,
            **kwargs
        )
    
    @staticmethod
    def default_value_rule(rule_id: str, name: str, default_value: Any,
                           **kwargs) -> FallbackRule:
        """Create default value rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.CONNECTION_ERROR,
            strategy=FallbackStrategy.DEFAULT_VALUE,
            default_value=default_value,
            **kwargs
        )
    
    @staticmethod
    def simplified_rule(rule_id: str, name: str, **kwargs) -> FallbackRule:
        """Create simplified rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.SYSTEM_ERROR,
            strategy=FallbackStrategy.SIMPLIFIED,
            **kwargs
        )
    
    @staticmethod
    def degraded_rule(rule_id: str, name: str, **kwargs) -> FallbackRule:
        """Create degraded rule."""
        return FallbackRule(
            id=rule_id,
            name=name,
            trigger=FallbackTrigger.SYSTEM_ERROR,
            strategy=FallbackStrategy.DEGRADED,
            **kwargs
        )


# Decorator for fallback handling
def with_fallback(rules: List[FallbackRule] = None, fallback_manager: FallbackManager = None):
    """Decorator to add fallback handling to function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Use provided fallback manager or default
                manager = fallback_manager or fallback_manager
                
                # Add rules if provided
                if rules:
                    for rule in rules:
                        manager.add_rule(rule)
                
                # Create context
                context = {
                    'function': func,
                    'args': args,
                    'kwargs': kwargs,
                    'attempt_count': kwargs.get('attempt_count', 0)
                }
                
                # Execute fallback
                result = manager.execute_fallback(exc, context)
                
                if result.success:
                    return result.fallback_data
                else:
                    raise exc
        
        return wrapper
    return decorator


# Global fallback manager instance
fallback_manager = FallbackManager()
