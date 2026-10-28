# api/rate_limit/integ_signals.py
"""
Integration signals for rate limit module.

Provides signal-based integration event handling.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.contrib.auth import get_user_model

from api.rate_limit.integ_handler import integration_handler
from api.rate_limit.integ_constants import IntegrationEvent, IntegrationType
from api.rate_limit.models import RateLimitLog, RateLimitConfig, UserRateLimitProfile, AbuseReport

logger = logging.getLogger(__name__)
User = get_user_model()


# Custom signals
integration_event_signal = Signal()
integration_status_change_signal = Signal()
integration_error_signal = Signal()
integration_performance_signal = Signal()


class IntegrationSignalManager:
    """
    Manager for integration signals and event handling.
    """
    
    def __init__(self):
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.signal_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
    
    def register_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered integration signal handler for {event_type}")
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """
        Unregister an event handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                logger.info(f"Unregistered integration signal handler for {event_type}")
            except ValueError:
                pass
    
    def emit_event(self, event_type: str, data: Dict[str, Any] = None, **kwargs):
        """
        Emit an integration event.
        
        Args:
            event_type: Event type
            data: Event data
            **kwargs: Additional keyword arguments
        """
        try:
            event_data = data or {}
            event_data.update(kwargs)
            
            # Record event in history
            event_record = {
                'event_type': event_type,
                'data': event_data,
                'timestamp': timezone.now().isoformat()
            }
            
            self.signal_history.append(event_record)
            
            # Maintain history size
            if len(self.signal_history) > self.max_history_size:
                self.signal_history = self.signal_history[-self.max_history_size:]
            
            # Call registered handlers
            if event_type in self.event_handlers:
                for handler in self.event_handlers[event_type]:
                    try:
                        handler(event_type, event_data)
                    except Exception as e:
                        logger.error(f"Signal handler failed for {event_type}: {str(e)}")
            
            # Send Django signal
            integration_event_signal.send(
                sender=self.__class__,
                event_type=event_type,
                data=event_data
            )
            
            logger.debug(f"Emitted integration signal: {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to emit integration signal {event_type}: {str(e)}")
    
    def get_signal_history(self, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get signal history.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of records
            
        Returns:
            Signal history
        """
        history = self.signal_history
        
        if event_type:
            history = [record for record in history if record['event_type'] == event_type]
        
        return history[-limit:] if len(history) > limit else history
    
    def clear_history(self, event_type: str = None):
        """
        Clear signal history.
        
        Args:
            event_type: Event type to clear (None for all)
        """
        if event_type:
            self.signal_history = [
                record for record in self.signal_history 
                if record['event_type'] != event_type
            ]
        else:
            self.signal_history = []
        
        logger.info(f"Cleared signal history for {event_type or 'all events'}")


# Global signal manager instance
signal_manager = IntegrationSignalManager()


# Rate limit model signal handlers
@receiver(post_save, sender=RateLimitLog)
def rate_limit_log_created(sender, instance, created, **kwargs):
    """
    Handle rate limit log creation.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    if created:
        # Emit integration event
        signal_manager.emit_event(
            IntegrationEvent.RATE_LIMIT_EXCEEDED,
            data={
                'log_id': instance.id,
                'user_id': instance.user.id if instance.user else None,
                'ip_address': instance.ip_address,
                'endpoint': instance.endpoint,
                'status': instance.status,
                'suspicion_score': instance.suspicion_score,
                'timestamp': instance.timestamp.isoformat()
            }
        )


@receiver(post_save, sender=RateLimitConfig)
def rate_limit_config_changed(sender, instance, created, **kwargs):
    """
    Handle rate limit config changes.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    event_type = IntegrationEvent.CONFIG_CREATED if created else IntegrationEvent.CONFIG_UPDATED
    
    signal_manager.emit_event(
        event_type,
        data={
            'config_id': instance.id,
            'name': instance.name,
            'rate_limit_type': instance.rate_limit_type,
            'requests_per_unit': instance.requests_per_unit,
            'time_unit': instance.time_unit,
            'is_active': instance.is_active,
            'timestamp': timezone.now().isoformat()
        }
    )


@receiver(post_save, sender=UserRateLimitProfile)
def user_rate_limit_profile_changed(sender, instance, created, **kwargs):
    """
    Handle user rate limit profile changes.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    event_type = IntegrationEvent.USER_PROFILE_CREATED if created else IntegrationEvent.USER_PROFILE_UPDATED
    
    signal_manager.emit_event(
        event_type,
        data={
            'profile_id': instance.id,
            'user_id': instance.user.id,
            'api_health_score': instance.api_health_score,
            'suspicion_score': instance.suspicion_score,
            'is_premium': instance.is_premium,
            'timestamp': timezone.now().isoformat()
        }
    )


@receiver(post_save, sender=AbuseReport)
def abuse_report_created(sender, instance, created, **kwargs):
    """
    Handle abuse report creation.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    if created:
        signal_manager.emit_event(
            IntegrationEvent.ABUSE_DETECTED,
            data={
                'report_id': instance.id,
                'abuse_type': instance.abuse_type,
                'severity': instance.severity,
                'ip_address': instance.ip_address,
                'user_id': instance.user.id if instance.user else None,
                'description': instance.description,
                'timestamp': instance.created_at.isoformat()
            }
        )


# Integration event handlers
def handle_rate_limit_exceeded(event_type: str, data: Dict[str, Any]):
    """
    Handle rate limit exceeded events.
    
    Args:
        event_type: Event type
        data: Event data
    """
    try:
        # Check for active integrations that should handle rate limit events
        active_integrations = integration_handler.active_integrations
        
        for int_id, int_info in active_integrations.items():
            adapter = int_info['adapter']
            
            # Check if adapter handles rate limit events
            if hasattr(adapter, 'handle_rate_limit_exceeded'):
                adapter.handle_rate_limit_exceeded(data)
    
    except Exception as e:
        logger.error(f"Failed to handle rate limit exceeded event: {str(e)}")


def handle_abuse_detected(event_type: str, data: Dict[str, Any]):
    """
    Handle abuse detected events.
    
    Args:
        event_type: Event type
        data: Event data
    """
    try:
        # Check for active integrations that should handle abuse events
        active_integrations = integration_handler.active_integrations
        
        for int_id, int_info in active_integrations.items():
            adapter = int_info['adapter']
            
            # Check if adapter handles abuse events
            if hasattr(adapter, 'handle_abuse_detected'):
                adapter.handle_abuse_detected(data)
    
    except Exception as e:
        logger.error(f"Failed to handle abuse detected event: {str(e)}")


def handle_config_updated(event_type: str, data: Dict[str, Any]):
    """
    Handle configuration update events.
    
    Args:
        event_type: Event type
        data: Event data
    """
    try:
        # Check for active integrations that should handle config events
        active_integrations = integration_handler.active_integrations
        
        for int_id, int_info in active_integrations.items():
            adapter = int_info['adapter']
            
            # Check if adapter handles config events
            if hasattr(adapter, 'handle_config_updated'):
                adapter.handle_config_updated(data)
    
    except Exception as e:
        logger.error(f"Failed to handle config updated event: {str(e)}")


def handle_user_profile_updated(event_type: str, data: Dict[str, Any]):
    """
    Handle user profile update events.
    
    Args:
        event_type: Event type
        data: Event data
    """
    try:
        # Check for active integrations that should handle user profile events
        active_integrations = integration_handler.active_integrations
        
        for int_id, int_info in active_integrations.items():
            adapter = int_info['adapter']
            
            # Check if adapter handles user profile events
            if hasattr(adapter, 'handle_user_profile_updated'):
                adapter.handle_user_profile_updated(data)
    
    except Exception as e:
        logger.error(f"Failed to handle user profile updated event: {str(e)}")


# Register default event handlers
signal_manager.register_handler(IntegrationEvent.RATE_LIMIT_EXCEEDED, handle_rate_limit_exceeded)
signal_manager.register_handler(IntegrationEvent.ABUSE_DETECTED, handle_abuse_detected)
signal_manager.register_handler(IntegrationEvent.CONFIG_CREATED, handle_config_updated)
signal_manager.register_handler(IntegrationEvent.CONFIG_UPDATED, handle_config_updated)
signal_manager.register_handler(IntegrationEvent.USER_PROFILE_CREATED, handle_user_profile_updated)
signal_manager.register_handler(IntegrationEvent.USER_PROFILE_UPDATED, handle_user_profile_updated)


# Django signal receivers for integration events
@receiver(integration_event_signal)
def handle_integration_event(sender, event_type: str, data: Dict[str, Any], **kwargs):
    """
    Handle integration events from Django signals.
    
    Args:
        sender: Signal sender
        event_type: Event type
        data: Event data
        **kwargs: Additional arguments
    """
    try:
        # Log integration event
        logger.info(f"Integration event received: {event_type}")
        
        # Update integration performance metrics
        if event_type in [IntegrationEvent.INTEGRATION_SUCCESS, IntegrationEvent.INTEGRATION_FAILURE]:
            integration_id = data.get('integration_id')
            if integration_id:
                # Update performance stats
                if event_type == IntegrationEvent.INTEGRATION_SUCCESS:
                    integration_handler.performance_stats[integration_id]['successful_requests'] += 1
                else:
                    integration_handler.performance_stats[integration_id]['failed_requests'] += 1
                    integration_handler.error_counts[integration_id] += 1
        
    except Exception as e:
        logger.error(f"Failed to handle integration event: {str(e)}")


@receiver(integration_status_change_signal)
def handle_integration_status_change(sender, integration_id: str, old_status: str, 
                                   new_status: str, **kwargs):
    """
    Handle integration status change events.
    
    Args:
        sender: Signal sender
        integration_id: Integration ID
        old_status: Previous status
        new_status: New status
        **kwargs: Additional arguments
    """
    try:
        # Emit status change event
        signal_manager.emit_event(
            IntegrationEvent.STATUS_CHANGE,
            data={
                'integration_id': integration_id,
                'old_status': old_status,
                'new_status': new_status,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        logger.info(f"Integration {integration_id} status changed from {old_status} to {new_status}")
        
    except Exception as e:
        logger.error(f"Failed to handle integration status change: {str(e)}")


@receiver(integration_error_signal)
def handle_integration_error(sender, integration_id: str, error: Exception, 
                            context: Dict[str, Any] = None, **kwargs):
    """
    Handle integration error events.
    
    Args:
        sender: Signal sender
        integration_id: Integration ID
        error: Error instance
        context: Error context
        **kwargs: Additional arguments
    """
    try:
        # Emit error event
        signal_manager.emit_event(
            IntegrationEvent.INTEGRATION_ERROR,
            data={
                'integration_id': integration_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {},
                'timestamp': timezone.now().isoformat()
            }
        )
        
        logger.error(f"Integration {integration_id} error: {str(error)}")
        
    except Exception as e:
        logger.error(f"Failed to handle integration error: {str(e)}")


@receiver(integration_performance_signal)
def handle_integration_performance(sender, integration_id: str, metric: str, 
                                  value: float, **kwargs):
    """
    Handle integration performance events.
    
    Args:
        sender: Signal sender
        integration_id: Integration ID
        metric: Metric name
        value: Metric value
        **kwargs: Additional arguments
    """
    try:
        # Emit performance event
        signal_manager.emit_event(
            IntegrationEvent.PERFORMANCE_UPDATE,
            data={
                'integration_id': integration_id,
                'metric': metric,
                'value': value,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        logger.debug(f"Integration {integration_id} performance: {metric}={value}")
        
    except Exception as e:
        logger.error(f"Failed to handle integration performance: {str(e)}")


# Utility functions for emitting integration events
def emit_rate_limit_event(event_type: str, log_data: Dict[str, Any]):
    """
    Emit rate limit related event.
    
    Args:
        event_type: Event type
        log_data: Log data
    """
    signal_manager.emit_event(event_type, data=log_data)


def emit_config_event(event_type: str, config_data: Dict[str, Any]):
    """
    Emit configuration related event.
    
    Args:
        event_type: Event type
        config_data: Configuration data
    """
    signal_manager.emit_event(event_type, data=config_data)


def emit_user_event(event_type: str, user_data: Dict[str, Any]):
    """
    Emit user related event.
    
    Args:
        event_type: Event type
        user_data: User data
    """
    signal_manager.emit_event(event_type, data=user_data)


def emit_abuse_event(event_type: str, abuse_data: Dict[str, Any]):
    """
    Emit abuse related event.
    
    Args:
        event_type: Event type
        abuse_data: Abuse data
    """
    signal_manager.emit_event(event_type, data=abuse_data)


def emit_integration_event(event_type: str, integration_data: Dict[str, Any]):
    """
    Emit integration related event.
    
    Args:
        event_type: Event type
        integration_data: Integration data
    """
    signal_manager.emit_event(event_type, data=integration_data)


# Export classes and functions
__all__ = [
    'IntegrationSignalManager',
    'signal_manager',
    'integration_event_signal',
    'integration_status_change_signal',
    'integration_error_signal',
    'integration_performance_signal',
    'emit_rate_limit_event',
    'emit_config_event',
    'emit_user_event',
    'emit_abuse_event',
    'emit_integration_event'
]
