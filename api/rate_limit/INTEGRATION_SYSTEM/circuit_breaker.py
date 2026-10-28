"""
Circuit Breaker - Fault Tolerance Pattern

Circuit breaker implementation for preventing cascading failures
and providing fallback mechanisms for external service calls.
"""
from typing import List
import asyncio

import logging
import time
import threading
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationStatus
from .integ_exceptions import IntegrationError, CircuitBreakerError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail immediately
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: type = IntegrationError
    fallback_function: Optional[Callable] = None
    success_threshold: int = 3
    timeout: int = 30
    monitor_timeout: int = 10
    reset_timeout: int = 300


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    circuit_breaker_calls: int = 0
    fallback_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    average_response_time: float = 0.0
    current_state: CircuitState = CircuitState.CLOSED
    state_changes: int = 0


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, integration_name: str, **kwargs):
        self.integration_name = integration_name
        self.config = CircuitBreakerConfig(**kwargs)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.stats = CircuitBreakerStats()
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Start monitoring thread
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start monitoring thread for circuit breaker."""
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name=f"CircuitBreakerMonitor-{self.integration_name}",
            daemon=True
        )
        self._monitor_thread.start()
    
    def _monitor_loop(self):
        """Monitoring loop for circuit breaker."""
        while self._running:
            try:
                self._check_circuit_state()
                time.sleep(self.config.monitor_timeout)
            except Exception as e:
                logger.error(f"Circuit breaker monitor error: {str(e)}")
    
    def _check_circuit_state(self):
        """Check and update circuit state."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (self.last_failure_time and 
                    timezone.now() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout)):
                    self._transition_to_half_open()
            
            elif self.state == CircuitState.HALF_OPEN:
                # Check if we should close the circuit or keep it open
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
                elif self.failure_count >= 1:
                    self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to open state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        self.stats.state_changes += 1
        self.stats.current_state = self.state
        
        logger.warning(f"Circuit breaker {self.integration_name} transitioned from {old_state.value} to OPEN")
        
        # Publish circuit breaker open event
        self._publish_state_change_event(old_state, CircuitState.OPEN)
    
    def _transition_to_half_open(self):
        """Transition to half-open state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0
        self.stats.state_changes += 1
        self.stats.current_state = self.state
        
        logger.info(f"Circuit breaker {self.integration_name} transitioned from {old_state.value} to HALF_OPEN")
        
        # Publish circuit breaker half-open event
        self._publish_state_change_event(old_state, CircuitState.HALF_OPEN)
    
    def _transition_to_closed(self):
        """Transition to closed state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.stats.state_changes += 1
        self.stats.current_state = self.state
        
        logger.info(f"Circuit breaker {self.integration_name} transitioned from {old_state.value} to CLOSED")
        
        # Publish circuit breaker closed event
        self._publish_state_change_event(old_state, CircuitState.CLOSED)
    
    def _publish_state_change_event(self, old_state: CircuitState, new_state: CircuitState):
        """Publish circuit breaker state change event."""
        try:
            from .event_bus import event_bus, EventBuilder
            import asyncio
            
            event = EventBuilder.create_system_event(
                "circuit_breaker_state_change",
                {
                    'integration_name': self.integration_name,
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'failure_count': self.failure_count,
                    'success_count': self.success_count,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Publish asynchronously
            asyncio.create_task(event_bus.publish(event))
            
        except Exception as e:
            logger.error(f"Failed to publish circuit breaker event: {str(e)}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker."""
        start_time = timezone.now()
        
        try:
            with self._lock:
                self.stats.total_calls += 1
            
            # Check circuit state
            if self.state == CircuitState.OPEN:
                self.stats.circuit_breaker_calls += 1
                return await self._handle_open_circuit()
            
            # Execute function
            if self._should_timeout():
                self.stats.timeout_calls += 1
                self._record_failure()
                raise IntegrationError(f"Call timeout: {self.config.timeout}s")
            
            # Execute the function
            if callable(func):
                result = await self._execute_function(func, *args, **kwargs)
            else:
                raise IntegrationError("Provided function is not callable")
            
            # Record success
            self._record_success()
            
            # Update response time
            response_time = (timezone.now() - start_time).total_seconds()
            self._update_response_time(response_time)
            
            return result
            
        except self.config.expected_exception as e:
            self._record_failure()
            self.stats.failed_calls += 1
            
            # Try fallback if available
            if self.config.fallback_function:
                return await self._execute_fallback(*args, **kwargs)
            
            raise e
        
        except Exception as e:
            self._record_failure()
            self.stats.failed_calls += 1
            
            # Try fallback if available
            if self.config.fallback_function:
                return await self._execute_fallback(*args, **kwargs)
            
            raise IntegrationError(f"Circuit breaker call failed: {str(e)}")
    
    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout."""
        import asyncio
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
            else:
                return await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=self.config.timeout)
        except asyncio.TimeoutError:
            raise IntegrationError(f"Function timeout: {self.config.timeout}s")
    
    async def _handle_open_circuit(self) -> Any:
        """Handle call when circuit is open."""
        if self.config.fallback_function:
            return await self._execute_fallback()
        else:
            raise CircuitBreakerError(f"Circuit breaker is OPEN for {self.integration_name}")
    
    async def _execute_fallback(self, *args, **kwargs) -> Any:
        """Execute fallback function."""
        try:
            self.stats.fallback_calls += 1
            
            if asyncio.iscoroutinefunction(self.config.fallback_function):
                return await self.config.fallback_function(*args, **kwargs)
            else:
                return await asyncio.to_thread(self.config.fallback_function, *args, **kwargs)
        
        except Exception as e:
            raise CircuitBreakerError(f"Fallback function failed: {str(e)}")
    
    def _should_timeout(self) -> bool:
        """Check if call should timeout based on recent failures."""
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False
    
    def _record_success(self):
        """Record successful call."""
        with self._lock:
            self.success_count += 1
            self.last_success_time = timezone.now()
            self.stats.successful_calls += 1
            
            # Reset failure count if we're in half-open state
            if self.state == CircuitState.HALF_OPEN:
                self.failure_count = 0
    
    def _record_failure(self):
        """Record failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = timezone.now()
            
            # Check if we should open the circuit
            if (self.state == CircuitState.CLOSED and 
                self.failure_count >= self.config.failure_threshold):
                self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
    
    def _update_response_time(self, response_time: float):
        """Update average response time."""
        with self._lock:
            total_calls = self.stats.successful_calls + self.stats.failed_calls
            if total_calls == 1:
                self.stats.average_response_time = response_time
            else:
                current_avg = self.stats.average_response_time
                self.stats.average_response_time = (
                    (current_avg * (total_calls - 1) + response_time) / total_calls
                )
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        with self._lock:
            self.stats.current_state = self.state
            return self.stats
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_success_time = None
            self.stats = CircuitBreakerStats()
            self.stats.current_state = self.state
            
            logger.info(f"Circuit breaker {self.integration_name} reset to CLOSED state")
    
    def force_open(self):
        """Force circuit breaker to open state."""
        with self._lock:
            self._transition_to_open()
    
    def force_close(self):
        """Force circuit breaker to closed state."""
        with self._lock:
            if self.state != CircuitState.CLOSED:
                self._transition_to_closed()
    
    def is_healthy(self) -> bool:
        """Check if circuit breaker is healthy."""
        return (
            self.state == CircuitState.CLOSED or
            (self.state == CircuitState.HALF_OPEN and self.failure_count == 0)
        )
    
    def get_failure_rate(self) -> float:
        """Get failure rate (0-1)."""
        with self._lock:
            total_calls = self.stats.successful_calls + self.stats.failed_calls
            if total_calls == 0:
                return 0.0
            return self.stats.failed_calls / total_calls
    
    def get_success_rate(self) -> float:
        """Get success rate (0-1)."""
        with self._lock:
            total_calls = self.stats.successful_calls + self.stats.failed_calls
            if total_calls == 0:
                return 0.0
            return self.stats.successful_calls / total_calls
    
    def shutdown(self):
        """Shutdown circuit breaker."""
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        logger.info(f"Circuit breaker {self.integration_name} shutdown")


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def create_circuit_breaker(self, integration_name: str, **kwargs) -> CircuitBreaker:
        """Create a new circuit breaker."""
        with self._lock:
            if integration_name in self.circuit_breakers:
                logger.warning(f"Circuit breaker already exists: {integration_name}")
                return self.circuit_breakers[integration_name]
            
            circuit_breaker = CircuitBreaker(integration_name, **kwargs)
            self.circuit_breakers[integration_name] = circuit_breaker
            
            logger.info(f"Created circuit breaker: {integration_name}")
            return circuit_breaker
    
    def get_circuit_breaker(self, integration_name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(integration_name)
    
    def remove_circuit_breaker(self, integration_name: str) -> bool:
        """Remove circuit breaker."""
        with self._lock:
            if integration_name in self.circuit_breakers:
                circuit_breaker = self.circuit_breakers[integration_name]
                circuit_breaker.shutdown()
                del self.circuit_breakers[integration_name]
                logger.info(f"Removed circuit breaker: {integration_name}")
                return True
            return False
    
    def get_all_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self.circuit_breakers.copy()
    
    def get_circuit_breakers_by_state(self, state: CircuitState) -> List[CircuitBreaker]:
        """Get circuit breakers by state."""
        return [
            cb for cb in self.circuit_breakers.values()
            if cb.get_state() == state
        ]
    
    def get_healthy_circuit_breakers(self) -> List[CircuitBreaker]:
        """Get healthy circuit breakers."""
        return [
            cb for cb in self.circuit_breakers.values()
            if cb.is_healthy()
        ]
    
    def get_unhealthy_circuit_breakers(self) -> List[CircuitBreaker]:
        """Get unhealthy circuit breakers."""
        return [
            cb for cb in self.circuit_breakers.values()
            if not cb.is_healthy()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers."""
        stats = {
            'total_circuit_breakers': len(self.circuit_breakers),
            'healthy_circuit_breakers': len(self.get_healthy_circuit_breakers()),
            'unhealthy_circuit_breakers': len(self.get_unhealthy_circuit_breakers()),
            'circuit_breakers_by_state': {
                'closed': len(self.get_circuit_breakers_by_state(CircuitState.CLOSED)),
                'open': len(self.get_circuit_breakers_by_state(CircuitState.OPEN)),
                'half_open': len(self.get_circuit_breakers_by_state(CircuitState.HALF_OPEN))
            },
            'total_calls': 0,
            'total_failures': 0,
            'average_failure_rate': 0.0,
            'circuit_breakers': {}
        }
        
        total_failure_rate = 0.0
        
        for name, cb in self.circuit_breakers.items():
            cb_stats = cb.get_stats()
            stats['circuit_breakers'][name] = {
                'state': cb_stats.current_state.value,
                'total_calls': cb_stats.total_calls,
                'successful_calls': cb_stats.successful_calls,
                'failed_calls': cb_stats.failed_calls,
                'failure_rate': cb.get_failure_rate(),
                'success_rate': cb.get_success_rate(),
                'average_response_time': cb_stats.average_response_time,
                'state_changes': cb_stats.state_changes,
                'last_failure_time': cb_stats.last_failure_time.isoformat() if cb_stats.last_failure_time else None,
                'last_success_time': cb_stats.last_success_time.isoformat() if cb_stats.last_success_time else None
            }
            
            stats['total_calls'] += cb_stats.total_calls
            stats['total_failures'] += cb_stats.failed_calls
            total_failure_rate += cb.get_failure_rate()
        
        # Calculate average failure rate
        if self.circuit_breakers:
            stats['average_failure_rate'] = total_failure_rate / len(self.circuit_breakers)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all circuit breakers."""
        health_status = {
            'total_circuit_breakers': len(self.circuit_breakers),
            'healthy_circuit_breakers': 0,
            'unhealthy_circuit_breakers': 0,
            'circuit_breakers': {}
        }
        
        for name, cb in self.circuit_breakers.items():
            is_healthy = cb.is_healthy()
            
            if is_healthy:
                health_status['healthy_circuit_breakers'] += 1
            else:
                health_status['unhealthy_circuit_breakers'] += 1
            
            health_status['circuit_breakers'][name] = {
                'state': cb.get_state().value,
                'healthy': is_healthy,
                'failure_rate': cb.get_failure_rate(),
                'success_rate': cb.get_success_rate(),
                'last_failure_time': cb.stats.last_failure_time.isoformat() if cb.stats.last_failure_time else None
            }
        
        return health_status
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()
        
        logger.info("Reset all circuit breakers")
    
    def shutdown(self):
        """Shutdown all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.shutdown()
        
        self.circuit_breakers.clear()
        logger.info("Shutdown all circuit breakers")


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


# Decorator for circuit breaker protection
def circuit_breaker_protection(integration_name: str, **config):
    """Decorator for circuit breaker protection."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get or create circuit breaker
            cb = circuit_breaker_manager.get_circuit_breaker(integration_name)
            if not cb:
                cb = circuit_breaker_manager.create_circuit_breaker(integration_name, **config)
            
            # Call through circuit breaker
            return await cb.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Convenience functions
def create_default_circuit_breaker(integration_name: str) -> CircuitBreaker:
    """Create circuit breaker with default configuration."""
    return circuit_breaker_manager.create_circuit_breaker(
        integration_name,
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=IntegrationError
    )


def create_sensitive_circuit_breaker(integration_name: str) -> CircuitBreaker:
    """Create sensitive circuit breaker (lower threshold)."""
    return circuit_breaker_manager.create_circuit_breaker(
        integration_name,
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=IntegrationError
    )


def create_resilient_circuit_breaker(integration_name: str) -> CircuitBreaker:
    """Create resilient circuit breaker (higher threshold)."""
    return circuit_breaker_manager.create_circuit_breaker(
        integration_name,
        failure_threshold=10,
        recovery_timeout=120,
        expected_exception=IntegrationError
    )
