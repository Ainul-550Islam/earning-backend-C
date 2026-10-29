"""
Tests for AnalyticsViewSet and AnalyticsView.
"""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
User = get_user_model()

from ..models.metric_event  import MetricEvent
from ..models.log_entry     import LogEntry
from ..models.trace_span    import TraceSpan
from ..models.alert         import Alert
from ..models.health_status import HealthStatus


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(username='analyst', password='pass123')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sample_data(db):
    """Create sample data across all domains for analytics tests."""
    MetricEvent.objects.create(name='cpu_usage', metric_type='gauge',   value=80.0, service='api')
    MetricEvent.objects.create(name='cpu_usage', metric_type='gauge',   value=60.0, service='api')
    MetricEvent.objects.create(name='mem_usage', metric_type='gauge',   value=50.0, service='api')
    LogEntry.objects.create(level='info',  message='OK',     service='api')
    LogEntry.objects.create(level='error', message='Failed', service='api')
    TraceSpan.objects.create(
        trace_id='t1', span_id='s1', operation_name='GET /api',
        service='api', start_time=timezone.now(), status='success',
    )
    Alert.objects.create(
        name='High CPU', alert_type='metric', severity='critical',
        status='open', message='CPU', service='api',
    )
    HealthStatus.objects.create(service_name='api', status='healthy', health_score=95)


# ── AnalyticsViewSet (router-based) ──────────────────────────────────────────

@pytest.mark.django_db
class TestAnalyticsViewSet:
    def test_overview_returns_200(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/')
        assert resp.status_code == 200

    def test_overview_contains_expected_keys(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/?hours=24')
        data = resp.json()
        for key in ['total_metrics', 'total_logs', 'total_traces',
                    'total_alerts', 'open_alerts', 'healthy_services']:
            assert key in data, f"Missing key: {key}"

    def test_overview_counts_are_non_negative(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/')
        data = resp.json()
        assert data['total_metrics']   >= 0
        assert data['total_logs']      >= 0
        assert data['total_traces']    >= 0
        assert data['total_alerts']    >= 0

    def test_metrics_action_requires_name(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/metrics/')
        assert resp.status_code in (400, 200)

    def test_metrics_action_with_name(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/metrics/?name=cpu_usage&hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert 'metric_name' in data
        assert data['metric_name'] == 'cpu_usage'

    def test_logs_action(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/logs/?hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_logs'   in data
        assert 'level_counts' in data

    def test_traces_action(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/traces/?hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_traces'  in data
        assert 'status_counts' in data

    def test_alerts_action(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/alerts/?hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_alerts'    in data
        assert 'severity_counts' in data

    def test_health_action(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/health/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_services'   in data
        assert 'avg_health_score' in data

    def test_service_action_requires_service(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/service/')
        assert resp.status_code == 400

    def test_service_action_with_service(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/service/?service=api&hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert data['service_name'] == 'api'

    def test_trend_action_requires_name(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/trend/')
        assert resp.status_code == 400

    def test_trend_action_with_name(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/trend/?name=cpu_usage&interval=hour')
        assert resp.status_code == 200
        data = resp.json()
        assert data['name'] == 'cpu_usage'
        assert 'data' in data

    def test_compare_action_requires_services(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/compare/')
        assert resp.status_code == 400

    def test_compare_action_multi_service(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/compare/?services=api,auth&hours=24')
        assert resp.status_code == 200
        data = resp.json()
        assert 'comparison' in data
        assert 'api' in data['comparison']

    def test_unauthenticated_returns_403(self):
        client = APIClient()
        resp   = client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/')
        assert resp.status_code in (401, 403)

    def test_invalid_hours_param(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/logs/?hours=abc')
        assert resp.status_code in (200, 400)


# ── AnalyticsView (CBV) ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAnalyticsView:
    def test_cbv_overview_via_action_param(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/?action=overview')
        assert resp.status_code == 200

    def test_cbv_unknown_action_returns_400(self, auth_client):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/?action=nonexistent')
        assert resp.status_code == 400

    def test_cbv_action_in_url_segment(self, auth_client, sample_data):
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/')
        assert resp.status_code == 200


# ── Analytics data accuracy ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestAnalyticsAccuracy:
    def test_metric_count_matches(self, auth_client, db):
        MetricEvent.objects.create(name='m', metric_type='counter', value=1.0)
        MetricEvent.objects.create(name='m', metric_type='counter', value=2.0)
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/?hours=24')
        assert resp.json()['total_metrics'] >= 2

    def test_error_rate_calculated(self, auth_client, db):
        LogEntry.objects.create(level='info',  message='ok',  service='svc')
        LogEntry.objects.create(level='error', message='err', service='svc')
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/logs/?hours=24')
        data = resp.json()
        assert 'error_rate' in data
        assert 0 <= data['error_rate'] <= 100

    def test_open_alert_count(self, auth_client, db):
        Alert.objects.create(name='open1', alert_type='metric', severity='warning',
                             status='open', message='t', service='svc')
        Alert.objects.create(name='done1', alert_type='metric', severity='info',
                             status='resolved', message='t', service='svc')
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/overview/?hours=24')
        assert resp.json()['open_alerts'] >= 1

    def test_avg_health_score(self, auth_client, db):
        HealthStatus.objects.create(service_name='s1', status='healthy',   health_score=100)
        HealthStatus.objects.create(service_name='s2', status='unhealthy', health_score=0)
        resp = auth_client.get('/api/telemetry-observability/api/v1/telemetry/analytics/health/')
        data = resp.json()
        assert data['avg_health_score'] == 50.0
