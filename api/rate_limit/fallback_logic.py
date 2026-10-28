# api/rate_limit/fallback_logic.py
"""
Fallback logic system for rate limit module.

Provides fallback mechanisms and error recovery strategies.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import random
import time

from api.rate_limit.integ_exceptions import IntegrationError, IntegrationFallbackError

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """Base class for fallback strategies."""
    
    def __init__(self, name: str, priority: int = 0, enabled: bool = True):
        self.name = name
        self.priority = priority
        self.enabled = enabled
        self.success_count = 0
        self.failure_count = 0
        self.last_used = None
        self.total_executions = 0
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fallback strategy.
        
        Args:
            context: Execution context
            
        Returns:
            Execution result
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if strategy can be executed.
        
        Args:
            context: Execution context
            
        Returns:
            True if can execute
        """
        return self.enabled
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        success_rate = (
            self.success_count / max(self.total_executions, 1)
        ) * 100
        
        return {
            'name': self.name,
            'priority': self.priority,
            'enabled': self.enabled,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'total_executions': self.total_executions,
            'success_rate': success_rate,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


class CacheFallbackStrategy(FallbackStrategy):
    """Fallback strategy using cached data."""
    
    def __init__(self, cache_key_prefix: str = 'fallback_cache', ttl: int = 3600):
        super().__init__('cache_fallback', priority=1)
        self.cache_key_prefix = cache_key_prefix
        self.ttl = ttl
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cache fallback."""
        try:
            operation_key = context.get('operation_key')
            if not operation_key:
                raise IntegrationFallbackError("Operation key not provided for cache fallback")
            
            cache_key = f"{self.cache_key_prefix}:{operation_key}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                self.success_count += 1
                self.last_used = timezone.now()
                
                return {
                    'success': True,
                    'data': cached_data,
                    'source': 'cache',
                    'timestamp': timezone.now().isoformat()
                }
            else:
                self.failure_count += 1
                raise IntegrationFallbackError(f"No cached data found for key: {cache_key}")
                
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Cache fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Cache fallback failed: {str(e)}")
    
    def store_cache(self, operation_key: str, data: Dict[str, Any]):
        """Store data in cache for fallback."""
        cache_key = f"{self.cache_key_prefix}:{operation_key}"
        cache.set(cache_key, data, timeout=self.ttl)


class DefaultResponseFallbackStrategy(FallbackStrategy):
    """Fallback strategy returning default response."""
    
    def __init__(self, default_responses: Dict[str, Any] = None):
        super().__init__('default_response', priority=2)
        self.default_responses = default_responses or {}
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute default response fallback."""
        try:
            operation_type = context.get('operation_type', 'default')
            
            # Get default response or create generic one
            default_response = self.default_responses.get(operation_type, {
                'success': False,
                'message': 'Service temporarily unavailable',
                'fallback_used': True,
                'timestamp': timezone.now().isoformat()
            })
            
            self.success_count += 1
            self.last_used = timezone.now()
            
            return {
                'success': True,
                'data': default_response,
                'source': 'default_response',
                'operation_type': operation_type,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Default response fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Default response fallback failed: {str(e)}")
    
    def add_default_response(self, operation_type: str, response: Dict[str, Any]):
        """Add a default response for an operation type."""
        self.default_responses[operation_type] = response


class RetryFallbackStrategy(FallbackStrategy):
    """Fallback strategy that retries the operation."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0, backoff_factor: float = 2.0):
        super().__init__('retry', priority=3)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute retry fallback."""
        try:
            original_function = context.get('original_function')
            if not original_function:
                raise IntegrationFallbackError("Original function not provided for retry fallback")
            
            args = context.get('args', [])
            kwargs = context.get('kwargs', {})
            
            last_exception = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        # Calculate delay with exponential backoff
                        delay = min(self.base_delay * (self.backoff_factor ** (attempt - 1)), self.max_delay)
                        time.sleep(delay)
                    
                    result = original_function(*args, **kwargs)
                    
                    if attempt > 0:
                        self.success_count += 1
                        self.last_used = timezone.now()
                    
                    return {
                        'success': True,
                        'data': result,
                        'source': 'retry',
                        'attempts': attempt + 1,
                        'timestamp': timezone.now().isoformat()
                    }
                    
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Retry attempt {attempt + 1} failed: {str(e)}")
            
            # All retries failed
            self.failure_count += 1
            raise IntegrationFallbackError(f"All {self.max_retries + 1} retry attempts failed: {str(last_exception)}")
            
        except IntegrationFallbackError:
            raise
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Retry fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Retry fallback failed: {str(e)}")


class CircuitBreakerFallbackStrategy(FallbackStrategy):
    """Fallback strategy using circuit breaker state."""
    
    def __init__(self, circuit_breaker_manager):
        super().__init__('circuit_breaker', priority=4)
        self.circuit_breaker_manager = circuit_breaker_manager
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute circuit breaker fallback."""
        try:
            circuit_breaker_name = context.get('circuit_breaker_name')
            if not circuit_breaker_name:
                raise IntegrationFallbackError("Circuit breaker name not provided")
            
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(circuit_breaker_name)
            if not circuit_breaker:
                raise IntegrationFallbackError(f"Circuit breaker not found: {circuit_breaker_name}")
            
            # Check if circuit is open
            from api.rate_limit.circuit_breaker import CircuitState
            if circuit_breaker.get_state() == CircuitState.OPEN:
                self.success_count += 1
                self.last_used = timezone.now()
                
                return {
                    'success': True,
                    'data': {
                        'circuit_breaker_open': True,
                        'message': 'Service temporarily unavailable due to circuit breaker',
                        'fallback_used': True
                    },
                    'source': 'circuit_breaker',
                    'circuit_breaker_name': circuit_breaker_name,
                    'timestamp': timezone.now().isoformat()
                }
            else:
                self.failure_count += 1
                raise IntegrationFallbackError(f"Circuit breaker is not open: {circuit_breaker_name}")
                
        except IntegrationFallbackError:
            raise
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Circuit breaker fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Circuit breaker fallback failed: {str(e)}")


class DegradedServiceFallbackStrategy(FallbackStrategy):
    """Fallback strategy providing degraded service functionality."""
    
    def __init__(self, degraded_functions: Dict[str, Callable] = None):
        super().__init__('degraded_service', priority=5)
        self.degraded_functions = degraded_functions or {}
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute degraded service fallback."""
        try:
            operation_type = context.get('operation_type')
            if not operation_type:
                raise IntegrationFallbackError("Operation type not provided for degraded service fallback")
            
            degraded_function = self.degraded_functions.get(operation_type)
            if not degraded_function:
                raise IntegrationFallbackError(f"No degraded function available for: {operation_type}")
            
            args = context.get('args', [])
            kwargs = context.get('kwargs', {})
            
            result = degraded_function(*args, **kwargs)
            
            self.success_count += 1
            self.last_used = timezone.now()
            
            return {
                'success': True,
                'data': result,
                'source': 'degraded_service',
                'operation_type': operation_type,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Degraded service fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Degraded service fallback failed: {str(e)}")
    
    def add_degraded_function(self, operation_type: str, function: Callable):
        """Add a degraded function for an operation type."""
        self.degraded_functions[operation_type] = function


class RandomSelectionFallbackStrategy(FallbackStrategy):
    """Fallback strategy that randomly selects from available options."""
    
    def __init__(self, options: List[Dict[str, Any]] = None):
        super().__init__('random_selection', priority=6)
        self.options = options or []
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute random selection fallback."""
        try:
            if not self.options:
                raise IntegrationFallbackError("No options available for random selection fallback")
            
            selected_option = random.choice(self.options)
            
            self.success_count += 1
            self.last_used = timezone.now()
            
            return {
                'success': True,
                'data': selected_option,
                'source': 'random_selection',
                'selected_option': selected_option,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Random selection fallback failed: {str(e)}")
            raise IntegrationFallbackError(f"Random selection fallback failed: {str(e)}")
    
    def add_option(self, option: Dict[str, Any]):
        """Add an option to the selection pool."""
        self.options.append(option)


class FallbackManager:
    """
    Manager for fallback strategies.
    """
    
    def __init__(self):
        self.strategies: List[FallbackStrategy] = []
        self.global_strategies: List[FallbackStrategy] = []
        self.operation_strategies: Dict[str, List[FallbackStrategy]] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self):
        """Initialize default fallback strategies."""
        # Cache fallback
        cache_fallback = CacheFallbackStrategy()
        self.add_global_strategy(cache_fallback)
        
        # Default response fallback
        default_responses = {
            'rate_limit_check': {
                'success': False,
                'is_limited': False,
                'remaining': 100,
                'message': 'Rate limit check temporarily unavailable'
            },
            'user_profile': {
                'success': True,
                'api_health_score': 50,
                'suspicion_score': 0,
                'is_premium': False
            },
            'analytics': {
                'success': True,
                'data': {},
                'message': 'Analytics temporarily unavailable'
            }
        }
        default_fallback = DefaultResponseFallbackStrategy(default_responses)
        self.add_global_strategy(default_fallback)
        
        # Retry fallback
        retry_fallback = RetryFallbackStrategy()
        self.add_global_strategy(retry_fallback)
        
        # Degraded service fallback
        degraded_functions = {
            'rate_limit_check': self._degraded_rate_limit_check,
            'user_profile': self._degraded_user_profile,
            'analytics': self._degraded_analytics
        }
        degraded_fallback = DegradedServiceFallbackStrategy(degraded_functions)
        self.add_global_strategy(degraded_fallback)
    
    def _degraded_rate_limit_check(self, *args, **kwargs) -> Dict[str, Any]:
        """Degraded rate limit check function."""
        return {
            'success': True,
            'is_limited': False,
            'remaining': 100,
            'message': 'Rate limit check (degraded mode)'
        }
    
    def _degraded_user_profile(self, *args, **kwargs) -> Dict[str, Any]:
        """Degraded user profile function."""
        return {
            'success': True,
            'api_health_score': 50,
            'suspicion_score': 0,
            'is_premium': False,
            'message': 'User profile (degraded mode)'
        }
    
    def _degraded_analytics(self, *args, **kwargs) -> Dict[str, Any]:
        """Degraded analytics function."""
        return {
            'success': True,
            'data': {
                'total_requests': 0,
                'blocked_requests': 0,
                'success_rate': 0
            },
            'message': 'Analytics (degraded mode)'
        }
    
    def add_global_strategy(self, strategy: FallbackStrategy):
        """Add a global fallback strategy."""
        self.strategies.append(strategy)
        self.global_strategies.append(strategy)
        logger.info(f"Added global fallback strategy: {strategy.name}")
    
    def add_operation_strategy(self, operation_type: str, strategy: FallbackStrategy):
        """Add an operation-specific fallback strategy."""
        if operation_type not in self.operation_strategies:
            self.operation_strategies[operation_type] = []
        
        self.operation_strategies[operation_type].append(strategy)
        self.strategies.append(strategy)
        logger.info(f"Added operation fallback strategy: {strategy.name} for {operation_type}")
    
    def remove_strategy(self, strategy_name: str):
        """Remove a fallback strategy."""
        self.strategies = [s for s in self.strategies if s.name != strategy_name]
        self.global_strategies = [s for s in self.global_strategies if s.name != strategy_name]
        
        for operation_type in self.operation_strategies:
            self.operation_strategies[operation_type] = [
                s for s in self.operation_strategies[operation_type] 
                if s.name != strategy_name
            ]
        
        logger.info(f"Removed fallback strategy: {strategy_name}")
    
    def execute_fallback(self, operation_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute fallback strategies for an operation.
        
        Args:
            operation_type: Type of operation
            context: Execution context
            
        Returns:
            Fallback execution result
        """
        try:
            context = context or {}
            context['operation_type'] = operation_type
            
            # Get applicable strategies
            strategies = []
            
            # Add operation-specific strategies first
            if operation_type in self.operation_strategies:
                strategies.extend(self.operation_strategies[operation_type])
            
            # Add global strategies
            strategies.extend(self.global_strategies)
            
            # Sort by priority (lower number = higher priority)
            strategies.sort(key=lambda s: s.priority)
            
            # Try each strategy
            for strategy in strategies:
                if strategy.can_execute(context):
                    try:
                        strategy.total_executions += 1
                        result = strategy.execute(context)
                        
                        # Record execution
                        execution_record = {
                            'timestamp': timezone.now().isoformat(),
                            'operation_type': operation_type,
                            'strategy_name': strategy.name,
                            'success': True,
                            'result': result
                        }
                        self._add_to_history(execution_record)
                        
                        logger.info(f"Fallback strategy {strategy.name} succeeded for {operation_type}")
                        return result
                        
                    except IntegrationFallbackError as e:
                        logger.warning(f"Fallback strategy {strategy.name} failed for {operation_type}: {str(e)}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error in fallback strategy {strategy.name}: {str(e)}")
                        continue
            
            # All strategies failed
            error_record = {
                'timestamp': timezone.now().isoformat(),
                'operation_type': operation_type,
                'strategy_name': 'none',
                'success': False,
                'error': 'All fallback strategies failed'
            }
            self._add_to_history(error_record)
            
            raise IntegrationFallbackError(f"All fallback strategies failed for operation: {operation_type}")
            
        except IntegrationFallbackError:
            raise
        except Exception as e:
            logger.error(f"Fallback execution failed: {str(e)}")
            raise IntegrationFallbackError(f"Fallback execution failed: {str(e)}")
    
    def _add_to_history(self, record: Dict[str, Any]):
        """Add record to execution history."""
        self.execution_history.append(record)
        
        # Maintain history size
        if len(self.execution_history) > self.max_history_size:
            self.execution_history = self.execution_history[-self.max_history_size:]
    
    def get_strategy_statistics(self, strategy_name: str = None) -> Dict[str, Any]:
        """Get statistics for fallback strategies."""
        if strategy_name:
            strategy = next((s for s in self.strategies if s.name == strategy_name), None)
            if strategy:
                return strategy.get_statistics()
            else:
                return {'error': f'Strategy not found: {strategy_name}'}
        else:
            return {
                strategy.name: strategy.get_statistics()
                for strategy in self.strategies
            }
    
    def get_execution_history(self, operation_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fallback execution history."""
        history = self.execution_history
        
        if operation_type:
            history = [record for record in history if record.get('operation_type') == operation_type]
        
        # Sort by timestamp (most recent first)
        history.sort(key=lambda r: r['timestamp'], reverse=True)
        
        return history[:limit]
    
    def get_success_rates(self) -> Dict[str, Any]:
        """Get success rates for strategies and operations."""
        strategy_stats = {}
        operation_stats = {}
        
        # Strategy success rates
        for strategy in self.strategies:
            if strategy.total_executions > 0:
                strategy_stats[strategy.name] = {
                    'success_rate': (strategy.success_count / strategy.total_executions) * 100,
                    'total_executions': strategy.total_executions
                }
        
        # Operation success rates
        for record in self.execution_history:
            operation_type = record.get('operation_type')
            if operation_type not in operation_stats:
                operation_stats[operation_type] = {'success': 0, 'total': 0}
            
            operation_stats[operation_type]['total'] += 1
            if record.get('success'):
                operation_stats[operation_type]['success'] += 1
        
        # Calculate success rates
        for operation_type in operation_stats:
            stats = operation_stats[operation_type]
            stats['success_rate'] = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        
        return {
            'strategy_success_rates': strategy_stats,
            'operation_success_rates': operation_stats
        }


# Global fallback manager instance
fallback_manager = FallbackManager()


# Decorator for fallback protection
def with_fallback(operation_type: str, context: Dict[str, Any] = None):
    """
    Decorator for fallback protection.
    
    Args:
        operation_type: Type of operation
        context: Additional context for fallback
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Primary function failed for {operation_type}: {str(e)}")
                
                # Prepare fallback context
                fallback_context = (context or {}).copy()
                fallback_context.update({
                    'original_function': func,
                    'args': args,
                    'kwargs': kwargs,
                    'original_error': str(e)
                })
                
                # Execute fallback
                try:
                    return fallback_manager.execute_fallback(operation_type, fallback_context)
                except IntegrationFallbackError as fallback_error:
                    logger.error(f"Fallback also failed for {operation_type}: {str(fallback_error)}")
                    raise
        return wrapper
    return decorator


# Export classes and functions
__all__ = [
    'FallbackStrategy',
    'CacheFallbackStrategy',
    'DefaultResponseFallbackStrategy',
    'RetryFallbackStrategy',
    'CircuitBreakerFallbackStrategy',
    'DegradedServiceFallbackStrategy',
    'RandomSelectionFallbackStrategy',
    'FallbackManager',
    'fallback_manager',
    'with_fallback'
]
