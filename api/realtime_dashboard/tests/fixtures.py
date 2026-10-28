"""
Test fixtures for Real-time Dashboard Backend.
"""
from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
from api.realtime_dashboard.models.widget_configuration import WidgetConfiguration
from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
from api.realtime_dashboard.models.dashboard_layout import DashboardLayout
from api.realtime_dashboard.models.user_dashboard import UserDashboard
from api.realtime_dashboard.models.websocket_connection import WebSocketConnection


def create_dashboard_widget(**kwargs):
    """
    Create a test DashboardWidget instance.
    """
    defaults = {
        'name': 'Test Widget',
        'description': 'A test widget',
        'widget_type': DashboardWidget.WidgetType.CHART,
        'status': DashboardWidget.WidgetStatus.ACTIVE,
        'configuration': {},
        'data_source': 'test_source',
        'refresh_interval': 60,
        'width': 6,
        'height': 4,
        'metadata': {},
        'tags': ['test'],
        'created_by': 'test_user'
    }
    defaults.update(kwargs)
    return DashboardWidget.objects.create(**defaults)


def create_widget_configuration(widget, **kwargs):
    """
    Create a test WidgetConfiguration instance.
    """
    defaults = {
        'widget': widget,
        'config_type': WidgetConfiguration.ConfigType.CHART,
        'key': 'test_config',
        'value': {},
        'metadata': {}
    }
    defaults.update(kwargs)
    return WidgetConfiguration.objects.create(**defaults)


def create_real_time_metric(**kwargs):
    """
    Create a test RealTimeMetric instance.
    """
    defaults = {
        'name': 'Test Metric',
        'description': 'A test metric',
        'metric_type': RealTimeMetric.MetricType.GAUGE,
        'status': RealTimeMetric.MetricStatus.ACTIVE,
        'value': 100.0,
        'previous_value': 90.0,
        'unit': 'units',
        'warning_threshold': 80.0,
        'critical_threshold': 90.0,
        'metadata': {},
        'tags': ['test']
    }
    defaults.update(kwargs)
    return RealTimeMetric.objects.create(**defaults)


def create_dashboard_layout(**kwargs):
    """
    Create a test DashboardLayout instance.
    """
    defaults = {
        'name': 'Test Layout',
        'description': 'A test layout',
        'layout_type': DashboardLayout.LayoutType.GRID,
        'columns': 12,
        'rows': 12,
        'configuration': {},
        'metadata': {},
        'tags': ['test'],
        'created_by': 'test_user'
    }
    defaults.update(kwargs)
    return DashboardLayout.objects.create(**defaults)


def create_user_dashboard(**kwargs):
    """
    Create a test UserDashboard instance.
    """
    defaults = {
        'name': 'Test Dashboard',
        'description': 'A test dashboard',
        'status': UserDashboard.DashboardStatus.ACTIVE,
        'widgets': [],
        'user_id': 'test_user_123',
        'metadata': {},
        'tags': ['test']
    }
    defaults.update(kwargs)
    return UserDashboard.objects.create(**defaults)


def create_websocket_connection(**kwargs):
    """
    Create a test WebSocketConnection instance.
    """
    defaults = {
        'connection_id': 'test_connection_123',
        'user_id': 'test_user_123',
        'session_id': 'test_session_123',
        'status': WebSocketConnection.ConnectionStatus.CONNECTED,
        'metadata': {}
    }
    defaults.update(kwargs)
    return WebSocketConnection.objects.create(**defaults)


def cleanup_test_data():
    """
    Clean up test data.
    """
    DashboardWidget.objects.all().delete()
    WidgetConfiguration.objects.all().delete()
    RealTimeMetric.objects.all().delete()
    DashboardLayout.objects.all().delete()
    UserDashboard.objects.all().delete()
    WebSocketConnection.objects.all().delete()
