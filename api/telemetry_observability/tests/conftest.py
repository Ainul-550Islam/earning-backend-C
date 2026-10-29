"""
Pytest configuration and shared fixtures for Telemetry Observability.
All fixtures available to every test file automatically.
"""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
User = get_user_model()


# ── API Clients ───────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def authenticated_api_client(db):
    """
    Force-authenticated DRF API client.
    Use for any endpoint requiring IsAuthenticated.
    """
    user, _ = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com', 'is_active': True},
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_api_client(db):
    """Force-authenticated admin DRF API client (staff + superuser)."""
    user, _ = User.objects.get_or_create(
        username='adminuser',
        defaults={
            'email':        'admin@example.com',
            'is_active':    True,
            'is_staff':     True,
            'is_superuser': True,
        },
    )
    user.is_staff     = True
    user.is_superuser = True
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def regular_user(db):
    """A regular (non-staff, non-superuser) active User."""
    user, _ = User.objects.get_or_create(
        username='regularuser',
        defaults={'email': 'regular@example.com', 'is_active': True},
    )
    return user


@pytest.fixture
def admin_user(db):
    """A staff + superuser User."""
    user, _ = User.objects.get_or_create(
        username='adminuser2',
        defaults={
            'email':        'admin2@example.com',
            'is_active':    True,
            'is_staff':     True,
            'is_superuser': True,
        },
    )
    user.is_staff     = True
    user.is_superuser = True
    user.save()
    return user


# ── Model fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def metric(db):
    """A single saved MetricEvent instance."""
    from ..models.metric_event import MetricEvent
    return MetricEvent.objects.create(
        name='cpu_usage', metric_type='gauge', value=80.0,
        unit='%', source='test', service='test-service',
        environment='production', labels={'region': 'us-east-1'},
    )


@pytest.fixture
def counter_metric(db):
    """A counter-type MetricEvent."""
    from ..models.metric_event import MetricEvent
    return MetricEvent.objects.create(
        name='request_count', metric_type='counter', value=1.0,
        source='test', service='api', environment='production',
    )


@pytest.fixture
def metric_batch(db):
    """A list of 5 MetricEvent instances."""
    from ..models.metric_event import MetricEvent
    names = ['cpu', 'mem', 'disk', 'net_in', 'net_out']
    return [
        MetricEvent.objects.create(
            name=n, metric_type='gauge', value=float(i * 10),
            service='test-svc', environment='production',
        )
        for i, n in enumerate(names, 1)
    ]


@pytest.fixture
def log_entry(db):
    """A single saved LogEntry instance."""
    from ..models.log_entry import LogEntry
    return LogEntry.objects.create(
        level='info', message='Test log message',
        logger_name='test.logger', source='test',
        service='test-service', environment='production',
        context={'request_id': 'req-123'},
        tags=['test'],
    )


@pytest.fixture
def error_log(db):
    """An error-level LogEntry."""
    from ..models.log_entry import LogEntry
    return LogEntry.objects.create(
        level='error', message='Something went wrong',
        logger_name='test.logger', source='test',
        service='test-service', environment='production',
        stack_trace='Traceback (most recent call last):\n  ...',
    )


@pytest.fixture
def trace_span(db):
    """A single saved TraceSpan instance (in progress)."""
    from ..models.trace_span import TraceSpan
    return TraceSpan.objects.create(
        trace_id='trace-test-id-001', span_id='span-test-id-001',
        operation_name='GET /api/test', service='test-service',
        start_time=timezone.now(), status='success',
        tags={'http.method': 'GET'},
    )


@pytest.fixture
def finished_trace(db):
    """A completed TraceSpan with duration."""
    from ..models.trace_span import TraceSpan
    start = timezone.now()
    span  = TraceSpan.objects.create(
        trace_id='trace-finished-001', span_id='span-finished-001',
        operation_name='db.query', service='test-service',
        start_time=start, status='success',
    )
    from datetime import timedelta
    span.end_time    = start + timedelta(milliseconds=250)
    span.duration_ms = 250.0
    span.save()
    return span


@pytest.fixture
def alert(db):
    """A single open Alert instance."""
    from ..models.alert import Alert
    return Alert.objects.create(
        name='test-alert', alert_type='metric',
        severity='warning', status='open',
        message='Test alert message', source='test',
        service='test-service', environment='production',
        condition={'threshold': 90, 'metric': 'cpu_usage'},
        metadata={'priority': 'high'},
    )


@pytest.fixture
def critical_alert(db):
    """A critical-severity open Alert."""
    from ..models.alert import Alert
    return Alert.objects.create(
        name='critical-test-alert', alert_type='health',
        severity='critical', status='open',
        message='Service is down', source='test',
        service='api-gateway', environment='production',
    )


@pytest.fixture
def resolved_alert(db):
    """A resolved Alert instance."""
    from ..models.alert import Alert
    alert = Alert.objects.create(
        name='resolved-alert', alert_type='metric',
        severity='info', status='resolved',
        message='Resolved alert', service='test-svc',
    )
    alert.resolve()
    return alert


@pytest.fixture
def health(db):
    """A healthy HealthStatus instance."""
    from ..models.health_status import HealthStatus
    return HealthStatus.objects.create(
        service_name='test-service', status='healthy',
        health_score=100, uptime=99.9, response_time_ms=50.0,
        error_rate=0.1, environment='production',
    )


@pytest.fixture
def degraded_health(db):
    """A degraded HealthStatus instance."""
    from ..models.health_status import HealthStatus
    return HealthStatus.objects.create(
        service_name='degraded-service', status='degraded',
        health_score=55, uptime=95.0, response_time_ms=800.0,
        error_rate=8.0, environment='production',
    )


@pytest.fixture
def unhealthy_health(db):
    """An unhealthy HealthStatus instance."""
    from ..models.health_status import HealthStatus
    return HealthStatus.objects.create(
        service_name='unhealthy-service', status='unhealthy',
        health_score=10, uptime=60.0, response_time_ms=5000.0,
        error_rate=45.0, environment='production',
    )


@pytest.fixture
def dashboard_widget(db):
    """A single active DashboardWidget instance."""
    from ..models.dashboard_widget import DashboardWidget
    return DashboardWidget.objects.create(
        name='CPU Usage Chart', widget_type='line_chart',
        data_source='metric', position_x=0, position_y=0,
        width=6, height=4, refresh_interval=60, is_active=True,
        query={'metric_name': 'cpu_usage', 'interval': 'hour'},
        config={'color': '#FF5733', 'show_legend': True},
    )


# ── Service fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def telemetry_service():
    from ..services.telemetry_service import TelemetryService
    return TelemetryService()


@pytest.fixture
def metrics_collector_service():
    from ..services.metrics_collector import MetricsCollectorService
    return MetricsCollectorService()


@pytest.fixture
def alert_service():
    from ..services.alert_service import AlertService
    return AlertService()


@pytest.fixture
def trace_service():
    from ..services.trace_service import TraceService
    return TraceService()


@pytest.fixture
def dashboard_service():
    from ..services.dashboard_service import DashboardService
    return DashboardService()


@pytest.fixture
def analytics_service():
    from ..services.analytics_service import AnalyticsService
    return AnalyticsService()


# ── Logic fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def metric_logic():
    from ..logic import MetricLogic
    return MetricLogic()


@pytest.fixture
def log_logic():
    from ..logic import LogLogic
    return LogLogic()


@pytest.fixture
def alert_logic():
    from ..logic import AlertLogic
    return AlertLogic()


@pytest.fixture
def trace_logic():
    from ..logic import TraceLogic
    return TraceLogic()


@pytest.fixture
def health_logic():
    from ..logic import HealthLogic
    return HealthLogic()


@pytest.fixture
def dashboard_logic():
    from ..logic import DashboardLogic
    return DashboardLogic()


# ── Composite fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def full_telemetry_dataset(db):
    """
    Creates a complete dataset across all models.
    Use for analytics and overview tests.
    """
    from ..models.metric_event    import MetricEvent
    from ..models.log_entry       import LogEntry
    from ..models.trace_span      import TraceSpan
    from ..models.alert           import Alert
    from ..models.health_status   import HealthStatus
    from ..models.dashboard_widget import DashboardWidget
    import uuid

    services = ['api', 'auth', 'payment']

    for svc in services:
        MetricEvent.objects.create(name='cpu', metric_type='gauge', value=70.0, service=svc)
        MetricEvent.objects.create(name='mem', metric_type='gauge', value=50.0, service=svc)
        LogEntry.objects.create(level='info',  message='OK',    service=svc)
        LogEntry.objects.create(level='error', message='Error', service=svc)
        TraceSpan.objects.create(
            trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()),
            operation_name='GET /api', service=svc,
            start_time=timezone.now(), status='success',
        )
        Alert.objects.create(
            name=f'{svc}-alert', alert_type='metric', severity='warning',
            status='open', message='test', service=svc,
        )
        HealthStatus.objects.create(
            service_name=svc, status='healthy', health_score=90
        )
        DashboardWidget.objects.create(
            name=f'{svc} widget', widget_type='metric_card', data_source='metric'
        )

    return {
        'services':        services,
        'metrics_count':   MetricEvent.objects.count(),
        'logs_count':      LogEntry.objects.count(),
        'traces_count':    TraceSpan.objects.count(),
        'alerts_count':    Alert.objects.count(),
        'health_count':    HealthStatus.objects.count(),
        'widgets_count':   DashboardWidget.objects.count(),
    }
