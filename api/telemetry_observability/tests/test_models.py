"""
Tests for all 6 models — fields, managers, methods.
Covers: MetricEvent, LogEntry, TraceSpan, Alert, HealthStatus, DashboardWidget.
"""
import pytest
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models.metric_event    import MetricEvent
from ..models.log_entry       import LogEntry
from ..models.trace_span      import TraceSpan
from ..models.alert           import Alert
from ..models.health_status   import HealthStatus
from ..models.dashboard_widget import DashboardWidget


@pytest.mark.django_db
class TestMetricEventModel:
    def test_create_metric(self):
        m = MetricEvent.objects.create(name='cpu', metric_type='gauge', value=80.0)
        assert m.pk is not None
        assert m.name == 'cpu'
        assert m.metric_type == 'gauge'

    def test_str_representation(self):
        m = MetricEvent(name='cpu', metric_type='gauge', value=80.0, unit='%')
        assert 'cpu' in str(m)
        assert '80.0' in str(m)

    def test_default_environment(self):
        m = MetricEvent.objects.create(name='cpu', metric_type='gauge', value=1.0)
        assert m.environment == 'production'

    def test_manager_by_name(self):
        MetricEvent.objects.create(name='cpu_usage', metric_type='gauge',   value=80.0)
        MetricEvent.objects.create(name='mem_usage', metric_type='gauge',   value=60.0)
        result = MetricEvent.objects.by_name('cpu_usage')
        assert all(m.name == 'cpu_usage' for m in result)

    def test_manager_by_type(self):
        MetricEvent.objects.create(name='m1', metric_type='counter', value=1.0)
        MetricEvent.objects.create(name='m2', metric_type='gauge',   value=2.0)
        result = MetricEvent.objects.counters()
        assert all(m.metric_type == 'counter' for m in result)

    def test_manager_by_service(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='svc-a')
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='svc-b')
        result = MetricEvent.objects.by_service('svc-a')
        assert all(m.service == 'svc-a' for m in result)

    def test_manager_recent(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0)
        result = MetricEvent.objects.recent(hours=24)
        assert result.count() >= 1

    def test_manager_search(self):
        MetricEvent.objects.create(name='unique_metric_name', metric_type='gauge', value=1.0)
        result = MetricEvent.objects.search('unique_metric')
        assert result.count() >= 1

    def test_ordering_by_timestamp_desc(self):
        MetricEvent.objects.create(name='m1', metric_type='counter', value=1.0)
        MetricEvent.objects.create(name='m2', metric_type='counter', value=2.0)
        metrics = list(MetricEvent.objects.all()[:2])
        assert metrics[0].timestamp >= metrics[1].timestamp

    def test_labels_default_dict(self):
        m = MetricEvent.objects.create(name='m', metric_type='counter', value=1.0)
        assert m.labels == {}

    def test_json_labels_stored(self):
        m = MetricEvent.objects.create(
            name='m', metric_type='gauge', value=1.0,
            labels={'region': 'us-east-1', 'env': 'prod'},
        )
        m.refresh_from_db()
        assert m.labels['region'] == 'us-east-1'


@pytest.mark.django_db
class TestLogEntryModel:
    def test_create_log(self):
        log = LogEntry.objects.create(level='info', message='Test message', service='svc')
        assert log.pk is not None
        assert log.level == 'info'

    def test_str_representation(self):
        log = LogEntry(level='error', message='Something failed')
        assert 'ERROR' in str(log)

    def test_manager_by_level(self):
        LogEntry.objects.create(level='error',   message='err', service='svc')
        LogEntry.objects.create(level='warning', message='warn', service='svc')
        errors = LogEntry.objects.errors()
        assert all(l.level == 'error' for l in errors)

    def test_manager_errors_and_critical(self):
        LogEntry.objects.create(level='error',    message='e', service='svc')
        LogEntry.objects.create(level='critical', message='c', service='svc')
        LogEntry.objects.create(level='info',     message='i', service='svc')
        result = LogEntry.objects.errors_and_critical()
        assert all(l.level in ('error', 'critical') for l in result)

    def test_manager_search(self):
        LogEntry.objects.create(level='info', message='unique log keyword here', service='svc')
        result = LogEntry.objects.search('unique log keyword')
        assert result.count() >= 1

    def test_context_default_dict(self):
        log = LogEntry.objects.create(level='info', message='t', service='svc')
        assert log.context == {}

    def test_tags_default_list(self):
        log = LogEntry.objects.create(level='info', message='t', service='svc')
        assert log.tags == []


@pytest.mark.django_db
class TestTraceSpanModel:
    def test_create_trace_span(self):
        span = TraceSpan.objects.create(
            trace_id='t1', span_id='s1',
            operation_name='GET /api', service='api',
            start_time=timezone.now(),
        )
        assert span.pk is not None
        assert span.span_id == 's1'

    def test_str_representation(self):
        span = TraceSpan(operation_name='db.query', span_id='s1')
        assert 'db.query' in str(span)

    def test_manager_by_trace_id(self):
        TraceSpan.objects.create(trace_id='trace-abc', span_id='s1',
                                  operation_name='op', service='svc', start_time=timezone.now())
        TraceSpan.objects.create(trace_id='trace-abc', span_id='s2',
                                  operation_name='op', service='svc', start_time=timezone.now())
        result = TraceSpan.objects.by_trace_id('trace-abc')
        assert result.count() == 2

    def test_manager_errors(self):
        TraceSpan.objects.create(trace_id='t', span_id='e1', operation_name='op',
                                  service='svc', start_time=timezone.now(), status='error')
        TraceSpan.objects.create(trace_id='t', span_id='s1', operation_name='op',
                                  service='svc', start_time=timezone.now(), status='success')
        errors = TraceSpan.objects.errors()
        assert all(s.status == 'error' for s in errors)

    def test_manager_slow(self):
        TraceSpan.objects.create(trace_id='t', span_id='slow1', operation_name='op',
                                  service='svc', start_time=timezone.now(), duration_ms=10000)
        TraceSpan.objects.create(trace_id='t', span_id='fast1', operation_name='op',
                                  service='svc', start_time=timezone.now(), duration_ms=10)
        slow = TraceSpan.objects.slow(threshold_ms=5000)
        assert all(s.duration_ms >= 5000 for s in slow)

    def test_manager_in_progress(self):
        TraceSpan.objects.create(trace_id='t', span_id='ip1', operation_name='op',
                                  service='svc', start_time=timezone.now(), end_time=None)
        in_progress = TraceSpan.objects.in_progress()
        assert all(s.end_time is None for s in in_progress)

    def test_end_time_none_by_default(self):
        span = TraceSpan.objects.create(trace_id='t', span_id='new',
                                         operation_name='op', service='svc', start_time=timezone.now())
        assert span.end_time is None


@pytest.mark.django_db
class TestAlertModel:
    def test_create_alert(self):
        a = Alert.objects.create(
            name='High CPU', alert_type='metric', severity='warning',
            status='open', message='CPU is high', service='svc',
        )
        assert a.pk is not None
        assert a.status == 'open'

    def test_str_representation(self):
        a = Alert(name='Test Alert', severity='critical')
        assert 'Test Alert' in str(a)
        assert 'critical'   in str(a)

    def test_acknowledge_sets_status(self):
        a = Alert.objects.create(
            name='a', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        a.acknowledge('ops-team')
        assert a.status == 'acknowledged'
        assert a.acknowledged_by == 'ops-team'
        assert a.acknowledged_at is not None

    def test_resolve_sets_status(self):
        a = Alert.objects.create(
            name='a', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        a.resolve()
        assert a.status == 'resolved'
        assert a.resolved_at is not None

    def test_manager_open(self):
        Alert.objects.create(name='open1', alert_type='metric', severity='warning',
                              status='open', message='t', service='svc')
        Alert.objects.create(name='res1',  alert_type='metric', severity='info',
                              status='resolved', message='t', service='svc')
        open_alerts = Alert.objects.open()
        assert all(a.status == 'open' for a in open_alerts)

    def test_manager_critical(self):
        Alert.objects.create(name='crit', alert_type='metric', severity='critical',
                              status='open', message='t', service='svc')
        Alert.objects.create(name='warn', alert_type='metric', severity='warning',
                              status='open', message='t', service='svc')
        critical = Alert.objects.critical()
        assert all(a.severity == 'critical' for a in critical)

    def test_manager_by_service(self):
        Alert.objects.create(name='a1', alert_type='metric', severity='warning',
                              status='open', message='t', service='my-svc')
        result = Alert.objects.by_service('my-svc')
        assert all(a.service == 'my-svc' for a in result)


@pytest.mark.django_db
class TestHealthStatusModel:
    def test_create_health_status(self):
        h = HealthStatus.objects.create(service_name='api', status='healthy', health_score=100)
        assert h.pk is not None
        assert h.service_name == 'api'

    def test_str_without_component(self):
        h = HealthStatus(service_name='api', status='healthy')
        assert 'api' in str(h)
        assert 'healthy' in str(h)

    def test_str_with_component(self):
        h = HealthStatus(service_name='api', component_name='db', status='degraded')
        assert 'db' in str(h)

    def test_is_healthy_true(self):
        h = HealthStatus(service_name='svc', status='healthy', health_score=100)
        assert h.is_healthy() is True

    def test_is_healthy_false_low_score(self):
        h = HealthStatus(service_name='svc', status='healthy', health_score=60)
        assert h.is_healthy() is False

    def test_is_degraded_true(self):
        h = HealthStatus(service_name='svc', status='degraded', health_score=60)
        assert h.is_degraded() is True

    def test_is_unhealthy_true(self):
        h = HealthStatus(service_name='svc', status='unhealthy', health_score=10)
        assert h.is_unhealthy() is True

    def test_manager_healthy(self):
        HealthStatus.objects.create(service_name='h1', status='healthy',   health_score=100)
        HealthStatus.objects.create(service_name='h2', status='unhealthy', health_score=0)
        result = HealthStatus.objects.healthy()
        assert all(h.status == 'healthy' for h in result)

    def test_manager_unhealthy(self):
        HealthStatus.objects.create(service_name='u1', status='unhealthy', health_score=0,   component_name='c1')
        HealthStatus.objects.create(service_name='u2', status='degraded',  health_score=50,  component_name='c2')
        HealthStatus.objects.create(service_name='u3', status='healthy',   health_score=100, component_name='c3')
        result = HealthStatus.objects.unhealthy()
        assert all(h.status in ('degraded', 'unhealthy') for h in result)

    def test_manager_above_score(self):
        HealthStatus.objects.create(service_name='s1', status='healthy', health_score=90, component_name='c1')
        HealthStatus.objects.create(service_name='s2', status='healthy', health_score=40, component_name='c2')
        result = HealthStatus.objects.above_score(80)
        assert all(h.health_score >= 80 for h in result)

    def test_unique_together_constraint(self):
        from django.db import IntegrityError
        HealthStatus.objects.create(
            service_name='svc', component_name='comp', environment='production',
            status='healthy', health_score=100,
        )
        with pytest.raises(IntegrityError):
            HealthStatus.objects.create(
                service_name='svc', component_name='comp', environment='production',
                status='degraded', health_score=50,
            )


@pytest.mark.django_db
class TestDashboardWidgetModel:
    def test_create_widget(self):
        w = DashboardWidget.objects.create(
            name='CPU Chart', widget_type='line_chart', data_source='metric',
        )
        assert w.pk is not None
        assert w.name == 'CPU Chart'

    def test_str_representation(self):
        w = DashboardWidget(name='My Widget')
        assert 'My Widget' in str(w)

    def test_default_values(self):
        w = DashboardWidget.objects.create(
            name='Widget', widget_type='gauge', data_source='metric',
        )
        assert w.position_x      == 0
        assert w.position_y      == 0
        assert w.width           == 4
        assert w.height          == 4
        assert w.refresh_interval == 60
        assert w.is_active       is True

    def test_manager_active(self):
        DashboardWidget.objects.create(name='A', widget_type='gauge', data_source='metric', is_active=True)
        DashboardWidget.objects.create(name='I', widget_type='gauge', data_source='metric', is_active=False)
        active = DashboardWidget.objects.active()
        assert all(w.is_active for w in active)

    def test_manager_inactive(self):
        DashboardWidget.objects.create(name='A', widget_type='gauge', data_source='metric', is_active=True)
        DashboardWidget.objects.create(name='I', widget_type='gauge', data_source='metric', is_active=False)
        inactive = DashboardWidget.objects.inactive()
        assert all(not w.is_active for w in inactive)

    def test_manager_by_type(self):
        DashboardWidget.objects.create(name='LC', widget_type='line_chart', data_source='metric')
        DashboardWidget.objects.create(name='G',  widget_type='gauge',      data_source='metric')
        result = DashboardWidget.objects.by_type('line_chart')
        assert all(w.widget_type == 'line_chart' for w in result)

    def test_manager_by_data_source(self):
        DashboardWidget.objects.create(name='M', widget_type='gauge', data_source='metric')
        DashboardWidget.objects.create(name='L', widget_type='table', data_source='log')
        result = DashboardWidget.objects.by_data_source('metric')
        assert all(w.data_source == 'metric' for w in result)

    def test_manager_search(self):
        DashboardWidget.objects.create(name='unique_dashboard_widget_name', widget_type='gauge', data_source='metric')
        result = DashboardWidget.objects.search('unique_dashboard')
        assert result.count() >= 1

    def test_ordering_by_position(self):
        DashboardWidget.objects.create(name='Row2', widget_type='gauge', data_source='metric', position_y=2, position_x=0)
        DashboardWidget.objects.create(name='Row1', widget_type='gauge', data_source='metric', position_y=1, position_x=0)
        widgets = list(DashboardWidget.objects.all()[:2])
        assert widgets[0].position_y <= widgets[1].position_y

    def test_query_default_dict(self):
        w = DashboardWidget.objects.create(name='W', widget_type='gauge', data_source='metric')
        assert w.query == {}

    def test_config_default_dict(self):
        w = DashboardWidget.objects.create(name='W', widget_type='gauge', data_source='metric')
        assert w.config == {}
