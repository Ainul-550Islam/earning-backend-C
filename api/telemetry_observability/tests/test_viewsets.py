"""
ViewSet tests for Telemetry Observability.
All endpoints require authentication — using authenticated_api_client fixture.
"""
import pytest
from rest_framework.test import APIClient

from ..models.metric_event import MetricEvent
from ..models.log_entry import LogEntry
from ..models.trace_span import TraceSpan
from ..models.alert import Alert
from ..models.health_status import HealthStatus
from ..models.dashboard_widget import DashboardWidget


@pytest.mark.django_db
class TestMetricViewSet:
    """Tests for MetricViewSet (/api/v1/telemetry/metrics/)."""

    def test_list_metrics(self, authenticated_api_client):
        """GET /metrics/ returns 200 and a list."""
        MetricEvent.objects.create(
            name='test-metric',
            metric_type='counter',
            value=1.0,
            source='test',
            service='test-service'
        )
        response = authenticated_api_client.get('/api/v1/telemetry/metrics/')
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) >= 1

    def test_create_metric(self, authenticated_api_client):
        """POST /metrics/ returns 201 and the created metric."""
        data = {
            'name': 'new-metric',
            'metric_type': 'counter',
            'value': 1.0,
            'source': 'test',
            'service': 'test-service'
        }
        response = authenticated_api_client.post('/api/v1/telemetry/metrics/', data, format='json')
        assert response.status_code == 201
        assert response.data['name'] == 'new-metric'

    def test_retrieve_metric(self, authenticated_api_client):
        """GET /metrics/<pk>/ returns 200 with correct data."""
        metric = MetricEvent.objects.create(
            name='test-metric',
            metric_type='gauge',
            value=42.5,
            source='test',
            service='test-service'
        )
        response = authenticated_api_client.get(f'/api/v1/telemetry/metrics/{metric.id}/')
        assert response.status_code == 200
        assert response.data['name'] == 'test-metric'
        assert response.data['value'] == 42.5

    def test_delete_metric(self, authenticated_api_client):
        """DELETE /metrics/<pk>/ returns 204 and removes the record."""
        metric = MetricEvent.objects.create(
            name='to-delete',
            metric_type='counter',
            value=1.0,
            source='test',
            service='test-service'
        )
        response = authenticated_api_client.delete(f'/api/v1/telemetry/metrics/{metric.id}/')
        assert response.status_code == 204
        assert not MetricEvent.objects.filter(id=metric.id).exists()

    def test_statistics_action(self, authenticated_api_client):
        """GET /metrics/statistics/?name=x returns statistics dict."""
        MetricEvent.objects.create(
            name='cpu_usage', metric_type='gauge', value=80.0, source='test', service='svc'
        )
        response = authenticated_api_client.get(
            '/api/v1/telemetry/metrics/statistics/?name=cpu_usage'
        )
        assert response.status_code == 200
        assert 'metric_name' in response.data
        assert 'avg' in response.data

    def test_batch_create(self, authenticated_api_client):
        """POST /metrics/batch/ creates multiple metrics."""
        data = {
            'metrics': [
                {'name': 'metric1', 'metric_type': 'counter', 'value': 1.0},
                {'name': 'metric2', 'metric_type': 'gauge', 'value': 2.5},
            ]
        }
        response = authenticated_api_client.post(
            '/api/v1/telemetry/metrics/batch/', data, format='json'
        )
        assert response.status_code == 201
        assert len(response.data) == 2

    def test_unauthenticated_returns_403(self):
        """Unauthenticated requests are rejected."""
        client = APIClient()
        response = client.get('/api/v1/telemetry/metrics/')
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestLogViewSet:
    """Tests for LogViewSet (/api/v1/telemetry/logs/)."""

    def test_list_logs(self, authenticated_api_client):
        """GET /logs/ returns 200 with list of logs."""
        LogEntry.objects.create(
            level='info',
            message='Test log',
            source='test',
            service='test-service'
        )
        response = authenticated_api_client.get('/api/v1/telemetry/logs/')
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_create_log(self, authenticated_api_client):
        """POST /logs/ returns 201 with created log."""
        data = {
            'level': 'info',
            'message': 'New log entry',
            'source': 'test',
            'service': 'test-service'
        }
        response = authenticated_api_client.post('/api/v1/telemetry/logs/', data, format='json')
        assert response.status_code == 201
        assert response.data['message'] == 'New log entry'

    def test_filter_by_level(self, authenticated_api_client):
        """GET /logs/?level=error returns only error-level logs."""
        LogEntry.objects.create(level='info', message='Info log', source='t', service='s')
        LogEntry.objects.create(level='error', message='Error log', source='t', service='s')
        response = authenticated_api_client.get('/api/v1/telemetry/logs/?level=error')
        assert response.status_code == 200
        for log in response.data:
            assert log['level'] == 'error'

    def test_errors_action(self, authenticated_api_client):
        """GET /logs/errors/ returns only error and critical logs."""
        LogEntry.objects.create(level='error', message='Err', source='t', service='s')
        LogEntry.objects.create(level='info', message='Info', source='t', service='s')
        response = authenticated_api_client.get('/api/v1/telemetry/logs/errors/')
        assert response.status_code == 200
        for log in response.data:
            assert log['level'] in ('error', 'critical')

    def test_analytics_action(self, authenticated_api_client):
        """GET /logs/analytics/ returns analytics dict."""
        response = authenticated_api_client.get('/api/v1/telemetry/logs/analytics/?hours=24')
        assert response.status_code == 200
        assert 'total_logs' in response.data
        assert 'level_counts' in response.data


@pytest.mark.django_db
class TestTraceViewSet:
    """Tests for TraceViewSet (/api/v1/telemetry/traces/)."""

    def test_list_traces(self, authenticated_api_client):
        """GET /traces/ returns 200 with list."""
        from django.utils import timezone
        TraceSpan.objects.create(
            trace_id='t1', span_id='s1', operation_name='op',
            service='svc', start_time=timezone.now()
        )
        response = authenticated_api_client.get('/api/v1/telemetry/traces/')
        assert response.status_code == 200

    def test_create_span(self, authenticated_api_client):
        """POST /traces/ starts a new span."""
        data = {'operation_name': 'test-op', 'service': 'test-service'}
        response = authenticated_api_client.post(
            '/api/v1/telemetry/traces/', data, format='json'
        )
        assert response.status_code == 201
        assert response.data['operation_name'] == 'test-op'
        assert 'span_id' in response.data

    def test_finish_action(self, authenticated_api_client):
        """POST /traces/<pk>/finish/ finishes the span."""
        from django.utils import timezone
        span = TraceSpan.objects.create(
            trace_id='t2', span_id='s2', operation_name='op2',
            service='svc', start_time=timezone.now()
        )
        response = authenticated_api_client.post(
            f'/api/v1/telemetry/traces/{span.id}/finish/',
            {'status': 'success'},
            format='json'
        )
        assert response.status_code == 200
        span.refresh_from_db()
        assert span.end_time is not None
        assert span.duration_ms is not None

    def test_slow_action(self, authenticated_api_client):
        """GET /traces/slow/ returns slow spans."""
        response = authenticated_api_client.get(
            '/api/v1/telemetry/traces/slow/?threshold_ms=100'
        )
        assert response.status_code == 200

    def test_statistics_action(self, authenticated_api_client):
        """GET /traces/statistics/ returns stats dict."""
        response = authenticated_api_client.get('/api/v1/telemetry/traces/statistics/')
        assert response.status_code == 200
        assert 'total_spans' in response.data


@pytest.mark.django_db
class TestAlertViewSet:
    """Tests for AlertViewSet (/api/v1/telemetry/alerts/)."""

    def test_list_alerts(self, authenticated_api_client):
        """GET /alerts/ returns 200 with list."""
        Alert.objects.create(
            name='test-alert', alert_type='metric', severity='warning',
            status='open', message='Test', source='test', service='svc'
        )
        response = authenticated_api_client.get('/api/v1/telemetry/alerts/')
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_create_alert(self, authenticated_api_client):
        """POST /alerts/ returns 201 with the created alert."""
        data = {
            'name': 'new-alert',
            'alert_type': 'metric',
            'severity': 'warning',
            'message': 'New alert',
            'source': 'test',
            'service': 'test-service'
        }
        response = authenticated_api_client.post(
            '/api/v1/telemetry/alerts/', data, format='json'
        )
        assert response.status_code == 201
        assert response.data['name'] == 'new-alert'

    def test_acknowledge_action(self, authenticated_api_client):
        """POST /alerts/<pk>/acknowledge/ acknowledges the alert."""
        alert = Alert.objects.create(
            name='ack-alert', alert_type='metric', severity='warning',
            status='open', message='Ack me', source='test', service='svc'
        )
        response = authenticated_api_client.post(
            f'/api/v1/telemetry/alerts/{alert.id}/acknowledge/',
            {'user': 'ops-team'},
            format='json'
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.status == 'acknowledged'
        assert alert.acknowledged_by == 'ops-team'

    def test_resolve_action(self, authenticated_api_client):
        """POST /alerts/<pk>/resolve/ resolves the alert."""
        alert = Alert.objects.create(
            name='res-alert', alert_type='metric', severity='critical',
            status='open', message='Resolve me', source='test', service='svc'
        )
        response = authenticated_api_client.post(
            f'/api/v1/telemetry/alerts/{alert.id}/resolve/',
            format='json'
        )
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.status == 'resolved'
        assert alert.resolved_at is not None

    def test_statistics_action(self, authenticated_api_client):
        """GET /alerts/statistics/ returns stats."""
        response = authenticated_api_client.get('/api/v1/telemetry/alerts/statistics/')
        assert response.status_code == 200
        assert 'total_alerts' in response.data

    def test_open_action(self, authenticated_api_client):
        """GET /alerts/open/ returns only open alerts."""
        Alert.objects.create(
            name='open-alert', alert_type='metric', severity='warning',
            status='open', message='Open', source='t', service='s'
        )
        Alert.objects.create(
            name='resolved-alert', alert_type='metric', severity='info',
            status='resolved', message='Done', source='t', service='s'
        )
        response = authenticated_api_client.get('/api/v1/telemetry/alerts/open/')
        assert response.status_code == 200
        for alert_data in response.data:
            assert alert_data['status'] == 'open'


@pytest.mark.django_db
class TestHealthViewSet:
    """Tests for HealthViewSet (/api/v1/telemetry/health/)."""

    def test_list_health(self, authenticated_api_client):
        """GET /health/ returns 200."""
        HealthStatus.objects.create(
            service_name='svc-1', status='healthy', health_score=100
        )
        response = authenticated_api_client.get('/api/v1/telemetry/health/')
        assert response.status_code == 200

    def test_create_health(self, authenticated_api_client):
        """POST /health/ returns 201."""
        data = {
            'service_name': 'new-service',
            'status': 'healthy',
            'health_score': 95,
            'environment': 'production'
        }
        response = authenticated_api_client.post(
            '/api/v1/telemetry/health/', data, format='json'
        )
        assert response.status_code == 201
        assert response.data['service_name'] == 'new-service'

    def test_upsert_action(self, authenticated_api_client):
        """POST /health/upsert/ creates or updates idempotently."""
        data = {
            'service_name': 'upsert-svc',
            'status': 'healthy',
            'health_score': 90,
            'environment': 'staging'
        }
        r1 = authenticated_api_client.post(
            '/api/v1/telemetry/health/upsert/', data, format='json'
        )
        assert r1.status_code == 201

        data['health_score'] = 75
        r2 = authenticated_api_client.post(
            '/api/v1/telemetry/health/upsert/', data, format='json'
        )
        assert r2.status_code == 200
        assert r2.data['health_score'] == 75

    def test_summary_action(self, authenticated_api_client):
        """GET /health/summary/ returns summary dict."""
        response = authenticated_api_client.get('/api/v1/telemetry/health/summary/')
        assert response.status_code == 200
        assert 'total_services' in response.data
        assert 'avg_health_score' in response.data


@pytest.mark.django_db
class TestDashboardViewSet:
    """Tests for DashboardViewSet (/api/v1/telemetry/dashboards/)."""

    def test_list_widgets(self, authenticated_api_client):
        """GET /dashboards/ returns 200."""
        DashboardWidget.objects.create(
            name='Widget 1', widget_type='metric_card', data_source='metric'
        )
        response = authenticated_api_client.get('/api/v1/telemetry/dashboards/')
        assert response.status_code == 200

    def test_create_widget(self, authenticated_api_client):
        """POST /dashboards/ returns 201."""
        data = {
            'name': 'New Widget',
            'widget_type': 'line_chart',
            'data_source': 'metric',
            'query': {'metric_name': 'cpu_usage'},
            'config': {}
        }
        response = authenticated_api_client.post(
            '/api/v1/telemetry/dashboards/', data, format='json'
        )
        assert response.status_code == 201
        assert response.data['name'] == 'New Widget'

    def test_retrieve_widget(self, authenticated_api_client):
        """GET /dashboards/<pk>/ returns 200."""
        widget = DashboardWidget.objects.create(
            name='My Widget', widget_type='gauge', data_source='metric'
        )
        response = authenticated_api_client.get(f'/api/v1/telemetry/dashboards/{widget.id}/')
        assert response.status_code == 200
        assert response.data['name'] == 'My Widget'

    def test_activate_action(self, authenticated_api_client):
        """POST /dashboards/<pk>/activate/ sets is_active=True."""
        widget = DashboardWidget.objects.create(
            name='Inactive Widget', widget_type='table',
            data_source='log', is_active=False
        )
        response = authenticated_api_client.post(
            f'/api/v1/telemetry/dashboards/{widget.id}/activate/'
        )
        assert response.status_code == 200
        widget.refresh_from_db()
        assert widget.is_active is True

    def test_deactivate_action(self, authenticated_api_client):
        """POST /dashboards/<pk>/deactivate/ sets is_active=False."""
        widget = DashboardWidget.objects.create(
            name='Active Widget', widget_type='pie_chart',
            data_source='metric', is_active=True
        )
        response = authenticated_api_client.post(
            f'/api/v1/telemetry/dashboards/{widget.id}/deactivate/'
        )
        assert response.status_code == 200
        widget.refresh_from_db()
        assert widget.is_active is False
