"""
Tests for Real-time Dashboard Backend services.
"""
import pytest
from api.realtime_dashboard.services.dashboard_service import DashboardService
from api.realtime_dashboard.services.widget_service import WidgetService
from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
from api.realtime_dashboard.services.websocket_manager_service import WebSocketManagerService
from api.realtime_dashboard.services.dashboard_engine_service import DashboardEngineService
from api.realtime_dashboard.services.event_streaming_service import EventStreamingService
from api.realtime_dashboard.exceptions import DashboardEngineError
from .fixtures import (
    create_dashboard_widget,
    create_real_time_metric,
    create_user_dashboard,
    create_websocket_connection,
)


# ─── DashboardService ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardService:

    @pytest.fixture
    def service(self):
        return DashboardService()

    def test_create_dashboard(self, service):
        data = {
            'name': 'Test Dashboard', 'description': 'A test dashboard',
            'status': 'active', 'user_id': 'user123',
            'widgets': [], 'metadata': {}, 'tags': ['test']
        }
        dashboard = service.create_dashboard(data)
        assert dashboard.name == 'Test Dashboard'
        assert dashboard.user_id == 'user123'
        assert dashboard.status == 'active'

    def test_get_dashboard(self, service):
        dashboard = create_user_dashboard(name='Test Dashboard')
        retrieved = service.get_dashboard(dashboard.id)
        assert retrieved is not None
        assert retrieved.name == 'Test Dashboard'

    def test_get_dashboard_not_found(self, service):
        assert service.get_dashboard(99999) is None

    def test_get_user_dashboards(self, service):
        create_user_dashboard(name='Dashboard 1', user_id='user123')
        create_user_dashboard(name='Dashboard 2', user_id='user123')
        create_user_dashboard(name='Dashboard 3', user_id='user456')
        dashboards = service.get_user_dashboards('user123')
        assert len(dashboards) == 2
        assert all(d.user_id == 'user123' for d in dashboards)

    def test_get_user_dashboards_excludes_inactive(self, service):
        """get_user_dashboards() uses .active() - inactive are excluded."""
        create_user_dashboard(name='Active', user_id='userA', status='active')
        create_user_dashboard(name='Inactive', user_id='userA', status='inactive')
        dashboards = service.get_user_dashboards('userA')
        assert len(dashboards) == 1
        assert dashboards[0].name == 'Active'


# ─── WidgetService ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestWidgetService:

    @pytest.fixture
    def service(self):
        return WidgetService()

    def test_create_widget(self, service):
        data = {
            'name': 'Test Widget', 'widget_type': 'chart', 'status': 'active',
            'configuration': {}, 'refresh_interval': 60,
            'width': 6, 'height': 4, 'created_by': 'user123'
        }
        widget = service.create_widget(data)
        assert widget.name == 'Test Widget'
        assert widget.widget_type == 'chart'
        assert widget.created_by == 'user123'

    def test_get_widget(self, service):
        widget = create_dashboard_widget(name='Test Widget')
        retrieved = service.get_widget(widget.id)
        assert retrieved is not None
        assert retrieved.name == 'Test Widget'

    def test_get_widget_not_found(self, service):
        assert service.get_widget(99999) is None

    def test_update_widget(self, service):
        widget = create_dashboard_widget(name='Old Name')
        updated = service.update_widget(widget, {'name': 'New Name'})
        assert updated.name == 'New Name'

    def test_delete_widget(self, service):
        from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
        widget = create_dashboard_widget()
        pk = widget.pk
        service.delete_widget(widget)
        assert not DashboardWidget.objects.filter(pk=pk).exists()

    def test_get_widgets_by_type(self, service):
        create_dashboard_widget(name='Chart1', widget_type='chart')
        create_dashboard_widget(name='Chart2', widget_type='chart')
        create_dashboard_widget(name='Table1', widget_type='table')
        results = service.get_widgets_by_type('chart')
        assert len(results) == 2
        assert all(w.widget_type == 'chart' for w in results)


# ─── RealTimeMetricService ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRealTimeMetricService:

    @pytest.fixture
    def service(self):
        return RealTimeMetricService()

    def test_create_metric(self, service):
        data = {
            'name': 'Test Metric', 'metric_type': 'gauge',
            'status': 'active', 'value': 100.0, 'unit': 'units'
        }
        metric = service.create_metric(data)
        assert metric.name == 'Test Metric'
        assert metric.value == 100.0
        assert metric.metric_type == 'gauge'

    def test_update_metric(self, service):
        """
        v1.5.0: update_metric_value(id, value) was removed — it was a
        strict subset of update_metric(instance, data), which is now the
        single owner of "apply an update + auto-track previous_value"
        (also the method perform_update() actually delegates to).
        """
        metric = create_real_time_metric(value=100.0)
        updated = service.update_metric(metric, {'value': 150.0})
        assert updated.value == 150.0
        assert updated.previous_value == 100.0

    def test_update_metric_non_value_field_does_not_touch_previous_value(self, service):
        metric = create_real_time_metric(value=100.0, previous_value=None, name='Old Name')
        updated = service.update_metric(metric, {'name': 'New Name'})
        assert updated.name == 'New Name'
        assert updated.value == 100.0
        assert updated.previous_value is None

    def test_check_thresholds_critical(self, service):
        metric = create_real_time_metric(
            value=95.0, warning_threshold=80.0, critical_threshold=90.0)
        assert service.check_thresholds(metric) == 'critical'

    def test_check_thresholds_warning(self, service):
        metric = create_real_time_metric(
            value=85.0, warning_threshold=80.0, critical_threshold=90.0)
        assert service.check_thresholds(metric) == 'warning'

    def test_check_thresholds_normal(self, service):
        metric = create_real_time_metric(
            value=50.0, warning_threshold=80.0, critical_threshold=90.0)
        assert service.check_thresholds(metric) == 'normal'

    def test_get_metrics_by_type(self, service):
        create_real_time_metric(name='G1', metric_type='gauge')
        create_real_time_metric(name='G2', metric_type='gauge')
        create_real_time_metric(name='C1', metric_type='counter')
        metrics = service.get_metrics_by_type('gauge')
        assert len(metrics) == 2
        assert all(m.metric_type == 'gauge' for m in metrics)


# ─── WebSocketManagerService ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestWebSocketManagerService:

    @pytest.fixture
    def service(self):
        return WebSocketManagerService()

    def test_add_connection(self, service):
        connection = service.add_connection('conn123', 'user123', 'session123')
        assert connection.connection_id == 'conn123'
        assert connection.user_id == 'user123'
        assert connection.status == 'connected'

    def test_remove_connection(self, service):
        connection = create_websocket_connection(connection_id='conn123')
        result = service.remove_connection('conn123')
        assert result is True
        connection.refresh_from_db()
        assert connection.status == 'disconnected'

    def test_get_active_connections(self, service):
        create_websocket_connection(connection_id='c1', status='connected')
        create_websocket_connection(connection_id='c2', status='connected')
        create_websocket_connection(connection_id='c3', status='disconnected')
        connections = service.get_active_connections()
        assert len(connections) == 2
        assert all(c.status == 'connected' for c in connections)

    def test_broadcast_to_user(self, service):
        create_websocket_connection(connection_id='c1', user_id='user1')
        create_websocket_connection(connection_id='c2', user_id='user1')
        create_websocket_connection(connection_id='c3', user_id='user2')
        result = service.broadcast_to_user('user1', {'message': 'test'})
        assert result is True

    def test_cleanup_old_connections(self, service):
        from datetime import timedelta
        from django.utils import timezone
        from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
        conn = create_websocket_connection(connection_id='old_conn')
        old_ping = timezone.now() - timedelta(seconds=7200)
        WebSocketConnection.objects.filter(pk=conn.pk).update(last_ping=old_ping)
        cleaned = service.cleanup_old_connections(timeout_seconds=3600)
        assert cleaned == 1
        conn.refresh_from_db()
        assert conn.status == 'disconnected'


# ─── DashboardEngineService (was 0% covered via service layer) ────────────────

@pytest.mark.django_db
class TestDashboardEngineService:

    @pytest.fixture
    def service(self):
        return DashboardEngineService()

    def test_render_dashboard(self, service):
        widget = create_dashboard_widget(name='W1')
        dashboard = create_user_dashboard(name='D1', widgets=[widget.pk])
        result = service.render_dashboard(dashboard.pk)
        assert result['id'] == dashboard.pk
        assert result['name'] == 'D1'
        assert len(result['widgets']) == 1
        assert result['widgets'][0]['id'] == widget.pk

    def test_render_dashboard_not_found(self, service):
        with pytest.raises(DashboardEngineError):
            service.render_dashboard(99999)

    def test_render_dashboard_with_invalid_widget(self, service):
        """Dashboard referencing a deleted widget must raise DashboardEngineError."""
        dashboard = create_user_dashboard(widgets=[999999])
        with pytest.raises(DashboardEngineError):
            service.render_dashboard(dashboard.pk)

    def test_render_empty_dashboard(self, service):
        dashboard = create_user_dashboard(widgets=[])
        result = service.render_dashboard(dashboard.pk)
        assert result['widgets'] == []

    def test_get_widget_data(self, service):
        widget = create_dashboard_widget(name='DataWidget')
        result = service.get_widget_data(widget.pk)
        assert result['id'] == widget.pk
        assert result['name'] == 'DataWidget'
        assert 'metrics' in result

    def test_get_widget_data_not_found(self, service):
        with pytest.raises(DashboardEngineError):
            service.get_widget_data(99999)


# ─── EventStreamingService (was 0% covered) ───────────────────────────────────

@pytest.mark.django_db
class TestEventStreamingService:

    @pytest.fixture
    def service(self):
        return EventStreamingService()

    def test_stream_metric_updates_returns_true(self, service):
        m1 = create_real_time_metric(name='M1')
        m2 = create_real_time_metric(name='M2')
        # channel_layer is InMemoryChannelLayer in test settings; broadcast
        # is fire-and-forget, so we just assert no exception and True returned.
        result = service.stream_metric_updates([m1.pk, m2.pk])
        assert result is True

    def test_stream_metric_updates_empty_ids(self, service):
        result = service.stream_metric_updates([])
        assert result is True

    def test_stream_dashboard_updates_returns_true(self, service):
        dashboard = create_user_dashboard(name='StreamDash')
        result = service.stream_dashboard_updates(dashboard.pk)
        assert result is True

    def test_broadcast_event_no_channel_layer(self, service, monkeypatch):
        """If CHANNEL_LAYERS is not configured, _broadcast_event must not raise."""
        monkeypatch.setattr(
            'api.realtime_dashboard.services.event_streaming_service.get_channel_layer',
            lambda: None
        )
        result = service._broadcast_event('events', {'type': 'test', 'data': {}})
        assert result is True
