"""
Test fixtures for Telemetry Observability.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from ..models.metric_event import MetricEvent
from ..models.log_entry import LogEntry
from ..models.trace_span import TraceSpan
from ..models.alert import Alert
from ..models.health_status import HealthStatus


@pytest.fixture
def sample_metric():
    """
    Create a sample metric for testing.
    
    Returns:
        MetricEvent instance
    """
    return MetricEvent.objects.create(
        name='sample-metric',
        metric_type='counter',
        value=1.0,
        unit='count',
        labels={'key1': 'value1'},
        source='test',
        service='test-service',
        environment='production'
    )


@pytest.fixture
def sample_gauge_metric():
    """
    Create a sample gauge metric for testing.
    
    Returns:
        MetricEvent instance
    """
    return MetricEvent.objects.create(
        name='sample-gauge',
        metric_type='gauge',
        value=123.45,
        unit='ms',
        labels={'operation': 'test'},
        source='test',
        service='test-service',
        environment='production'
    )


@pytest.fixture
def sample_log():
    """
    Create a sample log entry for testing.
    
    Returns:
        LogEntry instance
    """
    return LogEntry.objects.create(
        level='info',
        message='Sample log message',
        logger_name='sample.logger',
        source='test',
        service='test-service',
        environment='production',
        context={'key': 'value'},
        tags=['tag1', 'tag2']
    )


@pytest.fixture
def sample_error_log():
    """
    Create a sample error log for testing.
    
    Returns:
        LogEntry instance
    """
    return LogEntry.objects.create(
        level='error',
        message='Sample error message',
        logger_name='sample.logger',
        source='test',
        service='test-service',
        environment='production',
        stack_trace='Sample stack trace'
    )


@pytest.fixture
def sample_trace():
    """
    Create a sample trace span for testing.
    
    Returns:
        TraceSpan instance
    """
    return TraceSpan.objects.create(
        trace_id='sample-trace-id',
        span_id='sample-span-id',
        operation_name='sample-operation',
        service='test-service',
        start_time=timezone.now(),
        status='success',
        tags={'key': 'value'},
        logs=[{'message': 'Sample log'}]
    )


@pytest.fixture
def sample_error_trace():
    """
    Create a sample error trace for testing.
    
    Returns:
        TraceSpan instance
    """
    return TraceSpan.objects.create(
        trace_id='sample-error-trace-id',
        span_id='sample-error-span-id',
        operation_name='error-operation',
        service='test-service',
        start_time=timezone.now(),
        end_time=timezone.now(),
        duration_ms=5000.0,
        status='error',
        logs=[{'error': 'Sample error'}]
    )


@pytest.fixture
def sample_alert():
    """
    Create a sample alert for testing.
    
    Returns:
        Alert instance
    """
    return Alert.objects.create(
        name='sample-alert',
        alert_type='metric',
        severity='warning',
        status='open',
        message='Sample alert message',
        condition={'metric_name': 'test', 'threshold': 100},
        source='test',
        service='test-service',
        environment='production',
        metadata={'key': 'value'}
    )


@pytest.fixture
def sample_critical_alert():
    """
    Create a sample critical alert for testing.
    
    Returns:
        Alert instance
    """
    return Alert.objects.create(
        name='sample-critical-alert',
        alert_type='metric',
        severity='critical',
        status='open',
        message='Sample critical alert message',
        condition={'metric_name': 'test', 'threshold': 100},
        source='test',
        service='test-service',
        environment='production'
    )


@pytest.fixture
def sample_health():
    """
    Create a sample health status for testing.
    
    Returns:
        HealthStatus instance
    """
    return HealthStatus.objects.create(
        service_name='sample-service',
        status='healthy',
        health_score=100,
        uptime=99.99,
        response_time_ms=45.67,
        error_rate=0.01,
        environment='production',
        metadata={'key': 'value'}
    )


@pytest.fixture
def sample_unhealthy_health():
    """
    Create a sample unhealthy health status for testing.
    
    Returns:
        HealthStatus instance
    """
    return HealthStatus.objects.create(
        service_name='unhealthy-service',
        status='unhealthy',
        health_score=0,
        uptime=95.0,
        response_time_ms=500.0,
        error_rate=10.0,
        environment='production'
    )
