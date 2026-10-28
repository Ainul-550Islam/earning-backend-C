"""
Constants for Real-time Dashboard Backend.

FIXED (v1.3.0): Previously defined standalone Python Enums (WidgetType,
WidgetStatus, etc.) that were NEVER imported anywhere. The model classes
already define equivalent TextChoices (DashboardWidget.WidgetType,
RealTimeMetric.MetricType, etc.) — the two sets were duplicated and
diverged over time.

Resolution: re-export the authoritative TextChoices from model classes.
This file is now a single canonical import point for all choice constants.
No duplication — no drift.

Usage in any Python file:
    from api.realtime_dashboard.constants import (
        WidgetType, WidgetStatus, MetricType, LayoutType, ConnectionStatus
    )
    # or directly from models (both are equivalent):
    from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
    WidgetType = DashboardWidget.WidgetType

Preferred usage in filters, validators, serializers:
    from .constants import WidgetType
    choices = WidgetType.choices      # Django TextChoices compatible
    values  = WidgetType.values       # list of string values
    labels  = WidgetType.labels       # list of display labels

DRY: Do NOT re-define these choices anywhere else. If a new choice is
needed, add it to the model's TextChoices class only — constants.py
picks it up automatically via the re-export.
"""

# Re-export from model TextChoices — single source of truth.
# Import is lazy (inside function) avoided here because constants should
# be importable at module load time without triggering the Django app registry.
# Django models must be fully loaded before this module is imported.

from .models.dashboard_widget import DashboardWidget
from .models.real_time_metric import RealTimeMetric
from .models.dashboard_layout import DashboardLayout
from .models.websocket_connection import WebSocketConnection

# Widget choices
WidgetType = DashboardWidget.WidgetType
WidgetStatus = DashboardWidget.WidgetStatus

# Metric choices
MetricType = RealTimeMetric.MetricType
MetricStatus = RealTimeMetric.MetricStatus

# Layout choices
LayoutType = DashboardLayout.LayoutType

# Connection choices
ConnectionStatus = WebSocketConnection.ConnectionStatus

__all__ = [
    'WidgetType',
    'WidgetStatus',
    'MetricType',
    'MetricStatus',
    'LayoutType',
    'ConnectionStatus',
]
