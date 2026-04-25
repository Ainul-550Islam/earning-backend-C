"""
Cap-specific Signals for Offer Routing System

This module contains signals specifically related to cap management,
including cap limit events, cap resets, and cap violations.
"""

import logging
from typing import Dict, Any, Optional
from django.dispatch import Signal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# Cap Management Signals

# Fired when a cap limit is reached
cap_limit_reached = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'current_count',
        'max_count',
        'user_id',
        'offer_id',
        'timestamp',
        'context'
    ]
)

# Fired when a cap is reset
cap_reset = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'previous_count',
        'reset_reason',
        'reset_by',
        'timestamp'
    ]
)

# Fired when a cap is created or updated
cap_updated = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'old_max_count',
        'new_max_count',
        'updated_by',
        'timestamp',
        'changes'
    ]
)

# Fired when a cap violation is detected
cap_violation_detected = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'violation_type',
        'attempted_count',
        'max_count',
        'user_id',
        'offer_id',
        'timestamp',
        'context',
        'severity'
    ]
)

# Fired when caps are automatically adjusted
cap_auto_adjusted = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'old_value',
        'new_value',
        'adjustment_reason',
        'adjustment_type',
        'timestamp',
        'auto_adjustment_config'
    ]
)

# Fired when cap performance is analyzed
cap_performance_analyzed = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'performance_metrics',
        'analysis_period',
        'insights',
        'recommendations',
        'timestamp'
    ]
)

# Fired when cap warning thresholds are crossed
cap_warning_threshold_crossed = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'current_count',
        'max_count',
        'warning_level',
        'threshold_percentage',
        'timestamp',
        'context'
    ]
)

# Fired when cap emergency actions are triggered
cap_emergency_triggered = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'emergency_type',
        'trigger_reason',
        'actions_taken',
        'timestamp',
        'context'
    ]
)

# Fired when cap analytics are generated
cap_analytics_generated = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'analytics_data',
        'period_start',
        'period_end',
        'generated_by',
        'timestamp'
    ]
)

# Fired when cap dependencies are resolved
cap_dependency_resolved = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'dependency_type',
        'dependency_id',
        'resolution_result',
        'timestamp'
    ]
)

# Fired when cap health check is performed
cap_health_check_completed = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'health_status',
        'issues_found',
        'recommendations',
        'check_timestamp'
    ]
)


# Cap Configuration Signals

# Fired when cap configuration is validated
cap_config_validated = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'validation_result',
        'validation_errors',
        'validation_warnings',
        'timestamp'
    ]
)

# Fired when cap configuration is imported/exported
cap_config_imported = Signal(
    providing_args=[
        'import_source',
        'import_count',
        'import_results',
        'import_timestamp'
    ]
)

cap_config_exported = Signal(
    providing_args=[
        'export_destination',
        'export_count',
        'export_results',
        'export_timestamp'
    ]
)


# Cap Monitoring Signals

# Fired when cap monitoring starts/stops
cap_monitoring_started = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'monitoring_config',
        'start_timestamp'
    ]
)

cap_monitoring_stopped = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'stop_reason',
        'monitoring_results',
        'stop_timestamp'
    ]
)

# Fired when cap alerts are generated
cap_alert_generated = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'alert_type',
        'alert_message',
        'alert_severity',
        'alert_data',
        'timestamp'
    ]
)

# Fired when cap reports are generated
cap_report_generated = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'report_type',
        'report_data',
        'report_period',
        'generated_by',
        'timestamp'
    ]
)


# Cap Integration Signals

# Fired when cap integrates with external systems
cap_external_sync_completed = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'external_system',
        'sync_result',
        'sync_data',
        'timestamp'
    ]
)

# Fired when cap webhook is called
cap_webhook_called = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'webhook_url',
        'webhook_data',
        'webhook_response',
        'timestamp'
    ]
)

# Fired when cap API is accessed
cap_api_access = Signal(
    providing_args=[
        'cap_type',
        'cap_id',
        'api_endpoint',
        'access_type',
        'user_id',
        'access_data',
        'timestamp'
    ]
)


# Signal Utility Functions

def send_cap_limit_reached(cap_type: str, cap_id: int, current_count: int, max_count: int, 
                           user_id: Optional[int] = None, offer_id: Optional[int] = None, 
                           context: Optional[Dict[str, Any]] = None):
    """Send cap limit reached signal."""
    try:
        cap_limit_reached.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            current_count=current_count,
            max_count=max_count,
            user_id=user_id,
            offer_id=offer_id,
            timestamp=timezone.now(),
            context=context or {}
        )
        logger.info(f"Cap limit reached signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_limit_reached signal: {str(e)}")


def send_cap_reset(cap_type: str, cap_id: int, previous_count: int, reset_reason: str, 
                   reset_by: Optional[int] = None):
    """Send cap reset signal."""
    try:
        cap_reset.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            previous_count=previous_count,
            reset_reason=reset_reason,
            reset_by=reset_by,
            timestamp=timezone.now()
        )
        logger.info(f"Cap reset signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_reset signal: {str(e)}")


def send_cap_violation_detected(cap_type: str, cap_id: int, violation_type: str, 
                                attempted_count: int, max_count: int, user_id: Optional[int] = None, 
                                offer_id: Optional[int] = None, context: Optional[Dict[str, Any]] = None, 
                                severity: str = 'medium'):
    """Send cap violation detected signal."""
    try:
        cap_violation_detected.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            violation_type=violation_type,
            attempted_count=attempted_count,
            max_count=max_count,
            user_id=user_id,
            offer_id=offer_id,
            timestamp=timezone.now(),
            context=context or {},
            severity=severity
        )
        logger.info(f"Cap violation detected signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_violation_detected signal: {str(e)}")


def send_cap_warning_threshold_crossed(cap_type: str, cap_id: int, current_count: int, 
                                      max_count: int, warning_level: str, threshold_percentage: float, 
                                      context: Optional[Dict[str, Any]] = None):
    """Send cap warning threshold crossed signal."""
    try:
        cap_warning_threshold_crossed.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            current_count=current_count,
            max_count=max_count,
            warning_level=warning_level,
            threshold_percentage=threshold_percentage,
            timestamp=timezone.now(),
            context=context or {}
        )
        logger.info(f"Cap warning threshold crossed signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_warning_threshold_crossed signal: {str(e)}")


def send_cap_emergency_triggered(cap_type: str, cap_id: int, emergency_type: str, 
                                 trigger_reason: str, actions_taken: list, 
                                 context: Optional[Dict[str, Any]] = None):
    """Send cap emergency triggered signal."""
    try:
        cap_emergency_triggered.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            emergency_type=emergency_type,
            trigger_reason=trigger_reason,
            actions_taken=actions_taken,
            timestamp=timezone.now(),
            context=context or {}
        )
        logger.info(f"Cap emergency triggered signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_emergency_triggered signal: {str(e)}")


def send_cap_alert_generated(cap_type: str, cap_id: int, alert_type: str, 
                             alert_message: str, alert_severity: str, 
                             alert_data: Optional[Dict[str, Any]] = None):
    """Send cap alert generated signal."""
    try:
        cap_alert_generated.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            alert_type=alert_type,
            alert_message=alert_message,
            alert_severity=alert_severity,
            alert_data=alert_data or {},
            timestamp=timezone.now()
        )
        logger.info(f"Cap alert generated signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_alert_generated signal: {str(e)}")


def send_cap_performance_analyzed(cap_type: str, cap_id: int, performance_metrics: Dict[str, Any], 
                                  analysis_period: str, insights: list, recommendations: list):
    """Send cap performance analyzed signal."""
    try:
        cap_performance_analyzed.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            performance_metrics=performance_metrics,
            analysis_period=analysis_period,
            insights=insights,
            recommendations=recommendations,
            timestamp=timezone.now()
        )
        logger.info(f"Cap performance analyzed signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_performance_analyzed signal: {str(e)}")


def send_cap_health_check_completed(cap_type: str, cap_id: int, health_status: str, 
                                     issues_found: list, recommendations: list):
    """Send cap health check completed signal."""
    try:
        cap_health_check_completed.send(
            sender=None,
            cap_type=cap_type,
            cap_id=cap_id,
            health_status=health_status,
            issues_found=issues_found,
            recommendations=recommendations,
            check_timestamp=timezone.now()
        )
        logger.info(f"Cap health check completed signal sent: {cap_type} cap {cap_id}")
    except Exception as e:
        logger.error(f"Error sending cap_health_check_completed signal: {str(e)}")


# Signal Configuration

def get_cap_signal_config():
    """Get cap signal configuration from settings."""
    return getattr(settings, 'CAP_SIGNAL_CONFIG', {
        'enabled_signals': [
            'cap_limit_reached',
            'cap_reset',
            'cap_violation_detected',
            'cap_warning_threshold_crossed',
            'cap_emergency_triggered',
            'cap_alert_generated',
            'cap_performance_analyzed',
            'cap_health_check_completed'
        ],
        'async_processing': True,
        'retry_attempts': 3,
        'retry_delay': 1.0,
        'log_signals': True,
        'monitor_signal_performance': True
    })


def is_signal_enabled(signal_name: str) -> bool:
    """Check if a signal is enabled in configuration."""
    config = get_cap_signal_config()
    return signal_name in config.get('enabled_signals', [])


# Signal Performance Monitoring

def monitor_signal_performance(signal_name: str, execution_time: float, success: bool):
    """Monitor signal performance."""
    if not get_cap_signal_config().get('monitor_signal_performance', False):
        return
    
    try:
        from django.core.cache import cache
        
        cache_key = f"signal_perf:{signal_name}"
        perf_data = cache.get(cache_key, {
            'total_calls': 0,
            'total_time': 0.0,
            'success_count': 0,
            'error_count': 0
        })
        
        perf_data['total_calls'] += 1
        perf_data['total_time'] += execution_time
        perf_data['success_count'] += 1 if success else 0
        perf_data['error_count'] += 0 if success else 1
        
        cache.set(cache_key, perf_data, timeout=3600)  # 1 hour
        
    except Exception as e:
        logger.error(f"Error monitoring signal performance for {signal_name}: {str(e)}")


def get_signal_performance_stats(signal_name: str) -> Optional[Dict[str, Any]]:
    """Get signal performance statistics."""
    try:
        from django.core.cache import cache
        
        cache_key = f"signal_perf:{signal_name}"
        perf_data = cache.get(cache_key)
        
        if not perf_data:
            return None
        
        avg_time = perf_data['total_time'] / perf_data['total_calls'] if perf_data['total_calls'] > 0 else 0
        success_rate = perf_data['success_count'] / perf_data['total_calls'] if perf_data['total_calls'] > 0 else 0
        
        return {
            'signal_name': signal_name,
            'total_calls': perf_data['total_calls'],
            'average_time': avg_time,
            'success_rate': success_rate,
            'success_count': perf_data['success_count'],
            'error_count': perf_data['error_count']
        }
        
    except Exception as e:
        logger.error(f"Error getting signal performance stats for {signal_name}: {str(e)}")
        return None


# Export all signals and utility functions
__all__ = [
    # Main signals
    'cap_limit_reached',
    'cap_reset',
    'cap_updated',
    'cap_violation_detected',
    'cap_auto_adjusted',
    'cap_performance_analyzed',
    'cap_warning_threshold_crossed',
    'cap_emergency_triggered',
    'cap_analytics_generated',
    'cap_dependency_resolved',
    'cap_health_check_completed',
    
    # Configuration signals
    'cap_config_validated',
    'cap_config_imported',
    'cap_config_exported',
    
    # Monitoring signals
    'cap_monitoring_started',
    'cap_monitoring_stopped',
    'cap_alert_generated',
    'cap_report_generated',
    
    # Integration signals
    'cap_external_sync_completed',
    'cap_webhook_called',
    'cap_api_access',
    
    # Utility functions
    'send_cap_limit_reached',
    'send_cap_reset',
    'send_cap_violation_detected',
    'send_cap_warning_threshold_crossed',
    'send_cap_emergency_triggered',
    'send_cap_alert_generated',
    'send_cap_performance_analyzed',
    'send_cap_health_check_completed',
    
    # Configuration functions
    'get_cap_signal_config',
    'is_signal_enabled',
    
    # Performance monitoring
    'monitor_signal_performance',
    'get_signal_performance_stats',
]
