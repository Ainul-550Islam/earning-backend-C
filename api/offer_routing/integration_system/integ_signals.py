"""
Integration Signals

Django signals for integration system events.
"""

from django.dispatch import Signal
from django.utils import timezone
from typing import Dict, Any, Optional

# Integration registration signals
integration_registered = Signal()
integration_updated = Signal()
integration_enabled = Signal()
integration_disabled = Signal()
integration_removed = Signal()

# Integration execution signals
integration_before_execute = Signal()
integration_after_execute = Signal()
integration_error = Signal()

# Integration synchronization signals
integrations_synced = Signal()
integration_sync_started = Signal()
integration_sync_completed = Signal()

# Integration health signals
integration_health_check = Signal()
integration_healthy = Signal()
integration_unhealthy = Signal()

# Integration data signals
integration_data_received = Signal()
integration_data_sent = Signal()
integration_data_processed = Signal()

# Integration lifecycle signals
integration_created = Signal()
integration_modified = Signal()
integration_deleted = Signal()

# Integration performance signals
integration_slow = Signal()
integration_timeout = Signal()
integration_retry = Signal()

# Integration security signals
integration_authentication_success = Signal()
integration_authentication_failure = Signal()
integration_authorization_denied = Signal()

# Integration configuration signals
integration_config_validated = Signal()
integration_config_changed = Signal()
integration_config_reloaded = Signal()

# Integration error handling signals
integration_error_handled = Signal()
integration_error_escalated = Signal()
integration_error_resolved = Signal()

# Integration batch processing signals
integration_batch_started = Signal()
integration_batch_completed = Signal()
integration_batch_failed = Signal()

# Integration monitoring signals
integration_metrics_collected = Signal()
integration_alert_triggered = Signal()
integration_threshold_exceeded = Signal()

# Integration webhook signals
webhook_received = Signal()
webhook_processed = Signal()
webhook_failed = Signal()

# Integration API signals
api_request_received = Signal()
api_response_sent = Signal()
api_error_occurred = Signal()

# Integration database signals
database_connection_established = Signal()
database_connection_lost = Signal()
database_query_executed = Signal()

# Integration message queue signals
message_received = Signal()
message_processed = Signal()
message_failed = Signal()
queue_empty = Signal()

# Integration cache signals
cache_hit = Signal()
cache_miss = Signal()
cache_cleared = Signal()

# Integration rate limiting signals
rate_limit_exceeded = Signal()
rate_limit_reset = Signal()

# Integration logging signals
integration_log_created = Signal()
integration_log_updated = Signal()
integration_log_archived = Signal()


def send_integration_signal(signal: Signal, sender: Any = None, **kwargs):
    """
    Send integration signal with proper error handling.
    
    Args:
        signal: Django signal to send
        sender: Signal sender
        **kwargs: Signal arguments
    """
    try:
        signal.send(sender=sender, **kwargs)
    except Exception as e:
        # Log signal sending error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending integration signal: {e}")


def create_signal_context(integration_id: str, action: str, 
                        data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create standardized signal context.
    
    Args:
        integration_id: Integration identifier
        action: Action being performed
        data: Additional data
        
    Returns:
        Signal context dictionary
    """
    return {
        'integration_id': integration_id,
        'action': action,
        'data': data or {},
        'timestamp': timezone.now().isoformat(),
        'context': {
            'source': 'integration_system',
            'version': '1.0.0'
        }
    }


def validate_signal_data(signal_data: Dict[str, Any]) -> bool:
    """
    Validate signal data structure.
    
    Args:
        signal_data: Signal data to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        required_fields = ['integration_id', 'action', 'timestamp']
        
        for field in required_fields:
            if field not in signal_data:
                return False
        
        return True
    except Exception:
        return False


def enrich_signal_data(signal_data: Dict[str, Any], 
                    additional_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich signal data with additional information.
    
    Args:
        signal_data: Original signal data
        additional_data: Additional data to add
        
    Returns:
        Enriched signal data
    """
    try:
        enriched_data = signal_data.copy()
        enriched_data.update(additional_data)
        enriched_data['enriched_at'] = timezone.now().isoformat()
        
        return enriched_data
    except Exception:
        return signal_data


def create_error_context(integration_id: str, error: Exception, 
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create standardized error context for signals.
    
    Args:
        integration_id: Integration identifier
        error: Error that occurred
        context: Additional context
        
    Returns:
        Error context dictionary
    """
    return {
        'integration_id': integration_id,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'error_traceback': getattr(error, '__traceback__', None),
        'context': context or {},
        'timestamp': timezone.now().isoformat(),
        'severity': 'error'
    }


def create_performance_context(integration_id: str, metric_name: str, 
                           metric_value: Any, unit: str = None) -> Dict[str, Any]:
    """
    Create standardized performance context for signals.
    
    Args:
        integration_id: Integration identifier
        metric_name: Name of the metric
        metric_value: Value of the metric
        unit: Unit of measurement
        
    Returns:
        Performance context dictionary
    """
    return {
        'integration_id': integration_id,
        'metric_name': metric_name,
        'metric_value': metric_value,
        'unit': unit,
        'timestamp': timezone.now().isoformat(),
        'context': {
            'source': 'integration_system',
            'metric_type': 'performance'
        }
    }
