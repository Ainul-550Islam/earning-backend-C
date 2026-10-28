"""
Integration Signals
Signal handling for integration events and cross-module communication
"""

import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.core.exceptions import ObjectDoesNotExist

from .integ_constants import IntegrationEventTypes, SignalPriorities
from .integ_exceptions import IntegrationSignalException

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Signal types for integration events"""
    PRE_INTEGRATION = "pre_integration"
    POST_INTEGRATION = "post_integration"
    INTEGRATION_FAILED = "integration_failed"
    INTEGRATION_SUCCESS = "integration_success"
    DATA_TRANSFORMED = "data_transformed"
    VALIDATION_FAILED = "validation_failed"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    PERFORMANCE_ALERT = "performance_alert"
    SECURITY_EVENT = "security_event"


@dataclass
class IntegrationSignalData:
    """Data structure for integration signals"""
    signal_type: SignalType
    source_system: str
    target_system: str
    request_id: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    priority: SignalPriorities = SignalPriorities.NORMAL
    error: Optional[str] = None


# Define custom integration signals
integration_pre_process = Signal()
integration_post_process = Signal()
integration_failed = Signal()
integration_success = Signal()
data_transformation_started = Signal()
data_transformation_completed = Signal()
validation_started = Signal()
validation_completed = Signal()
circuit_breaker_triggered = Signal()
performance_threshold_exceeded = Signal()
security_violation_detected = Signal()


class IntegrationSignalManager:
    """
    Manager for handling integration signals
    """
    
    def __init__(self):
        self.signal_handlers: Dict[str, List[Callable]] = {}
        self.signal_history: List[IntegrationSignalData] = []
        self.active_listeners: Dict[str, List[Callable]] = {}
        self.signal_stats = {
            'total_signals': 0,
            'signals_by_type': {},
            'failed_signals': 0
        }
    
    def register_handler(self, signal_type: str, handler: Callable, priority: int = 5):
        """
        Register a signal handler
        
        Args:
            signal_type: Type of signal to handle
            handler: Handler function
            priority: Handler priority (lower = higher priority)
        """
        if signal_type not in self.signal_handlers:
            self.signal_handlers[signal_type] = []
        
        # Insert handler based on priority
        inserted = False
        for i, (existing_priority, _) in enumerate(self.signal_handlers[signal_type]):
            if priority < existing_priority:
                self.signal_handlers[signal_type].insert(i, (priority, handler))
                inserted = True
                break
        
        if not inserted:
            self.signal_handlers[signal_type].append((priority, handler))
        
        logger.info(f"Registered handler for signal type: {signal_type}")
    
    def unregister_handler(self, signal_type: str, handler: Callable):
        """
        Unregister a signal handler
        
        Args:
            signal_type: Type of signal
            handler: Handler function to remove
        """
        if signal_type in self.signal_handlers:
            self.signal_handlers[signal_type] = [
                (priority, h) for priority, h in self.signal_handlers[signal_type]
                if h != handler
            ]
        
        logger.info(f"Unregistered handler for signal type: {signal_type}")
    
    def emit_signal(self, signal_data: IntegrationSignalData):
        """
        Emit an integration signal
        
        Args:
            signal_data: Signal data to emit
        """
        try:
            # Update statistics
            self.signal_stats['total_signals'] += 1
            signal_type_str = signal_data.signal_type.value
            self.signal_stats['signals_by_type'][signal_type_str] = \
                self.signal_stats['signals_by_type'].get(signal_type_str, 0) + 1
            
            # Add to history
            self.signal_history.append(signal_data)
            
            # Keep history size manageable
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-500:]
            
            # Emit Django signal
            django_signal = self._get_django_signal(signal_data.signal_type)
            if django_signal:
                django_signal.send(
                    sender=self.__class__,
                    signal_data=signal_data
                )
            
            # Call registered handlers
            if signal_type_str in self.signal_handlers:
                for priority, handler in self.signal_handlers[signal_type_str]:
                    try:
                        handler(signal_data)
                    except Exception as e:
                        logger.error(f"Signal handler failed for {signal_type_str}: {e}")
                        self.signal_stats['failed_signals'] += 1
            
            logger.debug(f"Emitted signal: {signal_type_str}")
            
        except Exception as e:
            logger.error(f"Failed to emit signal: {e}")
            self.signal_stats['failed_signals'] += 1
            raise IntegrationSignalException(f"Failed to emit signal: {e}")
    
    def add_listener(self, event_type: str, listener: Callable):
        """
        Add a listener for specific events
        
        Args:
            event_type: Event type to listen for
            listener: Listener function
        """
        if event_type not in self.active_listeners:
            self.active_listeners[event_type] = []
        
        self.active_listeners[event_type].append(listener)
        logger.info(f"Added listener for event type: {event_type}")
    
    def remove_listener(self, event_type: str, listener: Callable):
        """
        Remove a listener for specific events
        
        Args:
            event_type: Event type
            listener: Listener function to remove
        """
        if event_type in self.active_listeners:
            self.active_listeners[event_type] = [
                l for l in self.active_listeners[event_type] if l != listener
            ]
        
        logger.info(f"Removed listener for event type: {event_type}")
    
    def get_signal_history(self, signal_type: Optional[SignalType] = None, limit: int = 100) -> List[IntegrationSignalData]:
        """
        Get signal history
        
        Args:
            signal_type: Filter by signal type (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of signal data
        """
        history = self.signal_history
        
        if signal_type:
            history = [s for s in history if s.signal_type == signal_type]
        
        return history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get signal statistics
        
        Returns:
            Signal statistics
        """
        return {
            'total_signals': self.signal_stats['total_signals'],
            'signals_by_type': self.signal_stats['signals_by_type'].copy(),
            'failed_signals': self.signal_stats['failed_signals'],
            'registered_handlers': {
                signal_type: len(handlers)
                for signal_type, handlers in self.signal_handlers.items()
            },
            'active_listeners': {
                event_type: len(listeners)
                for event_type, listeners in self.active_listeners.items()
            },
            'history_size': len(self.signal_history)
        }
    
    def _get_django_signal(self, signal_type: SignalType):
        """Get corresponding Django signal"""
        signal_mapping = {
            SignalType.PRE_INTEGRATION: integration_pre_process,
            SignalType.POST_INTEGRATION: integration_post_process,
            SignalType.INTEGRATION_FAILED: integration_failed,
            SignalType.INTEGRATION_SUCCESS: integration_success,
            SignalType.DATA_TRANSFORMED: data_transformation_completed,
            SignalType.VALIDATION_FAILED: validation_completed,
            SignalType.CIRCUIT_BREAKER_OPENED: circuit_breaker_triggered,
            SignalType.PERFORMANCE_ALERT: performance_threshold_exceeded,
            SignalType.SECURITY_EVENT: security_violation_detected
        }
        
        return signal_mapping.get(signal_type)


# Global signal manager instance
_signal_manager = None


def get_signal_manager() -> IntegrationSignalManager:
    """Get the global signal manager instance"""
    global _signal_manager
    if _signal_manager is None:
        _signal_manager = IntegrationSignalManager()
    return _signal_manager


# Signal handlers
@receiver(integration_pre_process)
def handle_pre_integration(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle pre-integration signals"""
    logger.info(f"Pre-integration signal for {signal_data.request_id}")
    
    # Add any pre-integration logic here
    # For example: logging, validation, security checks
    
    # Check for security violations
    if signal_data.data.get('sensitive_data'):
        # Emit security event
        security_signal = IntegrationSignalData(
            signal_type=SignalType.SECURITY_EVENT,
            source_system=signal_data.source_system,
            target_system=signal_data.target_system,
            request_id=signal_data.request_id,
            timestamp=datetime.utcnow(),
            data={'event': 'sensitive_data_access', 'request_id': signal_data.request_id},
            priority=SignalPriorities.HIGH
        )
        get_signal_manager().emit_signal(security_signal)


@receiver(integration_post_process)
def handle_post_integration(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle post-integration signals"""
    logger.info(f"Post-integration signal for {signal_data.request_id}")
    
    # Add any post-integration logic here
    # For example: cleanup, notifications, analytics
    
    # Update performance metrics
    if signal_data.metadata and 'processing_time' in signal_data.metadata:
        processing_time = signal_data.metadata['processing_time']
        if processing_time > 10.0:  # 10 seconds threshold
            # Emit performance alert
            perf_signal = IntegrationSignalData(
                signal_type=SignalType.PERFORMANCE_ALERT,
                source_system=signal_data.source_system,
                target_system=signal_data.target_system,
                request_id=signal_data.request_id,
                timestamp=datetime.utcnow(),
                data={
                    'event': 'slow_processing',
                    'processing_time': processing_time,
                    'threshold': 10.0
                },
                priority=SignalPriorities.MEDIUM
            )
            get_signal_manager().emit_signal(perf_signal)


@receiver(integration_failed)
def handle_integration_failure(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle integration failure signals"""
    logger.error(f"Integration failed for {signal_data.request_id}: {signal_data.error}")
    
    # Add failure handling logic here
    # For example: retry logic, alerting, fallback activation
    
    # Check if circuit breaker should be triggered
    if signal_data.metadata and 'consecutive_failures' in signal_data.metadata:
        consecutive_failures = signal_data.metadata['consecutive_failures']
        if consecutive_failures >= 5:  # Threshold for circuit breaker
            cb_signal = IntegrationSignalData(
                signal_type=SignalType.CIRCUIT_BREAKER_OPENED,
                source_system=signal_data.source_system,
                target_system=signal_data.target_system,
                request_id=signal_data.request_id,
                timestamp=datetime.utcnow(),
                data={
                    'event': 'circuit_breaker_opened',
                    'consecutive_failures': consecutive_failures,
                    'system': signal_data.target_system
                },
                priority=SignalPriorities.HIGH
            )
            get_signal_manager().emit_signal(cb_signal)


@receiver(integration_success)
def handle_integration_success(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle integration success signals"""
    logger.info(f"Integration succeeded for {signal_data.request_id}")
    
    # Add success handling logic here
    # For example: metrics collection, notifications, cache updates
    
    # Reset circuit breaker if it was open
    cb_signal = IntegrationSignalData(
        signal_type=SignalType.CIRCUIT_BREAKER_CLOSED,
        source_system=signal_data.source_system,
        target_system=signal_data.target_system,
        request_id=signal_data.request_id,
        timestamp=datetime.utcnow(),
        data={
            'event': 'circuit_breaker_closed',
            'system': signal_data.target_system
        },
        priority=SignalPriorities.NORMAL
    )
    get_signal_manager().emit_signal(cb_signal)


@receiver(data_transformation_started)
def handle_data_transformation_started(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle data transformation started signals"""
    logger.debug(f"Data transformation started for {signal_data.request_id}")


@receiver(data_transformation_completed)
def handle_data_transformation_completed(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle data transformation completed signals"""
    logger.debug(f"Data transformation completed for {signal_data.request_id}")
    
    # Validate transformation results
    if signal_data.data.get('transformation_errors'):
        error_signal = IntegrationSignalData(
            signal_type=SignalType.VALIDATION_FAILED,
            source_system=signal_data.source_system,
            target_system=signal_data.target_system,
            request_id=signal_data.request_id,
            timestamp=datetime.utcnow(),
            data={
                'event': 'transformation_validation_failed',
                'errors': signal_data.data['transformation_errors']
            },
            priority=SignalPriorities.HIGH
        )
        get_signal_manager().emit_signal(error_signal)


@receiver(circuit_breaker_triggered)
def handle_circuit_breaker_triggered(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle circuit breaker triggered signals"""
    logger.warning(f"Circuit breaker triggered for {signal_data.target_system}")
    
    # Add circuit breaker handling logic here
    # For example: system alert, traffic rerouting, manual intervention notification


@receiver(performance_threshold_exceeded)
def handle_performance_threshold_exceeded(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle performance threshold exceeded signals"""
    logger.warning(f"Performance threshold exceeded for {signal_data.request_id}")
    
    # Add performance handling logic here
    # For example: scaling alerts, optimization suggestions


@receiver(security_violation_detected)
def handle_security_violation_detected(sender, signal_data: IntegrationSignalData, **kwargs):
    """Handle security violation detected signals"""
    logger.error(f"Security violation detected for {signal_data.request_id}")
    
    # Add security handling logic here
    # For example: security team notification, audit logging, access revocation


# Utility functions for signal emission
def emit_pre_integration_signal(source_system: str, target_system: str, request_id: str, data: Dict[str, Any], **kwargs):
    """Emit pre-integration signal"""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.PRE_INTEGRATION,
        source_system=source_system,
        target_system=target_system,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        data=data,
        **kwargs
    )
    get_signal_manager().emit_signal(signal_data)


def emit_post_integration_signal(source_system: str, target_system: str, request_id: str, data: Dict[str, Any], **kwargs):
    """Emit post-integration signal"""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.POST_INTEGRATION,
        source_system=source_system,
        target_system=target_system,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        data=data,
        **kwargs
    )
    get_signal_manager().emit_signal(signal_data)


def emit_integration_failure_signal(source_system: str, target_system: str, request_id: str, error: str, **kwargs):
    """Emit integration failure signal"""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.INTEGRATION_FAILED,
        source_system=source_system,
        target_system=target_system,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        data={'error': error},
        error=error,
        **kwargs
    )
    get_signal_manager().emit_signal(signal_data)


def emit_integration_success_signal(source_system: str, target_system: str, request_id: str, data: Dict[str, Any], **kwargs):
    """Emit integration success signal"""
    signal_data = IntegrationSignalData(
        signal_type=SignalType.INTEGRATION_SUCCESS,
        source_system=source_system,
        target_system=target_system,
        request_id=request_id,
        timestamp=datetime.utcnow(),
        data=data,
        **kwargs
    )
    get_signal_manager().emit_signal(signal_data)


# Export main classes and functions
__all__ = [
    'IntegrationSignalManager',
    'IntegrationSignalData',
    'SignalType',
    'get_signal_manager',
    'emit_pre_integration_signal',
    'emit_post_integration_signal',
    'emit_integration_failure_signal',
    'emit_integration_success_signal',
    # Django signals
    'integration_pre_process',
    'integration_post_process',
    'integration_failed',
    'integration_success',
    'data_transformation_started',
    'data_transformation_completed',
    'validation_started',
    'validation_completed',
    'circuit_breaker_triggered',
    'performance_threshold_exceeded',
    'security_violation_detected',
]
