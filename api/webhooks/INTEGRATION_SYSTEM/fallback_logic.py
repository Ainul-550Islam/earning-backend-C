"""Fallback Logic

This module provides fallback logic for integration system
with comprehensive error handling and recovery mechanisms.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_constants import HealthStatus
from .integ_exceptions import IntegrationError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """Base class for fallback strategies."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the fallback strategy."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load strategy configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.max_attempts = self.config.get('max_attempts', 3)
            self.retry_delay = self.config.get('retry_delay', 1)
            self.exponential_backoff = self.config.get('exponential_backoff', True)
            
        except Exception as e:
            self.logger.error(f"Error loading strategy configuration: {str(e)}")
            self.enabled = True
            self.max_attempts = 3
            self.retry_delay = 1
            self.exponential_backoff = True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the fallback strategy.
        
        Args:
            context: Fallback context
            
        Returns:
            Fallback result
        """
        raise NotImplementedError("Subclasses must implement execute method")
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if strategy can be executed.
        
        Args:
            context: Fallback context
            
        Returns:
            True if strategy can be executed
        """
        return self.enabled
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Get strategy information.
        
        Returns:
            Strategy information
        """
        return {
            'name': self.__class__.__name__,
            'enabled': self.enabled,
            'max_attempts': self.max_attempts,
            'retry_delay': self.retry_delay,
            'exponential_backoff': self.exponential_backoff
        }


class RetryStrategy(FallbackStrategy):
    """Retry strategy for failed operations."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the retry strategy."""
        super().__init__(config)
        self.retry_function = None
        self._load_retry_function()
    
    def _load_retry_function(self):
        """Load retry function."""
        try:
            function_path = self.config.get('retry_function')
            if function_path:
                module_path, function_name = function_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                self.retry_function = getattr(module, function_name)
        except Exception as e:
            self.logger.error(f"Error loading retry function: {str(e)}")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute retry strategy.
        
        Args:
            context: Fallback context
            
        Returns:
            Fallback result
        """
        try:
            result = {
                'strategy': 'retry',
                'success': False,
                'attempts': 0,
                'errors': [],
                'executed_at': timezone.now().isoformat()
            }
            
            original_function = context.get('original_function')
            original_args = context.get('original_args', [])
            original_kwargs = context.get('original_kwargs', {})
            
            for attempt in range(self.max_attempts):
                try:
                    # Calculate delay
                    if self.exponential_backoff and attempt > 0:
                        delay = self.retry_delay * (2 ** attempt)
                    else:
                        delay = self.retry_delay
                    
                    # Wait before retry
                    if attempt > 0:
                        import time
                        time.sleep(delay)
                    
                    # Execute original function
                    if self.retry_function:
                        success = self.retry_function(*original_args, **original_kwargs)
                    else:
                        success = original_function(*original_args, **original_kwargs)
                    
                    if success:
                        result['success'] = True
                        result['attempts'] = attempt + 1
                        return result
                    
                except Exception as e:
                    result['errors'].append(f"Attempt {attempt + 1}: {str(e)}")
                    continue
            
            result['attempts'] = self.max_attempts
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing retry strategy: {str(e)}")
            return {
                'strategy': 'retry',
                'success': False,
                'error': str(e),
                'executed_at': timezone.now().isoformat()
            }
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if retry strategy can be executed."""
        if not super().can_execute(context):
            return False
        
        # Check if original function is available
        return context.get('original_function') is not None


class CircuitBreakerStrategy(FallbackStrategy):
    """Circuit breaker strategy for service protection."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the circuit breaker strategy."""
        super().__init__(config)
        self.failure_threshold = self.config.get('failure_threshold', 5)
        self.recovery_timeout = self.config.get('recovery_timeout', 60)
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute circuit breaker strategy.
        
        Args:
            context: Fallback context
            
        Returns:
            Fallback result
        """
        try:
            result = {
                'strategy': 'circuit_breaker',
                'success': False,
                'state': self.state,
                'failure_count': self.failure_count,
                'executed_at': timezone.now().isoformat()
            }
            
            # Check circuit state
            if self.state == 'open':
                # Check if recovery timeout has passed
                if self._should_attempt_reset():
                    self.state = 'half_open'
                else:
                    result['message'] = 'Circuit breaker is open'
                    return result
            
            # Execute operation
            try:
                original_function = context.get('original_function')
                original_args = context.get('original_args', [])
                original_kwargs = context.get('original_kwargs', {})
                
                success = original_function(*original_args, **original_kwargs)
                
                if success:
                    # Reset failure count on success
                    self.failure_count = 0
                    self.state = 'closed'
                    result['success'] = True
                else:
                    self._record_failure()
                
                result['state'] = self.state
                result['failure_count'] = self.failure_count
                return result
                
            except Exception as e:
                self._record_failure()
                result['error'] = str(e)
                result['state'] = self.state
                result['failure_count'] = self.failure_count
                return result
                
        except Exception as e:
            self.logger.error(f"Error executing circuit breaker strategy: {str(e)}")
            return {
                'strategy': 'circuit_breaker',
                'success': False,
                'error': str(e),
                'state': self.state,
                'executed_at': timezone.now().isoformat()
            }
    
    def _record_failure(self):
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = timezone.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return (timezone.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if circuit breaker strategy can be executed."""
        if not super().can_execute(context):
            return False
        
        # Check if original function is available
        return context.get('original_function') is not None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        info = super().get_strategy_info()
        info.update({
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
            'current_state': self.state,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
        })
        return info


class CacheStrategy(FallbackStrategy):
    """Cache strategy for fallback data."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the cache strategy."""
        super().__init__(config)
        self.cache_timeout = self.config.get('cache_timeout', 300)
        self.cache_key_prefix = self.config.get('cache_key_prefix', 'fallback')
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute cache strategy.
        
        Args:
            context: Fallback context
            
        Returns:
            Fallback result
        """
        try:
            result = {
                'strategy': 'cache',
                'success': False,
                'cache_hit': False,
                'executed_at': timezone.now().isoformat()
            }
            
            # Generate cache key
            cache_key = self._generate_cache_key(context)
            
            # Try to get from cache
            cached_data = cache.get(cache_key)
            if cached_data:
                result['success'] = True
                result['cache_hit'] = True
                result['data'] = cached_data
                return result
            
            # Cache miss, try to get and cache data
            fallback_function = context.get('fallback_function')
            if fallback_function:
                try:
                    data = fallback_function(**context.get('fallback_args', {}))
                    
                    # Cache the data
                    cache.set(cache_key, data, timeout=self.cache_timeout)
                    
                    result['success'] = True
                    result['data'] = data
                    return result
                    
                except Exception as e:
                    result['error'] = str(e)
                    return result
            
            result['message'] = 'No cached data and no fallback function'
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing cache strategy: {str(e)}")
            return {
                'strategy': 'cache',
                'success': False,
                'error': str(e),
                'executed_at': timezone.now().isoformat()
            }
    
    def _generate_cache_key(self, context: Dict[str, Any]) -> str:
        """Generate cache key from context."""
        try:
            key_parts = [self.cache_key_prefix]
            
            # Add relevant context parts
            for key in ['event_type', 'endpoint_id', 'source', 'destination']:
                if key in context:
                    key_parts.append(f"{key}:{context[key]}")
            
            return ':'.join(key_parts)
            
        except Exception as e:
            self.logger.error(f"Error generating cache key: {str(e)}")
            return f"{self.cache_key_prefix}:default"
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if cache strategy can be executed."""
        if not super().can_execute(context):
            return False
        
        # Check if fallback function is available
        return context.get('fallback_function') is not None


class DefaultResponseStrategy(FallbackStrategy):
    """Default response strategy for fallback."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the default response strategy."""
        super().__init__(config)
        self.default_responses = self.config.get('default_responses', {})
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute default response strategy.
        
        Args:
            context: Fallback context
            
        Returns:
            Fallback result
        """
        try:
            result = {
                'strategy': 'default_response',
                'success': True,
                'executed_at': timezone.now().isoformat()
            }
            
            # Get default response based on context
            default_response = self._get_default_response(context)
            
            result['data'] = default_response
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing default response strategy: {str(e)}")
            return {
                'strategy': 'default_response',
                'success': False,
                'error': str(e),
                'executed_at': timezone.now().isoformat()
            }
    
    def _get_default_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get default response based on context."""
        try:
            event_type = context.get('event_type', 'unknown')
            
            # Check for specific event type response
            if event_type in self.default_responses:
                return self.default_responses[event_type]
            
            # Check for generic response
            if 'generic' in self.default_responses:
                return self.default_responses['generic']
            
            # Return basic default response
            return {
                'status': 'fallback_applied',
                'message': 'Operation failed, fallback response applied',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting default response: {str(e)}")
            return {
                'status': 'fallback_applied',
                'message': 'Operation failed, fallback response applied',
                'timestamp': timezone.now().isoformat()
            }
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if default response strategy can be executed."""
        return super().can_execute(context)


class FallbackLogic:
    """
    Main fallback logic for integration system.
    Coordinates multiple fallback strategies and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the fallback logic."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Strategy storage
        self.strategies = {}
        self.strategy_order = []
        
        # Statistics
        self.stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'strategy_usage': {}
        }
        
        # Load configuration
        self._load_configuration()
        
        # Initialize strategies
        self._initialize_strategies()
    
    def _load_configuration(self):
        """Load fallback configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_FALLBACK_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.default_strategy = self.config.get('default_strategy', 'default_response')
            self.max_fallback_attempts = self.config.get('max_fallback_attempts', 3)
            
            self.logger.info("Fallback configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading fallback configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.default_strategy = 'default_response'
            self.max_fallback_attempts = 3
    
    def _initialize_strategies(self):
        """Initialize fallback strategies."""
        try:
            strategy_configs = self.config.get('strategies', {})
            
            # Initialize built-in strategies
            self.strategies['retry'] = RetryStrategy(strategy_configs.get('retry', {}))
            self.strategies['circuit_breaker'] = CircuitBreakerStrategy(strategy_configs.get('circuit_breaker', {}))
            self.strategies['cache'] = CacheStrategy(strategy_configs.get('cache', {}))
            self.strategies['default_response'] = DefaultResponseStrategy(strategy_configs.get('default_response', {}))
            
            # Set default strategy order
            self.strategy_order = self.config.get('strategy_order', ['retry', 'cache', 'default_response'])
            
            # Filter enabled strategies
            self.strategy_order = [
                strategy for strategy in self.strategy_order
                if strategy in self.strategies and self.strategies[strategy].enabled
            ]
            
            self.logger.info(f"Initialized {len(self.strategies)} fallback strategies")
            
        except Exception as e:
            self.logger.error(f"Error initializing fallback strategies: {str(e)}")
    
    def execute_fallback(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute fallback logic for an error.
        
        Args:
            error: The error that occurred
            context: Additional context
            
        Returns:
            Fallback result
        """
        try:
            if not self.enabled:
                return {
                    'success': False,
                    'error': 'Fallback logic is disabled',
                    'fallback_applied': False
                }
            
            with self.monitor.measure_fallback('execute') as measurement:
                self.stats['total_fallbacks'] += 1
                
                # Prepare context
                if not context:
                    context = {}
                
                context['error'] = str(error)
                context['error_type'] = error.__class__.__name__
                context['fallback_triggered_at'] = timezone.now().isoformat()
                
                # Try strategies in order
                for strategy_name in self.strategy_order:
                    strategy = self.strategies[strategy_name]
                    
                    if strategy.can_execute(context):
                        try:
                            result = strategy.execute(context)
                            
                            # Update statistics
                            self._update_strategy_stats(strategy_name, result)
                            
                            if result.get('success', False):
                                self.stats['successful_fallbacks'] += 1
                                return {
                                    'success': True,
                                    'strategy': strategy_name,
                                    'result': result,
                                    'fallback_applied': True
                                }
                            
                        except Exception as e:
                            self.logger.error(f"Error in fallback strategy {strategy_name}: {str(e)}")
                            continue
                
                # All strategies failed
                self.stats['failed_fallbacks'] += 1
                return {
                    'success': False,
                    'error': 'All fallback strategies failed',
                    'fallback_applied': False,
                    'attempted_strategies': self.strategy_order
                }
                
        except Exception as e:
            self.logger.error(f"Error executing fallback logic: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fallback_applied': False
            }
    
    def handle_handler_error(self, handler_name: str, error: Exception, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle handler error with fallback logic.
        
        Args:
            handler_name: Name of the handler that failed
            error: The error that occurred
            event_type: Event type
            data: Event data
            context: Additional context
            
        Returns:
            Fallback result
        """
        try:
            # Prepare context
            fallback_context = {
                'handler_name': handler_name,
                'event_type': event_type,
                'data': data,
                'error': str(error),
                'error_type': error.__class__.__name__
            }
            
            if context:
                fallback_context.update(context)
            
            return self.execute_fallback(error, fallback_context)
            
        except Exception as e:
            self.logger.error(f"Error handling handler error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fallback_applied': False
            }
    
    def handle_no_handlers(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle case when no handlers are found.
        
        Args:
            event_type: Event type
            data: Event data
            context: Additional context
            
        Returns:
            Fallback result
        """
        try:
            # Create a dummy error
            error = IntegrationError(f"No handlers found for event type: {event_type}")
            
            # Prepare context
            fallback_context = {
                'event_type': event_type,
                'data': data,
                'no_handlers': True
            }
            
            if context:
                fallback_context.update(context)
            
            return self.execute_fallback(error, fallback_context)
            
        except Exception as e:
            self.logger.error(f"Error handling no handlers case: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fallback_applied': False
            }
    
    def handle_webhook_error(self, error: Exception, endpoint_id: str, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle webhook error with fallback logic.
        
        Args:
            error: The error that occurred
            endpoint_id: Webhook endpoint ID
            event_type: Event type
            data: Event data
            context: Additional context
            
        Returns:
            Fallback result
        """
        try:
            # Prepare context
            fallback_context = {
                'endpoint_id': endpoint_id,
                'event_type': event_type,
                'data': data,
                'error': str(error),
                'error_type': error.__class__.__name__
            }
            
            if context:
                fallback_context.update(context)
            
            return self.execute_fallback(error, fallback_context)
            
        except Exception as e:
            self.logger.error(f"Error handling webhook error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fallback_applied': False
            }
    
    def _update_strategy_stats(self, strategy_name: str, result: Dict[str, Any]):
        """Update strategy statistics."""
        try:
            if strategy_name not in self.stats['strategy_usage']:
                self.stats['strategy_usage'][strategy_name] = {
                    'total_usage': 0,
                    'success_count': 0,
                    'failure_count': 0
                }
            
            stats = self.stats['strategy_usage'][strategy_name]
            stats['total_usage'] += 1
            
            if result.get('success', False):
                stats['success_count'] += 1
            else:
                stats['failure_count'] += 1
                
        except Exception as e:
            self.logger.error(f"Error updating strategy stats: {str(e)}")
    
    def get_fallback_statistics(self) -> Dict[str, Any]:
        """
        Get fallback statistics.
        
        Returns:
            Fallback statistics
        """
        try:
            return {
                'total_fallbacks': self.stats['total_fallbacks'],
                'successful_fallbacks': self.stats['successful_fallbacks'],
                'failed_fallbacks': self.stats['failed_fallbacks'],
                'success_rate': (
                    (self.stats['successful_fallbacks'] / self.stats['total_fallbacks'] * 100)
                    if self.stats['total_fallbacks'] > 0 else 0
                ),
                'strategy_usage': self.stats['strategy_usage'],
                'enabled_strategies': self.strategy_order
            }
            
        except Exception as e:
            self.logger.error(f"Error getting fallback statistics: {str(e)}")
            return {'error': str(e)}
    
    def get_strategy_status(self, strategy_name: str = None) -> Dict[str, Any]:
        """
        Get strategy status.
        
        Args:
            strategy_name: Optional specific strategy name
            
        Returns:
            Strategy status information
        """
        try:
            if strategy_name:
                if strategy_name in self.strategies:
                    return self.strategies[strategy_name].get_strategy_info()
                else:
                    return {'error': f'Strategy {strategy_name} not found'}
            else:
                return {
                    'total_strategies': len(self.strategies),
                    'enabled_strategies': self.strategy_order,
                    'strategies': {
                        name: strategy.get_strategy_info()
                        for name, strategy in self.strategies.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting strategy status: {str(e)}")
            return {'error': str(e)}
    
    def register_strategy(self, strategy_name: str, strategy: FallbackStrategy) -> bool:
        """
        Register a custom fallback strategy.
        
        Args:
            strategy_name: Name of the strategy
            strategy: Strategy instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(strategy, FallbackStrategy):
                raise IntegrationError("Strategy must inherit from FallbackStrategy")
            
            self.strategies[strategy_name] = strategy
            
            # Add to strategy order if not already present
            if strategy_name not in self.strategy_order:
                self.strategy_order.append(strategy_name)
            
            self.logger.info(f"Strategy {strategy_name} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering strategy {strategy_name}: {str(e)}")
            return False
    
    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a fallback strategy.
        
        Args:
            strategy_name: Name of the strategy to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if strategy_name in self.strategies:
                del self.strategies[strategy_name]
                
                # Remove from strategy order
                if strategy_name in self.strategy_order:
                    self.strategy_order.remove(strategy_name)
                
                self.logger.info(f"Strategy {strategy_name} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Strategy {strategy_name} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering strategy {strategy_name}: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of fallback system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check strategies
            for strategy_name, strategy in self.strategies.items():
                strategy_info = strategy.get_strategy_info()
                health_status['components'][strategy_name] = {
                    'status': HealthStatus.HEALTHY if strategy_info['enabled'] else HealthStatus.DISABLED
                }
            
            # Check statistics
            if self.stats['total_fallbacks'] > 0:
                success_rate = (self.stats['successful_fallbacks'] / self.stats['total_fallbacks'] * 100)
                if success_rate < 50:
                    health_status['overall'] = HealthStatus.DEGRADED
                elif success_rate < 20:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get fallback system status.
        
        Returns:
            System status
        """
        try:
            return {
                'fallback_logic': {
                    'status': 'running' if self.enabled else 'disabled',
                    'total_strategies': len(self.strategies),
                    'enabled_strategies': len(self.strategy_order),
                    'default_strategy': self.default_strategy,
                    'max_fallback_attempts': self.max_fallback_attempts,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'statistics': self.get_fallback_statistics(),
                'strategies': {
                    name: strategy.get_strategy_info()
                    for name, strategy in self.strategies.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting fallback status: {str(e)}")
            return {'error': str(e)}
