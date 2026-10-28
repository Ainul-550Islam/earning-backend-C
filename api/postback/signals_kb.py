"""
signals_kb.py – Knowledge base signals for postback module.

Provides comprehensive signal functionality including:
- Knowledge base integration
- Signal processing and routing
- Event aggregation
- Signal analytics
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import Signal, receiver
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class SignalCategory(Enum):
    """Signal category enumeration."""
    POSTBACK_PROCESSING = "postback_processing"
    ANALYTICS = "analytics"
    NETWORK_CONFIG = "network_config"
    SYSTEM = "system"
    USER_ACTIVITY = "user_activity"
    COMPLIANCE = "compliance"


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
    SKIPPED = "skipped"


@dataclass
class SignalEvent:
    """Signal event data structure."""
    signal_name: str
    category: SignalCategory
    priority: SignalPriority
    sender: Any
    instance: Any = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    status: SignalStatus = SignalStatus.PENDING
    error_message: str = ""
    processing_time: float = 0.0
    handlers_executed: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signal_name': self.signal_name,
            'category': self.category.value,
            'priority': self.priority.value,
            'sender': str(self.sender) if self.sender else None,
            'instance': str(self.instance) if self.instance else None,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'error_message': self.error_message,
            'processing_time': self.processing_time,
            'handlers_executed': self.handlers_executed,
        }


class SignalHandler:
    """
    Signal handler base class.
    
    Provides common functionality for signal handlers
    with error handling and performance monitoring.
    """
    
    def __init__(self, name: str, category: SignalCategory = SignalCategory.SYSTEM, 
                 priority: SignalPriority = SignalPriority.NORMAL):
        self.name = name
        self.category = category
        self.priority = priority
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.logger = logging.getLogger(f"signals.{name}")
    
    def handle(self, signal_event: SignalEvent) -> bool:
        """
        Handle signal event.
        
        Args:
            signal_event: Signal event to handle
            
        Returns:
            True if handled successfully
        """
        if not self.enabled:
            return False
        
        start_time = timezone.now()
        self.execution_count += 1
        
        try:
            self.logger.info(f"Handling signal: {signal_event.signal_name}")
            
            # Call the actual handler method
            result = self._handle_signal(signal_event)
            
            # Update statistics
            self.success_count += 1
            processing_time = (timezone.now() - start_time).total_seconds()
            self.total_processing_time += processing_time
            signal_event.processing_time += processing_time
            signal_event.handlers_executed.append(self.name)
            
            self.logger.info(f"Signal handled successfully: {signal_event.signal_name}")
            return result
            
        except Exception as e:
            self.error_count += 1
            processing_time = (timezone.now() - start_time).total_seconds()
            self.total_processing_time += processing_time
            signal_event.processing_time += processing_time
            signal_event.error_message = str(e)
            
            self.logger.error(f"Error handling signal {signal_event.signal_name}: {str(e)}")
            return False
    
    def _handle_signal(self, signal_event: SignalEvent) -> bool:
        """
        Override this method in subclasses.
        
        Args:
            signal_event: Signal event to handle
            
        Returns:
            True if handled successfully
        """
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        avg_processing_time = (self.total_processing_time / self.execution_count) if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'category': self.category.value,
            'priority': self.priority.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': f"{success_rate:.2f}%",
            'avg_processing_time': f"{avg_processing_time:.3f}s",
            'total_processing_time': f"{self.total_processing_time:.3f}s",
        }
    
    def enable(self):
        """Enable handler."""
        self.enabled = True
        self.logger.info(f"Handler enabled: {self.name}")
    
    def disable(self):
        """Disable handler."""
        self.enabled = False
        self.logger.info(f"Handler disabled: {self.name}")


class PostbackProcessingHandler(SignalHandler):
    """Handler for postback processing signals."""
    
    def __init__(self, name: str):
        super().__init__(name, SignalCategory.POSTBACK_PROCESSING)
    
    def _handle_signal(self, signal_event: SignalEvent) -> bool:
        """Handle postback processing signal."""
        if signal_event.signal_name == 'postback_received':
            return self._handle_postback_received(signal_event)
        elif signal_event.signal_name == 'postback_processed':
            return self._handle_postback_processed(signal_event)
        elif signal_event.signal_name == 'postback_failed':
            return self._handle_postback_failed(signal_event)
        
        return True
    
    def _handle_postback_received(self, signal_event: SignalEvent) -> bool:
        """Handle postback received signal."""
        postback = signal_event.instance
        
        if not postback:
            return False
        
        # Log postback reception
        self.logger.info(f"Postback received: {postback.lead_id} from {postback.network.network_key}")
        
        # Update analytics
        self._update_analytics('postback_received', postback)
        
        # Check for anomalies
        self._check_anomalies(postback)
        
        return True
    
    def _handle_postback_processed(self, signal_event: SignalEvent) -> bool:
        """Handle postback processed signal."""
        postback = signal_event.instance
        
        if not postback:
            return False
        
        # Log successful processing
        self.logger.info(f"Postback processed successfully: {postback.lead_id}")
        
        # Update analytics
        self._update_analytics('postback_processed', postback)
        
        # Send notifications
        self._send_notifications(postback)
        
        return True
    
    def _handle_postback_failed(self, signal_event: SignalEvent) -> bool:
        """Handle postback failed signal."""
        postback = signal_event.instance
        
        if not postback:
            return False
        
        # Log failure
        self.logger.warning(f"Postback failed: {postback.lead_id} - {postback.rejection_reason}")
        
        # Update analytics
        self._update_analytics('postback_failed', postback)
        
        # Check for fraud patterns
        self._check_fraud_patterns(postback)
        
        return True
    
    def _update_analytics(self, event_type: str, postback):
        """Update analytics for postback event."""
        # This would integrate with analytics system
        pass
    
    def _check_anomalies(self, postback):
        """Check for anomalies in postback."""
        # This would integrate with anomaly detection system
        pass
    
    def _send_notifications(self, postback):
        """Send notifications for postback."""
        # This would integrate with notification system
        pass
    
    def _check_fraud_patterns(self, postback):
        """Check for fraud patterns."""
        # This would integrate with fraud detection system
        pass


class AnalyticsHandler(SignalHandler):
    """Handler for analytics signals."""
    
    def __init__(self, name: str):
        super().__init__(name, SignalCategory.ANALYTICS)
    
    def _handle_signal(self, signal_event: SignalEvent) -> bool:
        """Handle analytics signal."""
        if signal_event.signal_name == 'insight_generated':
            return self._handle_insight_generated(signal_event)
        elif signal_event.signal_name == 'anomaly_detected':
            return self._handle_anomaly_detected(signal_event)
        elif signal_event.signal_name == 'metrics_calculated':
            return self._handle_metrics_calculated(signal_event)
        
        return True
    
    def _handle_insight_generated(self, signal_event: SignalEvent) -> bool:
        """Handle insight generated signal."""
        insight = signal_event.instance
        
        if not insight:
            return False
        
        # Log insight generation
        self.logger.info(f"Insight generated: {insight.network.network_key} - {insight.date}")
        
        # Update cache
        self._update_insight_cache(insight)
        
        # Check alerts
        self._check_alerts(insight)
        
        return True
    
    def _handle_anomaly_detected(self, signal_event: SignalEvent) -> bool:
        """Handle anomaly detected signal."""
        anomaly_data = signal_event.data
        
        # Log anomaly
        self.logger.warning(f"Anomaly detected: {anomaly_data.get('type', 'unknown')}")
        
        # Create alert
        self._create_alert(anomaly_data)
        
        # Notify administrators
        self._notify_administrators(anomaly_data)
        
        return True
    
    def _handle_metrics_calculated(self, signal_event: SignalEvent) -> bool:
        """Handle metrics calculated signal."""
        metrics_data = signal_event.data
        
        # Log metrics calculation
        self.logger.info(f"Metrics calculated: {metrics_data.get('type', 'unknown')}")
        
        # Update dashboard cache
        self._update_dashboard_cache(metrics_data)
        
        return True
    
    def _update_insight_cache(self, insight):
        """Update insight cache."""
        cache_key = f"insight_{insight.network.network_key}_{insight.date}"
        cache.set(cache_key, insight.to_dict(), timeout=3600)
    
    def _check_alerts(self, insight):
        """Check if alerts should be triggered."""
        if insight.health_score < 50:
            self.logger.warning(f"Low health score detected: {insight.health_score}")
    
    def _create_alert(self, anomaly_data):
        """Create alert for anomaly."""
        # This would integrate with alert system
        pass
    
    def _notify_administrators(self, anomaly_data):
        """Notify administrators of anomaly."""
        # This would integrate with notification system
        pass
    
    def _update_dashboard_cache(self, metrics_data):
        """Update dashboard cache."""
        cache_key = f"dashboard_metrics_{metrics_data.get('type', 'unknown')}"
        cache.set(cache_key, metrics_data, timeout=300)


class NetworkConfigHandler(SignalHandler):
    """Handler for network configuration signals."""
    
    def __init__(self, name: str):
        super().__init__(name, SignalCategory.NETWORK_CONFIG)
    
    def _handle_signal(self, signal_event: SignalEvent) -> bool:
        """Handle network config signal."""
        if signal_event.signal_name == 'network_created':
            return self._handle_network_created(signal_event)
        elif signal_event.signal_name == 'network_updated':
            return self._handle_network_updated(signal_event)
        elif signal_event.signal_name == 'network_activated':
            return self._handle_network_activated(signal_event)
        elif signal_event.signal_name == 'network_deactivated':
            return self._handle_network_deactivated(signal_event)
        
        return True
    
    def _handle_network_created(self, signal_event: SignalEvent) -> bool:
        """Handle network created signal."""
        network = signal_event.instance
        
        if not network:
            return False
        
        # Log network creation
        self.logger.info(f"Network created: {network.network_key}")
        
        # Initialize network analytics
        self._initialize_network_analytics(network)
        
        # Set up default monitoring
        self._setup_monitoring(network)
        
        return True
    
    def _handle_network_updated(self, signal_event: SignalEvent) -> bool:
        """Handle network updated signal."""
        network = signal_event.instance
        
        if not network:
            return False
        
        # Log network update
        self.logger.info(f"Network updated: {network.network_key}")
        
        # Update monitoring configuration
        self._update_monitoring(network)
        
        return True
    
    def _handle_network_activated(self, signal_event: SignalEvent) -> bool:
        """Handle network activated signal."""
        network = signal_event.instance
        
        if not network:
            return False
        
        # Log network activation
        self.logger.info(f"Network activated: {network.network_key}")
        
        # Enable monitoring
        self._enable_monitoring(network)
        
        return True
    
    def _handle_network_deactivated(self, signal_event: SignalEvent) -> bool:
        """Handle network deactivated signal."""
        network = signal_event.instance
        
        if not network:
            return False
        
        # Log network deactivation
        self.logger.info(f"Network deactivated: {network.network_key}")
        
        # Disable monitoring
        self._disable_monitoring(network)
        
        return True
    
    def _initialize_network_analytics(self, network):
        """Initialize analytics for new network."""
        # This would integrate with analytics system
        pass
    
    def _setup_monitoring(self, network):
        """Set up monitoring for network."""
        # This would integrate with monitoring system
        pass
    
    def _update_monitoring(self, network):
        """Update monitoring configuration."""
        # This would integrate with monitoring system
        pass
    
    def _enable_monitoring(self, network):
        """Enable monitoring for network."""
        # This would integrate with monitoring system
        pass
    
    def _disable_monitoring(self, network):
        """Disable monitoring for network."""
        # This would integrate with monitoring system
        pass


class SignalRouter:
    """
    Router for signal events.
    
    Provides centralized signal routing and
    handler management.
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[SignalHandler]] = defaultdict(list)
        self.signal_history: List[SignalEvent] = []
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default signal handlers."""
        # Postback processing handlers
        self.register_handler('postback_received', PostbackProcessingHandler('postback_received_handler'))
        self.register_handler('postback_processed', PostbackProcessingHandler('postback_processed_handler'))
        self.register_handler('postback_failed', PostbackProcessingHandler('postback_failed_handler'))
        
        # Analytics handlers
        self.register_handler('insight_generated', AnalyticsHandler('insight_generated_handler'))
        self.register_handler('anomaly_detected', AnalyticsHandler('anomaly_detected_handler'))
        self.register_handler('metrics_calculated', AnalyticsHandler('metrics_calculated_handler'))
        
        # Network config handlers
        self.register_handler('network_created', NetworkConfigHandler('network_created_handler'))
        self.register_handler('network_updated', NetworkConfigHandler('network_updated_handler'))
        self.register_handler('network_activated', NetworkConfigHandler('network_activated_handler'))
        self.register_handler('network_deactivated', NetworkConfigHandler('network_deactivated_handler'))
    
    def register_handler(self, signal_name: str, handler: SignalHandler):
        """
        Register signal handler.
        
        Args:
            signal_name: Signal name
            handler: Handler instance
        """
        self.handlers[signal_name].append(handler)
        self.logger.info(f"Registered handler for {signal_name}: {handler.name}")
    
    def unregister_handler(self, signal_name: str, handler_name: str):
        """
        Unregister signal handler.
        
        Args:
            signal_name: Signal name
            handler_name: Handler name
        """
        self.handlers[signal_name] = [
            h for h in self.handlers[signal_name] 
            if h.name != handler_name
        ]
        self.logger.info(f"Unregistered handler for {signal_name}: {handler_name}")
    
    def route_signal(self, signal_name: str, sender: Any = None, instance: Any = None, 
                    data: Dict[str, Any] = None) -> SignalEvent:
        """
        Route signal to handlers.
        
        Args:
            signal_name: Signal name
            sender: Signal sender
            instance: Signal instance
            data: Additional data
            
        Returns:
            Signal event
        """
        # Create signal event
        signal_event = SignalEvent(
            signal_name=signal_name,
            category=self._get_signal_category(signal_name),
            priority=self._get_signal_priority(signal_name),
            sender=sender,
            instance=instance,
            data=data or {}
        )
        
        # Get handlers for this signal
        handlers = self.handlers.get(signal_name, [])
        
        # Sort handlers by priority (highest first)
        handlers.sort(key=lambda h: h.priority.value, reverse=True)
        
        # Execute handlers
        signal_event.status = SignalStatus.PROCESSING
        
        for handler in handlers:
            try:
                handler.handle(signal_event)
            except Exception as e:
                self.logger.error(f"Handler {handler.name} failed: {str(e)}")
        
        # Update status
        if signal_event.error_message:
            signal_event.status = SignalStatus.FAILED
        else:
            signal_event.status = SignalStatus.COMPLETED
        
        # Record signal event
        self._record_signal_event(signal_event)
        
        return signal_event
    
    def _get_signal_category(self, signal_name: str) -> SignalCategory:
        """Get signal category."""
        if 'postback' in signal_name:
            return SignalCategory.POSTBACK_PROCESSING
        elif 'insight' in signal_name or 'anomaly' in signal_name or 'metrics' in signal_name:
            return SignalCategory.ANALYTICS
        elif 'network' in signal_name:
            return SignalCategory.NETWORK_CONFIG
        else:
            return SignalCategory.SYSTEM
    
    def _get_signal_priority(self, signal_name: str) -> SignalPriority:
        """Get signal priority."""
        if 'failed' in signal_name or 'anomaly' in signal_name:
            return SignalPriority.HIGH
        elif 'processed' in signal_name or 'generated' in signal_name:
            return SignalPriority.NORMAL
        else:
            return SignalPriority.LOW
    
    def _record_signal_event(self, signal_event: SignalEvent):
        """Record signal event in history."""
        self.signal_history.append(signal_event)
        
        # Keep only last 1000 events
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-1000:]
        
        # Cache recent events
        cache_key = f"signal_event_{signal_event.signal_name}"
        cache.set(cache_key, signal_event.to_dict(), timeout=3600)
    
    def get_signal_statistics(self, signal_name: str = None) -> Dict[str, Any]:
        """
        Get signal statistics.
        
        Args:
            signal_name: Specific signal name (None = all)
            
        Returns:
            Signal statistics
        """
        events = self.signal_history
        
        if signal_name:
            events = [e for e in events if e.signal_name == signal_name]
        
        if not events:
            return {'total_events': 0}
        
        total_events = len(events)
        completed_events = len([e for e in events if e.status == SignalStatus.COMPLETED])
        failed_events = len([e for e in events if e.status == SignalStatus.FAILED])
        avg_processing_time = sum(e.processing_time for e in events) / total_events
        
        return {
            'total_events': total_events,
            'completed_events': completed_events,
            'failed_events': failed_events,
            'success_rate': f"{(completed_events / total_events * 100):.2f}%",
            'avg_processing_time': f"{avg_processing_time:.3f}s",
            'recent_events': [e.to_dict() for e in events[-10:]],
        }
    
    def get_handler_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        stats = {}
        
        for signal_name, handlers in self.handlers.items():
            stats[signal_name] = {
                'handler_count': len(handlers),
                'handlers': [handler.get_statistics() for handler in handlers]
            }
        
        return stats


# Custom Django signals
postback_received = Signal()
postback_processed = Signal()
postback_failed = Signal()
insight_generated = Signal()
anomaly_detected = Signal()
metrics_calculated = Signal()
network_created = Signal()
network_updated = Signal()
network_activated = Signal()
network_deactivated = Signal()


# Global signal router instance
signal_router = SignalRouter()


# Signal receivers
@receiver(post_save, sender=PostbackLog)
def postback_log_saved(sender, instance, created, **kwargs):
    """Handle PostbackLog save signal."""
    if created:
        signal_router.route_signal('postback_received', sender=sender, instance=instance)
    else:
        if instance.status == 'rewarded':
            signal_router.route_signal('postback_processed', sender=sender, instance=instance)
        elif instance.status == 'failed':
            signal_router.route_signal('postback_failed', sender=sender, instance=instance)


@receiver(post_save, sender=PostbackInsight)
def postback_insight_saved(sender, instance, created, **kwargs):
    """Handle PostbackInsight save signal."""
    if created:
        signal_router.route_signal('insight_generated', sender=sender, instance=instance)
        
        if instance.anomaly_detected:
            signal_router.route_signal('anomaly_detected', sender=sender, instance=instance, data=instance.anomaly_details)


@receiver(post_save, sender=NetworkPostbackConfig)
def network_config_saved(sender, instance, created, **kwargs):
    """Handle NetworkPostbackConfig save signal."""
    if created:
        signal_router.route_signal('network_created', sender=sender, instance=instance)
    else:
        signal_router.route_signal('network_updated', sender=sender, instance=instance)


# Convenience functions
def send_signal(signal_name: str, sender: Any = None, instance: Any = None, data: Dict[str, Any] = None):
    """Send custom signal."""
    return signal_router.route_signal(signal_name, sender, instance, data)


def register_signal_handler(signal_name: str, handler: SignalHandler):
    """Register signal handler."""
    signal_router.register_handler(signal_name, handler)


def get_signal_statistics(signal_name: str = None) -> Dict[str, Any]:
    """Get signal statistics."""
    return signal_router.get_signal_statistics(signal_name)


def get_handler_statistics() -> Dict[str, Any]:
    """Get handler statistics."""
    return signal_router.get_handler_statistics()


# Signal utilities
def create_signal_handler(name: str, handler_func: Callable, category: SignalCategory = SignalCategory.SYSTEM, 
                         priority: SignalPriority = SignalPriority.NORMAL) -> SignalHandler:
    """
    Create custom signal handler.
    
    Args:
        name: Handler name
        handler_func: Handler function
        category: Handler category
        priority: Handler priority
        
    Returns:
        SignalHandler instance
    """
    class CustomHandler(SignalHandler):
        def _handle_signal(self, signal_event: SignalEvent) -> bool:
            return handler_func(signal_event)
    
    return CustomHandler(name, category, priority)


def batch_signal_processing(signals: List[Dict[str, Any]]) -> List[SignalEvent]:
    """
    Process multiple signals in batch.
    
    Args:
        signals: List of signal dictionaries
        
    Returns:
        List of signal events
    """
    events = []
    
    for signal_data in signals:
        signal_name = signal_data.get('signal_name')
        sender = signal_data.get('sender')
        instance = signal_data.get('instance')
        data = signal_data.get('data', {})
        
        event = signal_router.route_signal(signal_name, sender, instance, data)
        events.append(event)
    
    return events


def get_signal_history(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get signal history.
    
    Args:
        limit: Number of events to return
        
    Returns:
        List of signal events
    """
    recent_events = signal_router.signal_history[-limit:]
    return [event.to_dict() for event in recent_events]


# Signal health check
def check_signal_health() -> Dict[str, Any]:
    """Check signal system health."""
    health_status = {
        'overall': 'healthy',
        'signal_router': 'healthy',
        'handlers': {},
        'recent_signals': [],
        'issues': [],
    }
    
    # Check signal router
    try:
        stats = signal_router.get_signal_statistics()
        health_status['signal_router'] = 'healthy'
    except Exception as e:
        health_status['signal_router'] = 'error'
        health_status['issues'].append(f"Signal router error: {str(e)}")
    
    # Check handlers
    for signal_name, handlers in signal_router.handlers.items():
        handler_health = {
            'signal_name': signal_name,
            'handler_count': len(handlers),
            'enabled_handlers': len([h for h in handlers if h.enabled]),
            'status': 'healthy',
        }
        
        if handler_health['enabled_handlers'] == 0:
            handler_health['status'] = 'warning'
            health_status['issues'].append(f"No enabled handlers for {signal_name}")
        
        health_status['handlers'][signal_name] = handler_health
    
    # Get recent signals
    recent_signals = get_signal_history(10)
    health_status['recent_signals'] = recent_signals
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
