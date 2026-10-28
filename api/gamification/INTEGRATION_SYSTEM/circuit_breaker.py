"""
Circuit Breaker Pattern — Circuit breaker implementation for fault tolerance.

This module provides a comprehensive circuit breaker implementation
for handling failures in external service calls and integrations.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, CircuitBreakerOpenError, CircuitBreakerHalfOpenError,
    TimeoutError, ServiceUnavailableError
)
from .integ_signals import (
    circuit_breaker_opened, circuit_breaker_closed, circuit_breaker_half_open,
    circuit_breaker_blocked
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker States
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    """Circuit breaker state enumeration."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, blocking calls
    HALF_OPEN = "half_open"  # Testing if service has recovered


class FailureType(Enum):
    """Failure type enumeration."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    BUSINESS_ERROR = "business_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Circuit Breaker Data Classes
# ---------------------------------------------------------------------------

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    service_name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    expected_recovery_time: float = 30.0  # seconds
    monitoring_period: float = 300.0  # seconds
    success_threshold: int = 3  # successes needed to close circuit
    timeout: float = 30.0  # seconds for individual calls
    max_concurrent_calls: int = 100
    sliding_window_size: int = 100  # number of recent calls to consider
    reset_timeout: float = 600.0  # seconds before forced reset
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "expected_recovery_time": self.expected_recovery_time,
            "monitoring_period": self.monitoring_period,
            "success_threshold": self.success_threshold,
            "timeout": self.timeout,
            "max_concurrent_calls": self.max_concurrent_calls,
            "sliding_window_size": self.sliding_window_size,
            "reset_timeout": self.reset_timeout,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


@dataclass
class CallResult:
    """Result of a circuit breaker call."""
    
    success: bool
    execution_time: float
    error: Optional[Exception] = None
    failure_type: Optional[FailureType] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    response_data: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "execution_time": self.execution_time,
            "error": str(self.error) if self.error else None,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "timestamp": self.timestamp.isoformat(),
            "response_data": self.response_data
        }


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker."""
    
    service_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    current_state: CircuitState = CircuitState.CLOSED
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    circuit_opened_time: Optional[datetime] = None
    circuit_closed_time: Optional[datetime] = None
    average_execution_time: float = 0.0
    failure_rate: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    current_concurrent_calls: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    @property
    def uptime_percentage(self) -> float:
        """Calculate uptime percentage."""
        if not self.circuit_opened_time:
            return 100.0
        
        total_time = (datetime.now(timezone.utc) - (self.circuit_closed_time or self.circuit_opened_time)).total_seconds()
        downtime = (datetime.now(timezone.utc) - self.circuit_opened_time).total_seconds() if self.current_state == CircuitState.OPEN else 0
        
        return max(0.0, 100.0 - (downtime / total_time * 100.0))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "timeout_calls": self.timeout_calls,
            "current_state": self.current_state.value,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "circuit_opened_time": self.circuit_opened_time.isoformat() if self.circuit_opened_time else None,
            "circuit_closed_time": self.circuit_closed_time.isoformat() if self.circuit_closed_time else None,
            "average_execution_time": self.average_execution_time,
            "failure_rate": self.failure_rate,
            "success_rate": self.success_rate,
            "uptime_percentage": self.uptime_percentage,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "current_concurrent_calls": self.current_concurrent_calls
        }


# ---------------------------------------------------------------------------
# Abstract Circuit Breaker
# ---------------------------------------------------------------------------

class BaseCircuitBreaker(ABC):
    """Abstract base class for circuit breakers."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics(service_name=config.service_name)
        self.call_history: List[CallResult] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = threading.RLock()
        self._last_state_change = datetime.now(timezone.utc)
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @abstractmethod
    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function through the circuit breaker."""
        pass
    
    @abstractmethod
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        pass
    
    @abstractmethod
    def is_open(self) -> bool:
        """Check if circuit is open."""
        pass
    
    @abstractmethod
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        pass
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        with self._lock:
            self._update_metrics()
            return self.metrics
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes = 0
            self.metrics.circuit_closed_time = datetime.now(timezone.utc)
            self._last_state_change = datetime.now(timezone.utc)
            self.call_history.clear()
            
            self.emit_event("reset")
            self.logger.info(f"Circuit breaker reset for service: {self.config.service_name}")
    
    def force_open(self) -> None:
        """Force the circuit breaker to open state."""
        with self._lock:
            self._transition_to_open()
            self.logger.info(f"Circuit breaker forced open for service: {self.config.service_name}")
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add an event handler."""
        with self._lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable) -> None:
        """Remove an event handler."""
        with self._lock:
            if event_type in self._event_handlers:
                try:
                    self._event_handlers[event_type].remove(handler)
                except ValueError:
                    pass
    
    def emit_event(self, event_type: str, **kwargs: Any) -> None:
        """Emit an event to all handlers."""
        with self._lock:
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        handler(self, **kwargs)
                    except Exception as e:
                        self.logger.error(f"Error in event handler for {event_type}: {e}")
    
    def _record_call(self, result: CallResult) -> None:
        """Record a call result."""
        with self._lock:
            self.call_history.append(result)
            
            # Maintain sliding window
            if len(self.call_history) > self.config.sliding_window_size:
                self.call_history.pop(0)
            
            # Update metrics
            self.metrics.total_calls += 1
            self.metrics.last_failure_time = datetime.now(timezone.utc) if not result.success else self.metrics.last_failure_time
            self.metrics.last_success_time = datetime.now(timezone.utc) if result.success else self.metrics.last_success_time
            
            if result.success:
                self.metrics.successful_calls += 1
                self.metrics.consecutive_failures = 0
                self.metrics.consecutive_successes += 1
            else:
                self.metrics.failed_calls += 1
                self.metrics.consecutive_failures += 1
                self.metrics.consecutive_successes = 0
            
            # Update average execution time
            total_time = self.metrics.average_execution_time * (self.metrics.total_calls - 1) + result.execution_time
            self.metrics.average_execution_time = total_time / self.metrics.total_calls
            
            # Update failure rate
            self.metrics.failure_rate = self.metrics.failed_calls / self.metrics.total_calls
    
    def _update_metrics(self) -> None:
        """Update derived metrics."""
        # Update current state in metrics
        self.metrics.current_state = self.state
        
        # Calculate failure rate from recent calls
        if self.call_history:
            recent_failures = sum(1 for call in self.call_history if not call.success)
            self.metrics.failure_rate = recent_failures / len(self.call_history)
    
    def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.metrics.circuit_opened_time = datetime.now(timezone.utc)
            self._last_state_change = datetime.now(timezone.utc)
            
            self.emit_event("opened")
            circuit_breaker_opened.send(
                sender=self,
                service_name=self.config.service_name,
                failure_count=self.metrics.consecutive_failures,
                threshold=self.config.failure_threshold
            )
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        if self.state == CircuitState.OPEN:
            self.state = CircuitState.HALF_OPEN
            self._last_state_change = datetime.now(timezone.utc)
            
            self.emit_event("half_open")
            circuit_breaker_half_open.send(
                sender=self,
                service_name=self.config.service_name
            )
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.metrics.circuit_closed_time = datetime.now(timezone.utc)
            self._last_state_change = datetime.now(timezone.utc)
            
            self.emit_event("closed")
            circuit_breaker_closed.send(
                sender=self,
                service_name=self.config.service_name,
                success_count=self.metrics.consecutive_successes
            )


# ---------------------------------------------------------------------------
# Standard Circuit Breaker Implementation
# ---------------------------------------------------------------------------

class StandardCircuitBreaker(BaseCircuitBreaker):
    """Standard circuit breaker implementation."""
    
    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function through the circuit breaker."""
        if not self.config.enabled:
            return func(*args, **kwargs)
        
        start_time = time.time()
        
        # Check circuit state
        if self.is_open():
            self.emit_event("blocked")
            circuit_breaker_blocked.send(
                sender=self,
                service_name=self.config.service_name,
                request_id=str(id(func))
            )
            raise CircuitBreakerOpenError(f"Circuit breaker is open for service: {self.config.service_name}")
        
        # Check concurrent call limit
        with self._lock:
            if self.metrics.current_concurrent_calls >= self.config.max_concurrent_calls:
                raise ServiceUnavailableError(f"Maximum concurrent calls exceeded for service: {self.config.service_name}")
            
            self.metrics.current_concurrent_calls += 1
        
        try:
            # Execute the function
            if self.config.timeout > 0:
                result = self._execute_with_timeout(func, self.config.timeout, *args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            execution_time = time.time() - start_time
            
            # Record successful call
            call_result = CallResult(
                success=True,
                execution_time=execution_time,
                response_data=result
            )
            self._record_call(call_result)
            
            # Check if we should transition to closed (from half-open)
            if self.is_half_open() and self.metrics.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Determine failure type
            failure_type = self._classify_failure(e)
            
            # Record failed call
            call_result = CallResult(
                success=False,
                execution_time=execution_time,
                error=e,
                failure_type=failure_type
            )
            self._record_call(call_result)
            
            # Check if we should open the circuit
            if self.metrics.consecutive_failures >= self.config.failure_threshold:
                self._transition_to_open()
            
            raise e
            
        finally:
            with self._lock:
                self.metrics.current_concurrent_calls -= 1
    
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            # Check if circuit should transition from half-open to closed
            if self.state == CircuitState.HALF_OPEN:
                return self.metrics.consecutive_successes >= self.config.success_threshold
            
            return False
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self.metrics.circuit_opened_time:
                    time_since_open = (datetime.now(timezone.utc) - self.metrics.circuit_opened_time).total_seconds()
                    if time_since_open >= self.config.recovery_timeout:
                        self._transition_to_half_open()
                        return False
                return True
            
            return False
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        with self._lock:
            return self.state == CircuitState.HALF_OPEN
    
    def _execute_with_timeout(self, func: Callable, timeout: float, *args: Any, **kwargs: Any) -> Any:
        """Execute function with timeout."""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function call timed out after {timeout} seconds")
        
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Restore old handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    
    def _classify_failure(self, error: Exception) -> FailureType:
        """Classify the type of failure."""
        if isinstance(error, TimeoutError):
            return FailureType.TIMEOUT
        elif isinstance(error, ConnectionError):
            return FailureType.CONNECTION_ERROR
        elif hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            # HTTP error
            return FailureType.HTTP_ERROR
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            return FailureType.BUSINESS_ERROR
        elif isinstance(error, (OSError, IOError, MemoryError)):
            return FailureType.SYSTEM_ERROR
        else:
            return FailureType.UNKNOWN


# ---------------------------------------------------------------------------
# Circuit Breaker Registry
# ---------------------------------------------------------------------------

class CircuitBreakerRegistry:
    """Registry for managing circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, BaseCircuitBreaker] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def register_circuit_breaker(self, circuit_breaker: BaseCircuitBreaker) -> None:
        """Register a circuit breaker."""
        with self._lock:
            service_name = circuit_breaker.config.service_name
            if service_name in self.circuit_breakers:
                raise IntegrationError(f"Circuit breaker for service '{service_name}' already exists")
            
            self.circuit_breakers[service_name] = circuit_breaker
            self.logger.info(f"Registered circuit breaker for service: {service_name}")
    
    def unregister_circuit_breaker(self, service_name: str) -> bool:
        """Unregister a circuit breaker."""
        with self._lock:
            if service_name in self.circuit_breakers:
                del self.circuit_breakers[service_name]
                self.logger.info(f"Unregistered circuit breaker for service: {service_name}")
                return True
            return False
    
    def get_circuit_breaker(self, service_name: str) -> Optional[BaseCircuitBreaker]:
        """Get a circuit breaker by service name."""
        with self._lock:
            return self.circuit_breakers.get(service_name)
    
    def list_circuit_breakers(self) -> List[BaseCircuitBreaker]:
        """List all circuit breakers."""
        with self._lock:
            return list(self.circuit_breakers.values())
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all circuit breakers."""
        metrics = {}
        
        for service_name, circuit_breaker in self.circuit_breakers.items():
            try:
                metrics[service_name] = circuit_breaker.get_metrics().to_dict()
            except Exception as e:
                metrics[service_name] = {"error": str(e)}
        
        return {
            "circuit_breakers": metrics,
            "total_circuit_breakers": len(self.circuit_breakers),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for circuit_breaker in self.circuit_breakers.values():
                circuit_breaker.reset()
        
        self.logger.info("All circuit breakers reset")
    
    def force_open_all(self) -> None:
        """Force all circuit breakers to open."""
        with self._lock:
            for circuit_breaker in self.circuit_breakers.values():
                circuit_breaker.force_open()
        
        self.logger.info("All circuit breakers forced open")


# Global circuit breaker registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


# ---------------------------------------------------------------------------
# Decorator and Convenience Functions
# ---------------------------------------------------------------------------

def circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    timeout: float = 30.0,
    **kwargs: Any
) -> Callable:
    """Decorator to add circuit breaker protection to a function."""
    
    def decorator(func: Callable) -> Callable:
        # Create or get circuit breaker
        circuit_breaker = circuit_breaker_registry.get_circuit_breaker(service_name)
        
        if not circuit_breaker:
            config = CircuitBreakerConfig(
                service_name=service_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                timeout=timeout,
                **kwargs
            )
            circuit_breaker = StandardCircuitBreaker(config)
            circuit_breaker_registry.register_circuit_breaker(circuit_breaker)
        
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


def call_with_circuit_breaker(
    service_name: str,
    func: Callable,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Call a function with circuit breaker protection."""
    circuit_breaker = circuit_breaker_registry.get_circuit_breaker(service_name)
    
    if not circuit_breaker:
        config = CircuitBreakerConfig(service_name=service_name)
        circuit_breaker = StandardCircuitBreaker(config)
        circuit_breaker_registry.register_circuit_breaker(circuit_breaker)
    
    return circuit_breaker.call(func, *args, **kwargs)


def create_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    timeout: float = 30.0,
    **kwargs: Any
) -> BaseCircuitBreaker:
    """Create a new circuit breaker."""
    config = CircuitBreakerConfig(
        service_name=service_name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        timeout=timeout,
        **kwargs
    )
    
    circuit_breaker = StandardCircuitBreaker(config)
    circuit_breaker_registry.register_circuit_breaker(circuit_breaker)
    
    return circuit_breaker


# Initialize logging
logger.info("Circuit breaker module initialized")
