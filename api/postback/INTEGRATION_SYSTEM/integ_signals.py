"""
integ_signals.py – Integration signals for postback module.

Provides comprehensive signal functionality including:
- Integration event signals
- Signal handlers and processors
- Event broadcasting and subscription
- Signal-based communication
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.dispatch import Signal, receiver
from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationEventType, IntegrationStatus
from api.postback.INTEGRATION_SYSTEM.integ_handler import integration_handler
from api.postback.INTEGRATION_SYSTEM.integ_registry import integration_registry

logger = logging.getLogger(__name__)


class SignalPriority(Enum):
    """Signal priority enumeration."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class SignalStatus(Enum):
    """Signal status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IntegrationSignal:
    """Integration signal data structure."""
    id: str
    event_type: IntegrationEventType
    source: str
    target: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    priority: SignalPriority = SignalPriority.NORMAL
    status: SignalStatus = SignalStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    handlers_executed: List[str] = field(default_factory=list)
    error_message: str = ""
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'source': self.source,
            'target': self.target,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'status': self.status.value,
            'metadata': self.metadata,
            'handlers_executed': self.handlers_executed,
            'error_message': self.error_message,
            'processing_time': self.processing_time,
        }


class SignalHandler:
    """
    Base signal handler class.
    
    Provides common functionality for signal handlers
    with error handling and performance monitoring.
    """
    
    def __init__(self, name: str, event_types: List[IntegrationEventType],
                 priority: SignalPriority = SignalPriority.NORMAL):
        self.name = name
        self.event_types = event_types
        self.priority = priority
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.logger = logging.getLogger(f"signals.{name}")
    
    def can_handle(self, signal: IntegrationSignal) -> bool:
        """
        Check if handler can handle signal.
        
        Args:
            signal: Integration signal
            
        Returns:
            True if can handle
        """
        return (self.enabled and 
                signal.event_type in self.event_types and
                self.priority.value >= signal.priority.value)
    
    def handle(self, signal: IntegrationSignal) -> bool:
        """
        Handle signal.
        
        Args:
            signal: Integration signal
            
        Returns:
            True if handled successfully
        """
        if not self.can_handle(signal):
            return False
        
        start_time = timezone.now()
        self.execution_count += 1
        
        try:
            self.logger.info(f"Handling signal: {signal.event_type.value} with handler: {self.name}")
            
            # Call the actual handler method
            result = self._handle_signal(signal)
            
            # Update statistics
            self.success_count += 1
            processing_time = (timezone.now() - start_time).total_seconds()
            self.total_processing_time += processing_time
            signal.processing_time += processing_time
            signal.handlers_executed.append(self.name)
            
            self.logger.info(f"Signal handled successfully: {signal.event_type.value}")
            return result
        
        except Exception as e:
            self.error_count += 1
            processing_time = (timezone.now() - start_time).total_seconds()
            self.total_processing_time += processing_time
            signal.processing_time += processing_time
            signal.error_message = str(e)
            
            self.logger.error(f"Error handling signal {signal.event_type.value}: {str(e)}")
            return False
    
    def _handle_signal(self, signal: IntegrationSignal) -> bool:
        """
        Override this method in subclasses.
        
        Args:
            signal: Integration signal
            
        Returns:
            True if handled successfully
        """
        return True
    
    def enable(self):
        """Enable handler."""
        self.enabled = True
        self.logger.info(f"Handler enabled: {self.name}")
    
    def disable(self):
        """Disable handler."""
        self.enabled = False
        self.logger.info(f"Handler disabled: {self.name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        avg_processing_time = (self.total_processing_time / self.execution_count) if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'event_types': [et.value for et in self.event_types],
            'priority': self.priority.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': f"{success_rate:.2f}%",
            'avg_processing_time': f"{avg_processing_time:.3f}s",
            'total_processing_time': f"{self.total_processing_time:.3f}s",
        }


class IntegrationEventHandler(SignalHandler):
    """Handler for integration events."""
    
    def __init__(self, name: str):
        event_types = [
            IntegrationEventType.INTEGRATION_REGISTERED,
            IntegrationEventType.INTEGRATION_UNREGISTERED,
            IntegrationEventType.INTEGRATION_UPDATED,
            IntegrationEventType.INTEGRATION_STATUS_CHANGED,
        ]
        super().__init__(name, event_types)
    
    def _handle_signal(self, signal: IntegrationSignal) -> bool:
        """Handle integration event signal."""
        if signal.event_type == IntegrationEventType.INTEGRATION_REGISTERED:
            return self._handle_integration_registered(signal)
        elif signal.event_type == IntegrationEventType.INTEGRATION_UNREGISTERED:
            return self._handle_integration_unregistered(signal)
        elif signal.event_type == IntegrationEventType.INTEGRATION_UPDATED:
            return self._handle_integration_updated(signal)
        elif signal.event_type == IntegrationEventType.INTEGRATION_STATUS_CHANGED:
            return self._handle_integration_status_changed(signal)
        
        return True
    
    def _handle_integration_registered(self, signal: IntegrationSignal) -> bool:
        """Handle integration registered event."""
        integration_name = signal.data.get('integration_name')
        config = signal.data.get('config')
        
        self.logger.info(f"Integration registered: {integration_name}")
        
        # Update cache
        cache_key = f"integration_status_{integration_name}"
        cache.set(cache_key, {'status': 'registered', 'config': config}, timeout=3600)
        
        return True
    
    def _handle_integration_unregistered(self, signal: IntegrationSignal) -> bool:
        """Handle integration unregistered event."""
        integration_name = signal.data.get('integration_name')
        
        self.logger.info(f"Integration unregistered: {integration_name}")
        
        # Update cache
        cache_key = f"integration_status_{integration_name}"
        cache.delete(cache_key)
        
        return True
    
    def _handle_integration_updated(self, signal: IntegrationSignal) -> bool:
        """Handle integration updated event."""
        integration_name = signal.data.get('integration_name')
        updates = signal.data.get('updates')
        
        self.logger.info(f"Integration updated: {integration_name}")
        
        # Update cache
        cache_key = f"integration_status_{integration_name}"
        cached_data = cache.get(cache_key, {})
        cached_data.update(updates)
        cache.set(cache_key, cached_data, timeout=3600)
        
        return True
    
    def _handle_integration_status_changed(self, signal: IntegrationSignal) -> bool:
        """Handle integration status changed event."""
        integration_name = signal.data.get('integration_name')
        old_status = signal.data.get('old_status')
        new_status = signal.data.get('new_status')
        
        self.logger.info(f"Integration status changed: {integration_name} from {old_status} to {new_status}")
        
        # Update cache
        cache_key = f"integration_status_{integration_name}"
        cached_data = cache.get(cache_key, {})
        cached_data['status'] = new_status
        cached_data['last_status_change'] = signal.timestamp.isoformat()
        cache.set(cache_key, cached_data, timeout=3600)
        
        return True


class RequestEventHandler(SignalHandler):
    """Handler for request events."""
    
    def __init__(self, name: str):
        event_types = [
            IntegrationEventType.REQUEST_RECEIVED,
            IntegrationEventType.REQUEST_PROCESSED,
            IntegrationEventType.REQUEST_FAILED,
            IntegrationEventType.REQUEST_RETRY,
        ]
        super().__init__(name, event_types)
    
    def _handle_signal(self, signal: IntegrationSignal) -> bool:
        """Handle request event signal."""
        if signal.event_type == IntegrationEventType.REQUEST_RECEIVED:
            return self._handle_request_received(signal)
        elif signal.event_type == IntegrationEventType.REQUEST_PROCESSED:
            return self._handle_request_processed(signal)
        elif signal.event_type == IntegrationEventType.REQUEST_FAILED:
            return self._handle_request_failed(signal)
        elif signal.event_type == IntegrationEventType.REQUEST_RETRY:
            return self._handle_request_retry(signal)
        
        return True
    
    def _handle_request_received(self, signal: IntegrationSignal) -> bool:
        """Handle request received event."""
        integration_name = signal.data.get('integration_name')
        request_id = signal.data.get('request_id')
        
        self.logger.info(f"Request received: {request_id} for {integration_name}")
        
        # Track request metrics
        metrics_key = f"request_metrics_{integration_name}"
        metrics = cache.get(metrics_key, {'total': 0, 'received': 0, 'processed': 0, 'failed': 0})
        metrics['received'] += 1
        metrics['total'] += 1
        cache.set(metrics_key, metrics, timeout=3600)
        
        return True
    
    def _handle_request_processed(self, signal: IntegrationSignal) -> bool:
        """Handle request processed event."""
        integration_name = signal.data.get('integration_name')
        request_id = signal.data.get('request_id')
        processing_time = signal.data.get('processing_time', 0)
        
        self.logger.info(f"Request processed: {request_id} for {integration_name} in {processing_time:.3f}s")
        
        # Track request metrics
        metrics_key = f"request_metrics_{integration_name}"
        metrics = cache.get(metrics_key, {'total': 0, 'received': 0, 'processed': 0, 'failed': 0})
        metrics['processed'] += 1
        cache.set(metrics_key, metrics, timeout=3600)
        
        return True
    
    def _handle_request_failed(self, signal: IntegrationSignal) -> bool:
        """Handle request failed event."""
        integration_name = signal.data.get('integration_name')
        request_id = signal.data.get('request_id')
        error_message = signal.data.get('error_message')
        
        self.logger.error(f"Request failed: {request_id} for {integration_name} - {error_message}")
        
        # Track request metrics
        metrics_key = f"request_metrics_{integration_name}"
        metrics = cache.get(metrics_key, {'total': 0, 'received': 0, 'processed': 0, 'failed': 0})
        metrics['failed'] += 1
        cache.set(metrics_key, metrics, timeout=3600)
        
        return True
    
    def _handle_request_retry(self, signal: IntegrationSignal) -> bool:
        """Handle request retry event."""
        integration_name = signal.data.get('integration_name')
        request_id = signal.data.get('request_id')
        retry_count = signal.data.get('retry_count', 0)
        
        self.logger.info(f"Request retry: {request_id} for {integration_name} (attempt {retry_count})")
        
        return True


class SystemEventHandler(SignalHandler):
    """Handler for system events."""
    
    def __init__(self, name: str):
        event_types = [
            IntegrationEventType.SYSTEM_STARTED,
            IntegrationEventType.SYSTEM_STOPPED,
            IntegrationEventType.HEALTH_CHECK,
            IntegrationEventType.CACHE_CLEARED,
        ]
        super().__init__(name, event_types)
    
    def _handle_signal(self, signal: IntegrationSignal) -> bool:
        """Handle system event signal."""
        if signal.event_type == IntegrationEventType.SYSTEM_STARTED:
            return self._handle_system_started(signal)
        elif signal.event_type == IntegrationEventType.SYSTEM_STOPPED:
            return self._handle_system_stopped(signal)
        elif signal.event_type == IntegrationEventType.HEALTH_CHECK:
            return self._handle_health_check(signal)
        elif signal.event_type == IntegrationEventType.CACHE_CLEARED:
            return self._handle_cache_cleared(signal)
        
        return True
    
    def _handle_system_started(self, signal: IntegrationSignal) -> bool:
        """Handle system started event."""
        self.logger.info("Integration system started")
        
        # Initialize system state
        cache.set('integration_system_status', {'started': True, 'start_time': signal.timestamp.isoformat()}, timeout=86400)
        
        return True
    
    def _handle_system_stopped(self, signal: IntegrationSignal) -> bool:
        """Handle system stopped event."""
        self.logger.info("Integration system stopped")
        
        # Update system state
        cache.set('integration_system_status', {'started': False, 'stop_time': signal.timestamp.isoformat()}, timeout=86400)
        
        return True
    
    def _handle_health_check(self, signal: IntegrationSignal) -> bool:
        """Handle health check event."""
        health_status = signal.data.get('health_status')
        
        self.logger.info(f"Health check completed: {health_status}")
        
        # Cache health status
        cache.set('integration_health_status', health_status, timeout=300)
        
        return True
    
    def _handle_cache_cleared(self, signal: IntegrationSignal) -> bool:
        """Handle cache cleared event."""
        cache_target = signal.data.get('target', 'all')
        
        self.logger.info(f"Cache cleared: {cache_target}")
        
        return True


class SignalManager:
    """
    Manager for integration signals.
    
    Handles signal creation, broadcasting, and handler management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.handlers: List[SignalHandler] = []
        self.signal_history: List[IntegrationSignal] = []
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default signal handlers."""
        self.handlers = [
            IntegrationEventHandler("integration_events"),
            RequestEventHandler("request_events"),
            SystemEventHandler("system_events"),
        ]
    
    def create_signal(self, event_type: IntegrationEventType, source: str, target: str,
                      data: Dict[str, Any] = None, priority: SignalPriority = SignalPriority.NORMAL,
                      metadata: Dict[str, Any] = None) -> IntegrationSignal:
        """
        Create integration signal.
        
        Args:
            event_type: Type of event
            source: Signal source
            target: Signal target
            data: Signal data
            priority: Signal priority
            metadata: Additional metadata
            
        Returns:
            Created signal
        """
        import uuid
        
        signal = IntegrationSignal(
            id=f"signal_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            source=source,
            target=target,
            data=data or {},
            priority=priority,
            metadata=metadata or {}
        )
        
        return signal
    
    def broadcast_signal(self, signal: IntegrationSignal) -> bool:
        """
        Broadcast signal to all handlers.
        
        Args:
            signal: Integration signal
            
        Returns:
            True if broadcasted successfully
        """
        try:
            signal.status = SignalStatus.PROCESSING
            
            # Sort handlers by priority (highest first)
            sorted_handlers = sorted(self.handlers, key=lambda h: h.priority.value, reverse=True)
            
            # Execute handlers
            handlers_executed = 0
            for handler in sorted_handlers:
                if handler.handle(signal):
                    handlers_executed += 1
            
            # Update signal status
            if signal.error_message:
                signal.status = SignalStatus.FAILED
            else:
                signal.status = SignalStatus.COMPLETED
            
            # Record signal
            self.signal_history.append(signal)
            
            # Keep only last 1000 signals
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]
            
            self.logger.info(f"Signal broadcasted: {signal.event_type.value} to {handlers_executed} handlers")
            return True
        
        except Exception as e:
            signal.status = SignalStatus.FAILED
            signal.error_message = str(e)
            self.logger.error(f"Error broadcasting signal {signal.event_type.value}: {str(e)}")
            return False
    
    def register_handler(self, handler: SignalHandler):
        """
        Register signal handler.
        
        Args:
            handler: Signal handler
        """
        self.handlers.append(handler)
        self.logger.info(f"Handler registered: {handler.name}")
    
    def unregister_handler(self, handler_name: str):
        """
        Unregister signal handler.
        
        Args:
            handler_name: Handler name
        """
        self.handlers = [h for h in self.handlers if h.name != handler_name]
        self.logger.info(f"Handler unregistered: {handler_name}")
    
    def emit_event(self, event_type: IntegrationEventType, source: str, target: str,
                  data: Dict[str, Any] = None, priority: SignalPriority = SignalPriority.NORMAL):
        """
        Emit event signal.
        
        Args:
            event_type: Type of event
            source: Signal source
            target: Signal target
            data: Event data
            priority: Signal priority
        """
        signal = self.create_signal(event_type, source, target, data, priority)
        return self.broadcast_signal(signal)
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get signal statistics."""
        total_signals = len(self.signal_history)
        
        # Count by event type
        event_type_counts = {}
        for signal in self.signal_history:
            event_type = signal.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Count by status
        status_counts = {}
        for signal in self.signal_history:
            status = signal.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Handler statistics
        handler_stats = {}
        for handler in self.handlers:
            handler_stats[handler.name] = handler.get_statistics()
        
        return {
            'total_signals': total_signals,
            'event_type_counts': event_type_counts,
            'status_counts': status_counts,
            'handler_count': len(self.handlers),
            'handler_statistics': handler_stats,
        }
    
    def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent signals."""
        recent_signals = self.signal_history[-limit:]
        return [signal.to_dict() for signal in recent_signals]


# Global signal manager instance
signal_manager = SignalManager()


# Convenience functions
def emit_integration_event(event_type: IntegrationEventType, source: str, target: str,
                          data: Dict[str, Any] = None, priority: SignalPriority = SignalPriority.NORMAL):
    """Emit integration event."""
    return signal_manager.emit_event(event_type, source, target, data, priority)


def register_signal_handler(handler: SignalHandler):
    """Register signal handler."""
    signal_manager.register_handler(handler)


def get_signal_statistics() -> Dict[str, Any]:
    """Get signal statistics."""
    return signal_manager.get_signal_statistics()


def get_recent_signals(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent signals."""
    return signal_manager.get_recent_signals(limit)


# Django signal connections
def connect_django_signals():
    """Connect Django signals to integration system."""
    from django.db.models.signals import post_save, post_delete
    
    @receiver(post_save)
    def handle_model_save(sender, instance, created, **kwargs):
        """Handle model save events."""
        if hasattr(instance, 'integration_name'):
            event_type = IntegrationEventType.INTEGRATION_REGISTERED if created else IntegrationEventType.INTEGRATION_UPDATED
            signal_manager.emit_event(
                event_type=event_type,
                source='django_model',
                target='integration_system',
                data={
                    'integration_name': instance.integration_name,
                    'model': sender.__name__,
                    'created': created,
                }
            )
    
    @receiver(post_delete)
    def handle_model_delete(sender, instance, **kwargs):
        """Handle model delete events."""
        if hasattr(instance, 'integration_name'):
            signal_manager.emit_event(
                event_type=IntegrationEventType.INTEGRATION_UNREGISTERED,
                source='django_model',
                target='integration_system',
                data={
                    'integration_name': instance.integration_name,
                    'model': sender.__name__,
                }
            )


# Initialize Django signal connections
connect_django_signals()
