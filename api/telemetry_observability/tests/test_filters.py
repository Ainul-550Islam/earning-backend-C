"""
Tests for filters.py — all FilterSets filter correctly.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from ..models.metric_event  import MetricEvent
from ..models.log_entry     import LogEntry
from ..models.trace_span    import TraceSpan
from ..models.alert         import Alert
from ..models.health_status import HealthStatus
from ..models.dashboard_widget import DashboardWidget
from ..filters import (
    MetricEventFilter, LogEntryFilter, TraceSpanFilter,
    AlertFilter, HealthStatusFilter, DashboardWidgetFilter,
)


@pytest.mark.django_db
class TestMetricEventFilter:
    def setup_method(self):
        MetricEvent.objects.all().delete()
        MetricEvent.objects.create(name='cpu_usage',    metric_type='gauge',   value=80.0,  service='svc-a', environment='production')
        MetricEvent.objects.create(name='memory_usage', metric_type='gauge',   value=60.0,  service='svc-a', environment='production')
        MetricEvent.objects.create(name='req_count',    metric_type='counter', value=100.0, service='svc-b', environment='staging')

    def test_filter_by_name(self):
        f = MetricEventFilter({'name': 'cpu'}, queryset=MetricEvent.objects.all())
        assert all('cpu' in m.name for m in f.qs)

    def test_filter_by_metric_type(self):
        f = MetricEventFilter({'metric_type': 'counter'}, queryset=MetricEvent.objects.all())
        assert all(m.metric_type == 'counter' for m in f.qs)

    def test_filter_by_service(self):
        f = MetricEventFilter({'service': 'svc-a'}, queryset=MetricEvent.objects.all())
        assert all('svc-a' in m.service for m in f.qs)

    def test_filter_by_environment(self):
        f = MetricEventFilter({'environment': 'staging'}, queryset=MetricEvent.objects.all())
        assert all(m.environment == 'staging' for m in f.qs)

    def test_filter_value_gte(self):
        f = MetricEventFilter({'value_gte': 70.0}, queryset=MetricEvent.objects.all())
        assert all(m.value >= 70.0 for m in f.qs)

    def test_filter_value_lte(self):
        f = MetricEventFilter({'value_lte': 80.0}, queryset=MetricEvent.objects.all())
        assert all(m.value <= 80.0 for m in f.qs)

    def test_filter_time_range_1h(self):
        f = MetricEventFilter({'time_range': '1h'}, queryset=MetricEvent.objects.all())
        # All test records were just created — should all be within 1h
        assert f.qs.count() == MetricEvent.objects.all().count()

    def test_no_filter_returns_all(self):
        f = MetricEventFilter({}, queryset=MetricEvent.objects.all())
        assert f.qs.count() == 3


@pytest.mark.django_db
class TestLogEntryFilter:
    def setup_method(self):
        LogEntry.objects.all().delete()
        LogEntry.objects.create(level='info',  message='User logged in',  service='auth', environment='production')
        LogEntry.objects.create(level='error', message='Payment failed',  service='pay',  environment='production')
        LogEntry.objects.create(level='debug', message='Cache miss',      service='cache', environment='staging')

    def test_filter_by_level(self):
        f = LogEntryFilter({'level': 'error'}, queryset=LogEntry.objects.all())
        assert all(l.level == 'error' for l in f.qs)

    def test_filter_by_service(self):
        f = LogEntryFilter({'service': 'auth'}, queryset=LogEntry.objects.all())
        assert all('auth' in l.service for l in f.qs)

    def test_filter_by_message(self):
        f = LogEntryFilter({'message': 'Payment'}, queryset=LogEntry.objects.all())
        assert all('Payment' in l.message for l in f.qs)

    def test_filter_by_environment(self):
        f = LogEntryFilter({'environment': 'staging'}, queryset=LogEntry.objects.all())
        assert all(l.environment == 'staging' for l in f.qs)


@pytest.mark.django_db
class TestAlertFilter:
    def setup_method(self):
        Alert.objects.all().delete()
        Alert.objects.create(name='Alert1', alert_type='metric', severity='critical', status='open',     message='m', service='svc-a', environment='production')
        Alert.objects.create(name='Alert2', alert_type='log',    severity='warning',  status='resolved', message='m', service='svc-b', environment='production')
        Alert.objects.create(name='Alert3', alert_type='health', severity='info',     status='open',     message='m', service='svc-a', environment='staging')

    def test_filter_by_severity(self):
        f = AlertFilter({'severity': 'critical'}, queryset=Alert.objects.all())
        assert all(a.severity == 'critical' for a in f.qs)

    def test_filter_by_status(self):
        f = AlertFilter({'status': 'open'}, queryset=Alert.objects.all())
        assert all(a.status == 'open' for a in f.qs)

    def test_filter_by_alert_type(self):
        f = AlertFilter({'alert_type': 'metric'}, queryset=Alert.objects.all())
        assert all(a.alert_type == 'metric' for a in f.qs)

    def test_filter_by_service(self):
        f = AlertFilter({'service': 'svc-a'}, queryset=Alert.objects.all())
        assert all('svc-a' in a.service for a in f.qs)

    def test_filter_by_environment(self):
        f = AlertFilter({'environment': 'staging'}, queryset=Alert.objects.all())
        assert all(a.environment == 'staging' for a in f.qs)


@pytest.mark.django_db
class TestHealthStatusFilter:
    def setup_method(self):
        HealthStatus.objects.all().delete()
        HealthStatus.objects.create(service_name='svc-a', status='healthy',   health_score=100, environment='production')
        HealthStatus.objects.create(service_name='svc-b', status='degraded',  health_score=60,  environment='production')
        HealthStatus.objects.create(service_name='svc-c', status='unhealthy', health_score=10,  environment='staging')

    def test_filter_by_status(self):
        f = HealthStatusFilter({'status': 'healthy'}, queryset=HealthStatus.objects.all())
        assert all(h.status == 'healthy' for h in f.qs)

    def test_filter_health_score_gte(self):
        f = HealthStatusFilter({'health_score_gte': 60}, queryset=HealthStatus.objects.all())
        assert all(h.health_score >= 60 for h in f.qs)

    def test_filter_health_score_lte(self):
        f = HealthStatusFilter({'health_score_lte': 60}, queryset=HealthStatus.objects.all())
        assert all(h.health_score <= 60 for h in f.qs)

    def test_filter_by_service_name(self):
        f = HealthStatusFilter({'service_name': 'svc-a'}, queryset=HealthStatus.objects.all())
        assert all('svc-a' in h.service_name for h in f.qs)

    def test_filter_by_environment(self):
        f = HealthStatusFilter({'environment': 'staging'}, queryset=HealthStatus.objects.all())
        assert all(h.environment == 'staging' for h in f.qs)


@pytest.mark.django_db
class TestDashboardWidgetFilter:
    def setup_method(self):
        DashboardWidget.objects.all().delete()
        DashboardWidget.objects.create(name='CPU Chart', widget_type='line_chart', data_source='metric', is_active=True)
        DashboardWidget.objects.create(name='Log View',  widget_type='log_view',   data_source='log',    is_active=True)
        DashboardWidget.objects.create(name='Inactive',  widget_type='gauge',      data_source='metric', is_active=False)

    def test_filter_by_widget_type(self):
        f = DashboardWidgetFilter({'widget_type': 'line_chart'}, queryset=DashboardWidget.objects.all())
        assert all(w.widget_type == 'line_chart' for w in f.qs)

    def test_filter_by_data_source(self):
        f = DashboardWidgetFilter({'data_source': 'metric'}, queryset=DashboardWidget.objects.all())
        assert all(w.data_source == 'metric' for w in f.qs)

    def test_filter_by_is_active_true(self):
        f = DashboardWidgetFilter({'is_active': True}, queryset=DashboardWidget.objects.all())
        assert all(w.is_active for w in f.qs)

    def test_filter_by_is_active_false(self):
        f = DashboardWidgetFilter({'is_active': False}, queryset=DashboardWidget.objects.all())
        assert all(not w.is_active for w in f.qs)
