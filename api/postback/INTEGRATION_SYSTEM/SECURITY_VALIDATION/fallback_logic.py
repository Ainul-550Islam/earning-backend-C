"""
fallback_logic.py – Fallback logic system for postback module.

Provides comprehensive fallback functionality including:
- Fallback strategies and policies
- Graceful degradation
- Circuit breaker integration
- Fallback monitoring and reporting
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import time

from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException, IntegrationServiceUnavailableException
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategy enumeration."""
    IMMEDIATE = "immediate"
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    ALTERNATIVE = "alternative"
    DEGRADED = "degraded"
    FAIL_FAST = "fail_fast"
    GRACEFUL = "graceful"


class FallbackStatus(Enum):
    """Fallback status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"
    RECOVERED = "recovered"
    FAILED = "failed"


@dataclass
class FallbackConfig:
    """Fallback configuration."""
    name: str
    strategy: FallbackStrategy
    primary_handler: Callable
    fallback_handlers: List[Callable]
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    timeout: float = 30.0
    circuit_breaker_threshold: int = 5
    recovery_timeout: int = 60
    health_check_interval: int = 30
    enable_monitoring: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackEvent:
    """Fallback event data structure."""
    id: str
    config_name: str
    strategy: FallbackStrategy
    handler_index: int
    success: bool
    error_message: str = ""
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'config_name': self.config_name,
            'strategy': self.strategy.value,
            'handler_index': self.handler_index,
            'success': self.success,
            'error_message': self.error_message,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
        }


class FallbackHandler(ABC):
    """
    Abstract base class for fallback handlers.
    
    Provides common interface for different
    fallback implementations.
    """
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.logger = logging.getLogger(f"fallback.{config.name}")
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute fallback handler."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if handler is available."""
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return {
            'available': self.is_available(),
            'timestamp': timezone.now().isoformat(),
        }


class ImmediateFallbackHandler(FallbackHandler):
    """Immediate fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute immediate fallback."""
        try:
            return self.config.fallback_handlers[0](*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Immediate fallback failed: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Check if immediate fallback is available."""
        return len(self.config.fallback_handlers) > 0


class RetryFallbackHandler(FallbackHandler):
    """Retry fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute retry fallback."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt == 0:
                    # Try primary handler first
                    return self.config.primary_handler(*args, **kwargs)
                else:
                    # Try fallback handlers
                    for handler in self.config.fallback_handlers:
                        try:
                            return handler(*args, **kwargs)
                        except Exception:
                            continue
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (self.config.backoff_multiplier ** attempt)
                    self.logger.warning(f"Retry attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All retry attempts failed: {str(e)}")
        
        raise last_exception
    
    def is_available(self) -> bool:
        """Check if retry fallback is available."""
        return True


class CircuitBreakerFallbackHandler(FallbackHandler):
    """Circuit breaker fallback handler."""
    
    def __init__(self, config: FallbackConfig):
        super().__init__(config)
        self.circuit_breaker = CircuitBreaker(
            name=config.name,
            failure_threshold=config.circuit_breaker_threshold,
            recovery_timeout=config.recovery_timeout
        )
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute with circuit breaker protection."""
        try:
            with self.circuit_breaker:
                return self.config.primary_handler(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Circuit breaker triggered, using fallback: {str(e)}")
            
            # Try fallback handlers
            for handler in self.config.fallback_handlers:
                try:
                    return handler(*args, **kwargs)
                except Exception as fallback_error:
                    self.logger.error(f"Fallback handler failed: {str(fallback_error)}")
                    continue
            
            raise e
    
    def is_available(self) -> bool:
        """Check if circuit breaker fallback is available."""
        return not self.circuit_breaker.is_open()


class AlternativeFallbackHandler(FallbackHandler):
    """Alternative fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute alternative fallback."""
        last_exception = None
        
        # Try primary handler first
        try:
            return self.config.primary_handler(*args, **kwargs)
        except Exception as e:
            last_exception = e
            self.logger.warning(f"Primary handler failed, trying alternatives: {str(e)}")
        
        # Try alternative handlers
        for i, handler in enumerate(self.config.fallback_handlers):
            try:
                return handler(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self.logger.warning(f"Alternative handler {i} failed: {str(e)}")
                continue
        
        raise last_exception
    
    def is_available(self) -> bool:
        """Check if alternative fallback is available."""
        return len(self.config.fallback_handlers) > 0


class DegradedFallbackHandler(FallbackHandler):
    """Degraded fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute degraded fallback."""
        try:
            return self.config.primary_handler(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Primary handler failed, using degraded mode: {str(e)}")
            
            # Try degraded handlers
            for handler in self.config.fallback_handlers:
                try:
                    result = handler(*args, **kwargs)
                    # Mark as degraded response
                    if isinstance(result, dict):
                        result['_degraded'] = True
                        result['_degraded_at'] = timezone.now().isoformat()
                    return result
                except Exception as fallback_error:
                    self.logger.error(f"Degraded handler failed: {str(fallback_error)}")
                    continue
            
            raise e
    
    def is_available(self) -> bool:
        """Check if degraded fallback is available."""
        return len(self.config.fallback_handlers) > 0


class FailFastFallbackHandler(FallbackHandler):
    """Fail fast fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute fail fast fallback."""
        try:
            return self.config.primary_handler(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Fail fast triggered: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Check if fail fast fallback is available."""
        return True


class GracefulFallbackHandler(FallbackHandler):
    """Graceful fallback handler."""
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute graceful fallback."""
        try:
            return self.config.primary_handler(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Primary handler failed, trying graceful fallback: {str(e)}")
            
            # Try graceful handlers
            for handler in self.config.fallback_handlers:
                try:
                    result = handler(*args, **kwargs)
                    # Add graceful metadata
                    if isinstance(result, dict):
                        result['_graceful'] = True
                        result['_graceful_at'] = timezone.now().isoformat()
                        result['_original_error'] = str(e)
                    return result
                except Exception as fallback_error:
                    self.logger.error(f"Graceful handler failed: {str(fallback_error)}")
                    continue
            
            # Return graceful error response
            return {
                'success': False,
                'error': 'Service temporarily unavailable',
                'graceful_degradation': True,
                'timestamp': timezone.now().isoformat(),
            }
    
    def is_available(self) -> bool:
        """Check if graceful fallback is available."""
        return True


class FallbackManager:
    """
    Manager for fallback configurations and execution.
    
    Handles fallback registration, execution,
    and monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.configs: Dict[str, FallbackConfig] = {}
        self.handlers: Dict[str, FallbackHandler] = {}
        self.events: List[FallbackEvent] = []
        self._setup_default_fallbacks()
    
    def _setup_default_fallbacks(self):
        """Setup default fallback configurations."""
        default_configs = [
            FallbackConfig(
                name="webhook_fallback",
                strategy=FallbackStrategy.CIRCUIT_BREAKER,
                primary_handler=lambda: None,  # Would be set during registration
                fallback_handlers=[lambda: None],
                circuit_breaker_threshold=3,
                recovery_timeout=60,
            ),
            FallbackConfig(
                name="api_fallback",
                strategy=FallbackStrategy.RETRY,
                primary_handler=lambda: None,
                fallback_handlers=[lambda: None],
                max_retries=3,
                retry_delay=1.0,
            ),
        ]
        
        for config in default_configs:
            self.register_fallback(config)
    
    def register_fallback(self, config: FallbackConfig) -> bool:
        """
        Register fallback configuration.
        
        Args:
            config: Fallback configuration
            
        Returns:
            True if registered successfully
        """
        try:
            self.configs[config.name] = config
            
            # Create handler based on strategy
            handler = self._create_handler(config)
            self.handlers[config.name] = handler
            
            self.logger.info(f"Fallback registered: {config.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register fallback {config.name}: {str(e)}")
            return False
    
    def unregister_fallback(self, name: str) -> bool:
        """
        Unregister fallback.
        
        Args:
            name: Fallback name
            
        Returns:
            True if unregistered successfully
        """
        if name in self.configs:
            del self.configs[name]
            if name in self.handlers:
                del self.handlers[name]
            self.logger.info(f"Fallback unregistered: {name}")
            return True
        return False
    
    def _create_handler(self, config: FallbackConfig) -> FallbackHandler:
        """Create handler based on strategy."""
        if config.strategy == FallbackStrategy.IMMEDIATE:
            return ImmediateFallbackHandler(config)
        elif config.strategy == FallbackStrategy.RETRY:
            return RetryFallbackHandler(config)
        elif config.strategy == FallbackStrategy.CIRCUIT_BREAKER:
            return CircuitBreakerFallbackHandler(config)
        elif config.strategy == FallbackStrategy.ALTERNATIVE:
            return AlternativeFallbackHandler(config)
        elif config.strategy == FallbackStrategy.DEGRADED:
            return DegradedFallbackHandler(config)
        elif config.strategy == FallbackStrategy.FAIL_FAST:
            return FailFastFallbackHandler(config)
        elif config.strategy == FallbackStrategy.GRACEFUL:
            return GracefulFallbackHandler(config)
        else:
            raise IntegrationException(f"Unknown fallback strategy: {config.strategy}")
    
    def execute_fallback(self, name: str, *args, **kwargs) -> Any:
        """
        Execute fallback by name.
        
        Args:
            name: Fallback name
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        handler = self.handlers.get(name)
        if not handler:
            raise IntegrationException(f"Fallback not found: {name}")
        
        start_time = time.time()
        event_id = f"fallback_{int(time.time() * 1000)}"
        
        try:
            result = handler.execute(*args, **kwargs)
            
            # Record success event
            event = FallbackEvent(
                id=event_id,
                config_name=name,
                strategy=handler.config.strategy,
                handler_index=0,
                success=True,
                execution_time=time.time() - start_time
            )
            self.events.append(event)
            
            return result
        
        except Exception as e:
            # Record failure event
            event = FallbackEvent(
                id=event_id,
                config_name=name,
                strategy=handler.config.strategy,
                handler_index=0,
                success=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
            self.events.append(event)
            
            raise
    
    def is_available(self, name: str) -> bool:
        """
        Check if fallback is available.
        
        Args:
            name: Fallback name
            
        Returns:
            True if available
        """
        handler = self.handlers.get(name)
        return handler.is_available() if handler else False
    
    def health_check(self, name: str = None) -> Dict[str, Any]:
        """
        Perform health check.
        
        Args:
            name: Specific fallback name (None = all)
            
        Returns:
            Health check results
        """
        if name:
            handler = self.handlers.get(name)
            if not handler:
                return {'error': f'Fallback not found: {name}'}
            
            return {
                'name': name,
                'strategy': handler.config.strategy.value,
                'health': handler.health_check(),
            }
        
        # Check all fallbacks
        health_status = {
            'overall': 'healthy',
            'total_fallbacks': len(self.handlers),
            'healthy_fallbacks': 0,
            'unhealthy_fallbacks': 0,
            'fallback_health': {},
            'issues': [],
        }
        
        for fallback_name, handler in self.handlers.items():
            try:
                health = handler.health_check()
                health_status['fallback_health'][fallback_name] = health
                
                if health['available']:
                    health_status['healthy_fallbacks'] += 1
                else:
                    health_status['unhealthy_fallbacks'] += 1
                    health_status['issues'].append(f"Fallback {fallback_name} is unavailable")
            
            except Exception as e:
                health_status['unhealthy_fallbacks'] += 1
                health_status['issues'].append(f"Error checking fallback {fallback_name}: {str(e)}")
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        total_events = len(self.events)
        successful_events = len([e for e in self.events if e.success])
        failed_events = len([e for e in self.events if not e.success])
        
        # Strategy distribution
        strategy_counts = {}
        for event in self.events:
            strategy = event.strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Average execution time
        avg_execution_time = 0.0
        if self.events:
            total_time = sum(e.execution_time for e in self.events)
            avg_execution_time = total_time / len(self.events)
        
        # Recent events
        recent_events = [e.to_dict() for e in self.events[-10:]]
        
        return {
            'total_fallbacks': len(self.configs),
            'total_events': total_events,
            'successful_events': successful_events,
            'failed_events': failed_events,
            'success_rate': (successful_events / total_events * 100) if total_events > 0 else 0,
            'avg_execution_time': avg_execution_time,
            'strategy_distribution': strategy_counts,
            'recent_events': recent_events,
        }
    
    def get_events(self, config_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get fallback events.
        
        Args:
            config_name: Filter by config name
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        events = self.events
        
        if config_name:
            events = [e for e in events if e.config_name == config_name]
        
        events = events[-limit:]
        return [e.to_dict() for e in events]
    
    def clear_events(self, config_name: str = None):
        """
        Clear fallback events.
        
        Args:
            config_name: Filter by config name (None = all)
        """
        if config_name:
            self.events = [e for e in self.events if e.config_name != config_name]
        else:
            self.events.clear()
        
        self.logger.info(f"Events cleared for: {config_name or 'all'}")


# Global fallback manager instance
fallback_manager = FallbackManager()


# Decorators for fallback handling
def with_fallback(fallback_name: str):
    """
    Decorator for adding fallback to functions.
    
    Args:
        fallback_name: Fallback configuration name
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Try fallback
                try:
                    return fallback_manager.execute_fallback(fallback_name, *args, **kwargs)
                except Exception as fallback_error:
                    # Log both errors
                    logger.error(f"Primary function failed: {str(e)}")
                    logger.error(f"Fallback also failed: {str(fallback_error)}")
                    raise fallback_error
        return wrapper
    return decorator


def graceful_fallback(default_response: Any = None):
    """
    Decorator for graceful fallback.
    
    Args:
        default_response: Default response on failure
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Function {func.__name__} failed, using graceful fallback: {str(e)}")
                
                if default_response is not None:
                    return default_response
                
                # Return graceful error response
                return {
                    'success': False,
                    'error': 'Service temporarily unavailable',
                    'graceful_degradation': True,
                    'timestamp': timezone.now().isoformat(),
                }
        return wrapper
    return decorator


# Convenience functions
def register_fallback(name: str, strategy: FallbackStrategy, primary_handler: Callable,
                     fallback_handlers: List[Callable], **kwargs) -> bool:
    """Register fallback configuration."""
    config = FallbackConfig(
        name=name,
        strategy=strategy,
        primary_handler=primary_handler,
        fallback_handlers=fallback_handlers,
        **kwargs
    )
    return fallback_manager.register_fallback(config)


def execute_fallback(name: str, *args, **kwargs) -> Any:
    """Execute fallback by name."""
    return fallback_manager.execute_fallback(name, *args, **kwargs)


def is_fallback_available(name: str) -> bool:
    """Check if fallback is available."""
    return fallback_manager.is_available(name)


def get_fallback_statistics() -> Dict[str, Any]:
    """Get fallback statistics."""
    return fallback_manager.get_statistics()


def perform_fallback_health_check(name: str = None) -> Dict[str, Any]:
    """Perform fallback health check."""
    return fallback_manager.health_check(name)


# Fallback strategies factory
def create_circuit_breaker_fallback(name: str, primary_handler: Callable,
                                   fallback_handlers: List[Callable],
                                   failure_threshold: int = 5,
                                   recovery_timeout: int = 60) -> bool:
    """Create circuit breaker fallback."""
    return register_fallback(
        name=name,
        strategy=FallbackStrategy.CIRCUIT_BREAKER,
        primary_handler=primary_handler,
        fallback_handlers=fallback_handlers,
        circuit_breaker_threshold=failure_threshold,
        recovery_timeout=recovery_timeout
    )


def create_retry_fallback(name: str, primary_handler: Callable,
                         fallback_handlers: List[Callable],
                         max_retries: int = 3,
                         retry_delay: float = 1.0) -> bool:
    """Create retry fallback."""
    return register_fallback(
        name=name,
        strategy=FallbackStrategy.RETRY,
        primary_handler=primary_handler,
        fallback_handlers=fallback_handlers,
        max_retries=max_retries,
        retry_delay=retry_delay
    )


def create_alternative_fallback(name: str, primary_handler: Callable,
                              fallback_handlers: List[Callable]) -> bool:
    """Create alternative fallback."""
    return register_fallback(
        name=name,
        strategy=FallbackStrategy.ALTERNATIVE,
        primary_handler=primary_handler,
        fallback_handlers=fallback_handlers
    )


def create_degraded_fallback(name: str, primary_handler: Callable,
                            fallback_handlers: List[Callable]) -> bool:
    """Create degraded fallback."""
    return register_fallback(
        name=name,
        strategy=FallbackStrategy.DEGRADED,
        primary_handler=primary_handler,
        fallback_handlers=fallback_handlers
    )
