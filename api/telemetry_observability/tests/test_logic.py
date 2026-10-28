"""
Tests for logic.py — canonical business logic layer.
Every logic class tested: MetricLogic, LogLogic, AlertLogic,
TraceLogic, HealthLogic, DashboardLogic.
"""
import pytest
from django.utils import timezone

from ..logic import (
    MetricLogic, LogLogic, AlertLogic,
    TraceLogic, HealthLogic, DashboardLogic,
)
from ..models.metric_event  import MetricEvent
from ..models.log_entry     import LogEntry
from ..models.alert         import Alert
from ..models.trace_span    import TraceSpan
from ..models.health_status import HealthStatus
from ..models.dashboard_widget import DashboardWidget


# ── MetricLogic ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMetricLogic:
    def setup_method(self):
        self.logic = MetricLogic()

    def test_record_counter(self):
        m = self.logic.record_metric({
            'name': 'req_count', 'metric_type': 'counter', 'value': 1.0,
        })
        assert isinstance(m, MetricEvent)
        assert m.metric_type == 'counter'
        assert m.value == 1.0

    def test_record_gauge(self):
        m = self.logic.record_metric({
            'name': 'cpu_usage', 'metric_type': 'gauge', 'value': 75.5,
        })
        assert m.metric_type == 'gauge'
        assert m.value == 75.5

    def test_record_histogram(self):
        m = self.logic.record_metric({
            'name': 'latency', 'metric_type': 'histogram', 'value': 250.0,
        })
        assert m.metric_type == 'histogram'

    def test_record_summary(self):
        m = self.logic.record_metric({
            'name': 'response_time', 'metric_type': 'summary', 'value': 100.0,
        })
        assert m.metric_type == 'summary'

    def test_invalid_metric_type_raises(self):
        from ..exceptions import TelemetryException
        with pytest.raises(TelemetryException):
            self.logic.record_metric({
                'name': 'test', 'metric_type': 'unknown_type', 'value': 1.0,
            })

    def test_batch_record(self):
        data_list = [
            {'name': 'm1', 'metric_type': 'counter', 'value': 1.0},
            {'name': 'm2', 'metric_type': 'gauge',   'value': 2.0},
            {'name': 'm3', 'metric_type': 'counter', 'value': 3.0},
        ]
        metrics = self.logic.batch_record(data_list)
        assert len(metrics) == 3
        assert MetricEvent.objects.filter(name__in=['m1', 'm2', 'm3']).count() == 3

    def test_get_metrics_all(self):
        MetricEvent.objects.create(name='m1', metric_type='counter', value=1.0)
        MetricEvent.objects.create(name='m2', metric_type='gauge',   value=2.0)
        result = self.logic.get_metrics(limit=10)
        assert len(result) >= 2

    def test_get_metrics_filtered_by_name(self):
        MetricEvent.objects.create(name='unique_metric', metric_type='counter', value=1.0)
        result = self.logic.get_metrics(name='unique_metric', limit=10)
        assert all(m.name == 'unique_metric' for m in result)

    def test_get_metrics_filtered_by_service(self):
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='svc-a')
        MetricEvent.objects.create(name='m', metric_type='gauge', value=1.0, service='svc-b')
        result = self.logic.get_metrics(service='svc-a', limit=10)
        assert all(m.service == 'svc-a' for m in result)

    def test_get_statistics_empty(self):
        stats = self.logic.get_statistics('nonexistent_metric', hours=24)
        assert stats['count'] == 0
        assert stats['avg'] == 0.0

    def test_get_statistics_with_data(self):
        for v in [10.0, 20.0, 30.0]:
            MetricEvent.objects.create(name='stat_metric', metric_type='gauge', value=v)
        stats = self.logic.get_statistics('stat_metric', hours=24)
        assert stats['count'] == 3
        assert stats['avg'] == 20.0
        assert stats['min'] == 10.0
        assert stats['max'] == 30.0
        assert stats['sum'] == 60.0


# ── LogLogic ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogLogic:
    def setup_method(self):
        self.logic = LogLogic()

    def test_record_log(self):
        entry = self.logic.record_log({'level': 'info', 'message': 'Test'})
        assert isinstance(entry, LogEntry)
        assert entry.level == 'info'
        assert entry.message == 'Test'

    def test_record_error_log(self):
        entry = self.logic.record_log({'level': 'error', 'message': 'Error!'})
        assert entry.level == 'error'

    def test_defaults_applied(self):
        entry = self.logic.record_log({'message': 'No level'})
        assert entry.level == 'info'
        assert entry.environment == 'production'

    def test_batch_record(self):
        logs = self.logic.batch_record([
            {'level': 'info',  'message': 'Log 1'},
            {'level': 'error', 'message': 'Log 2'},
        ])
        assert len(logs) == 2

    def test_get_logs_filter_by_level(self):
        LogEntry.objects.create(level='info',  message='Info',  service='svc')
        LogEntry.objects.create(level='error', message='Error', service='svc')
        result = self.logic.get_logs(level='error', limit=10)
        assert all(l.level == 'error' for l in result)

    def test_get_logs_search(self):
        LogEntry.objects.create(level='info', message='unique keyword here', service='svc')
        LogEntry.objects.create(level='info', message='something else',      service='svc')
        result = self.logic.get_logs(search='unique keyword', limit=10)
        assert len(result) >= 1
        assert all('unique keyword' in l.message for l in result)


# ── AlertLogic ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAlertLogic:
    def setup_method(self):
        self.logic = AlertLogic()

    def test_create_alert(self):
        alert = self.logic.create_alert({
            'name': 'High CPU', 'alert_type': 'metric',
            'severity': 'warning', 'message': 'CPU is high',
        })
        assert isinstance(alert, Alert)
        assert alert.name == 'High CPU'
        assert alert.status == 'open'

    def test_batch_create(self):
        alerts = self.logic.batch_create([
            {'name': 'A1', 'alert_type': 'metric', 'severity': 'info',     'message': 'm1'},
            {'name': 'A2', 'alert_type': 'log',    'severity': 'critical', 'message': 'm2'},
        ])
        assert len(alerts) == 2
        assert Alert.objects.filter(name__in=['A1', 'A2']).count() == 2

    def test_acknowledge_alert(self):
        alert = Alert.objects.create(
            name='Ack Alert', alert_type='metric', severity='warning',
            status='open', message='test', service='svc',
        )
        result = self.logic.acknowledge(alert.id, 'ops-team')
        assert result is True
        alert.refresh_from_db()
        assert alert.status == 'acknowledged'
        assert alert.acknowledged_by == 'ops-team'

    def test_acknowledge_nonexistent_returns_false(self):
        result = self.logic.acknowledge(99999, 'user')
        assert result is False

    def test_resolve_alert(self):
        alert = Alert.objects.create(
            name='Res Alert', alert_type='metric', severity='warning',
            status='open', message='test', service='svc',
        )
        result = self.logic.resolve(alert.id)
        assert result is True
        alert.refresh_from_db()
        assert alert.status == 'resolved'
        assert alert.resolved_at is not None

    def test_resolve_nonexistent_returns_false(self):
        result = self.logic.resolve(99999)
        assert result is False

    def test_get_open_alerts(self):
        Alert.objects.create(
            name='Open1', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        Alert.objects.create(
            name='Closed', alert_type='metric', severity='info',
            status='resolved', message='t', service='svc',
        )
        open_alerts = self.logic.get_open()
        assert all(a.status == 'open' for a in open_alerts)

    def test_get_critical_alerts(self):
        Alert.objects.create(
            name='Crit', alert_type='metric', severity='critical',
            status='open', message='t', service='svc',
        )
        Alert.objects.create(
            name='Warn', alert_type='metric', severity='warning',
            status='open', message='t', service='svc',
        )
        critical = self.logic.get_critical()
        assert all(a.severity == 'critical' for a in critical)

    def test_get_statistics(self):
        Alert.objects.create(
            name='S1', alert_type='metric', severity='critical',
            status='open', message='t', service='svc',
        )
        stats = self.logic.get_statistics(hours=24)
        assert 'total_alerts' in stats
        assert stats['total_alerts'] >= 1


# ── TraceLogic ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTraceLogic:
    def setup_method(self):
        self.logic = TraceLogic()

    def test_start_span(self):
        span = self.logic.start_span({'operation_name': 'GET /api', 'service': 'api'})
        assert isinstance(span, TraceSpan)
        assert span.operation_name == 'GET /api'
        assert span.span_id is not None
        assert span.start_time is not None
        assert span.end_time is None

    def test_start_span_with_trace_id(self):
        span = self.logic.start_span({
            'operation_name': 'db.query',
            'trace_id':       'trace-123',
            'service':        'db',
        })
        assert span.trace_id == 'trace-123'

    def test_finish_span(self):
        span = self.logic.start_span({'operation_name': 'op', 'service': 'svc'})
        result = self.logic.finish_span(span.span_id, {'status': 'success'})
        assert result is True
        span.refresh_from_db()
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.status == 'success'

    def test_finish_span_with_error(self):
        span = self.logic.start_span({'operation_name': 'op', 'service': 'svc'})
        self.logic.finish_span(span.span_id, {'status': 'error'})
        span.refresh_from_db()
        assert span.status == 'error'

    def test_get_trace(self):
        self.logic.start_span({'operation_name': 'op1', 'trace_id': 'trace-abc'})
        self.logic.start_span({'operation_name': 'op2', 'trace_id': 'trace-abc'})
        spans = self.logic.get_trace('trace-abc')
        assert len(spans) == 2
        assert all(s.trace_id == 'trace-abc' for s in spans)

    def test_get_trace_empty(self):
        spans = self.logic.get_trace('nonexistent-trace')
        assert spans == []

    def test_get_slow_traces(self):
        span = self.logic.start_span({'operation_name': 'slow-op', 'service': 'svc'})
        # Manually set high duration
        TraceSpan.objects.filter(pk=span.pk).update(duration_ms=10000)
        slow = self.logic.get_slow_traces(threshold_ms=5000, hours=24)
        pks = [s.pk for s in slow]
        assert span.pk in pks

    def test_get_statistics(self):
        self.logic.start_span({'operation_name': 'op', 'service': 'svc'})
        stats = self.logic.get_statistics(hours=24)
        assert 'total_spans' in stats or 'total_traces' in stats


# ── HealthLogic ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthLogic:
    def setup_method(self):
        self.logic = HealthLogic()

    def test_upsert_creates_new(self):
        obj, created = self.logic.upsert({
            'service_name': 'new-svc', 'status': 'healthy', 'health_score': 100,
        })
        assert created is True
        assert obj.service_name == 'new-svc'
        assert obj.status == 'healthy'

    def test_upsert_updates_existing(self):
        HealthStatus.objects.create(
            service_name='existing-svc', status='healthy',
            health_score=100, environment='production',
        )
        obj, created = self.logic.upsert({
            'service_name': 'existing-svc', 'status': 'degraded',
            'health_score': 60, 'environment': 'production',
        })
        assert created is False
        assert obj.status == 'degraded'
        assert obj.health_score == 60

    def test_upsert_idempotent(self):
        data = {'service_name': 'idem-svc', 'status': 'healthy', 'health_score': 100}
        self.logic.upsert(data)
        self.logic.upsert(data)
        count = HealthStatus.objects.filter(service_name='idem-svc').count()
        assert count == 1


# ── DashboardLogic ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardLogic:
    def setup_method(self):
        self.logic = DashboardLogic()

    def test_create_widget(self):
        w = self.logic.create_widget({
            'name': 'CPU Widget', 'widget_type': 'line_chart', 'data_source': 'metric',
        })
        assert isinstance(w, DashboardWidget)
        assert w.name == 'CPU Widget'

    def test_get_widget_existing(self):
        w = DashboardWidget.objects.create(
            name='Test Widget', widget_type='gauge', data_source='metric',
        )
        result = self.logic.get_widget(w.id)
        assert result is not None
        assert result.id == w.id

    def test_get_widget_nonexistent(self):
        result = self.logic.get_widget(99999)
        assert result is None

    def test_update_widget(self):
        w = DashboardWidget.objects.create(
            name='Old Name', widget_type='gauge', data_source='metric',
        )
        result = self.logic.update_widget(w.id, {'name': 'New Name'})
        assert result is True
        w.refresh_from_db()
        assert w.name == 'New Name'

    def test_update_nonexistent_widget(self):
        result = self.logic.update_widget(99999, {'name': 'x'})
        assert result is False

    def test_delete_widget(self):
        w = DashboardWidget.objects.create(
            name='To Delete', widget_type='table', data_source='log',
        )
        result = self.logic.delete_widget(w.id)
        assert result is True
        assert not DashboardWidget.objects.filter(id=w.id).exists()

    def test_delete_nonexistent_widget(self):
        result = self.logic.delete_widget(99999)
        assert result is False

    def test_get_widgets_all(self):
        DashboardWidget.objects.create(name='W1', widget_type='gauge', data_source='metric')
        DashboardWidget.objects.create(name='W2', widget_type='table', data_source='log')
        result = self.logic.get_widgets()
        assert len(result) >= 2

    def test_get_widgets_filtered_active(self):
        DashboardWidget.objects.create(name='Active',   widget_type='gauge', data_source='metric', is_active=True)
        DashboardWidget.objects.create(name='Inactive', widget_type='gauge', data_source='metric', is_active=False)
        result = self.logic.get_widgets(is_active=True)
        assert all(w.is_active for w in result)
