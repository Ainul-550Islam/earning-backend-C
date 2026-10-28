"""
Constants for Telemetry Observability.
"""
from enum import Enum


class MetricType(Enum):
    """Metric type constants."""
    COUNTER = 'counter'
    GAUGE = 'gauge'
    HISTOGRAM = 'histogram'
    SUMMARY = 'summary'


class LogLevel(Enum):
    """Log level constants."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class TraceStatus(Enum):
    """Trace status constants."""
    SUCCESS = 'success'
    ERROR = 'error'
    TIMEOUT = 'timeout'


class AlertType(Enum):
    """Alert type constants."""
    METRIC = 'metric'
    LOG = 'log'
    TRACE = 'trace'
    HEALTH = 'health'
    CUSTOM = 'custom'


class AlertSeverity(Enum):
    """Alert severity constants."""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class AlertStatus(Enum):
    """Alert status constants."""
    OPEN = 'open'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'
    SUPPRESSED = 'suppressed'


class HealthStatus(Enum):
    """Health status constants."""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


class WidgetType(Enum):
    """Widget type constants."""
    LINE_CHART = 'line_chart'
    BAR_CHART = 'bar_chart'
    PIE_CHART = 'pie_chart'
    GAUGE = 'gauge'
    TABLE = 'table'
    METRIC_CARD = 'metric_card'
    LOG_VIEW = 'log_view'
    TRACE_VIEW = 'trace_view'
    ALERT_LIST = 'alert_list'
    CUSTOM = 'custom'


class DataSource(Enum):
    """Data source constants."""
    METRIC = 'metric'
    LOG = 'log'
    TRACE = 'trace'
    ALERT = 'alert'
    HEALTH = 'health'
    CUSTOM = 'custom'


# Default values
DEFAULT_METRIC_TYPE = MetricType.COUNTER.value
DEFAULT_LOG_LEVEL = LogLevel.INFO.value
DEFAULT_TRACE_STATUS = TraceStatus.SUCCESS.value
DEFAULT_ALERT_TYPE = AlertType.METRIC.value
DEFAULT_ALERT_SEVERITY = AlertSeverity.WARNING.value
DEFAULT_ALERT_STATUS = AlertStatus.OPEN.value
DEFAULT_HEALTH_STATUS = HealthStatus.UNKNOWN.value
DEFAULT_WIDGET_TYPE = WidgetType.METRIC_CARD.value
DEFAULT_DATA_SOURCE = DataSource.METRIC.value

# Configuration limits
MAX_METRIC_NAME_LENGTH = 255
MAX_LOG_MESSAGE_LENGTH = 10000
MAX_TRACE_OPERATION_NAME_LENGTH = 255
MAX_ALERT_NAME_LENGTH = 255
MAX_ALERT_MESSAGE_LENGTH = 1000
MAX_WIDGET_NAME_LENGTH = 255
MAX_SERVICE_NAME_LENGTH = 255

# Default limits
DEFAULT_REFRESH_INTERVAL = 60  # seconds
DEFAULT_WIDGET_WIDTH = 4
DEFAULT_WIDGET_HEIGHT = 4
DEFAULT_MAX_WIDGET_WIDTH = 12
DEFAULT_MAX_WIDGET_HEIGHT = 12

# Metric thresholds
DEFAULT_ERROR_RATE_THRESHOLD = 0.05  # 5%
DEFAULT_RESPONSE_TIME_THRESHOLD = 1000  # 1000ms
DEFAULT_MEMORY_USAGE_THRESHOLD = 0.9  # 90%
DEFAULT_CPU_USAGE_THRESHOLD = 0.8  # 80%

# Log thresholds
DEFAULT_ERROR_LOG_THRESHOLD = 10  # errors per 5 minutes
DEFAULT_CRITICAL_LOG_THRESHOLD = 5  # critical logs per 5 minutes

# Trace thresholds
DEFAULT_TRACE_DURATION_THRESHOLD = 5000  # 5000ms
DEFAULT_TRACE_TIMEOUT_THRESHOLD = 30000  # 30000ms

# Health thresholds
DEFAULT_HEALTH_SCORE_THRESHOLD = 70
DEFAULT_UPTIME_THRESHOLD = 99.9  # percentage
DEFAULT_RESPONSE_TIME_HEALTH_THRESHOLD = 200  # ms
DEFAULT_ERROR_RATE_HEALTH_THRESHOLD = 0.01  # 1%

# Time constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800
SECONDS_PER_MONTH = 2592000
SECONDS_PER_YEAR = 31536000

# Aggregation intervals
AGGREGATION_INTERVALS = ['minute', 'hour', 'day', 'week', 'month']

# Environment names
ENVIRONMENT_DEVELOPMENT = 'development'
ENVIRONMENT_STAGING = 'staging'
ENVIRONMENT_PRODUCTION = 'production'

# HTTP status codes for metrics
HTTP_STATUS_SUCCESS = [200, 201, 202, 204]
HTTP_STATUS_REDIRECT = [301, 302, 303, 307, 308]
HTTP_STATUS_CLIENT_ERROR = [400, 401, 403, 404, 429]
HTTP_STATUS_SERVER_ERROR = [500, 502, 503, 504]

# Cache key prefixes
METRIC_CACHE_PREFIX = 'metric:'
LOG_CACHE_PREFIX = 'log:'
TRACE_CACHE_PREFIX = 'trace:'
ALERT_CACHE_PREFIX = 'alert:'
HEALTH_CACHE_PREFIX = 'health:'

# Error codes
ERROR_METRIC_INVALID_TYPE = 'METRIC_INVALID_TYPE'
ERROR_LOG_INVALID_LEVEL = 'LOG_INVALID_LEVEL'
ERROR_TRACE_INVALID_STATUS = 'TRACE_INVALID_STATUS'
ERROR_ALERT_INVALID_SEVERITY = 'ALERT_INVALID_SEVERITY'
ERROR_HEALTH_INVALID_STATUS = 'HEALTH_INVALID_STATUS'

# Success messages
SUCCESS_METRIC_RECORDED = 'Metric recorded successfully'
SUCCESS_LOG_RECORDED = 'Log recorded successfully'
SUCCESS_TRACE_STARTED = 'Trace span started successfully'
SUCCESS_TRACE_FINISHED = 'Trace span finished successfully'
SUCCESS_ALERT_CREATED = 'Alert created successfully'
SUCCESS_ALERT_ACKNOWLEDGED = 'Alert acknowledged successfully'
SUCCESS_ALERT_RESOLVED = 'Alert resolved successfully'

# Validation messages
VALIDATION_METRIC_NAME_REQUIRED = 'Metric name is required'
VALIDATION_METRIC_NAME_TOO_LONG = f'Metric name must not exceed {MAX_METRIC_NAME_LENGTH} characters'
VALIDATION_LOG_MESSAGE_REQUIRED = 'Log message is required'
VALIDATION_LOG_MESSAGE_TOO_LONG = f'Log message must not exceed {MAX_LOG_MESSAGE_LENGTH} characters'
VALIDATION_TRACE_OPERATION_NAME_REQUIRED = 'Operation name is required'
VALIDATION_ALERT_NAME_REQUIRED = 'Alert name is required'
VALIDATION_ALERT_MESSAGE_REQUIRED = 'Alert message is required'

# Notification messages
NOTIFICATION_ALERT_TRIGGERED = 'Alert triggered'
NOTIFICATION_HEALTH_DEGRADED = 'Health status degraded'
NOTIFICATION_HEALTH_UNHEALTHY = 'Health status unhealthy'
NOTIFICATION_METRIC_THRESHOLD_EXCEEDED = 'Metric threshold exceeded'
NOTIFICATION_LOG_THRESHOLD_EXCEEDED = 'Log threshold exceeded'
NOTIFICATION_TRACE_THRESHOLD_EXCEEDED = 'Trace threshold exceeded'

# Environment variables
ENV_TELEMETRY_ENABLED = 'TELEMETRY_ENABLED'
ENV_TRACING_ENABLED = 'TRACING_ENABLED'
ENV_ALERTING_ENABLED = 'ALERTING_ENABLED'
ENV_LOGGING_ENABLED = 'LOGGING_ENABLED'
ENV_TELEMETRY_SERVICE_NAME = 'TELEMETRY_SERVICE_NAME'
ENV_TELEMETRY_ENVIRONMENT = 'TELEMETRY_ENVIRONMENT'
