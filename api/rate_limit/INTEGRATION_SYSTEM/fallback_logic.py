"""
Fallback Logic - Graceful Degradation and Recovery

Fallback logic system for handling failures gracefully with multiple
fallback strategies, recovery mechanisms, and circuit breaker integration.
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, CircuitBreakerError
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategy types."""
    DISABLED = "disabled"              # No fallback
    IMMEDIATE = "immediate"            # Immediate fallback
    DELAYED = "delayed"                # Delayed fallback
    CONDITIONAL = "conditional"        # Conditional fallback
    CACHED = "cached"                  # Use cached response
    DEFAULT_VALUE = "default_value"    # Use default value
    ALTERNATIVE_SERVICE = "alternative_service"  # Use alternative service
    CUSTOM = "custom"                  # Custom fallback logic


class FallbackTrigger(Enum):
    """Fallback trigger conditions."""
    ERROR = "error"                    # Any error
    TIMEOUT = "timeout"                # Timeout error
    RATE_LIMIT = "rate_limit"          # Rate limit error
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker open
    SPECIFIC_ERROR = "specific_error"  # Specific error type
    CUSTOM_CONDITION = "custom_condition"  # Custom condition


@dataclass
class FallbackConfig:
    """Fallback configuration."""
    name: str
    strategy: FallbackStrategy
    trigger: FallbackTrigger
    max_attempts: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_retry_delay: float = 60.0
    timeout: int = 30
    cache_ttl: int = 300  # seconds
    default_value: Any = None
    alternative_service: Optional[str] = None
    custom_fallback: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    """Fallback execution result."""
    success: bool
    strategy_used: FallbackStrategy
    attempt_count: int = 0
    execution_time: float = 0.0
    result: Any = None
    error_message: Optional[str] = None
    fallback_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackAttempt:
    """Fallback attempt record."""
    attempt_id: str
    config_name: str
    original_error: str
    strategy_used: FallbackStrategy
    result: FallbackResult
    timestamp: datetime = field(default_factory=timezone.now)


class FallbackManager:
    """Fallback management system."""
    
    def __init__(self):
        self.fallback_configs: Dict[str, FallbackConfig] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.cache_backend = cache
        self.attempt_history: List[FallbackAttempt] = []
        self.statistics = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'fallbacks_by_strategy': {},
            'average_execution_time': 0.0,
            'last_fallback_time': None
        }
        self._lock = threading.RLock()
        
        # Register default fallback handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default fallback handlers."""
        self.fallback_handlers.update({
            'cached_response': self._handle_cached_fallback,
            'default_value': self._handle_default_value_fallback,
            'alternative_service': self._handle_alternative_service_fallback,
            'retry_with_backoff': self._handle_retry_with_backoff,
            'graceful_degradation': self._handle_graceful_degradation,
            'circuit_breaker_fallback': self._handle_circuit_breaker_fallback
        })
    
    def register_fallback_config(self, config: FallbackConfig):
        """Register fallback configuration."""
        self.fallback_configs[config.name] = config
        logger.info(f"Registered fallback config: {config.name}")
    
    def register_fallback_handler(self, name: str, handler: Callable):
        """Register custom fallback handler."""
        self.fallback_handlers[name] = handler
        logger.info(f"Registered fallback handler: {name}")
    
    def execute_fallback(self, config_name: str, original_error: Exception,
                        context: Dict[str, Any] = None) -> FallbackResult:
        """Execute fallback logic."""
        start_time = timezone.now()
        
        try:
            config = self.fallback_configs.get(config_name)
            if not config:
                raise IntegrationError(f"Fallback config not found: {config_name}")
            
            # Check if fallback should be triggered
            if not self._should_trigger_fallback(config, original_error):
                return FallbackResult(
                    success=False,
                    strategy_used=config.strategy,
                    error_message="Fallback conditions not met",
                    execution_time=(timezone.now() - start_time).total_seconds()
                )
            
            # Execute fallback based on strategy
            result = self._execute_fallback_strategy(config, original_error, context)
            
            # Update statistics
            self._update_statistics(result)
            
            # Record attempt
            attempt = FallbackAttempt(
                attempt_id=f"fallback_{config_name}_{timezone.now().timestamp()}",
                config_name=config_name,
                original_error=str(original_error),
                strategy_used=result.strategy_used,
                result=result
            )
            
            with self._lock:
                self.attempt_history.append(attempt)
                # Keep only last 1000 attempts
                if len(self.attempt_history) > 1000:
                    self.attempt_history.pop(0)
            
            return result
            
        except Exception as e:
            logger.error(f"Fallback execution failed: {str(e)}")
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.DISABLED,
                error_message=f"Fallback execution failed: {str(e)}",
                execution_time=(timezone.now() - start_time).total_seconds()
            )
    
    def _should_trigger_fallback(self, config: FallbackConfig, error: Exception) -> bool:
        """Check if fallback should be triggered."""
        if config.trigger == FallbackTrigger.ERROR:
            return True
        elif config.trigger == FallbackTrigger.TIMEOUT:
            return 'timeout' in str(error).lower()
        elif config.trigger == FallbackTrigger.RATE_LIMIT:
            return 'rate limit' in str(error).lower()
        elif config.trigger == FallbackTrigger.CIRCUIT_BREAKER:
            return isinstance(error, CircuitBreakerError)
        elif config.trigger == FallbackTrigger.SPECIFIC_ERROR:
            expected_error = config.conditions.get('error_type')
            return expected_error and expected_error in str(type(error).__name__)
        elif config.trigger == FallbackTrigger.CUSTOM_CONDITION:
            return self._evaluate_custom_condition(config, error)
        
        return False
    
    def _evaluate_custom_condition(self, config: FallbackConfig, error: Exception) -> bool:
        """Evaluate custom fallback condition."""
        condition_func = config.conditions.get('condition_function')
        if condition_func and condition_func in self.fallback_handlers:
            try:
                return self.fallback_handlers[condition_func](error, config.conditions)
            except Exception as e:
                logger.error(f"Custom condition evaluation failed: {str(e)}")
                return False
        
        return False
    
    def _execute_fallback_strategy(self, config: FallbackConfig, error: Exception,
                                  context: Dict[str, Any]) -> FallbackResult:
        """Execute specific fallback strategy."""
        strategy_start = timezone.now()
        
        try:
            if config.strategy == FallbackStrategy.DISABLED:
                return FallbackResult(
                    success=False,
                    strategy_used=config.strategy,
                    error_message="Fallback is disabled"
                )
            
            elif config.strategy == FallbackStrategy.IMMEDIATE:
                return self._execute_immediate_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.DELAYED:
                return self._execute_delayed_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.CONDITIONAL:
                return self._execute_conditional_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.CACHED:
                return self._execute_cached_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.DEFAULT_VALUE:
                return self._execute_default_value_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.ALTERNATIVE_SERVICE:
                return self._execute_alternative_service_fallback(config, error, context)
            
            elif config.strategy == FallbackStrategy.CUSTOM:
                return self._execute_custom_fallback(config, error, context)
            
            else:
                raise IntegrationError(f"Unknown fallback strategy: {config.strategy}")
                
        except Exception as e:
            logger.error(f"Fallback strategy execution failed: {str(e)}")
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message=f"Strategy execution failed: {str(e)}",
                execution_time=(timezone.now() - strategy_start).total_seconds()
            )
    
    def _execute_immediate_fallback(self, config: FallbackConfig, error: Exception,
                                   context: Dict[str, Any]) -> FallbackResult:
        """Execute immediate fallback."""
        if config.custom_fallback:
            return self._execute_custom_fallback(config, error, context)
        else:
            # Try default fallback strategies in order
            if config.alternative_service:
                return self._execute_alternative_service_fallback(config, error, context)
            elif config.cache_ttl > 0:
                return self._execute_cached_fallback(config, error, context)
            elif config.default_value is not None:
                return self._execute_default_value_fallback(config, error, context)
            else:
                return FallbackResult(
                    success=False,
                    strategy_used=config.strategy,
                    error_message="No immediate fallback available"
                )
    
    def _execute_delayed_fallback(self, config: FallbackConfig, error: Exception,
                                 context: Dict[str, Any]) -> FallbackResult:
        """Execute delayed fallback with retry logic."""
        return self._execute_retry_with_backoff(config, error, context)
    
    def _execute_conditional_fallback(self, config: FallbackConfig, error: Exception,
                                    context: Dict[str, Any]) -> FallbackResult:
        """Execute conditional fallback."""
        # Check conditions
        for condition, expected_value in config.conditions.items():
            if condition == 'error_count':
                recent_attempts = self._get_recent_attempts(config.name, 3600)  # Last hour
                if len(recent_attempts) >= expected_value:
                    return self._execute_immediate_fallback(config, error, context)
            elif condition == 'time_of_day':
                current_hour = timezone.now().hour
                if isinstance(expected_value, (list, tuple)):
                    if current_hour in expected_value:
                        return self._execute_immediate_fallback(config, error, context)
                elif current_hour == expected_value:
                    return self._execute_immediate_fallback(config, error, context)
        
        return FallbackResult(
            success=False,
            strategy_used=config.strategy,
            error_message="Conditional fallback conditions not met"
        )
    
    def _execute_cached_fallback(self, config: FallbackConfig, error: Exception,
                               context: Dict[str, Any]) -> FallbackResult:
        """Execute cached fallback."""
        cache_key = f"fallback_{config.name}"
        
        try:
            cached_result = self.cache_backend.get(cache_key)
            if cached_result:
                return FallbackResult(
                    success=True,
                    strategy_used=config.strategy,
                    result=cached_result,
                    fallback_data={'cache_hit': True, 'cache_key': cache_key}
                )
            else:
                return FallbackResult(
                    success=False,
                    strategy_used=config.strategy,
                    error_message="No cached data available",
                    fallback_data={'cache_hit': False, 'cache_key': cache_key}
                )
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message=f"Cache fallback failed: {str(e)}"
            )
    
    def _execute_default_value_fallback(self, config: FallbackConfig, error: Exception,
                                      context: Dict[str, Any]) -> FallbackResult:
        """Execute default value fallback."""
        return FallbackResult(
            success=True,
            strategy_used=config.strategy,
            result=config.default_value,
            fallback_data={'default_value_used': True}
        )
    
    def _execute_alternative_service_fallback(self, config: FallbackConfig, error: Exception,
                                             context: Dict[str, Any]) -> FallbackResult:
        """Execute alternative service fallback."""
        if not config.alternative_service:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message="No alternative service configured"
            )
        
        try:
            # This would integrate with the alternative service
            # For now, we'll simulate the call
            alternative_result = self._call_alternative_service(config.alternative_service, context)
            
            return FallbackResult(
                success=True,
                strategy_used=config.strategy,
                result=alternative_result,
                fallback_data={'alternative_service': config.alternative_service}
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message=f"Alternative service failed: {str(e)}"
            )
    
    def _execute_custom_fallback(self, config: FallbackConfig, error: Exception,
                                context: Dict[str, Any]) -> FallbackResult:
        """Execute custom fallback."""
        if not config.custom_fallback:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message="No custom fallback handler configured"
            )
        
        handler = self.fallback_handlers.get(config.custom_fallback)
        if not handler:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message=f"Custom fallback handler not found: {config.custom_fallback}"
            )
        
        try:
            result = handler(error, config, context)
            return FallbackResult(
                success=True,
                strategy_used=config.strategy,
                result=result,
                fallback_data={'custom_handler': config.custom_fallback}
            )
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message=f"Custom fallback handler failed: {str(e)}"
            )
    
    def _execute_retry_with_backoff(self, config: FallbackConfig, error: Exception,
                                   context: Dict[str, Any]) -> FallbackResult:
        """Execute retry with exponential backoff."""
        attempt = 0
        last_error = error
        
        while attempt < config.max_attempts:
            attempt += 1
            
            # Calculate delay
            if attempt == 1:
                delay = config.retry_delay
            else:
                delay = min(
                    config.retry_delay * (config.backoff_multiplier ** (attempt - 1)),
                    config.max_retry_delay
                )
            
            # Wait before retry
            if delay > 0:
                time.sleep(delay)
            
            try:
                # This would retry the original operation
                # For now, we'll simulate the retry
                result = self._retry_original_operation(config, context)
                
                return FallbackResult(
                    success=True,
                    strategy_used=config.strategy,
                    result=result,
                    attempt_count=attempt,
                    fallback_data={'retry_successful': True, 'attempt': attempt}
                )
                
            except Exception as retry_error:
                last_error = retry_error
                logger.warning(f"Retry attempt {attempt} failed: {str(retry_error)}")
        
        return FallbackResult(
            success=False,
            strategy_used=config.strategy,
            error_message=f"All {config.max_attempts} retry attempts failed",
            attempt_count=attempt,
            fallback_data={'retry_successful': False, 'attempts_made': attempt}
        )
    
    def _execute_graceful_degradation(self, config: FallbackConfig, error: Exception,
                                    context: Dict[str, Any]) -> FallbackResult:
        """Execute graceful degradation."""
        # Try cached data first
        cached_result = self._execute_cached_fallback(config, error, context)
        if cached_result.success:
            return cached_result
        
        # Try default value
        if config.default_value is not None:
            return self._execute_default_value_fallback(config, error, context)
        
        # Try alternative service
        if config.alternative_service:
            return self._execute_alternative_service_fallback(config, error, context)
        
        # Return minimal response
        return FallbackResult(
            success=True,
            strategy_used=config.strategy,
            result={'status': 'degraded', 'message': 'Service temporarily unavailable'},
            fallback_data={'degraded_mode': True}
        )
    
    def _execute_circuit_breaker_fallback(self, config: FallbackConfig, error: Exception,
                                        context: Dict[str, Any]) -> FallbackResult:
        """Execute circuit breaker fallback."""
        # Check if circuit breaker is open
        circuit_breaker = self.circuit_breakers.get(config.name)
        if circuit_breaker and circuit_breaker.get_state().value == 'open':
            return FallbackResult(
                success=False,
                strategy_used=config.strategy,
                error_message="Circuit breaker is open",
                fallback_data={'circuit_breaker_state': 'open'}
            )
        
        # Use cached data if available
        cached_result = self._execute_cached_fallback(config, error, context)
        if cached_result.success:
            return cached_result
        
        # Return fallback response
        return FallbackResult(
            success=True,
            strategy_used=config.strategy,
            result={'status': 'fallback', 'message': 'Service unavailable, using fallback'},
            fallback_data={'circuit_breaker_fallback': True}
        )
    
    def _call_alternative_service(self, service_name: str, context: Dict[str, Any]) -> Any:
        """Call alternative service."""
        # This would integrate with the actual alternative service
        # For now, we'll simulate the call
        return {'status': 'success', 'service': service_name, 'fallback_used': True}
    
    def _retry_original_operation(self, config: FallbackConfig, context: Dict[str, Any]) -> Any:
        """Retry the original operation."""
        # This would retry the original operation
        # For now, we'll simulate the retry
        return {'status': 'success', 'retry': True}
    
    def _get_recent_attempts(self, config_name: str, seconds: int) -> List[FallbackAttempt]:
        """Get recent fallback attempts."""
        cutoff_time = timezone.now() - timedelta(seconds=seconds)
        
        with self._lock:
            return [
                attempt for attempt in self.attempt_history
                if attempt.config_name == config_name and attempt.timestamp >= cutoff_time
            ]
    
    def _update_statistics(self, result: FallbackResult):
        """Update fallback statistics."""
        with self._lock:
            self.statistics['total_fallbacks'] += 1
            self.statistics['last_fallback_time'] = timezone.now()
            
            if result.success:
                self.statistics['successful_fallbacks'] += 1
            else:
                self.statistics['failed_fallbacks'] += 1
            
            # Update strategy statistics
            strategy_name = result.strategy_used.value
            if strategy_name not in self.statistics['fallbacks_by_strategy']:
                self.statistics['fallbacks_by_strategy'][strategy_name] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0
                }
            
            self.statistics['fallbacks_by_strategy'][strategy_name]['total'] += 1
            
            if result.success:
                self.statistics['fallbacks_by_strategy'][strategy_name]['successful'] += 1
            else:
                self.statistics['fallbacks_by_strategy'][strategy_name]['failed'] += 1
            
            # Update average execution time
            total_fallbacks = self.statistics['total_fallbacks']
            if total_fallbacks == 1:
                self.statistics['average_execution_time'] = result.execution_time
            else:
                current_avg = self.statistics['average_execution_time']
                self.statistics['average_execution_time'] = (
                    (current_avg * (total_fallbacks - 1) + result.execution_time) / total_fallbacks
                )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'total_configs': len(self.fallback_configs),
                'total_handlers': len(self.fallback_handlers),
                'total_attempts': len(self.attempt_history),
                'recent_attempts': len(self._get_recent_attempts('*', 3600))  # Last hour
            })
            return stats
    
    def get_attempt_history(self, config_name: str = None, limit: int = 100) -> List[FallbackAttempt]:
        """Get fallback attempt history."""
        with self._lock:
            attempts = self.attempt_history.copy()
            
            if config_name:
                attempts = [a for a in attempts if a.config_name == config_name]
            
            # Sort by timestamp (newest first)
            attempts.sort(key=lambda a: a.timestamp, reverse=True)
            
            return attempts[:limit]
    
    def clear_history(self, config_name: str = None, older_than_hours: int = 24) -> int:
        """Clear fallback attempt history."""
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)
        
        with self._lock:
            original_count = len(self.attempt_history)
            
            if config_name:
                self.attempt_history = [
                    attempt for attempt in self.attempt_history
                    if not (attempt.config_name == config_name and attempt.timestamp < cutoff_time)
                ]
            else:
                self.attempt_history = [
                    attempt for attempt in self.attempt_history
                    if attempt.timestamp >= cutoff_time
                ]
            
            cleared_count = original_count - len(self.attempt_history)
            logger.info(f"Cleared {cleared_count} fallback attempts from history")
            return cleared_count


# Global fallback manager
fallback_manager = FallbackManager()


# Decorator for fallback protection
def fallback_protection(config_name: str, fallback_config: FallbackConfig = None):
    """Decorator for fallback protection."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Register config if provided
                if fallback_config:
                    fallback_manager.register_fallback_config(fallback_config)
                
                # Execute fallback
                result = fallback_manager.execute_fallback(config_name, e)
                
                if result.success:
                    return result.result
                else:
                    raise IntegrationError(f"Fallback failed: {result.error_message}")
        
        return wrapper
    return decorator


# Convenience functions
def create_immediate_fallback(name: str, trigger: FallbackTrigger = FallbackTrigger.ERROR,
                            **config) -> FallbackConfig:
    """Create immediate fallback configuration."""
    return FallbackConfig(
        name=name,
        strategy=FallbackStrategy.IMMEDIATE,
        trigger=trigger,
        **config
    )


def create_cached_fallback(name: str, cache_ttl: int = 300,
                         trigger: FallbackTrigger = FallbackTrigger.ERROR, **config) -> FallbackConfig:
    """Create cached fallback configuration."""
    return FallbackConfig(
        name=name,
        strategy=FallbackStrategy.CACHED,
        trigger=trigger,
        cache_ttl=cache_ttl,
        **config
    )


def create_retry_fallback(name: str, max_attempts: int = 3, retry_delay: float = 1.0,
                         trigger: FallbackTrigger = FallbackTrigger.ERROR, **config) -> FallbackConfig:
    """Create retry fallback configuration."""
    return FallbackConfig(
        name=name,
        strategy=FallbackStrategy.DELAYED,
        trigger=trigger,
        max_attempts=max_attempts,
        retry_delay=retry_delay,
        **config
    )


def create_default_value_fallback(name: str, default_value: Any,
                                trigger: FallbackTrigger = FallbackTrigger.ERROR, **config) -> FallbackConfig:
    """Create default value fallback configuration."""
    return FallbackConfig(
        name=name,
        strategy=FallbackStrategy.DEFAULT_VALUE,
        trigger=trigger,
        default_value=default_value,
        **config
    )


def create_alternative_service_fallback(name: str, alternative_service: str,
                                       trigger: FallbackTrigger = FallbackTrigger.ERROR, **config) -> FallbackConfig:
    """Create alternative service fallback configuration."""
    return FallbackConfig(
        name=name,
        strategy=FallbackStrategy.ALTERNATIVE_SERVICE,
        trigger=trigger,
        alternative_service=alternative_service,
        **config
    )
