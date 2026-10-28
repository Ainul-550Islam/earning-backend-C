"""
Integration Circuit Breaker Module
Circuit breaker pattern for integration resilience
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

from .integ_exceptions import CircuitBreakerOpenException
# আপনার প্রোজেক্টের স্ট্রাকচার অনুযায়ী এই মডেল ইম্পোর্টগুলো সঠিক আছে কি না নিশ্চিত হয়ে নিন
try:
    from ..models import SecurityLog, SecurityIncident
except (ImportError, ValueError):
    # যদি মডেল ইম্পোর্টে সমস্যা হয়, তবে এরর হ্যান্ডেল করার জন্য
    SecurityLog = None
    SecurityIncident = None

from .integ_constants import CircuitBreakerState

User = get_user_model()
logger = logging.getLogger('security.integration.circuit_breaker')


class CircuitBreaker:
    """Circuit breaker for integration resilience"""
    
    def __init__(self, name: str = "default", *args, failure_threshold: int = 5, 
                 reset_timeout: int = 300, expected_exception: Type[Exception] = Exception, 
                 success_threshold: int = 3, **kwargs):
        
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout  # এটিই হচ্ছে রিকভারি টাইম
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = timezone.now()
        
        self.statistics = {
            'total_calls': 0,
            'success_calls': 0,
            'failure_calls': 0,
            'short_circuited_calls': 0,
            'state_changes': 0
        }
        
        self.logger = logging.getLogger(f'security.circuit_breaker.{name}')
    
    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker"""
        self.statistics['total_calls'] += 1
        
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._attempt_reset()
            else:
                self.statistics['short_circuited_calls'] += 1
                self.logger.warning("Circuit breaker OPEN - call short-circuited")
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._on_success()
            
            self.statistics['success_calls'] += 1
            return result
            
        except self.expected_exception:
            self._on_failure()
            self.statistics['failure_calls'] += 1
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        return (timezone.now() - self.last_failure_time).total_seconds() >= self.reset_timeout
    
    def _attempt_reset(self):
        """Attempt to reset circuit breaker to HALF_OPEN"""
        self.logger.info("Circuit breaker transitioning to HALF_OPEN")
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.last_state_change = timezone.now()
        self.statistics['state_changes'] += 1
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.success_threshold:
                self._reset()
                
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = timezone.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._trip()
        elif self.failure_count >= self.failure_threshold:
            self._trip()
    
    def _trip(self):
        """Trip circuit breaker to OPEN"""
        self.logger.warning(f"Circuit breaker TRIPPED - failure count: {self.failure_count}")
        self.state = CircuitBreakerState.OPEN
        self.last_state_change = timezone.now()
        self.statistics['state_changes'] += 1
    
    def _reset(self):
        """Reset circuit breaker to CLOSED"""
        self.logger.info("Circuit breaker RESET to CLOSED")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = timezone.now()
        self.statistics['state_changes'] += 1
    
    def force_open(self):
        """Force circuit breaker to OPEN"""
        self.logger.warning("Circuit breaker forced OPEN")
        self.state = CircuitBreakerState.OPEN
        self.last_state_change = timezone.now()
        self.statistics['state_changes'] += 1
    
    def force_close(self):
        """Force circuit breaker to CLOSED"""
        self.logger.info("Circuit breaker forced CLOSED")
        self._reset()
    
    def get_state(self) -> CircuitBreakerState:
        """Get current state"""
        return self.state
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        success_rate = (
            self.statistics['success_calls'] / self.statistics['total_calls']
            if self.statistics['total_calls'] > 0 else 0
        )
        
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'reset_timeout': self.reset_timeout,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_state_change': self.last_state_change.isoformat(),
            'statistics': {
                **self.statistics,
                'success_rate': success_rate
            }
        }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""
    
    def __init__(self):
        self.circuit_breakers = {}
        self.global_config = {
            'failure_threshold': 5,
            'reset_timeout': 60,
            'success_threshold': 3,
            'expected_exception': Exception
        }
        self.enabled = True
        self.monitoring_enabled = True
    
    def create_circuit_breaker(self, name: str, failure_threshold: int = None,
                              recovery_timeout: int = None, expected_exception: Type[Exception] = None,
                              success_threshold: int = None) -> CircuitBreaker:
        """Create circuit breaker"""
        config = self.global_config.copy()
        
        if failure_threshold is not None:
            config['failure_threshold'] = failure_threshold
        if recovery_timeout is not None:
            config['reset_timeout'] = recovery_timeout
        if expected_exception is not None:
            config['expected_exception'] = expected_exception
        if success_threshold is not None:
            config['success_threshold'] = success_threshold
        
        # এখানে ৫টি প্যারামিটার পাঠানো হচ্ছে
        circuit_breaker = CircuitBreaker(
            name,
            failure_threshold=config['failure_threshold'],
            reset_timeout=config['reset_timeout'],
            expected_exception=config['expected_exception'],
            success_threshold=config['success_threshold']
        )
        
        self.circuit_breakers[name] = circuit_breaker
        logger.info(f"Created circuit breaker: {name}")
        
        return circuit_breaker
    
    def remove_circuit_breaker(self, name: str) -> bool:
        """Remove circuit breaker"""
        if name in self.circuit_breakers:
            del self.circuit_breakers[name]
            logger.info(f"Removed circuit breaker: {name}")
            return True
        return False
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self.circuit_breakers.get(name)
    
    def call_through_circuit_breaker(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(name)
        
        if not circuit_breaker:
            circuit_breaker = self.create_circuit_breaker(name)
        
        return circuit_breaker.call(func, *args, **kwargs)

    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        status = {
            'enabled': self.enabled,
            'monitoring_enabled': self.monitoring_enabled,
            'total_circuit_breakers': len(self.circuit_breakers),
            'open_circuit_breakers': len([
                cb for cb in self.circuit_breakers.values()
                if cb.get_state() == CircuitBreakerState.OPEN
            ]),
            'circuit_breakers': {}
        }
        
        for name, circuit_breaker in self.circuit_breakers.items():
            status['circuit_breakers'][name] = circuit_breaker.get_statistics()
        
        return status
    
    def get_open_circuit_breakers(self) -> List[str]:
        """Get list of open circuit breakers"""
        return [
            name for name, cb in self.circuit_breakers.items()
            if cb.get_state() == CircuitBreakerState.OPEN
        ]
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers to CLOSED"""
        for circuit_breaker in self.circuit_breakers.values():
            circuit_breaker.force_close()
        
        logger.info("All circuit breakers reset to CLOSED")
    
    def trip_circuit_breaker(self, name: str):
        """Trip specific circuit breaker to OPEN"""
        circuit_breaker = self.get_circuit_breaker(name)
        if circuit_breaker:
            circuit_breaker.force_open()
            logger.info(f"Circuit breaker {name} forced OPEN")
    
    def reset_circuit_breaker(self, name: str):
        """Reset specific circuit breaker to CLOSED"""
        circuit_breaker = self.get_circuit_breaker(name)
        if circuit_breaker:
            circuit_breaker.force_close()
            logger.info(f"Circuit breaker {name} forced CLOSED")
    
    def update_global_config(self, config: Dict[str, Any]):
        """Update global configuration"""
        self.global_config.update(config)
        logger.info("Updated global circuit breaker configuration")
    
    def enable_monitoring(self):
        """Enable monitoring"""
        self.monitoring_enabled = True
        logger.info("Circuit breaker monitoring enabled")
    
    def disable_monitoring(self):
        """Disable monitoring"""
        self.monitoring_enabled = False
        logger.info("Circuit breaker monitoring disabled")
    
    def enable(self):
        """Enable circuit breaker manager"""
        self.enabled = True
        logger.info("Circuit breaker manager enabled")
    
    def disable(self):
        """Disable circuit breaker manager"""
        self.enabled = False
        logger.info("Circuit breaker manager disabled")
    
    def monitor_circuit_breakers(self):
        """Monitor circuit breakers and create alerts if needed"""
        if not self.monitoring_enabled:
            return
        
        open_breakers = self.get_open_circuit_breakers()
        
        if open_breakers:
            if len(open_breakers) >= 3 and SecurityIncident:
                SecurityIncident.objects.create(
                    title="Multiple Circuit Breakers Open",
                    incident_type='system_failure',
                    severity='high',
                    priority='high',
                    description=f"Multiple circuit breakers are open: {', '.join(open_breakers)}",
                    metadata={
                        'open_circuit_breakers': open_breakers,
                        'total_circuit_breakers': len(self.circuit_breakers)
                    }
                )
            
            for breaker_name in open_breakers:
                circuit_breaker = self.get_circuit_breaker(breaker_name)
                if circuit_breaker and SecurityLog:
                    stats = circuit_breaker.get_statistics()
                    SecurityLog.objects.create(
                        security_type='circuit_breaker_open',
                        severity='warning',
                        description=f"Circuit breaker open: {breaker_name}",
                        metadata=stats
                    )


class CircuitBreakerDecorator:
    """Decorator for circuit breaker protection"""
    
    def __init__(self, circuit_breaker_name: str, manager=None):
        self.circuit_breaker_name = circuit_breaker_name
        self.manager = manager or circuit_breaker_manager
    
    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return self.manager.call_through_circuit_breaker(
                self.circuit_breaker_name, func, *args, **kwargs
            )
        return wrapper


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


# Decorator for easy circuit breaker usage
def circuit_breaker_protected(circuit_breaker_name: str):
    """Decorator for circuit breaker protection"""
    return CircuitBreakerDecorator(circuit_breaker_name)


# Built-in circuit breaker configurations
def create_default_circuit_breakers():
    """Create default circuit breakers for common integrations"""
    
    circuit_breaker_manager.create_circuit_breaker(
        'http_api',
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=ConnectionError
    )
    
    circuit_breaker_manager.create_circuit_breaker(
        'database',
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=Exception
    )
    
    circuit_breaker_manager.create_circuit_breaker(
        'message_queue',
        failure_threshold=7,
        recovery_timeout=120,
        expected_exception=ConnectionError
    )
    
    circuit_breaker_manager.create_circuit_breaker(
        'external_api',
        failure_threshold=10,
        recovery_timeout=300,
        expected_exception=Exception
    )
    
    logger.info("Created default circuit breakers")


# Initialize default circuit breakers
create_default_circuit_breakers()


# Export symbols
__all__ = [
    'CircuitBreaker',
    'CircuitBreakerOpenException',
    'CircuitBreakerManager',
    'circuit_breaker_manager',
    'CircuitBreakerDecorator',
    'circuit_breaker_protected',
    'create_default_circuit_breakers'
]