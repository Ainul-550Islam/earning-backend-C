"""
circuit_breaker.py – Circuit Breaker pattern implementation for postback module.

Provides comprehensive circuit breaker functionality including:
- Circuit state management
- Failure threshold handling
- Recovery mechanisms
- Metrics and monitoring
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import time

from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker state enumeration."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitEventType(Enum):
    """Circuit event type enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CIRCUIT_OPENED = "circuit_opened"
    CIRCUIT_CLOSED = "circuit_closed"
    CIRCUIT_HALF_OPENED = "circuit_half_opened"


@dataclass
class CircuitEvent:
    """Circuit event data structure."""
    timestamp: datetime
    event_type: CircuitEventType
    duration: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'duration': self.duration,
            'error_message': self.error_message,
            'metadata': self.metadata,
        }


@dataclass
class CircuitMetrics:
    """Circuit metrics data structure."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    circuit_opened_count: int = 0
    circuit_closed_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    average_response_time: float = 0.0
    events: List[CircuitEvent] = field(default_factory=list)
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    def get_failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    def get_timeout_rate(self) -> float:
        """Calculate timeout rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.timeout_requests / self.total_requests) * 100


class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    Prevents cascading failures by breaking the circuit
    when failure threshold is reached.
    """
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception, timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.timeout = timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.metrics = CircuitMetrics()
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"circuit_breaker.{name}")
        
        # Event callbacks
        self.on_circuit_opened: Optional[Callable] = None
        self.on_circuit_closed: Optional[Callable] = None
        self.on_circuit_half_opened: Optional[Callable] = None
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator for circuit breaker."""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
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
        start_time = time.time()
        
        with self.lock:
            self.metrics.total_requests += 1
        
        try:
            # Check if circuit is open
            if self.is_open():
                raise IntegrationException(f"Circuit breaker '{self.name}' is open")
            
            # Execute function
            if self.state == CircuitState.HALF_OPEN:
                # In half-open state, allow one request to test
                result = self._execute_with_timeout(func, *args, **kwargs)
                self._on_success()
                return result
            else:
                # Normal execution
                result = self._execute_with_timeout(func, *args, **kwargs)
                self._on_success()
                return result
        
        except self.expected_exception as e:
            duration = time.time() - start_time
            self._on_failure(str(e), duration)
            raise
        
        except Exception as e:
            duration = time.time() - start_time
            self._on_failure(str(e), duration)
            raise
        
        finally:
            duration = time.time() - start_time
            self._update_response_time(duration)
    
    def _execute_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout."""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution timed out after {self.timeout} seconds")
        
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(self.timeout))
        
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel timeout
            return result
        
        finally:
            signal.signal(signal.SIGALRM, old_handler)
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        with self.lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (self.last_failure_time and 
                    timezone.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)):
                    self._transition_to_half_open()
                    return False
                return True
            return False
    
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN
    
    def _on_success(self):
        """Handle successful request."""
        with self.lock:
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = timezone.now()
            
            # Reset failure count
            self.failure_count = 0
            
            # If in half-open state, close the circuit
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
            
            # Record success event
            event = CircuitEvent(
                timestamp=timezone.now(),
                event_type=CircuitEventType.SUCCESS
            )
            self.metrics.events.append(event)
            
            # Keep only last 100 events
            if len(self.metrics.events) > 100:
                self.metrics.events = self.metrics.events[-100:]
    
    def _on_failure(self, error_message: str, duration: float):
        """Handle failed request."""
        with self.lock:
            self.failure_count += 1
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = timezone.now()
            
            # Record failure event
            event = CircuitEvent(
                timestamp=timezone.now(),
                event_type=CircuitEventType.FAILURE,
                duration=duration,
                error_message=error_message
            )
            self.metrics.events.append(event)
            
            # Keep only last 100 events
            if len(self.metrics.events) > 100:
                self.metrics.events = self.metrics.events[-100:]
            
            # Check if circuit should open
            if (self.state == CircuitState.CLOSED and 
                self.failure_count >= self.failure_threshold):
                self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
    
    def _on_timeout(self, duration: float):
        """Handle timeout."""
        with self.lock:
            self.metrics.timeout_requests += 1
            self.metrics.last_failure_time = timezone.now()
            
            # Record timeout event
            event = CircuitEvent(
                timestamp=timezone.now(),
                event_type=CircuitEventType.TIMEOUT,
                duration=duration,
                error_message="Request timeout"
            )
            self.metrics.events.append(event)
            
            # Keep only last 100 events
            if len(self.metrics.events) > 100:
                self.metrics.events = self.metrics.events[-100:]
            
            # Timeout counts as failure
            self._on_failure("Request timeout", duration)
    
    def _transition_to_open(self):
        """Transition circuit to open state."""
        self.state = CircuitState.OPEN
        self.metrics.circuit_opened_count += 1
        
        self.logger.warning(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")
        
        # Record circuit opened event
        event = CircuitEvent(
            timestamp=timezone.now(),
            event_type=CircuitEventType.CIRCUIT_OPENED
        )
        self.metrics.events.append(event)
        
        # Call callback if set
        if self.on_circuit_opened:
            try:
                self.on_circuit_opened(self)
            except Exception as e:
                self.logger.error(f"Error in circuit opened callback: {str(e)}")
    
    def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        
        self.logger.info(f"Circuit breaker '{self.name}' transitioned to half-open")
        
        # Record circuit half-opened event
        event = CircuitEvent(
            timestamp=timezone.now(),
            event_type=CircuitEventType.CIRCUIT_HALF_OPENED
        )
        self.metrics.events.append(event)
        
        # Call callback if set
        if self.on_circuit_half_opened:
            try:
                self.on_circuit_half_opened(self)
            except Exception as e:
                self.logger.error(f"Error in circuit half-opened callback: {str(e)}")
    
    def _transition_to_closed(self):
        """Transition circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.metrics.circuit_closed_count += 1
        
        self.logger.info(f"Circuit breaker '{self.name}' closed")
        
        # Record circuit closed event
        event = CircuitEvent(
            timestamp=timezone.now(),
            event_type=CircuitEventType.CIRCUIT_CLOSED
        )
        self.metrics.events.append(event)
        
        # Call callback if set
        if self.on_circuit_closed:
            try:
                self.on_circuit_closed(self)
            except Exception as e:
                self.logger.error(f"Error in circuit closed callback: {str(e)}")
    
    def _update_response_time(self, duration: float):
        """Update average response time."""
        with self.lock:
            if self.metrics.total_requests == 1:
                self.metrics.average_response_time = duration
            else:
                # Calculate exponential moving average
                alpha = 0.1
                self.metrics.average_response_time = (
                    alpha * duration + 
                    (1 - alpha) * self.metrics.average_response_time
                )
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            self.metrics = CircuitMetrics()
            
            self.logger.info(f"Circuit breaker '{self.name}' reset")
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self.lock:
            return self.state
    
    def get_metrics(self) -> CircuitMetrics:
        """Get circuit metrics."""
        with self.lock:
            return self.metrics
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive circuit status."""
        with self.lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'failure_threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'metrics': {
                    'total_requests': self.metrics.total_requests,
                    'successful_requests': self.metrics.successful_requests,
                    'failed_requests': self.metrics.failed_requests,
                    'timeout_requests': self.metrics.timeout_requests,
                    'success_rate': self.metrics.get_success_rate(),
                    'failure_rate': self.metrics.get_failure_rate(),
                    'timeout_rate': self.metrics.get_timeout_rate(),
                    'average_response_time': self.metrics.average_response_time,
                    'circuit_opened_count': self.metrics.circuit_opened_count,
                    'circuit_closed_count': self.metrics.circuit_closed_count,
                }
            }


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Provides centralized management and monitoring
    of circuit breakers.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._setup_default_circuit_breakers()
    
    def _setup_default_circuit_breakers(self):
        """Setup default circuit breakers."""
        default_breakers = [
            {
                'name': 'webhook_service',
                'failure_threshold': 5,
                'recovery_timeout': 60,
                'timeout': 30.0,
            },
            {
                'name': 'api_service',
                'failure_threshold': 3,
                'recovery_timeout': 30,
                'timeout': 15.0,
            },
            {
                'name': 'database_service',
                'failure_threshold': 10,
                'recovery_timeout': 120,
                'timeout': 60.0,
            },
        ]
        
        for config in default_breakers:
            self.create_circuit_breaker(**config)
    
    def create_circuit_breaker(self, name: str, failure_threshold: int = 5,
                             recovery_timeout: int = 60, expected_exception: type = Exception,
                             timeout: float = 30.0) -> CircuitBreaker:
        """
        Create circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Failure threshold
            recovery_timeout: Recovery timeout in seconds
            expected_exception: Expected exception type
            timeout: Request timeout
            
        Returns:
            Created circuit breaker
        """
        circuit_breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            timeout=timeout
        )
        
        self.circuit_breakers[name] = circuit_breaker
        self.logger.info(f"Circuit breaker created: {name}")
        
        return circuit_breaker
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            Circuit breaker or None
        """
        return self.circuit_breakers.get(name)
    
    def remove_circuit_breaker(self, name: str) -> bool:
        """
        Remove circuit breaker.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            True if removed
        """
        if name in self.circuit_breakers:
            del self.circuit_breakers[name]
            self.logger.info(f"Circuit breaker removed: {name}")
            return True
        return False
    
    def get_all_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self.circuit_breakers.copy()
    
    def get_circuit_breakers_by_state(self, state: CircuitState) -> List[CircuitBreaker]:
        """
        Get circuit breakers by state.
        
        Args:
            state: Circuit state
            
        Returns:
            List of circuit breakers
        """
        return [cb for cb in self.circuit_breakers.values() if cb.get_state() == state]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_breakers = len(self.circuit_breakers)
        closed_breakers = len(self.get_circuit_breakers_by_state(CircuitState.CLOSED))
        open_breakers = len(self.get_circuit_breakers_by_state(CircuitState.OPEN))
        half_open_breakers = len(self.get_circuit_breakers_by_state(CircuitState.HALF_OPEN))
        
        # Aggregate metrics
        total_requests = 0
        total_successes = 0
        total_failures = 0
        total_timeouts = 0
        
        for circuit_breaker in self.circuit_breakers.values():
            metrics = circuit_breaker.get_metrics()
            total_requests += metrics.total_requests
            total_successes += metrics.successful_requests
            total_failures += metrics.failed_requests
            total_timeouts += metrics.timeout_requests
        
        overall_success_rate = (total_successes / total_requests * 100) if total_requests > 0 else 0
        overall_failure_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0
        overall_timeout_rate = (total_timeouts / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_circuit_breakers': total_breakers,
            'closed_breakers': closed_breakers,
            'open_breakers': open_breakers,
            'half_open_breakers': half_open_breakers,
            'overall_metrics': {
                'total_requests': total_requests,
                'successful_requests': total_successes,
                'failed_requests': total_failures,
                'timeout_requests': total_timeouts,
                'success_rate': overall_success_rate,
                'failure_rate': overall_failure_rate,
                'timeout_rate': overall_timeout_rate,
            },
            'circuit_breaker_details': {
                name: cb.get_status()
                for name, cb in self.circuit_breakers.items()
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all circuit breakers."""
        health_status = {
            'overall': 'healthy',
            'total_circuit_breakers': len(self.circuit_breakers),
            'healthy_breakers': 0,
            'unhealthy_breakers': 0,
            'circuit_breaker_health': {},
            'issues': [],
        }
        
        for name, circuit_breaker in self.circuit_breakers.items():
            state = circuit_breaker.get_state()
            
            if state == CircuitState.OPEN:
                health_status['unhealthy_breakers'] += 1
                health_status['circuit_breaker_health'][name] = 'unhealthy'
                health_status['issues'].append(f"Circuit breaker {name} is open")
            elif state == CircuitState.HALF_OPEN:
                health_status['unhealthy_breakers'] += 1
                health_status['circuit_breaker_health'][name] = 'degraded'
                health_status['issues'].append(f"Circuit breaker {name} is half-open")
            else:
                health_status['healthy_breakers'] += 1
                health_status['circuit_breaker_health'][name] = 'healthy'
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers."""
        for circuit_breaker in self.circuit_breakers.values():
            circuit_breaker.reset()
        
        self.logger.info("All circuit breakers reset")


# Global circuit breaker registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


# Convenience functions
def create_circuit_breaker(name: str, failure_threshold: int = 5,
                         recovery_timeout: int = 60, expected_exception: type = Exception,
                         timeout: float = 30.0) -> CircuitBreaker:
    """Create circuit breaker."""
    return circuit_breaker_registry.create_circuit_breaker(
        name, failure_threshold, recovery_timeout, expected_exception, timeout
    )


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get circuit breaker by name."""
    return circuit_breaker_registry.get_circuit_breaker(name)


def protect_with_circuit_breaker(name: str, failure_threshold: int = 5,
                               recovery_timeout: int = 60, expected_exception: type = Exception,
                               timeout: float = 30.0):
    """Decorator for protecting functions with circuit breaker."""
    circuit_breaker = circuit_breaker_registry.create_circuit_breaker(
        name, failure_threshold, recovery_timeout, expected_exception, timeout
    )
    return circuit_breaker


def get_circuit_breaker_statistics() -> Dict[str, Any]:
    """Get circuit breaker statistics."""
    return circuit_breaker_registry.get_statistics()


def perform_circuit_breaker_health_check() -> Dict[str, Any]:
    """Perform circuit breaker health check."""
    return circuit_breaker_registry.health_check()
