# engagement/integration_system/circuit_breaker.py
"""
Circuit breaker pattern implementation for integration system.
Provides fault tolerance and automatic recovery for integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
import time
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, DEFAULT_CONFIG, CACHE_KEYS
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureRateThreshold(Enum):
    """Failure rate threshold types."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    ADAPTIVE = "adaptive"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    id: str
    name: str
    failure_threshold: int = 5
    timeout: int = 60  # seconds
    recovery_timeout: int = 30  # seconds
    max_requests: int = 100
    window_size: int = 10
    failure_rate_threshold: float = 0.5
    success_threshold: int = 3
    monitoring_enabled: bool = True
    auto_recovery: bool = True
    custom_callbacks: Dict[str, Callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    current_consecutive_failures: int = 0
    max_consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: List[Dict[str, Any]] = field(default_factory=list)
    response_times: List[float] = field(default_factory=list)
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)


class BaseCircuitBreaker(ABC):
    """Base circuit breaker class."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.metrics = CircuitBreakerMetrics()
        self.state = CircuitBreakerState.CLOSED
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        self._lock = threading.RLock()
        self._last_state_change = timezone.now()
        self._callbacks = {}
        
        # Register default callbacks
        self._register_default_callbacks()
    
    @abstractmethod
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        pass
    
    @abstractmethod
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        pass
    
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.state
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self.metrics
    
    def _change_state(self, new_state: CircuitBreakerState, reason: str = ""):
        """Change circuit breaker state."""
        old_state = self.state
        self.state = new_state
        self._last_state_change = timezone.now()
        
        # Record state change
        self.metrics.state_changes.append({
            'from_state': old_state.value,
            'to_state': new_state.value,
            'timestamp': self._last_state_change.isoformat(),
            'reason': reason,
            'metrics': {
                'total_requests': self.metrics.total_requests,
                'failure_rate': self.metrics.failure_rate,
                'consecutive_failures': self.metrics.current_consecutive_failures
            }
        })
        
        # Log state change
        self.logger.info(f"Circuit breaker {self.config.name} changed from {old_state.value} to {new_state.value}: {reason}")
        
        # Trigger callbacks
        self._trigger_callbacks('state_change', {
            'old_state': old_state,
            'new_state': new_state,
            'reason': reason
        })
        
        # Cache state
        self._cache_state()
    
    def _record_success(self, response_time: float = 0):
        """Record successful request."""
        with self._lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.current_consecutive_failures = 0
            self.metrics.last_success_time = timezone.now()
            
            if response_time > 0:
                self.metrics.response_times.append(response_time)
                # Keep only recent response times
                if len(self.metrics.response_times) > self.config.window_size:
                    self.metrics.response_times = self.metrics.response_times[-self.config.window_size:]
            
            # Update max consecutive failures
            if self.metrics.current_consecutive_failures > self.metrics.max_consecutive_failures:
                self.metrics.max_consecutive_failures = self.metrics.current_consecutive_failures
            
            # Check if we should close the circuit
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.metrics.successful_requests >= self.config.success_threshold:
                    self._change_state(CircuitBreakerState.CLOSED, "Success threshold reached")
    
    def _record_failure(self):
        """Record failed request."""
        with self._lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.current_consecutive_failures += 1
            self.metrics.last_failure_time = timezone.now()
            
            # Update max consecutive failures
            if self.metrics.current_consecutive_failures > self.metrics.max_consecutive_failures:
                self.metrics.max_consecutive_failures = self.metrics.current_consecutive_failures
            
            # Check if we should open the circuit
            if self.state == CircuitBreakerState.CLOSED:
                if self.metrics.current_consecutive_failures >= self.config.failure_threshold:
                    self._change_state(CircuitBreakerState.OPEN, f"Failure threshold reached: {self.config.failure_threshold}")
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self._change_state(CircuitBreakerState.OPEN, "Failure in half-open state")
    
    def _register_default_callbacks(self):
        """Register default callbacks."""
        self._callbacks['state_change'] = []
        self._callbacks['failure'] = []
        self._callbacks['success'] = []
    
    def add_callback(self, event: str, callback: Callable):
        """Add callback for event."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _trigger_callbacks(self, event: str, data: Dict[str, Any]):
        """Trigger callbacks for event."""
        callbacks = self._callbacks.get(event, [])
        for callback in callbacks:
            try:
                callback(self, data)
            except Exception as exc:
                self.logger.error(f"Callback error for event {event}: {exc}")
    
    def _cache_state(self):
        """Cache circuit breaker state."""
        cache_key = CACHE_KEYS['CIRCUIT_BREAKER_STATE'].format(integration_id=self.config.id)
        cache.set(cache_key, {
            'state': self.state.value,
            'metrics': self.metrics.__dict__,
            'last_change': self._last_state_change.isoformat()
        }, timeout=300)  # 5 minutes
    
    def _load_cached_state(self):
        """Load cached state."""
        cache_key = CACHE_KEYS['CIRCUIT_BREAKER_STATE'].format(integration_id=self.config.id)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            try:
                self.state = CircuitBreakerState(cached_data['state'])
                # Restore metrics
                for key, value in cached_data['metrics'].items():
                    setattr(self.metrics, key, value)
                self._last_state_change = datetime.fromisoformat(cached_data['last_change'])
            except Exception as exc:
                self.logger.error(f"Failed to load cached state: {exc}")


class DefaultCircuitBreaker(BaseCircuitBreaker):
    """Default circuit breaker implementation."""
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if not self.can_execute():
            raise Exception(f"Circuit breaker is {self.state.value}")
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            
            self._record_success(response_time)
            self._trigger_callbacks('success', {'result': result, 'response_time': response_time})
            
            return result
            
        except Exception as exc:
            self._record_failure()
            self._trigger_callbacks('failure', {'error': exc})
            raise
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                # Check if timeout has passed
                if self.metrics.last_failure_time:
                    time_since_failure = timezone.now() - self.metrics.last_failure_time
                    if time_since_failure.total_seconds() >= self.config.timeout:
                        self._change_state(CircuitBreakerState.HALF_OPEN, "Timeout expired")
                        return True
                return False
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Allow limited requests in half-open state
                return self.metrics.total_requests < self.config.max_requests
            
            return True
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._change_state(CircuitBreakerState.CLOSED, "Manual reset")
            self.metrics = CircuitBreakerMetrics()


class AdaptiveCircuitBreaker(BaseCircuitBreaker):
    """Adaptive circuit breaker with dynamic thresholds."""
    
    def __init__(self, config: CircuitBreakerConfig):
        super().__init__(config)
        self._adaptive_threshold = config.failure_threshold
        self._performance_window = []
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with adaptive circuit breaker protection."""
        if not self.can_execute():
            raise Exception(f"Circuit breaker is {self.state.value}")
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            
            self._record_success(response_time)
            self._update_performance(response_time)
            self._adjust_threshold()
            self._trigger_callbacks('success', {'result': result, 'response_time': response_time})
            
            return result
            
        except Exception as exc:
            self._record_failure()
            self._trigger_callbacks('failure', {'error': exc})
            raise
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                # Check if timeout has passed
                if self.metrics.last_failure_time:
                    time_since_failure = timezone.now() - self.metrics.last_failure_time
                    if time_since_failure.total_seconds() >= self.config.timeout:
                        self._change_state(CircuitBreakerState.HALF_OPEN, "Timeout expired")
                        return True
                return False
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Allow limited requests in half-open state
                return self.metrics.total_requests < self.config.max_requests
            
            return True
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._change_state(CircuitBreakerState.CLOSED, "Manual reset")
            self.metrics = CircuitBreakerMetrics()
            self._adaptive_threshold = self.config.failure_threshold
            self._performance_window = []
    
    def _update_performance(self, response_time: float):
        """Update performance window."""
        self._performance_window.append(response_time)
        
        # Keep only recent performance data
        if len(self._performance_window) > self.config.window_size:
            self._performance_window = self._performance_window[-self.config.window_size:]
    
    def _adjust_threshold(self):
        """Adjust failure threshold based on performance."""
        if len(self._performance_window) < self.config.window_size:
            return
        
        avg_response_time = sum(self._performance_window) / len(self._performance_window)
        
        # Adjust threshold based on performance
        if avg_response_time > 5.0:  # Slow performance
            self._adaptive_threshold = max(3, self._adaptive_threshold - 1)
        elif avg_response_time < 1.0:  # Good performance
            self._adaptive_threshold = min(10, self._adaptive_threshold + 1)
        
        # Update threshold if changed
        if self._adaptive_threshold != self.config.failure_threshold:
            old_threshold = self.config.failure_threshold
            self.config.failure_threshold = self._adaptive_threshold
            self.logger.info(f"Adaptive threshold adjusted from {old_threshold} to {self._adaptive_threshold}")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._circuit_breakers: Dict[str, BaseCircuitBreaker] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.CircuitBreakerRegistry")
    
    def register(self, circuit_breaker: BaseCircuitBreaker) -> str:
        """Register a circuit breaker."""
        with self._lock:
            self._circuit_breakers[circuit_breaker.config.id] = circuit_breaker
            self.logger.info(f"Registered circuit breaker: {circuit_breaker.config.id}")
            return circuit_breaker.config.id
    
    def unregister(self, circuit_breaker_id: str) -> bool:
        """Unregister a circuit breaker."""
        with self._lock:
            if circuit_breaker_id in self._circuit_breakers:
                del self._circuit_breakers[circuit_breaker_id]
                self.logger.info(f"Unregistered circuit breaker: {circuit_breaker_id}")
                return True
        return False
    
    def get(self, circuit_breaker_id: str) -> Optional[BaseCircuitBreaker]:
        """Get circuit breaker by ID."""
        return self._circuit_breakers.get(circuit_breaker_id)
    
    def call(self, circuit_breaker_id: str, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        circuit_breaker = self.get(circuit_breaker_id)
        if not circuit_breaker:
            raise ValueError(f"Circuit breaker {circuit_breaker_id} not found")
        
        return circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, CircuitBreakerMetrics]:
        """Get metrics for all circuit breakers."""
        with self._lock:
            return {
                cb_id: cb.get_metrics()
                for cb_id, cb in self._circuit_breakers.items()
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            total_breakers = len(self._circuit_breakers)
            state_counts = {}
            total_requests = 0
            total_failures = 0
            
            for cb in self._circuit_breakers.values():
                state = cb.get_state()
                state_counts[state.value] = state_counts.get(state.value, 0) + 1
                
                metrics = cb.get_metrics()
                total_requests += metrics.total_requests
                total_failures += metrics.failed_requests
            
            overall_failure_rate = (total_failures / total_requests) if total_requests > 0 else 0
            
            return {
                'total_circuit_breakers': total_breakers,
                'state_counts': state_counts,
                'total_requests': total_requests,
                'total_failures': total_failures,
                'overall_failure_rate': overall_failure_rate,
                'last_updated': timezone.now().isoformat(),
            }
    
    def reset_all(self) -> int:
        """Reset all circuit breakers."""
        reset_count = 0
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()
                reset_count += 1
        
        self.logger.info(f"Reset {reset_count} circuit breakers")
        return reset_count
    
    def reset_by_state(self, state: CircuitBreakerState) -> int:
        """Reset circuit breakers by state."""
        reset_count = 0
        with self._lock:
            for cb in self._circuit_breakers.values():
                if cb.get_state() == state:
                    cb.reset()
                    reset_count += 1
        
        self.logger.info(f"Reset {reset_count} circuit breakers in {state.value} state")
        return reset_count
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all circuit breakers."""
        healthy_breakers = 0
        unhealthy_breakers = 0
        breaker_status = {}
        
        for cb_id, cb in self._circuit_breakers.items():
            try:
                metrics = cb.get_metrics()
                is_healthy = (
                    cb.get_state() != CircuitBreakerState.OPEN and
                    metrics.failure_rate < 0.5  # Less than 50% failure rate
                )
                
                if is_healthy:
                    healthy_breakers += 1
                else:
                    unhealthy_breakers += 1
                
                breaker_status[cb_id] = {
                    'state': cb.get_state().value,
                    'healthy': is_healthy,
                    'failure_rate': metrics.failure_rate,
                    'consecutive_failures': metrics.current_consecutive_failures
                }
                
            except Exception as exc:
                self.logger.error(f"Health check failed for {cb_id}: {exc}")
                unhealthy_breakers += 1
                breaker_status[cb_id] = {
                    'state': 'error',
                    'healthy': False,
                    'error': str(exc)
                }
        
        return {
            'total_breakers': len(self._circuit_breakers),
            'healthy_breakers': healthy_breakers,
            'unhealthy_breakers': unhealthy_breakers,
            'breaker_status': breaker_status,
            'overall_healthy': unhealthy_breakers == 0,
            'last_updated': timezone.now().isoformat()
        }


class CircuitBreakerFactory:
    """Factory for creating circuit breakers."""
    
    @staticmethod
    def create_default(config: CircuitBreakerConfig) -> DefaultCircuitBreaker:
        """Create default circuit breaker."""
        return DefaultCircuitBreaker(config)
    
    @staticmethod
    def create_adaptive(config: CircuitBreakerConfig) -> AdaptiveCircuitBreaker:
        """Create adaptive circuit breaker."""
        return AdaptiveCircuitBreaker(config)
    
    @staticmethod
    def create(config: CircuitBreakerConfig, breaker_type: str = 'default') -> BaseCircuitBreaker:
        """Create circuit breaker by type."""
        if breaker_type == 'adaptive':
            return AdaptiveCircuitBreaker(config)
        else:
            return DefaultCircuitBreaker(config)


# Global circuit breaker registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


# Circuit breaker utilities
class CircuitBreakerUtils:
    """Utilities for circuit breaker management."""
    
    @staticmethod
    def create_config(id: str, name: str, **kwargs) -> CircuitBreakerConfig:
        """Create circuit breaker configuration."""
        return CircuitBreakerConfig(
            id=id,
            name=name,
            **kwargs
        )
    
    @staticmethod
    def create_with_defaults(integration_id: str, integration_name: str, **kwargs) -> CircuitBreakerConfig:
        """Create configuration with sensible defaults."""
        return CircuitBreakerConfig(
            id=integration_id,
            name=integration_name,
            failure_threshold=kwargs.get('failure_threshold', 5),
            timeout=kwargs.get('timeout', 60),
            recovery_timeout=kwargs.get('recovery_timeout', 30),
            max_requests=kwargs.get('max_requests', 100),
            window_size=kwargs.get('window_size', 10),
            failure_rate_threshold=kwargs.get('failure_rate_threshold', 0.5),
            success_threshold=kwargs.get('success_threshold', 3),
            monitoring_enabled=kwargs.get('monitoring_enabled', True),
            auto_recovery=kwargs.get('auto_recovery', True)
        )
    
    @staticmethod
    def protect(integration_id: str, func: Callable, **kwargs):
        """Decorator to protect function with circuit breaker."""
        def wrapper(*args, **func_kwargs):
            return circuit_breaker_registry.call(integration_id, func, *args, **func_kwargs)
        return wrapper
    
    @staticmethod
    def get_circuit_breaker(integration_id: str) -> Optional[BaseCircuitBreaker]:
        """Get circuit breaker for integration."""
        return circuit_breaker_registry.get(integration_id)


# Circuit breaker monitoring
class CircuitBreakerMonitor:
    """Monitor for circuit breaker health and performance."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.CircuitBreakerMonitor")
    
    def monitor_all(self) -> Dict[str, Any]:
        """Monitor all circuit breakers."""
        return circuit_breaker_registry.health_check()
    
    def alert_on_state_change(self, circuit_breaker: BaseCircuitBreaker, old_state: CircuitBreakerState, new_state: CircuitBreakerState):
        """Alert on state change."""
        if new_state == CircuitBreakerState.OPEN:
            self.logger.warning(f"Circuit breaker {circuit_breaker.config.name} OPENED")
            # Send alert
            self._send_alert(
                title=f"Circuit Breaker Opened",
                message=f"Circuit breaker {circuit_breaker.config.name} has opened due to failures",
                severity='high'
            )
        elif new_state == CircuitBreakerState.CLOSED:
            self.logger.info(f"Circuit breaker {circuit_breaker.config.name} CLOSED")
            # Send recovery alert
            self._send_alert(
                title=f"Circuit Breaker Closed",
                message=f"Circuit breaker {circuit_breaker.config.name} has recovered and closed",
                severity='info'
            )
    
    def _send_alert(self, title: str, message: str, severity: str = 'info'):
        """Send alert notification."""
        # This would integrate with your notification system
        self.logger.info(f"Alert [{severity}]: {title} - {message}")


# Decorator for circuit breaker protection
def circuit_breaker_protector(circuit_breaker_id: str = None, **config_kwargs):
    """Decorator for circuit breaker protection."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Use provided circuit breaker ID or derive from function
            cb_id = circuit_breaker_id or f"func_{func.__name__}"
            
            # Get or create circuit breaker
            cb = circuit_breaker_registry.get(cb_id)
            if not cb:
                # Create new circuit breaker
                config = CircuitBreakerUtils.create_with_defaults(
                    cb_id,
                    func.__name__,
                    **config_kwargs
                )
                cb = CircuitBreakerFactory.create(config)
                circuit_breaker_registry.register(cb)
            
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator
