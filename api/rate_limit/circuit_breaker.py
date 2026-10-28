# api/rate_limit/circuit_breaker.py
"""
Circuit breaker system for rate limit module.

Provides fault tolerance and resilience patterns.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception, success_threshold: int = 3,
                 timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.timeout = timeout


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.lock = threading.RLock()
        
        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.state_changes = []
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        with self.lock:
            self.total_requests += 1
            
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self._record_state_change(CircuitState.OPEN, CircuitState.HALF_OPEN)
                else:
                    raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is open")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.config.expected_exception as e:
                self._on_failure()
                raise
            except Exception as e:
                self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return False
        
        return (timezone.now() - self.last_failure_time).total_seconds() >= self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful execution."""
        self.success_count += 1
        self.total_successes += 1
        self.last_success_time = timezone.now()
        
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                self._reset()
                self._record_state_change(CircuitState.HALF_OPEN, CircuitState.CLOSED)
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = timezone.now()
        self.success_count = 0
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self._record_state_change(CircuitState.CLOSED, CircuitState.OPEN)
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self._record_state_change(CircuitState.HALF_OPEN, CircuitState.OPEN)
    
    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def _record_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Record state change."""
        change_record = {
            'timestamp': timezone.now().isoformat(),
            'old_state': old_state.value,
            'new_state': new_state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count
        }
        self.state_changes.append(change_record)
        
        # Keep only last 100 state changes
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]
        
        logger.info(f"Circuit breaker {self.name} changed from {old_state.value} to {new_state.value}")
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        failure_rate = (self.total_failures / max(self.total_requests, 1)) * 100
        success_rate = (self.total_successes / max(self.total_requests, 1)) * 100
        
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'failure_rate': failure_rate,
            'success_rate': success_rate,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'success_threshold': self.config.success_threshold,
                'timeout': self.config.timeout
            },
            'recent_state_changes': self.state_changes[-10:] if self.state_changes else []
        }
    
    def force_open(self):
        """Force circuit breaker to open state."""
        with self.lock:
            old_state = self.state
            self.state = CircuitState.OPEN
            self._record_state_change(old_state, CircuitState.OPEN)
    
    def force_close(self):
        """Force circuit breaker to closed state."""
        with self.lock:
            old_state = self.state
            self._reset()
            self._record_state_change(old_state, CircuitState.CLOSED)


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers.
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """
        Register a circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Circuit breaker configuration
            
        Returns:
            Circuit breaker instance
        """
        breaker = CircuitBreaker(name, config or self.default_config)
        self.circuit_breakers[name] = breaker
        logger.info(f"Registered circuit breaker: {name}")
        return breaker
    
    def unregister_circuit_breaker(self, name: str):
        """
        Unregister a circuit breaker.
        
        Args:
            name: Circuit breaker name
        """
        if name in self.circuit_breakers:
            del self.circuit_breakers[name]
            logger.info(f"Unregistered circuit breaker: {name}")
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get a circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            Circuit breaker instance or None
        """
        return self.circuit_breakers.get(name)
    
    def call_with_breaker(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            name: Circuit breaker name
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        breaker = self.get_circuit_breaker(name)
        if not breaker:
            # Create default breaker if not exists
            breaker = self.register_circuit_breaker(name)
        
        return breaker.call(func, *args, **kwargs)
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers."""
        stats = {}
        
        for name, breaker in self.circuit_breakers.items():
            stats[name] = breaker.get_statistics()
        
        return stats
    
    def get_open_breakers(self) -> List[str]:
        """Get list of open circuit breakers."""
        return [
            name for name, breaker in self.circuit_breakers.items()
            if breaker.get_state() == CircuitState.OPEN
        ]
    
    def get_half_open_breakers(self) -> List[str]:
        """Get list of half-open circuit breakers."""
        return [
            name for name, breaker in self.circuit_breakers.items()
            if breaker.get_state() == CircuitState.HALF_OPEN
        ]
    
    def force_open_all(self):
        """Force all circuit breakers to open state."""
        for breaker in self.circuit_breakers.values():
            breaker.force_open()
    
    def force_close_all(self):
        """Force all circuit breakers to closed state."""
        for breaker in self.circuit_breakers.values():
            breaker.force_close()
    
    def reset_all(self):
        """Reset all circuit breakers statistics."""
        for breaker in self.circuit_breakers.values():
            breaker._reset()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all circuit breakers."""
        total_breakers = len(self.circuit_breakers)
        open_breakers = len(self.get_open_breakers())
        half_open_breakers = len(self.get_half_open_breakers())
        closed_breakers = total_breakers - open_breakers - half_open_breakers
        
        health_score = (closed_breakers / max(total_breakers, 1)) * 100
        
        return {
            'total_breakers': total_breakers,
            'open_breakers': open_breakers,
            'half_open_breakers': half_open_breakers,
            'closed_breakers': closed_breakers,
            'health_score': health_score,
            'health_status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'unhealthy',
            'breakers': {
                name: breaker.get_state().value
                for name, breaker in self.circuit_breakers.items()
            }
        }


class RateLimitCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for rate limiting operations.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        # Default configuration for rate limiting
        default_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception,
            success_threshold=2,
            timeout=10.0
        )
        
        super().__init__(name, config or default_config)
        self.rate_limit_stats = {
            'blocked_requests': 0,
            'allowed_requests': 0,
            'last_blocked_time': None,
            'last_allowed_time': None
        }
    
    def call_rate_limit_check(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute rate limit check with circuit breaker protection.
        
        Args:
            func: Rate limit check function
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        try:
            result = self.call(func, *args, **kwargs)
            
            # Track allowed requests
            if result and isinstance(result, tuple):
                is_limited, remaining, metadata = result
                if not is_limited:
                    self.rate_limit_stats['allowed_requests'] += 1
                    self.rate_limit_stats['last_allowed_time'] = timezone.now()
                else:
                    self.rate_limit_stats['blocked_requests'] += 1
                    self.rate_limit_stats['last_blocked_time'] = timezone.now()
            
            return result
            
        except CircuitBreakerOpenException:
            # When circuit is open, allow request (fail-safe)
            logger.warning(f"Circuit breaker {self.name} is open, allowing request")
            return False, 0, {'circuit_breaker_open': True}
    
    def get_rate_limit_statistics(self) -> Dict[str, Any]:
        """Get rate limit specific statistics."""
        base_stats = self.get_statistics()
        
        base_stats.update({
            'rate_limit_stats': self.rate_limit_stats,
            'block_rate': (
                self.rate_limit_stats['blocked_requests'] / 
                max(self.rate_limit_stats['blocked_requests'] + self.rate_limit_stats['allowed_requests'], 1)
            ) * 100
        })
        
        return base_stats


class IntegrationCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for integration operations.
    """
    
    def __init__(self, name: str, integration_id: str, config: CircuitBreakerConfig = None):
        # Default configuration for integrations
        default_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception,
            success_threshold=3,
            timeout=30.0
        )
        
        super().__init__(name, config or default_config)
        self.integration_id = integration_id
        self.integration_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'last_call_time': None,
            'last_success_time': None,
            'last_failure_time': None
        }
    
    def call_integration(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute integration call with circuit breaker protection.
        
        Args:
            func: Integration function
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        self.integration_stats['total_calls'] += 1
        self.integration_stats['last_call_time'] = timezone.now()
        
        try:
            result = self.call(func, *args, **kwargs)
            
            # Track successful integration calls
            if result and result.get('success', False):
                self.integration_stats['successful_calls'] += 1
                self.integration_stats['last_success_time'] = timezone.now()
            else:
                self.integration_stats['failed_calls'] += 1
                self.integration_stats['last_failure_time'] = timezone.now()
            
            return result
            
        except CircuitBreakerOpenException:
            # When circuit is open, return error response
            logger.warning(f"Circuit breaker {self.name} is open, returning error response")
            return {
                'success': False,
                'error': f'Circuit breaker is open for integration {self.integration_id}',
                'circuit_breaker_open': True
            }
    
    def get_integration_statistics(self) -> Dict[str, Any]:
        """Get integration specific statistics."""
        base_stats = self.get_statistics()
        
        base_stats.update({
            'integration_id': self.integration_id,
            'integration_stats': self.integration_stats,
            'success_rate': (
                self.integration_stats['successful_calls'] / 
                max(self.integration_stats['total_calls'], 1)
            ) * 100
        })
        
        return base_stats


# Decorator for circuit breaker protection
def circuit_breaker_protected(name: str, config: CircuitBreakerConfig = None):
    """
    Decorator for circuit breaker protection.
    
    Args:
        name: Circuit breaker name
        config: Circuit breaker configuration
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = CircuitBreakerManager()
            return manager.call_with_breaker(name, func, *args, **kwargs)
        return wrapper
    return decorator


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()

# Register default circuit breakers
rate_limit_breaker = RateLimitCircuitBreaker('rate_limit_check')
circuit_breaker_manager.register_circuit_breaker('rate_limit_check', rate_limit_breaker.config)


# Export classes and functions
__all__ = [
    'CircuitState',
    'CircuitBreakerConfig',
    'CircuitBreaker',
    'CircuitBreakerOpenException',
    'CircuitBreakerManager',
    'RateLimitCircuitBreaker',
    'IntegrationCircuitBreaker',
    'circuit_breaker_protected',
    'circuit_breaker_manager'
]
