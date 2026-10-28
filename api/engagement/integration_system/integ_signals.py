# engagement/integration_system/integ_signals.py
"""
Integration system signals.
Provides Django signals for integration events and communication.
"""
from django.dispatch import Signal, receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Integration lifecycle signals
integration_registered = Signal()
integration_unregistered = Signal()
integration_activated = Signal()
integration_deactivated = Signal()
integration_error = Signal()

# Execution signals
integration_execution_started = Signal()
integration_execution_completed = Signal()
integration_execution_failed = Signal()
integration_execution_retrying = Signal()

# Data flow signals
data_received = Signal()
data_processed = Signal()
data_transformed = Signal()
data_validated = Signal()
data_sent = Signal()

# System signals
system_started = Signal()
system_stopped = Signal()
system_error = Signal()
system_maintenance = Signal()

# Performance signals
performance_threshold_exceeded = Signal()
circuit_breaker_opened = Signal()
circuit_breaker_closed = Signal()
rate_limit_exceeded = Signal()

# Security signals
security_alert = Signal()
authentication_failed = Signal()
authorization_failed = Signal()
data_validation_failed = Signal()


# Signal receivers
@receiver(integration_registered)
def handle_integration_registered(sender, **kwargs):
    """Handle integration registration."""
    integration_id = kwargs.get('integration_id')
    integration_type = kwargs.get('integration_type')
    
    logger.info(f"Integration registered: {integration_id} ({integration_type})")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('integrations_registered', {
        'integration_id': integration_id,
        'integration_type': integration_type
    })


@receiver(integration_unregistered)
def handle_integration_unregistered(sender, **kwargs):
    """Handle integration unregistration."""
    integration_id = kwargs.get('integration_id')
    
    logger.info(f"Integration unregistered: {integration_id}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('integrations_unregistered', {
        'integration_id': integration_id
    })


@receiver(integration_execution_started)
def handle_integration_execution_started(sender, **kwargs):
    """Handle integration execution start."""
    integration_id = kwargs.get('integration_id')
    execution_id = kwargs.get('execution_id')
    data_size = kwargs.get('data_size', 0)
    
    logger.info(f"Integration execution started: {integration_id} ({execution_id})")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('executions_started', {
        'integration_id': integration_id,
        'execution_id': execution_id,
        'data_size': data_size
    })


@receiver(integration_execution_completed)
def handle_integration_execution_completed(sender, **kwargs):
    """Handle integration execution completion."""
    integration_id = kwargs.get('integration_id')
    execution_id = kwargs.get('execution_id')
    execution_time = kwargs.get('execution_time', 0)
    success = kwargs.get('success', False)
    
    logger.info(f"Integration execution completed: {integration_id} ({execution_id}) - Success: {success}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.record_execution_time(integration_id, execution_time)
    
    if success:
        performance_monitor.increment_metric('executions_completed', {
            'integration_id': integration_id,
            'execution_id': execution_id
        })
    else:
        performance_monitor.increment_metric('executions_failed', {
            'integration_id': integration_id,
            'execution_id': execution_id
        })


@receiver(integration_execution_failed)
def handle_integration_execution_failed(sender, **kwargs):
    """Handle integration execution failure."""
    integration_id = kwargs.get('integration_id')
    execution_id = kwargs.get('execution_id')
    error = kwargs.get('error')
    retry_count = kwargs.get('retry_count', 0)
    
    logger.error(f"Integration execution failed: {integration_id} ({execution_id}) - Error: {error}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('executions_failed', {
        'integration_id': integration_id,
        'execution_id': execution_id,
        'error_type': type(error).__name__,
        'retry_count': retry_count
    })
    
    # Check if circuit breaker should be triggered
    from .circuit_breaker import circuit_breaker_manager
    circuit_breaker_manager.record_failure(integration_id, error)


@receiver(data_received)
def handle_data_received(sender, **kwargs):
    """Handle data reception."""
    integration_id = kwargs.get('integration_id')
    data_type = kwargs.get('data_type')
    data_size = kwargs.get('data_size', 0)
    
    logger.info(f"Data received: {integration_id} - Type: {data_type} - Size: {data_size}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('data_received', {
        'integration_id': integration_id,
        'data_type': data_type,
        'data_size': data_size
    })


@receiver(data_processed)
def handle_data_processed(sender, **kwargs):
    """Handle data processing."""
    integration_id = kwargs.get('integration_id')
    processing_time = kwargs.get('processing_time', 0)
    records_processed = kwargs.get('records_processed', 0)
    
    logger.info(f"Data processed: {integration_id} - Time: {processing_time}s - Records: {records_processed}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.record_processing_time(integration_id, processing_time)
    performance_monitor.increment_metric('records_processed', {
        'integration_id': integration_id,
        'records_count': records_processed
    })


@receiver(circuit_breaker_opened)
def handle_circuit_breaker_opened(sender, **kwargs):
    """Handle circuit breaker opening."""
    integration_id = kwargs.get('integration_id')
    failure_count = kwargs.get('failure_count')
    
    logger.warning(f"Circuit breaker opened: {integration_id} - Failures: {failure_count}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('circuit_breaker_opened', {
        'integration_id': integration_id,
        'failure_count': failure_count
    })
    
    # Send alert
    from .notifications import notification_manager
    notification_manager.send_alert(
        title=f"Circuit Breaker Opened",
        message=f"Circuit breaker opened for integration {integration_id} after {failure_count} failures",
        priority='high'
    )


@receiver(circuit_breaker_closed)
def handle_circuit_breaker_closed(sender, **kwargs):
    """Handle circuit breaker closing."""
    integration_id = kwargs.get('integration_id')
    
    logger.info(f"Circuit breaker closed: {integration_id}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('circuit_breaker_closed', {
        'integration_id': integration_id
    })


@receiver(rate_limit_exceeded)
def handle_rate_limit_exceeded(sender, **kwargs):
    """Handle rate limit exceeded."""
    integration_id = kwargs.get('integration_id')
    limit = kwargs.get('limit')
    window = kwargs.get('window')
    
    logger.warning(f"Rate limit exceeded: {integration_id} - Limit: {limit}/{window}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('rate_limit_exceeded', {
        'integration_id': integration_id,
        'limit': limit,
        'window': window
    })


@receiver(security_alert)
def handle_security_alert(sender, **kwargs):
    """Handle security alert."""
    alert_type = kwargs.get('alert_type')
    integration_id = kwargs.get('integration_id')
    details = kwargs.get('details', {})
    
    logger.error(f"Security alert: {alert_type} - Integration: {integration_id} - Details: {details}")
    
    # Update metrics
    from .monitoring import performance_monitor
    performance_monitor.increment_metric('security_alerts', {
        'alert_type': alert_type,
        'integration_id': integration_id
    })
    
    # Send high-priority alert
    from .notifications import notification_manager
    notification_manager.send_alert(
        title=f"Security Alert: {alert_type}",
        message=f"Security alert triggered for integration {integration_id}: {details}",
        priority='critical'
    )


# Signal utilities
class SignalManager:
    """Manager for integration signals."""
    
    @staticmethod
    def send_integration_registered(integration_id, integration_type, **kwargs):
        """Send integration registered signal."""
        integration_registered.send(
            sender='integration_system',
            integration_id=integration_id,
            integration_type=integration_type,
            **kwargs
        )
    
    @staticmethod
    def send_integration_unregistered(integration_id, **kwargs):
        """Send integration unregistered signal."""
        integration_unregistered.send(
            sender='integration_system',
            integration_id=integration_id,
            **kwargs
        )
    
    @staticmethod
    def send_execution_started(integration_id, execution_id, data_size=0, **kwargs):
        """Send execution started signal."""
        integration_execution_started.send(
            sender='integration_system',
            integration_id=integration_id,
            execution_id=execution_id,
            data_size=data_size,
            **kwargs
        )
    
    @staticmethod
    def send_execution_completed(integration_id, execution_id, success=True, execution_time=0, **kwargs):
        """Send execution completed signal."""
        integration_execution_completed.send(
            sender='integration_system',
            integration_id=integration_id,
            execution_id=execution_id,
            success=success,
            execution_time=execution_time,
            **kwargs
        )
    
    @staticmethod
    def send_execution_failed(integration_id, execution_id, error, retry_count=0, **kwargs):
        """Send execution failed signal."""
        integration_execution_failed.send(
            sender='integration_system',
            integration_id=integration_id,
            execution_id=execution_id,
            error=error,
            retry_count=retry_count,
            **kwargs
        )
    
    @staticmethod
    def send_data_received(integration_id, data_type, data_size=0, **kwargs):
        """Send data received signal."""
        data_received.send(
            sender='integration_system',
            integration_id=integration_id,
            data_type=data_type,
            data_size=data_size,
            **kwargs
        )
    
    @staticmethod
    def send_data_processed(integration_id, processing_time=0, records_processed=0, **kwargs):
        """Send data processed signal."""
        data_processed.send(
            sender='integration_system',
            integration_id=integration_id,
            processing_time=processing_time,
            records_processed=records_processed,
            **kwargs
        )
    
    @staticmethod
    def send_circuit_breaker_opened(integration_id, failure_count, **kwargs):
        """Send circuit breaker opened signal."""
        circuit_breaker_opened.send(
            sender='integration_system',
            integration_id=integration_id,
            failure_count=failure_count,
            **kwargs
        )
    
    @staticmethod
    def send_circuit_breaker_closed(integration_id, **kwargs):
        """Send circuit breaker closed signal."""
        circuit_breaker_closed.send(
            sender='integration_system',
            integration_id=integration_id,
            **kwargs
        )
    
    @staticmethod
    def send_rate_limit_exceeded(integration_id, limit, window, **kwargs):
        """Send rate limit exceeded signal."""
        rate_limit_exceeded.send(
            sender='integration_system',
            integration_id=integration_id,
            limit=limit,
            window=window,
            **kwargs
        )
    
    @staticmethod
    def send_security_alert(alert_type, integration_id=None, details=None, **kwargs):
        """Send security alert signal."""
        security_alert.send(
            sender='integration_system',
            alert_type=alert_type,
            integration_id=integration_id,
            details=details or {},
            **kwargs
        )


# Global signal manager instance
signal_manager = SignalManager()
