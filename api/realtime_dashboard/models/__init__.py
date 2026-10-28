"""
Models for Real-time Dashboard Backend.
"""
from .base import BaseModel
from .dashboard_widget import DashboardWidget
from .widget_configuration import WidgetConfiguration
from .real_time_metric import RealTimeMetric
from .dashboard_layout import DashboardLayout
from .user_dashboard import UserDashboard
from .websocket_connection import WebSocketConnection

__all__ = [
    'BaseModel',
    'DashboardWidget',
    'WidgetConfiguration',
    'RealTimeMetric',
    'DashboardLayout',
    'UserDashboard',
    'WebSocketConnection',
]
