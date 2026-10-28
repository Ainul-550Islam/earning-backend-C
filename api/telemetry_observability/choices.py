"""
Choice field constants for Telemetry Observability.

SINGLE SOURCE OF TRUTH — import from here in:
  - models (field choices)
  - serializers (validate_xxx methods)
  - filters (ChoiceFilter choices=)
  - schemas (Enum values)

Never hardcode choice tuples anywhere else in the codebase.
"""
from django.db import models


class MetricTypeChoices(models.TextChoices):
    """Metric type choices."""
    COUNTER   = 'counter',   'Counter'
    GAUGE     = 'gauge',     'Gauge'
    HISTOGRAM = 'histogram', 'Histogram'
    SUMMARY   = 'summary',   'Summary'


class LogLevelChoices(models.TextChoices):
    """Log level choices."""
    DEBUG    = 'debug',    'Debug'
    INFO     = 'info',     'Info'
    WARNING  = 'warning',  'Warning'
    ERROR    = 'error',    'Error'
    CRITICAL = 'critical', 'Critical'


class TraceStatusChoices(models.TextChoices):
    """Trace span status choices."""
    SUCCESS = 'success', 'Success'
    ERROR   = 'error',   'Error'
    TIMEOUT = 'timeout', 'Timeout'


class AlertTypeChoices(models.TextChoices):
    """Alert type choices."""
    METRIC = 'metric', 'Metric'
    LOG    = 'log',    'Log'
    TRACE  = 'trace',  'Trace'
    HEALTH = 'health', 'Health'
    CUSTOM = 'custom', 'Custom'


class AlertSeverityChoices(models.TextChoices):
    """Alert severity choices."""
    INFO     = 'info',     'Info'
    WARNING  = 'warning',  'Warning'
    ERROR    = 'error',    'Error'
    CRITICAL = 'critical', 'Critical'


class AlertStatusChoices(models.TextChoices):
    """Alert status choices."""
    OPEN         = 'open',         'Open'
    ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
    RESOLVED     = 'resolved',     'Resolved'
    SUPPRESSED   = 'suppressed',   'Suppressed'


class HealthStatusChoices(models.TextChoices):
    """Health status choices."""
    HEALTHY   = 'healthy',   'Healthy'
    DEGRADED  = 'degraded',  'Degraded'
    UNHEALTHY = 'unhealthy', 'Unhealthy'
    UNKNOWN   = 'unknown',   'Unknown'


class WidgetTypeChoices(models.TextChoices):
    """Dashboard widget type choices."""
    LINE_CHART  = 'line_chart',  'Line Chart'
    BAR_CHART   = 'bar_chart',   'Bar Chart'
    PIE_CHART   = 'pie_chart',   'Pie Chart'
    GAUGE       = 'gauge',       'Gauge'
    TABLE       = 'table',       'Table'
    METRIC_CARD = 'metric_card', 'Metric Card'
    LOG_VIEW    = 'log_view',    'Log View'
    TRACE_VIEW  = 'trace_view',  'Trace View'
    ALERT_LIST  = 'alert_list',  'Alert List'
    CUSTOM      = 'custom',      'Custom'


class DataSourceChoices(models.TextChoices):
    """Dashboard data source choices."""
    METRIC = 'metric', 'Metric'
    LOG    = 'log',    'Log'
    TRACE  = 'trace',  'Trace'
    ALERT  = 'alert',  'Alert'
    HEALTH = 'health', 'Health'
    CUSTOM = 'custom', 'Custom'


class EnvironmentChoices(models.TextChoices):
    """Deployment environment choices."""
    DEVELOPMENT = 'development', 'Development'
    STAGING     = 'staging',     'Staging'
    PRODUCTION  = 'production',  'Production'


class AggregationTypeChoices(models.TextChoices):
    """Metric aggregation function choices."""
    AVG   = 'avg',   'Average'
    SUM   = 'sum',   'Sum'
    MIN   = 'min',   'Minimum'
    MAX   = 'max',   'Maximum'
    COUNT = 'count', 'Count'


class TimeWindowChoices(models.TextChoices):
    """Time window choices for queries and dashboards."""
    MINUTE_5  = '5m',  '5 Minutes'
    MINUTE_15 = '15m', '15 Minutes'
    HOUR_1    = '1h',  '1 Hour'
    HOUR_6    = '6h',  '6 Hours'
    HOUR_24   = '24h', '24 Hours'
    DAY_7     = '7d',  '7 Days'
    DAY_30    = '30d', '30 Days'


__all__ = [
    'MetricTypeChoices',
    'LogLevelChoices',
    'TraceStatusChoices',
    'AlertTypeChoices',
    'AlertSeverityChoices',
    'AlertStatusChoices',
    'HealthStatusChoices',
    'WidgetTypeChoices',
    'DataSourceChoices',
    'EnvironmentChoices',
    'AggregationTypeChoices',
    'TimeWindowChoices',
]
