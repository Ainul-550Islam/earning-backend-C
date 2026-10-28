# =============================================================================
# INTEGRATION_SYSTEM/integ_signals.py
# =============================================================================
"""
Integration Signal System.

Provides signal definitions and handlers for integration events.
Enables decoupled communication between integration components and other modules.
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from django.dispatch import Signal, receiver
from django.utils import timezone
from django.core.cache import cache

from .integ_constants import IntegrationStatus, IntegrationType
from .integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of integration signals."""
    INTEGRATION_STARTED = "integration_started"
    INTEGRATION_COMPLETED = "integration_completed"
    INTEGRATION_FAILED = "integration_failed"
    INTEGRATION_RETRY = "integration_retry"
    INTEGRATION_TIMEOUT = "integration_timeout"
    INTEGRATION_RATE_LIMITED = "integration_rate_limited"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    INTEGRATION_REGISTERED = "integration_registered"
    INTEGRATION_UNREGISTERED = "integration_unregistered"
    INTEGRATION_UPDATED = "integration_updated"
    BATCH_PROCESSING_STARTED = "batch_processing_started"
    BATCH_PROCESSING_COMPLETED = "batch_processing_completed"
    HEALTH_CHECK_COMPLETED = "health_check_completed"
    PERFORMANCE_ALERT = "performance_alert"


@dataclass
class IntegrationSignalData:
    """Data structure for integration signals."""
    signal_type: SignalType
    integration_name: str
    integration_type: IntegrationType
    timestamp: datetime
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    data: Dict[str, Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}


# Django Signal definitions
integration_started = Signal()
integration_completed = Signal()
integration_failed = Signal()
integration_retry = Signal()
integration_timeout = Signal()
integration_rate_limited = Signal()
circuit_breaker_opened = Signal()
circuit_breaker_closed = Signal()
integration_registered = Signal()
integration_unregistered = Signal()
integration_updated = Signal()
batch_processing_started = Signal()
batch_processing_completed = Signal()
health_check_completed = Signal()
performance_alert = Signal()


class IntegrationSignalManager:
    """
    Manager for integration signals and handlers.
    
    Provides centralized signal management, async support,
    and signal aggregation capabilities.
    """
    
    def __init__(self):
        """Initialize signal manager."""
        self.signal_handlers: Dict[SignalType, List[Callable]] = defaultdict(list)
        self.signal_history: List[IntegrationSignalData] = []
        self.signal_aggregates: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Configuration
        self.max_history_size = 10000
        self.enable_async_handlers = True
        self.enable_aggregation = True
        
        # Register Django signal handlers
        self._register_django_handlers()
        
        logger.info("IntegrationSignalManager initialized")
    
    def _register_django_handlers(self):
        """Register Django signal handlers."""
        @receiver(integration_started)
        def handle_integration_started(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_STARTED, sender, **kwargs)
        
        @receiver(integration_completed)
        def handle_integration_completed(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_COMPLETED, sender, **kwargs)
        
        @receiver(integration_failed)
        def handle_integration_failed(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_FAILED, sender, **kwargs)
        
        @receiver(integration_retry)
        def handle_integration_retry(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_RETRY, sender, **kwargs)
        
        @receiver(integration_timeout)
        def handle_integration_timeout(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_TIMEOUT, sender, **kwargs)
        
        @receiver(integration_rate_limited)
        def handle_integration_rate_limited(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_RATE_LIMITED, sender, **kwargs)
        
        @receiver(circuit_breaker_opened)
        def handle_circuit_breaker_opened(sender, **kwargs):
            self._handle_django_signal(SignalType.CIRCUIT_BREAKER_OPENED, sender, **kwargs)
        
        @receiver(circuit_breaker_closed)
        def handle_circuit_breaker_closed(sender, **kwargs):
            self._handle_django_signal(SignalType.CIRCUIT_BREAKER_CLOSED, sender, **kwargs)
        
        @receiver(integration_registered)
        def handle_integration_registered(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_REGISTERED, sender, **kwargs)
        
        @receiver(integration_unregistered)
        def handle_integration_unregistered(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_UNREGISTERED, sender, **kwargs)
        
        @receiver(integration_updated)
        def handle_integration_updated(sender, **kwargs):
            self._handle_django_signal(SignalType.INTEGRATION_UPDATED, sender, **kwargs)
        
        @receiver(batch_processing_started)
        def handle_batch_processing_started(sender, **kwargs):
            self._handle_django_signal(SignalType.BATCH_PROCESSING_STARTED, sender, **kwargs)
        
        @receiver(batch_processing_completed)
        def handle_batch_processing_completed(sender, **kwargs):
            self._handle_django_signal(SignalType.BATCH_PROCESSING_COMPLETED, sender, **kwargs)
        
        @receiver(health_check_completed)
        def handle_health_check_completed(sender, **kwargs):
            self._handle_django_signal(SignalType.HEALTH_CHECK_COMPLETED, sender, **kwargs)
        
        @receiver(performance_alert)
        def handle_performance_alert(sender, **kwargs):
            self._handle_django_signal(SignalType.PERFORMANCE_ALERT, sender, **kwargs)
    
    def _handle_django_signal(self, signal_type: SignalType, sender, **kwargs):
        """Handle Django signal and convert to internal format."""
        signal_data = IntegrationSignalData(
            signal_type=signal_type,
            integration_name=kwargs.get('integration_name', 'unknown'),
            integration_type=kwargs.get('integration_type', IntegrationType.API),
            timestamp=timezone.now(),
            request_id=kwargs.get('request_id'),
            correlation_id=kwargs.get('correlation_id'),
            data=kwargs.get('data', {}),
            error=kwargs.get('error'),
            metadata=kwargs.get('metadata', {})
        )
        
        self.emit_signal(signal_data)
    
    def emit_signal(self, signal_data: IntegrationSignalData) -> None:
        """
        Emit integration signal to all registered handlers.
        
        Args:
            signal_data: Signal data to emit
        """
        try:
            # Add to history
            self._add_to_history(signal_data)
            
            # Update aggregates
            if self.enable_aggregation:
                self._update_aggregates(signal_data)
            
            # Get handlers for this signal type
            handlers = self.signal_handlers.get(signal_data.signal_type, [])
            
            # Execute handlers
            if self.enable_async_handlers:
                # Execute asynchronously
                asyncio.create_task(self._execute_handlers_async(handlers, signal_data))
            else:
                # Execute synchronously
                self._execute_handlers_sync(handlers, signal_data)
            
            # Also emit Django signal
            self._emit_django_signal(signal_data)
            
        except Exception as e:
            logger.error(f"Error emitting signal {signal_data.signal_type}: {e}")
    
    async def emit_signal_async(self, signal_data: IntegrationSignalData) -> None:
        """
        Emit integration signal asynchronously.
        
        Args:
            signal_data: Signal data to emit
        """
        self.emit_signal(signal_data)
    
    def _execute_handlers_sync(self, handlers: List[Callable], signal_data: IntegrationSignalData) -> None:
        """Execute signal handlers synchronously."""
        for handler in handlers:
            try:
                handler(signal_data)
            except Exception as e:
                logger.error(f"Error in signal handler {handler.__name__}: {e}")
    
    async def _execute_handlers_async(self, handlers: List[Callable], signal_data: IntegrationSignalData) -> None:
        """Execute signal handlers asynchronously."""
        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(handler(signal_data))
            else:
                # Run sync handler in thread pool
                tasks.append(asyncio.get_event_loop().run_in_executor(None, handler, signal_data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _emit_django_signal(self, signal_data: IntegrationSignalData) -> None:
        """Emit corresponding Django signal."""
        signal_map = {
            SignalType.INTEGRATION_STARTED: integration_started,
            SignalType.INTEGRATION_COMPLETED: integration_completed,
            SignalType.INTEGRATION_FAILED: integration_failed,
            SignalType.INTEGRATION_RETRY: integration_retry,
            SignalType.INTEGRATION_TIMEOUT: integration_timeout,
            SignalType.INTEGRATION_RATE_LIMITED: integration_rate_limited,
            SignalType.CIRCUIT_BREAKER_OPENED: circuit_breaker_opened,
            SignalType.CIRCUIT_BREAKER_CLOSED: circuit_breaker_closed,
            SignalType.INTEGRATION_REGISTERED: integration_registered,
            SignalType.INTEGRATION_UNREGISTERED: integration_unregistered,
            SignalType.INTEGRATION_UPDATED: integration_updated,
            SignalType.BATCH_PROCESSING_STARTED: batch_processing_started,
            SignalType.BATCH_PROCESSING_COMPLETED: batch_processing_completed,
            SignalType.HEALTH_CHECK_COMPLETED: health_check_completed,
            SignalType.PERFORMANCE_ALERT: performance_alert,
        }
        
        django_signal = signal_map.get(signal_data.signal_type)
        if django_signal:
            django_signal.send(
                sender=self.__class__,
                integration_name=signal_data.integration_name,
                integration_type=signal_data.integration_type,
                request_id=signal_data.request_id,
                correlation_id=signal_data.correlation_id,
                data=signal_data.data,
                error=signal_data.error,
                metadata=signal_data.metadata
            )
    
    def register_handler(self, signal_type: SignalType, handler: Callable) -> None:
        """
        Register signal handler.
        
        Args:
            signal_type: Type of signal to handle
            handler: Handler function
        """
        self.signal_handlers[signal_type].append(handler)
        logger.debug(f"Registered handler for {signal_type}: {handler.__name__}")
    
    def unregister_handler(self, signal_type: SignalType, handler: Callable) -> None:
        """
        Unregister signal handler.
        
        Args:
            signal_type: Type of signal
            handler: Handler function to remove
        """
        if handler in self.signal_handlers[signal_type]:
            self.signal_handlers[signal_type].remove(handler)
            logger.debug(f"Unregistered handler for {signal_type}: {handler.__name__}")
    
    def _add_to_history(self, signal_data: IntegrationSignalData) -> None:
        """Add signal to history."""
        self.signal_history.append(signal_data)
        
        # Trim history if needed
        if len(self.signal_history) > self.max_history_size:
            self.signal_history = self.signal_history[-self.max_history_size:]
    
    def _update_aggregates(self, signal_data: IntegrationSignalData) -> None:
        """Update signal aggregates."""
        key = f"{signal_data.integration_name}_{signal_data.signal_type.value}"
        
        if key not in self.signal_aggregates:
            self.signal_aggregates[key] = {
                'count': 0,
                'first_seen': signal_data.timestamp,
                'last_seen': signal_data.timestamp,
                'integration_name': signal_data.integration_name,
                'signal_type': signal_data.signal_type.value
            }
        
        aggregate = self.signal_aggregates[key]
        aggregate['count'] += 1
        aggregate['last_seen'] = signal_data.timestamp
        
        # Add specific aggregates based on signal type
        if signal_data.signal_type == SignalType.INTEGRATION_FAILED:
            aggregate['error_count'] = aggregate.get('error_count', 0) + 1
        elif signal_data.signal_type == SignalType.INTEGRATION_COMPLETED:
            aggregate['success_count'] = aggregate.get('success_count', 0) + 1
    
    def get_signal_history(self, integration_name: Optional[str] = None, 
                          signal_type: Optional[SignalType] = None,
                          limit: int = 100) -> List[IntegrationSignalData]:
        """
        Get signal history with filtering.
        
        Args:
            integration_name: Filter by integration name
            signal_type: Filter by signal type
            limit: Maximum number of signals to return
            
        Returns:
            List of signal data
        """
        filtered_history = self.signal_history
        
        if integration_name:
            filtered_history = [
                s for s in filtered_history 
                if s.integration_name == integration_name
            ]
        
        if signal_type:
            filtered_history = [
                s for s in filtered_history 
                if s.signal_type == signal_type
            ]
        
        # Return most recent signals
        return filtered_history[-limit:]
    
    def get_signal_aggregates(self, integration_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get signal aggregates.
        
        Args:
            integration_name: Filter by integration name
            
        Returns:
            Signal aggregates dictionary
        """
        if integration_name:
            return {
                k: v for k, v in self.signal_aggregates.items()
                if v['integration_name'] == integration_name
            }
        
        return dict(self.signal_aggregates)
    
    def get_signal_statistics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get signal statistics for time window.
        
        Args:
            time_window_minutes: Time window in minutes
            
        Returns:
            Signal statistics
        """
        cutoff_time = timezone.now() - timezone.timedelta(minutes=time_window_minutes)
        recent_signals = [
            s for s in self.signal_history 
            if s.timestamp >= cutoff_time
        ]
        
        # Count by signal type
        signal_counts = {}
        for signal in recent_signals:
            signal_counts[signal.signal_type.value] = signal_counts.get(signal.signal_type.value, 0) + 1
        
        # Count by integration
        integration_counts = {}
        for signal in recent_signals:
            integration_counts[signal.integration_name] = integration_counts.get(signal.integration_name, 0) + 1
        
        return {
            'time_window_minutes': time_window_minutes,
            'total_signals': len(recent_signals),
            'signals_per_minute': len(recent_signals) / time_window_minutes,
            'signal_counts': signal_counts,
            'integration_counts': integration_counts,
            'error_rate': signal_counts.get('integration_failed', 0) / max(len(recent_signals), 1) * 100
        }
    
    def clear_history(self, integration_name: Optional[str] = None) -> None:
        """
        Clear signal history.
        
        Args:
            integration_name: Clear history for specific integration only
        """
        if integration_name:
            self.signal_history = [
                s for s in self.signal_history 
                if s.integration_name != integration_name
            ]
        else:
            self.signal_history.clear()
        
        logger.info(f"Cleared signal history for {integration_name or 'all integrations'}")
    
    def clear_aggregates(self, integration_name: Optional[str] = None) -> None:
        """
        Clear signal aggregates.
        
        Args:
            integration_name: Clear aggregates for specific integration only
        """
        if integration_name:
            self.signal_aggregates = {
                k: v for k, v in self.signal_aggregates.items()
                if v['integration_name'] != integration_name
            }
        else:
            self.signal_aggregates.clear()
        
        logger.info(f"Cleared signal aggregates for {integration_name or 'all integrations'}")


# Global signal manager instance
_signal_manager = None


def get_signal_manager() -> IntegrationSignalManager:
    """Get global signal manager instance."""
    global _signal_manager
    if _signal_manager is None:
        _signal_manager = IntegrationSignalManager()
    return _signal_manager


# Convenience decorators
def integration_signal_handler(signal_type: SignalType):
    """
    Decorator for registering integration signal handlers.
    
    Args:
        signal_type: Type of signal to handle
    """
    def decorator(handler_func):
        manager = get_signal_manager()
        manager.register_handler(signal_type, handler_func)
        return handler_func
    return decorator


# Common signal handlers
@integration_signal_handler(SignalType.INTEGRATION_FAILED)
def log_integration_failure(signal_data: IntegrationSignalData):
    """Log integration failure."""
    logger.error(f"Integration failed: {signal_data.integration_name} - {signal_data.error}")


@integration_signal_handler(SignalType.CIRCUIT_BREAKER_OPENED)
def handle_circuit_breaker_opened(signal_data: IntegrationSignalData):
    """Handle circuit breaker opened."""
    logger.warning(f"Circuit breaker opened for {signal_data.integration_name}")
    
    # Send alert notification
    # This could be extended to send emails, Slack messages, etc.


@integration_signal_handler(SignalType.PERFORMANCE_ALERT)
def handle_performance_alert(signal_data: IntegrationSignalData):
    """Handle performance alert."""
    logger.warning(f"Performance alert for {signal_data.integration_name}: {signal_data.data}")


# Signal emission functions
def emit_integration_started(integration_name: str, integration_type: IntegrationType,
                           request_id: Optional[str] = None, **kwargs) -> None:
    """Emit integration started signal."""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.INTEGRATION_STARTED,
        integration_name=integration_name,
        integration_type=integration_type,
        timestamp=timezone.now(),
        request_id=request_id,
        data=kwargs
    )
    
    get_signal_manager().emit_signal(signal_data)


def emit_integration_completed(integration_name: str, integration_type: IntegrationType,
                              request_id: Optional[str] = None, **kwargs) -> None:
    """Emit integration completed signal."""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.INTEGRATION_COMPLETED,
        integration_name=integration_name,
        integration_type=integration_type,
        timestamp=timezone.now(),
        request_id=request_id,
        data=kwargs
    )
    
    get_signal_manager().emit_signal(signal_data)


def emit_integration_failed(integration_name: str, integration_type: IntegrationType,
                           request_id: Optional[str] = None, error: Optional[str] = None, **kwargs) -> None:
    """Emit integration failed signal."""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.INTEGRATION_FAILED,
        integration_name=integration_name,
        integration_type=integration_type,
        timestamp=timezone.now(),
        request_id=request_id,
        error=error,
        data=kwargs
    )
    
    get_signal_manager().emit_signal(signal_data)


def emit_circuit_breaker_opened(integration_name: str, **kwargs) -> None:
    """Emit circuit breaker opened signal."""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.CIRCUIT_BREAKER_OPENED,
        integration_name=integration_name,
        integration_type=IntegrationType.API,  # Default
        timestamp=timezone.now(),
        data=kwargs
    )
    
    get_signal_manager().emit_signal(signal_data)


def emit_performance_alert(integration_name: str, alert_data: Dict[str, Any], **kwargs) -> None:
    """Emit performance alert signal."""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.PERFORMANCE_ALERT,
        integration_name=integration_name,
        integration_type=IntegrationType.API,  # Default
        timestamp=timezone.now(),
        data=alert_data,
        metadata=kwargs
    )
    
    get_signal_manager().emit_signal(signal_data)
