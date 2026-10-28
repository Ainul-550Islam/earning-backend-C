"""
Managers for Telemetry Observability.

NOTE: As of the latest refactor, all custom Manager classes have been moved
directly into their respective model files (models/metric_event.py,
models/log_entry.py, models/trace_span.py, models/alert.py,
models/health_status.py, models/dashboard_widget.py) and are attached via
`objects = XxxManager()`.

This package is kept for backwards compatibility only.
Import managers directly from the model files or via:
    MetricEvent.objects.by_name('cpu_usage')
    Alert.objects.critical()
    etc.
"""
from ..models.metric_event import MetricEventManager
from ..models.log_entry import LogEntryManager
from ..models.trace_span import TraceSpanManager
from ..models.alert import AlertManager
from ..models.health_status import HealthStatusManager
from ..models.dashboard_widget import DashboardWidgetManager

# Aliases for backwards compatibility with any code that imports from here
MetricManager = MetricEventManager
LogManager = LogEntryManager
TraceManager = TraceSpanManager
DashboardManager = DashboardWidgetManager

__all__ = [
    'MetricEventManager',
    'LogEntryManager',
    'TraceSpanManager',
    'AlertManager',
    'HealthStatusManager',
    'DashboardWidgetManager',
    # Aliases
    'MetricManager',
    'LogManager',
    'TraceManager',
    'DashboardManager',
]
