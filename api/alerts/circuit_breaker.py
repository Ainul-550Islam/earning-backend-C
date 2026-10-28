"""
Circuit Breaker for alerts app - Fault tolerance for external system calls
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging
import time
import threading

logger = logging.getLogger(__name__)


class CircuitBreakerState:
    """Circuit breaker state enumeration"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Partial recovery, some calls allowed


class CircuitBreaker(ABC):
    """Abstract base class for circuit breakers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        
        # Circuit breaker configuration
        self.failure_threshold = config.get('failure_threshold', 5)
        self.recovery_timeout = config.get('recovery_timeout', 60)  # seconds
        self.success_threshold = config.get('success_threshold', 3)
        self.monitoring_period = config.get('monitoring_period', 60)  # seconds
        
        # State tracking
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state_change_time = timezone.now()
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
    @abstractmethod
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        pass
    
    @abstractmethod
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        pass
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_success_time = None
            self.state_change_time = timezone.now()
            
            logger.info(f"Circuit breaker {self.name} reset to CLOSED state")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_calls': self.total_calls,
                'total_failures': self.total_failures,
                'total_successes': self.total_successes,
                'failure_rate': self._calculate_failure_rate(),
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None,
                'state_change_time': self.state_change_time.isoformat(),
                'configuration': self.config
            }
    
    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate in current monitoring period"""
        if self.total_calls == 0:
            return 0.0
        
        return self.total_failures / self.total_calls
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset from OPEN to HALF_OPEN"""
        if self.state != CircuitBreakerState.OPEN:
            return False
        
        if not self.last_failure_time:
            return False
        
        time_since_failure = (timezone.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
    
    def _should_reset_to_closed(self) -> bool:
        """Check if circuit should reset from HALF_OPEN to CLOSED"""
        if self.state != CircuitBreakerState.HALF_OPEN:
            return False
        
        return self.success_count >= self.success_threshold
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should open"""
        if self.state != CircuitBreakerState.CLOSED:
            return False
        
        return self.failure_count >= self.failure_threshold
    
    def _record_success(self):
        """Record a successful call"""
        with self._lock:
            self.total_successes += 1
            self.total_calls += 1
            self.last_success_time = timezone.now()
            self.success_count += 1
            self.failure_count = 0  # Reset failure count on success
    
    def _record_failure(self):
        """Record a failed call"""
        with self._lock:
            self.total_failures += 1
            self.total_calls += 1
            self.last_failure_time = timezone.now()
            self.failure_count += 1
            self.success_count = 0  # Reset success count on failure


class SimpleCircuitBreaker(CircuitBreaker):
    """Simple circuit breaker implementation"""
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker logic"""
        with self._lock:
            # Check if circuit should attempt reset
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.state_change_time = timezone.now()
                logger.info(f"Circuit breaker {self.name} changed to HALF_OPEN")
            
            # Fast fail if circuit is open
            if self.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN")
            
            # Allow limited calls in HALF_OPEN state
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Implement probabilistic call in HALF_OPEN
                import random
                if random.random() > 0.5:  # 50% chance of allowing call
                    raise CircuitBreakerOpenException(f"Circuit {self.name} is HALF_OPEN")
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            self._record_success()
            
            # Check if circuit should close from HALF_OPEN
            if self._should_reset_to_closed():
                self.state = CircuitBreakerState.CLOSED
                self.state_change_time = timezone.now()
                logger.info(f"Circuit breaker {self.name} changed to CLOSED")
            
            return result
            
        except Exception as e:
            self._record_failure()
            
            # Check if circuit should open
            if self._should_open_circuit():
                self.state = CircuitBreakerState.OPEN
                self.state_change_time = timezone.now()
                logger.warning(f"Circuit breaker {self.name} changed to OPEN after {self.failure_count} failures")
            
            raise e
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state


class TimeBasedCircuitBreaker(CircuitBreaker):
    """Time-based circuit breaker with sliding window"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.call_history = []
        self.window_size = config.get('window_size', 100)
        self.time_window = config.get('time_window', 300)  # 5 minutes
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with time-based circuit breaker logic"""
        current_time = timezone.now()
        
        with self._lock:
            # Update call history
            self._update_call_history(current_time)
            
            # Check if circuit should attempt reset
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.state_change_time = current_time
                logger.info(f"Time-based circuit breaker {self.name} changed to HALF_OPEN")
            
            # Fast fail if circuit is open
            if self.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenException(f"Time-based circuit {self.name} is OPEN")
            
            # Check failure rate in time window
            recent_failures = self._get_recent_failures(current_time)
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Allow calls if failure rate is improving
                if len(recent_failures) < self.failure_threshold:
                    pass  # Allow call
                else:
                    raise CircuitBreakerOpenException(f"Time-based circuit {self.name} is HALF_OPEN")
            elif len(recent_failures) >= self.failure_threshold:
                raise CircuitBreakerOpenException(f"Time-based circuit {self.name} opened due to high failure rate")
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            self._record_success()
            
            # Check if circuit should close from HALF_OPEN
            if self._should_reset_to_closed():
                self.state = CircuitBreakerState.CLOSED
                self.state_change_time = current_time
                logger.info(f"Time-based circuit breaker {self.name} changed to CLOSED")
            
            return result
            
        except Exception as e:
            self._record_failure()
            
            # Check if circuit should open
            if self._should_open_circuit():
                self.state = CircuitBreakerState.OPEN
                self.state_change_time = current_time
                logger.warning(f"Time-based circuit breaker {self.name} changed to OPEN")
            
            raise e
    
    def _update_call_history(self, current_time):
        """Update call history with sliding window"""
        # Add current call
        self.call_history.append({
            'timestamp': current_time,
            'success': False  # Will be updated after call
        })
        
        # Remove old calls outside time window
        cutoff_time = current_time - timedelta(seconds=self.time_window)
        self.call_history = [
            call for call in self.call_history 
            if call['timestamp'] > cutoff_time
        ]
        
        # Keep only recent calls for performance
        if len(self.call_history) > self.window_size:
            self.call_history = self.call_history[-self.window_size:]
    
    def _get_recent_failures(self, current_time) -> List[Dict[str, Any]]:
        """Get recent failures within time window"""
        cutoff_time = current_time - timedelta(seconds=self.time_window)
        
        return [
            call for call in self.call_history
            if call['timestamp'] > cutoff_time and not call['success']
        ]
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state


class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""
    
    def __init__(self):
        self.circuit_breakers = {}
        self.global_config = {
            'default_failure_threshold': 5,
            'default_recovery_timeout': 60,
            'default_success_threshold': 3,
            'default_monitoring_period': 60
        }
        
    def register_circuit_breaker(self, name: str, circuit_breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self.circuit_breakers[name] = circuit_breaker
        logger.info(f"Registered circuit breaker: {name}")
    
    def unregister_circuit_breaker(self, name: str):
        """Unregister a circuit breaker"""
        if name in self.circuit_breakers:
            del self.circuit_breakers[name]
            logger.info(f"Unregistered circuit breaker: {name}")
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self.circuit_breakers.get(name)

    def get_or_create(self, name: str, breaker_type: str = 'simple', **config) -> CircuitBreaker:
        """
        Get the circuit breaker registered under `name`, creating and
        registering a new one (via CircuitBreakerFactory) if it doesn't
        exist yet. Extra keyword args (failure_threshold, recovery_timeout,
        success_threshold, monitoring_period, ...) seed the config used
        only when a new breaker is created.
        """
        existing = self.get_circuit_breaker(name)
        if existing is not None:
            return existing

        merged_config = {**self.global_config, **config}
        breaker = CircuitBreakerFactory.create_circuit_breaker(breaker_type, merged_config)
        if breaker is None:
            # Unknown breaker_type or construction error - fall back to
            # the always-available simple implementation rather than
            # letting a bad breaker_type argument break callers.
            breaker = SimpleCircuitBreaker(merged_config)
        breaker.name = name
        self.register_circuit_breaker(name, breaker)
        return breaker
    
    def call_through_circuit(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(name)
        if not circuit_breaker:
            logger.error(f"Circuit breaker {name} not found")
            return func(*args, **kwargs)
        
        return circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_states(self) -> Dict[str, str]:
        """Get states of all circuit breakers"""
        return {
            name: breaker.get_state() 
            for name, breaker in self.circuit_breakers.items()
        }
    
    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics of all circuit breakers"""
        return {
            name: breaker.get_statistics() 
            for name, breaker in self.circuit_breakers.items()
        }
    
    def reset_circuit(self, name: str):
        """Reset specific circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(name)
        if circuit_breaker:
            circuit_breaker.reset()
    
    def reset_all_circuits(self):
        """Reset all circuit breakers"""
        for circuit_breaker in self.circuit_breakers.values():
            circuit_breaker.reset()
    
    def get_failed_circuits(self) -> List[str]:
        """Get list of failed circuit breakers"""
        failed = []
        
        for name, breaker in self.circuit_breakers.items():
            stats = breaker.get_statistics()
            if stats['state'] == CircuitBreakerState.OPEN:
                failed.append(name)
        
        return failed
    
    def get_half_open_circuits(self) -> List[str]:
        """Get list of half-open circuit breakers"""
        half_open = []
        
        for name, breaker in self.circuit_breakers.items():
            stats = breaker.get_statistics()
            if stats['state'] == CircuitBreakerState.HALF_OPEN:
                half_open.append(name)
        
        return half_open


class CircuitBreakerFactory:
    """Factory for creating circuit breakers"""
    
    _circuit_breakers = {
        'simple': SimpleCircuitBreaker,
        'time_based': TimeBasedCircuitBreaker
    }
    
    @classmethod
    def create_circuit_breaker(cls, breaker_type: str, config: Dict[str, Any]) -> Optional[CircuitBreaker]:
        """Create circuit breaker by type"""
        breaker_class = cls._circuit_breakers.get(breaker_type)
        if not breaker_class:
            logger.error(f"Unknown circuit breaker type: {breaker_type}")
            return None
        
        try:
            return breaker_class(config)
        except Exception as e:
            logger.error(f"Error creating circuit breaker {breaker_type}: {e}")
            return None
    
    @classmethod
    def register_circuit_breaker(cls, breaker_type: str, breaker_class: type):
        """Register a new circuit breaker type"""
        cls._circuit_breakers[breaker_type] = breaker_class
        logger.info(f"Registered circuit breaker: {breaker_type}")
    
    @classmethod
    def get_available_breakers(cls) -> List[str]:
        """Get list of available circuit breaker types"""
        return list(cls._circuit_breakers.keys())


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit is open"""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# Decorator for circuit breaker
def circuit_breaker(circuit_name: str, manager: CircuitBreakerManager = None):
    """Decorator to apply circuit breaker to function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if manager:
                return manager.call_through_circuit(circuit_name, func, *args, **kwargs)
            else:
                # Use global manager
                return circuit_breaker_manager.call_through_circuit(circuit_name, func, *args, **kwargs)
        return wrapper
    return decorator


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager"""
    return circuit_breaker_manager


def initialize_circuit_breakers():
    """Initialize circuit breakers from settings"""
    from django.conf import settings
    
    circuit_breaker_configs = getattr(settings, 'CIRCUIT_BREAKER_CONFIGS', {})
    
    for name, config in circuit_breaker_configs.items():
        try:
            breaker_type = config.get('type', 'simple')
            circuit_breaker = CircuitBreakerFactory.create_circuit_breaker(breaker_type, config)
            
            if circuit_breaker:
                circuit_breaker_manager.register_circuit_breaker(name, circuit_breaker)
            else:
                logger.error(f"Failed to create circuit breaker: {name}")
                
        except Exception as e:
            logger.error(f"Error initializing circuit breaker {name}: {e}")


# Utility functions
def create_circuit_breaker_config(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 3,
    monitoring_period: int = 60,
    breaker_type: str = 'simple'
) -> Dict[str, Any]:
    """Create circuit breaker configuration"""
    return {
        'type': breaker_type,
        'failure_threshold': failure_threshold,
        'recovery_timeout': recovery_timeout,
        'success_threshold': success_threshold,
        'monitoring_period': monitoring_period
    }


def validate_circuit_breaker_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate circuit breaker configuration"""
    errors = []
    
    # Check required fields
    if 'type' not in config:
        errors.append('Circuit breaker type is required')
    
    # Validate type
    valid_types = ['simple', 'time_based']
    if config.get('type') not in valid_types:
        errors.append(f"Invalid type. Must be one of: {valid_types}")
    
    # Validate numeric fields
    numeric_fields = ['failure_threshold', 'recovery_timeout', 'success_threshold', 'monitoring_period']
    for field in numeric_fields:
        if field in config:
            try:
                value = int(config[field])
                if value <= 0:
                    errors.append(f"{field} must be positive")
            except (ValueError, TypeError):
                errors.append(f"{field} must be a valid integer")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


# Initialize on module import
try:
    initialize_circuit_breakers()
except Exception as e:
    logger.error(f"Error initializing circuit breakers: {e}")
