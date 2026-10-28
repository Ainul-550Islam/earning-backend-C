"""
Fallback Logic Module
Fallback and recovery logic for integration system
"""

import logging
import time
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_exceptions import IntegrationException, ConnectionException, TimeoutException

User = get_user_model()
logger = logging.getLogger('security.integration.fallback')


class FallbackStrategy:
    """Base fallback strategy"""
    
    def __init__(self, name: str, priority: int = 5):
        self.name = name
        self.priority = priority  # Lower number = higher priority
        self.enabled = True
        self.conditions = {}
        self.config = {}
        self.statistics = {
            'executions': 0,
            'successes': 0,
            'failures': 0,
            'last_execution': None
        }
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if strategy can execute"""
        if not self.enabled:
            return False
        
        # Check conditions
        for condition_key, condition_value in self.conditions.items():
            if not self._check_condition(condition_key, condition_value, context):
                return False
        
        return True
    
    def _check_condition(self, key: str, value: Any, context: Dict[str, Any]) -> bool:
        """Check condition"""
        context_value = context.get(key)
        
        if isinstance(value, dict):
            # Range condition
            if 'min' in value and context_value < value['min']:
                return False
            if 'max' in value and context_value > value['max']:
                return False
        else:
            # Exact match
            if context_value != value:
                return False
        
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fallback strategy - override in subclasses"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def configure(self, config: Dict[str, Any]):
        """Configure strategy"""
        self.config = config
    
    def add_condition(self, key: str, value: Any):
        """Add execution condition"""
        self.conditions[key] = value
    
    def enable(self):
        """Enable strategy"""
        self.enabled = True
    
    def disable(self):
        """Disable strategy"""
        self.enabled = False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        total = self.statistics['executions']
        success_rate = (self.statistics['successes'] / total) if total > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'priority': self.priority,
            'conditions_count': len(self.conditions),
            'statistics': {
                **self.statistics,
                'success_rate': success_rate
            }
        }


class RetryStrategy(FallbackStrategy):
    """Retry fallback strategy"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        super().__init__("retry", priority=1)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute retry strategy"""
        self.statistics['executions'] += 1
        self.statistics['last_execution'] = timezone.now()
        
        original_func = context.get('function')
        args = context.get('args', [])
        kwargs = context.get('kwargs', {})
        current_attempt = context.get('attempt', 0)
        
        if current_attempt >= self.max_retries:
            self.statistics['failures'] += 1
            return {
                'status': 'failed',
                'message': f'Max retries ({self.max_retries}) exceeded',
                'attempts': current_attempt
            }
        
        # Calculate delay with exponential backoff
        delay = min(self.base_delay * (2 ** current_attempt), self.max_delay)
        
        if delay > 0:
            time.sleep(delay)
        
        try:
            result = original_func(*args, **kwargs)
            self.statistics['successes'] += 1
            return {
                'status': 'success',
                'result': result,
                'attempts': current_attempt + 1
            }
        
        except Exception as e:
            logger.warning(f"Retry attempt {current_attempt + 1} failed: {e}")
            
            # Update context for next retry
            context['attempt'] = current_attempt + 1
            context['last_error'] = str(e)
            
            return {
                'status': 'retry',
                'message': f'Retry attempt {current_attempt + 1} failed',
                'error': str(e),
                'next_attempt': current_attempt + 1
            }


class AlternativeEndpointStrategy(FallbackStrategy):
    """Alternative endpoint fallback strategy"""
    
    def __init__(self, alternative_endpoints: List[str] = None):
        super().__init__("alternative_endpoint", priority=2)
        self.alternative_endpoints = alternative_endpoints or []
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute alternative endpoint strategy"""
        self.statistics['executions'] += 1
        self.statistics['last_execution'] = timezone.now()
        
        original_endpoint = context.get('endpoint')
        current_endpoint_index = context.get('endpoint_index', 0)
        
        if current_endpoint_index >= len(self.alternative_endpoints):
            self.statistics['failures'] += 1
            return {
                'status': 'failed',
                'message': 'All alternative endpoints exhausted',
                'tried_endpoints': self.alternative_endpoints
            }
        
        # Get next endpoint
        if current_endpoint_index == 0:
            # First try original endpoint
            endpoint = original_endpoint
        else:
            endpoint = self.alternative_endpoints[current_endpoint_index - 1]
        
        try:
            # Update context with new endpoint
            context['endpoint'] = endpoint
            
            # Execute with new endpoint
            result = self._execute_with_endpoint(context)
            
            self.statistics['successes'] += 1
            return {
                'status': 'success',
                'result': result,
                'endpoint': endpoint,
                'endpoint_index': current_endpoint_index
            }
        
        except Exception as e:
            logger.warning(f"Alternative endpoint {endpoint} failed: {e}")
            
            # Try next endpoint
            context['endpoint_index'] = current_endpoint_index + 1
            context['last_error'] = str(e)
            
            return {
                'status': 'retry',
                'message': f'Alternative endpoint {endpoint} failed',
                'error': str(e),
                'next_endpoint_index': current_endpoint_index + 1
            }
    
    def _execute_with_endpoint(self, context: Dict[str, Any]) -> Any:
        """Execute with specific endpoint"""
        # This would implement the actual execution logic
        # For now, return success
        return {"success": True, "endpoint": context['endpoint']}
    
    def add_alternative_endpoint(self, endpoint: str):
        """Add alternative endpoint"""
        self.alternative_endpoints.append(endpoint)


class CacheStrategy(FallbackStrategy):
    """Cache fallback strategy"""
    
    def __init__(self, cache_ttl: int = 300):
        super().__init__("cache", priority=3)
        self.cache_ttl = cache_ttl
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cache strategy"""
        self.statistics['executions'] += 1
        self.statistics['last_execution'] = timezone.now()
        
        cache_key = context.get('cache_key')
        
        if not cache_key:
            self.statistics['failures'] += 1
            return {
                'status': 'failed',
                'message': 'No cache key provided'
            }
        
        try:
            # Try to get from cache
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                self.statistics['successes'] += 1
                return {
                    'status': 'success',
                    'result': cached_result,
                    'source': 'cache',
                    'cache_key': cache_key
                }
            else:
                self.statistics['failures'] += 1
                return {
                    'status': 'failed',
                    'message': 'No cached data found',
                    'cache_key': cache_key
                }
        
        except Exception as e:
            logger.error(f"Cache strategy error: {e}")
            self.statistics['failures'] += 1
            return {
                'status': 'failed',
                'message': f'Cache error: {str(e)}',
                'cache_key': cache_key
            }
    
    def store_in_cache(self, cache_key: str, data: Any):
        """Store data in cache"""
        try:
            cache.set(cache_key, data, self.cache_ttl)
        except Exception as e:
            logger.error(f"Error storing in cache: {e}")


class DefaultResponseStrategy(FallbackStrategy):
    """Default response fallback strategy"""
    
    def __init__(self, default_response: Any = None):
        super().__init__("default_response", priority=4)
        self.default_response = default_response or {"status": "fallback", "message": "Service unavailable"}
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute default response strategy"""
        self.statistics['executions'] += 1
        self.statistics['last_execution'] = timezone.now()
        
        self.statistics['successes'] += 1
        
        return {
            'status': 'success',
            'result': self.default_response,
            'strategy': 'default_response'
        }


class GracefulDegradationStrategy(FallbackStrategy):
    """Graceful degradation fallback strategy"""
    
    def __init__(self, degraded_functions: Dict[str, Callable] = None):
        super().__init__("graceful_degradation", priority=5)
        self.degraded_functions = degraded_functions or {}
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute graceful degradation strategy"""
        self.statistics['executions'] += 1
        self.statistics['last_execution'] = timezone.now()
        
        operation = context.get('operation')
        
        if operation in self.degraded_functions:
            try:
                degraded_func = self.degraded_functions[operation]
                result = degraded_func(context)
                
                self.statistics['successes'] += 1
                return {
                    'status': 'success',
                    'result': result,
                    'operation': operation,
                    'degraded': True
                }
            
            except Exception as e:
                logger.error(f"Graceful degradation failed for {operation}: {e}")
                self.statistics['failures'] += 1
                return {
                    'status': 'failed',
                    'message': f'Degraded function failed: {str(e)}',
                    'operation': operation
                }
        else:
            self.statistics['failures'] += 1
            return {
                'status': 'failed',
                'message': f'No degraded function for operation: {operation}',
                'operation': operation
            }
    
    def add_degraded_function(self, operation: str, func: Callable):
        """Add degraded function"""
        self.degraded_functions[operation] = func


class FallbackManager:
    """Manager for fallback strategies"""
    
    def __init__(self):
        self.strategies = []
        self.global_conditions = {}
        self.enabled = True
        self.statistics = {
            'total_executions': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0
        }
    
    def add_strategy(self, strategy: FallbackStrategy):
        """Add fallback strategy"""
        self.strategies.append(strategy)
        
        # Sort by priority
        self.strategies.sort(key=lambda s: s.priority)
        
        logger.info(f"Added fallback strategy: {strategy.name}")
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """Remove fallback strategy"""
        for i, strategy in enumerate(self.strategies):
            if strategy.name == strategy_name:
                del self.strategies[i]
                logger.info(f"Removed fallback strategy: {strategy_name}")
                return True
        return False
    
    def get_strategy(self, strategy_name: str) -> Optional[FallbackStrategy]:
        """Get strategy by name"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                return strategy
        return None
    
    def execute_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fallback strategies"""
        if not self.enabled:
            return {
                'status': 'failed',
                'message': 'Fallback manager disabled'
            }
        
        self.statistics['total_executions'] += 1
        
        # Check global conditions
        if not self._check_global_conditions(context):
            return {
                'status': 'failed',
                'message': 'Global conditions not met'
            }
        
        # Try strategies in priority order
        for strategy in self.strategies:
            if strategy.can_execute(context):
                try:
                    result = strategy.execute(context)
                    
                    if result.get('status') == 'success':
                        self.statistics['successful_fallbacks'] += 1
                        return {
                            'status': 'success',
                            'strategy': strategy.name,
                            'result': result
                        }
                    elif result.get('status') == 'retry':
                        # Continue to next strategy
                        continue
                    else:
                        # Strategy failed, continue to next
                        continue
                
                except Exception as e:
                    logger.error(f"Error in fallback strategy {strategy.name}: {e}")
                    continue
        
        # All strategies failed
        self.statistics['failed_fallbacks'] += 1
        return {
            'status': 'failed',
            'message': 'All fallback strategies failed'
        }
    
    def _check_global_conditions(self, context: Dict[str, Any]) -> bool:
        """Check global conditions"""
        for condition_key, condition_value in self.global_conditions.items():
            context_value = context.get(key)
            if context_value != condition_value:
                return False
        return True
    
    def add_global_condition(self, key: str, value: Any):
        """Add global condition"""
        self.global_conditions[key] = value
    
    def enable_all_strategies(self):
        """Enable all strategies"""
        for strategy in self.strategies:
            strategy.enable()
    
    def disable_all_strategies(self):
        """Disable all strategies"""
        for strategy in self.strategies:
            strategy.disable()
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all strategies"""
        return {
            'enabled': self.enabled,
            'total_strategies': len(self.strategies),
            'global_conditions_count': len(self.global_conditions),
            'statistics': self.statistics,
            'strategies': [strategy.get_statistics() for strategy in self.strategies]
        }
    
    def enable(self):
        """Enable fallback manager"""
        self.enabled = True
        logger.info("Fallback manager enabled")
    
    def disable(self):
        """Disable fallback manager"""
        self.enabled = False
        logger.info("Fallback manager disabled")


class ResilienceManager:
    """Resilience manager with fallback logic"""
    
    def __init__(self):
        self.fallback_manager = FallbackManager()
        self.circuit_breakers = {}
        self.retry_policies = {}
        self.enabled = True
    
    def execute_with_resilience(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with resilience"""
        if not self.enabled:
            return func(*args, **kwargs)
        
        context = {
            'function': func,
            'args': args,
            'kwargs': kwargs,
            'attempt': 0,
            'start_time': timezone.now()
        }
        
        try:
            # Try primary execution
            result = func(*args, **kwargs)
            return result
        
        except Exception as e:
            logger.warning(f"Primary execution failed: {e}")
            
            # Add error to context
            context['error'] = str(e)
            context['error_type'] = type(e).__name__
            
            # Execute fallback
            fallback_result = self.fallback_manager.execute_fallback(context)
            
            if fallback_result.get('status') == 'success':
                return fallback_result['result']['result']
            else:
                # Re-raise original exception
                raise e
    
    def add_fallback_strategy(self, strategy: FallbackStrategy):
        """Add fallback strategy"""
        self.fallback_manager.add_strategy(strategy)
    
    def get_resilience_status(self) -> Dict[str, Any]:
        """Get resilience status"""
        return {
            'enabled': self.enabled,
            'fallback_manager': self.fallback_manager.get_all_statistics(),
            'circuit_breakers_count': len(self.circuit_breakers),
            'retry_policies_count': len(self.retry_policies)
        }
    
    def enable(self):
        """Enable resilience manager"""
        self.enabled = True
        logger.info("Resilience manager enabled")
    
    def disable(self):
        """Disable resilience manager"""
        self.enabled = False
        logger.info("Resilience manager disabled")


# Global managers
fallback_manager = FallbackManager()
resilience_manager = ResilienceManager()


# Create default fallback strategies
def create_default_fallback_strategies():
    """Create default fallback strategies"""
    
    # Retry strategy
    retry_strategy = RetryStrategy(max_retries=3, base_delay=1.0, max_delay=30.0)
    fallback_manager.add_strategy(retry_strategy)
    
    # Alternative endpoint strategy
    alt_endpoint_strategy = AlternativeEndpointStrategy([
        'https://backup-api.example.com',
        'https://fallback-api.example.com'
    ])
    fallback_manager.add_strategy(alt_endpoint_strategy)
    
    # Cache strategy
    cache_strategy = CacheStrategy(cache_ttl=300)
    fallback_manager.add_strategy(cache_strategy)
    
    # Default response strategy
    default_strategy = DefaultResponseStrategy({
        'status': 'service_unavailable',
        'message': 'Service temporarily unavailable',
        'retry_after': 60
    })
    fallback_manager.add_strategy(default_strategy)
    
    # Graceful degradation strategy
    def degraded_search(context):
        """Degraded search function"""
        query = context.get('kwargs', {}).get('query', '')
        return {
            'results': [],
            'message': 'Search temporarily unavailable',
            'query': query
        }
    
    def degraded_analytics(context):
        """Degraded analytics function"""
        return {
            'metrics': {},
            'message': 'Analytics temporarily unavailable'
        }
    
    degradation_strategy = GracefulDegradationStrategy({
        'search': degraded_search,
        'analytics': degraded_analytics
    })
    fallback_manager.add_strategy(degradation_strategy)
    
    logger.info("Created default fallback strategies")


# Initialize default strategies
create_default_fallback_strategies()


# Export symbols
__all__ = [
    'FallbackStrategy',
    'RetryStrategy',
    'AlternativeEndpointStrategy',
    'CacheStrategy',
    'DefaultResponseStrategy',
    'GracefulDegradationStrategy',
    'FallbackManager',
    'ResilienceManager',
    'fallback_manager',
    'resilience_manager',
    'create_default_fallback_strategies'
]