"""
Serializers for Real-time Dashboard Backend.
"""
from .base_serializer import BaseSerializer
from .dashboard_widget_serializer import DashboardWidgetSerializer, DashboardWidgetListSerializer
from .widget_configuration_serializer import WidgetConfigurationSerializer, WidgetConfigurationListSerializer
from .real_time_metric_serializer import RealTimeMetricSerializer, RealTimeMetricListSerializer
from .dashboard_layout_serializer import DashboardLayoutSerializer, DashboardLayoutListSerializer
from .user_dashboard_serializer import UserDashboardSerializer, UserDashboardListSerializer
from .websocket_connection_serializer import WebSocketConnectionSerializer, WebSocketConnectionListSerializer

__all__ = [
    'BaseSerializer',
    'DashboardWidgetSerializer',
    'DashboardWidgetListSerializer',
    'WidgetConfigurationSerializer',
    'WidgetConfigurationListSerializer',
    'RealTimeMetricSerializer',
    'RealTimeMetricListSerializer',
    'DashboardLayoutSerializer',
    'DashboardLayoutListSerializer',
    'UserDashboardSerializer',
    'UserDashboardListSerializer',
    'WebSocketConnectionSerializer',
    'WebSocketConnectionListSerializer',
]
