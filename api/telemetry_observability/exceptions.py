"""
Custom exceptions for Telemetry Observability.
"""
from typing import Optional


class TelemetryException(Exception):
    """Base exception for telemetry-related errors."""
    
    def __init__(self, message: str, code: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            code: Optional error code
        """
        self.message = message
        self.code = code
        super().__init__(self.message)


class MetricException(TelemetryException):
    """Exception raised for metric-related errors."""
    
    def __init__(self, message: str, metric_name: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            metric_name: Optional metric name
        """
        self.metric_name = metric_name
        super().__init__(message, "METRIC_ERROR")


class LogException(TelemetryException):
    """Exception raised for log-related errors."""
    
    def __init__(self, message: str, log_level: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            log_level: Optional log level
        """
        self.log_level = log_level
        super().__init__(message, "LOG_ERROR")


class TraceException(TelemetryException):
    """Exception raised for trace-related errors."""
    
    def __init__(self, message: str, trace_id: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            trace_id: Optional trace ID
        """
        self.trace_id = trace_id
        super().__init__(message, "TRACE_ERROR")


class AlertException(TelemetryException):
    """Exception raised for alert-related errors."""
    
    def __init__(self, message: str, alert_name: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            alert_name: Optional alert name
        """
        self.alert_name = alert_name
        super().__init__(message, "ALERT_ERROR")


class HealthCheckException(TelemetryException):
    """Exception raised for health check errors."""
    
    def __init__(self, message: str, service_name: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            service_name: Optional service name
        """
        self.service_name = service_name
        super().__init__(message, "HEALTH_CHECK_ERROR")


class DashboardException(TelemetryException):
    """Exception raised for dashboard-related errors."""
    
    def __init__(self, message: str, widget_name: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Error message
            widget_name: Optional widget name
        """
        self.widget_name = widget_name
        super().__init__(message, "DASHBOARD_ERROR")


class MetricThresholdExceededError(MetricException):
    """Exception raised when a metric threshold is exceeded."""
    
    def __init__(self, metric_name: str, threshold: float, actual_value: float):
        """
        Initialize the exception.
        
        Args:
            metric_name: Name of the metric
            threshold: Threshold value
            actual_value: Actual value
        """
        self.threshold = threshold
        self.actual_value = actual_value
        super().__init__(
            f"Metric '{metric_name}' threshold {threshold} exceeded with value {actual_value}",
            "METRIC_THRESHOLD_EXCEEDED"
        )


class LogThresholdExceededError(LogException):
    """Exception raised when a log threshold is exceeded."""
    
    def __init__(self, log_level: str, threshold: int, actual_count: int):
        """
        Initialize the exception.
        
        Args:
            log_level: Log level
            threshold: Threshold count
            actual_count: Actual count
        """
        self.threshold = threshold
        self.actual_count = actual_count
        super().__init__(
            f"Log level '{log_level}' threshold {threshold} exceeded with count {actual_count}",
            "LOG_THRESHOLD_EXCEEDED"
        )


class TraceThresholdExceededError(TraceException):
    """Exception raised when a trace threshold is exceeded."""
    
    def __init__(self, operation_name: str, threshold: float, actual_duration: float):
        """
        Initialize the exception.
        
        Args:
            operation_name: Operation name
            threshold: Threshold duration
            actual_duration: Actual duration
        """
        self.threshold = threshold
        self.actual_duration = actual_duration
        super().__init__(
            f"Trace operation '{operation_name}' threshold {threshold}ms exceeded with duration {actual_duration}ms",
            "TRACE_THRESHOLD_EXCEEDED"
        )


class HealthThresholdExceededError(HealthCheckException):
    """Exception raised when a health threshold is exceeded."""
    
    def __init__(self, service_name: str, threshold: int, actual_score: int):
        """
        Initialize the exception.
        
        Args:
            service_name: Service name
            threshold: Threshold score
            actual_score: Actual score
        """
        self.threshold = threshold
        self.actual_score = actual_score
        super().__init__(
            f"Service '{service_name}' health threshold {threshold} exceeded with score {actual_score}",
            "HEALTH_THRESHOLD_EXCEEDED"
        )


class InvalidMetricTypeError(MetricException):
    """Exception raised for invalid metric type."""
    
    def __init__(self, metric_type: str):
        """
        Initialize the exception.
        
        Args:
            metric_type: Invalid metric type
        """
        super().__init__(f"Invalid metric type: {metric_type}", "INVALID_METRIC_TYPE")


class InvalidLogLevelError(LogException):
    """Exception raised for invalid log level."""
    
    def __init__(self, log_level: str):
        """
        Initialize the exception.
        
        Args:
            log_level: Invalid log level
        """
        super().__init__(f"Invalid log level: {log_level}", "INVALID_LOG_LEVEL")


class InvalidAlertSeverityError(AlertException):
    """Exception raised for invalid alert severity."""
    
    def __init__(self, severity: str):
        """
        Initialize the exception.
        
        Args:
            severity: Invalid severity
        """
        super().__init__(f"Invalid alert severity: {severity}", "INVALID_ALERT_SEVERITY")
