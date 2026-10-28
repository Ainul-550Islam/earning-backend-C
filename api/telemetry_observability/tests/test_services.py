"""
Tests for all service classes — thin facades over logic layer.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone

from ..services.metrics_collector import MetricsCollectorService
from ..services.alert_service     import AlertService
from ..services.trace_service     import TraceService
from ..services.dashboard_service import DashboardService
from ..services.analytics_service import AnalyticsService
from ..services.telemetry_service import TelemetryService

from ..models.metric_event    import MetricEvent
from ..models.log_entry       import LogEntry
from ..models.trace_span      import TraceSpan
from ..models.alert           import Alert
from ..models.health_status   import HealthStatus
from ..models.dashboard_widget import DashboardWidget


# ── MetricsCollectorService ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestMetricsCollectorService:
    def setup_method(self):
        self.service = MetricsCollectorService()

    def test_collect_metric_creates_record(self):
        m = self.service.collect_metric({
            'name': 'cpu', 'metric_type': 'gauge', 'value': 80.0,
        })
        assert isinstance(m, MetricEvent)
        assert MetricEvent.objects.filter(name='cpu').exists()

    def test_batch_collect_metrics(self):
        metrics = self.service.batch_collect_metrics([
            {'name': 'm1', 'metric_type': 'counter', 'value': 1.0},
            {'name': 'm2', 'metric_type': 'gauge',   'value': 2.0},
        ])
        assert len(metrics) == 2

    def test_get_metrics_all(self):
        MetricEvent.objects.create(name='x', metric_type='counter', value=1.0)
        result = self.service.get_metrics(limit=100)
        assert len(result) >= 1

    def test_get_metrics_filtered(self):
        MetricEvent.objects.create(name='filtered_m', metric_type='gauge', value=1.0)
        result = self.service.get_metrics(name='filtered_m', limit=10)
        assert all(m.name == 'filtered_m' for m in result)

    def test_get_metric_statistics(self):
        MetricEvent.objects.create(name='stat_m', metric_type='gauge', value=10.0)
        MetricEvent.objects.create(name='stat_m', metric_type='gauge', value=20.0)
        stats = self.service.get_metric_statistics('stat_m', hours=24)
        assert stats['count'] == 2
        assert stats['avg']   == 15.0

    def test_get_statistics_empty(self):
        stats = self.service.get_metric_statistics('nonexistent', hours=24)
        assert stats['count'] == 0


# ── AlertService ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAlertService:
    def setup_method(self):
        self.service = AlertService()

    def test_create_alert(self):
        alert = self.service.create_alert({
            'name': 'Test Alert', 'alert_type': 'metric',
            'severity': 'warning', 'message': 'Test',
        })
        assert isinstance(alert, Alert)
        assert Alert.objects.filter(name='Test Alert').exists()

    def test_acknowledge_alert(self):
        a = Alert.objects.create(
            name='Ack', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        result = self.service.acknowledge_alert(a.id, 'ops')
        assert result is True
        a.refresh_from_db()
        assert a.status == 'acknowledged'

    def test_resolve_alert(self):
        a = Alert.objects.create(
            name='Res', alert_type='metric', severity='info',
            status='open', message='t', service='svc',
        )
        result = self.service.resolve_alert(a.id)
        assert result is True
        a.refresh_from_db()
        assert a.status == 'resolved'

    def test_get_open_alerts(self):
        Alert.objects.create(name='open1', alert_type='metric', severity='warning',
                              status='open', message='t', service='svc')
        result = self.service.get_open_alerts()
        assert all(a.status == 'open' for a in result)

    def test_get_critical_alerts(self):
        Alert.objects.create(name='crit1', alert_type='metric', severity='critical',
                              status='open', message='t', service='svc')
        result = self.service.get_critical_alerts()
        assert all(a.severity == 'critical' for a in result)

    def test_get_alert_statistics(self):
        Alert.objects.create(name='s1', alert_type='metric', severity='critical',
                              status='open', message='t', service='svc')
        stats = self.service.get_alert_statistics(hours=24)
        assert 'total_alerts' in stats
        assert stats['total_alerts'] >= 1

    def test_batch_create_alerts(self):
        alerts = self.service.batch_create_alerts([
            {'name': 'B1', 'alert_type': 'metric', 'severity': 'info',     'message': 'm'},
            {'name': 'B2', 'alert_type': 'log',    'severity': 'critical', 'message': 'm'},
        ])
        assert len(alerts) == 2


# ── TraceService ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTraceService:
    def setup_method(self):
        self.service = TraceService()

    def test_start_trace(self):
        span = self.service.start_trace({'operation_name': 'GET /api', 'service': 'api'})
        assert isinstance(span, TraceSpan)
        assert span.operation_name == 'GET /api'

    def test_finish_trace(self):
        span   = self.service.start_trace({'operation_name': 'op', 'service': 'svc'})
        result = self.service.finish_trace(span.span_id, {'status': 'success'})
        assert result is True
        span.refresh_from_db()
        assert span.end_time    is not None
        assert span.duration_ms is not None

    def test_get_trace(self):
        self.service.start_trace({'operation_name': 'op1', 'trace_id': 'trace-xyz'})
        self.service.start_trace({'operation_name': 'op2', 'trace_id': 'trace-xyz'})
        spans = self.service.get_trace('trace-xyz')
        assert len(spans) == 2

    def test_get_slow_traces(self):
        span = self.service.start_trace({'operation_name': 'slow-op', 'service': 'svc'})
        TraceSpan.objects.filter(pk=span.pk).update(duration_ms=10000)
        result = self.service.get_slow_traces(threshold_ms=5000, hours=24)
        assert any(s.pk == span.pk for s in result)

    def test_get_trace_statistics(self):
        self.service.start_trace({'operation_name': 'op', 'service': 'svc'})
        stats = self.service.get_trace_statistics(hours=24)
        assert isinstance(stats, dict)


# ── DashboardService ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardService:
    def setup_method(self):
        self.service = DashboardService()

    def test_create_widget(self):
        w = self.service.create_widget({
            'name': 'My Widget', 'widget_type': 'gauge', 'data_source': 'metric',
        })
        assert isinstance(w, DashboardWidget)

    def test_get_widget(self):
        w = DashboardWidget.objects.create(
            name='W', widget_type='gauge', data_source='metric',
        )
        result = self.service.get_widget(w.id)
        assert result.id == w.id

    def test_get_nonexistent_widget(self):
        assert self.service.get_widget(99999) is None

    def test_update_widget(self):
        w = DashboardWidget.objects.create(
            name='Old', widget_type='gauge', data_source='metric',
        )
        result = self.service.update_widget(w.id, {'name': 'New'})
        assert result is True
        w.refresh_from_db()
        assert w.name == 'New'

    def test_delete_widget(self):
        w      = DashboardWidget.objects.create(name='Del', widget_type='gauge', data_source='metric')
        result = self.service.delete_widget(w.id)
        assert result is True
        assert not DashboardWidget.objects.filter(id=w.id).exists()

    def test_get_widget_data_metric(self):
        w    = DashboardWidget.objects.create(
            name='W', widget_type='line_chart', data_source='metric',
            query={'metric_name': 'cpu'},
        )
        data = self.service.get_widget_data(w, hours=24)
        assert data['data_source'] == 'metric'
        assert 'data' in data

    def test_get_widget_data_log(self):
        w    = DashboardWidget.objects.create(
            name='W', widget_type='log_view', data_source='log',
        )
        data = self.service.get_widget_data(w, hours=24)
        assert data['data_source'] == 'log'

    def test_get_widget_data_alert(self):
        w    = DashboardWidget.objects.create(
            name='W', widget_type='alert_list', data_source='alert',
        )
        data = self.service.get_widget_data(w, hours=24)
        assert data['data_source'] == 'alert'

    def test_get_widget_data_health(self):
        w    = DashboardWidget.objects.create(
            name='W', widget_type='metric_card', data_source='health',
        )
        data = self.service.get_widget_data(w, hours=24)
        assert data['data_source'] == 'health'


# ── AnalyticsService ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAnalyticsService:
    def setup_method(self):
        self.service = AnalyticsService()

    def test_get_metric_analytics_empty(self):
        data = self.service.get_metric_analytics('nonexistent', hours=24)
        assert data['count'] == 0
        assert data['avg']   == 0.0

    def test_get_metric_analytics_with_data(self):
        MetricEvent.objects.create(name='analytics_m', metric_type='gauge', value=10.0)
        MetricEvent.objects.create(name='analytics_m', metric_type='gauge', value=20.0)
        MetricEvent.objects.create(name='analytics_m', metric_type='gauge', value=30.0)
        data = self.service.get_metric_analytics('analytics_m', hours=24)
        assert data['count'] == 3
        assert data['avg']   == 20.0
        assert data['min']   == 10.0
        assert data['max']   == 30.0

    def test_get_log_analytics(self):
        LogEntry.objects.create(level='info',  message='ok',  service='svc')
        LogEntry.objects.create(level='error', message='err', service='svc')
        data = self.service.get_log_analytics(hours=24)
        assert 'total_logs'   in data
        assert 'level_counts' in data
        assert 'error_rate'   in data

    def test_get_trace_analytics(self):
        TraceSpan.objects.create(
            trace_id='t', span_id='s1', operation_name='op',
            service='svc', start_time=timezone.now(),
        )
        data = self.service.get_trace_analytics(hours=24)
        assert 'total_traces'  in data
        assert 'status_counts' in data

    def test_get_alert_analytics(self):
        Alert.objects.create(name='a', alert_type='metric', severity='critical',
                              status='open', message='t', service='svc')
        data = self.service.get_alert_analytics(hours=24)
        assert 'total_alerts'    in data
        assert 'severity_counts' in data

    def test_get_health_analytics(self):
        HealthStatus.objects.create(service_name='h1', status='healthy',   health_score=100)
        HealthStatus.objects.create(service_name='h2', status='unhealthy', health_score=0)
        data = self.service.get_health_analytics()
        assert 'total_services'   in data
        assert 'avg_health_score' in data

    def test_get_service_analytics(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='my-svc')
        LogEntry.objects.create(level='info', message='ok', service='my-svc')
        data = self.service.get_service_analytics('my-svc', hours=24)
        assert data['service_name'] == 'my-svc'
        assert data['metric_count'] >= 1
        assert data['log_count']    >= 1


# ── TelemetryService ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTelemetryService:
    def setup_method(self):
        self.service = TelemetryService()

    def test_get_overview_returns_dict(self):
        data = self.service.get_overview(hours=24)
        assert isinstance(data, dict)

    def test_get_overview_has_all_domains(self):
        data = self.service.get_overview(hours=24)
        for domain in ['metrics', 'logs', 'traces', 'alerts', 'health']:
            assert domain in data, f"Missing domain: {domain}"

    def test_get_overview_metrics_keys(self):
        data = self.service.get_overview(hours=24)
        assert 'total'   in data['metrics']
        assert 'by_type' in data['metrics']

    def test_get_overview_logs_has_error_count(self):
        LogEntry.objects.create(level='error', message='err', service='svc')
        data = self.service.get_overview(hours=24)
        assert 'errors' in data['logs']
        assert data['logs']['errors'] >= 1

    def test_get_overview_alerts_has_open_count(self):
        Alert.objects.create(name='o1', alert_type='metric', severity='warning',
                              status='open', message='t', service='svc')
        data = self.service.get_overview(hours=24)
        assert 'open' in data['alerts']
        assert data['alerts']['open'] >= 1

    def test_get_service_overview(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='svc-x')
        data = self.service.get_service_overview('svc-x', hours=24)
        assert data['service_name']   == 'svc-x'
        assert data['metrics_count']  >= 1

    def test_get_environment_overview(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, environment='staging')
        data = self.service.get_environment_overview('staging', hours=24)
        assert data['environment']   == 'staging'
        assert data['metrics_count'] >= 1

    def test_search_telemetry_finds_logs(self):
        LogEntry.objects.create(level='info', message='unique search keyword abc', service='svc')
        data = self.service.search_telemetry('unique search keyword abc', hours=24)
        assert len(data['logs']) >= 1

    def test_search_telemetry_finds_alerts(self):
        Alert.objects.create(name='search-unique-alert-xyz', alert_type='metric',
                              severity='warning', status='open', message='t', service='svc')
        data = self.service.search_telemetry('search-unique-alert-xyz', hours=24)
        assert len(data['alerts']) >= 1

    def test_search_telemetry_empty(self):
        data = self.service.search_telemetry('xyzzy_no_match_zzz', hours=24)
        assert data['logs']   == []
        assert data['alerts'] == []
