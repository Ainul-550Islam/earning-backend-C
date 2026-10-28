"""
Django field validators for Telemetry Observability.

SINGLE SOURCE OF TRUTH for all field validation logic.
Used in:
  - models (field validators=[...])
  - serializers (validate_<field> methods call these)

validator.py (legacy custom base class) is deprecated — do NOT use it.
"""
import re
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Metric validators
# ---------------------------------------------------------------------------

class MetricNameValidator:
    """
    Validates that a metric name contains only allowed characters.
    Pattern: alphanumeric, underscore, colon, dot — follows Prometheus naming conventions.
    """
    PATTERN = re.compile(r'^[a-zA-Z0-9_:.]+$')

    def __call__(self, value: str) -> None:
        if not value:
            raise ValidationError("Metric name is required.")
        if len(value) > 255:
            raise ValidationError("Metric name must not exceed 255 characters.")
        if not self.PATTERN.match(value):
            raise ValidationError(
                "Metric name may only contain letters, digits, underscores, colons, and dots."
            )

    def __eq__(self, other):
        return isinstance(other, MetricNameValidator)


class MetricValueValidator:
    """Validates that a metric value is a finite number."""

    def __call__(self, value) -> None:
        import math
        if value is None:
            raise ValidationError("Metric value cannot be null.")
        if math.isnan(value) or math.isinf(value):
            raise ValidationError("Metric value must be a finite number.")

    def __eq__(self, other):
        return isinstance(other, MetricValueValidator)


# ---------------------------------------------------------------------------
# Log validators
# ---------------------------------------------------------------------------

class LogLevelValidator:
    """Validates that a log level is one of the known levels."""
    VALID_LEVELS = {'debug', 'info', 'warning', 'error', 'critical'}

    def __call__(self, value: str) -> None:
        if value not in self.VALID_LEVELS:
            raise ValidationError(
                f"Invalid log level '{value}'. Must be one of: {', '.join(sorted(self.VALID_LEVELS))}."
            )

    def __eq__(self, other):
        return isinstance(other, LogLevelValidator)


class LogMessageValidator:
    """Validates that a log message is not blank."""

    def __call__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Log message cannot be empty or whitespace.")

    def __eq__(self, other):
        return isinstance(other, LogMessageValidator)


# ---------------------------------------------------------------------------
# Trace validators
# ---------------------------------------------------------------------------

class TraceIdValidator:
    """Validates trace_id / span_id format (non-empty alphanumeric-dash-underscore string)."""
    PATTERN = re.compile(r'^[a-zA-Z0-9\-_]+$')

    def __call__(self, value: str) -> None:
        if not value:
            raise ValidationError("Trace/Span ID cannot be empty.")
        if len(value) > 255:
            raise ValidationError("Trace/Span ID must not exceed 255 characters.")
        if not self.PATTERN.match(value):
            raise ValidationError(
                "Trace/Span ID may only contain letters, digits, hyphens, and underscores."
            )

    def __eq__(self, other):
        return isinstance(other, TraceIdValidator)


class OperationNameValidator:
    """Validates that an operation name is non-empty."""

    def __call__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Operation name cannot be empty or whitespace.")

    def __eq__(self, other):
        return isinstance(other, OperationNameValidator)


# ---------------------------------------------------------------------------
# Alert validators
# ---------------------------------------------------------------------------

class AlertNameValidator:
    """Validates that an alert name is non-empty and within length limits."""

    def __call__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Alert name cannot be empty or whitespace.")
        if len(value) > 255:
            raise ValidationError("Alert name must not exceed 255 characters.")

    def __eq__(self, other):
        return isinstance(other, AlertNameValidator)


# ---------------------------------------------------------------------------
# Health validators
# ---------------------------------------------------------------------------

class HealthScoreValidator:
    """Validates that a health score is an integer in [0, 100]."""

    def __call__(self, value) -> None:
        if not (0 <= value <= 100):
            raise ValidationError(f"Health score must be between 0 and 100, got {value}.")

    def __eq__(self, other):
        return isinstance(other, HealthScoreValidator)


class ErrorRateValidator:
    """Validates that an error rate is a float in [0.0, 100.0]."""

    def __call__(self, value) -> None:
        if not (0.0 <= value <= 100.0):
            raise ValidationError(f"Error rate must be between 0 and 100, got {value}.")

    def __eq__(self, other):
        return isinstance(other, ErrorRateValidator)


# ---------------------------------------------------------------------------
# Dashboard validators
# ---------------------------------------------------------------------------

class GridSizeValidator:
    """Validates that a grid width/height is in [1, 12] (12-column grid)."""

    def __call__(self, value) -> None:
        if not (1 <= value <= 12):
            raise ValidationError(f"Grid size must be between 1 and 12, got {value}.")

    def __eq__(self, other):
        return isinstance(other, GridSizeValidator)


class ServiceNameValidator:
    """Validates that a service name is non-empty and safe (no path separators)."""
    PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

    def __call__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Service name cannot be empty.")
        if len(value) > 255:
            raise ValidationError("Service name must not exceed 255 characters.")
        if not self.PATTERN.match(value):
            raise ValidationError(
                "Service name may only contain letters, digits, hyphens, underscores, and dots."
            )

    def __eq__(self, other):
        return isinstance(other, ServiceNameValidator)


__all__ = [
    'MetricNameValidator',
    'MetricValueValidator',
    'LogLevelValidator',
    'LogMessageValidator',
    'TraceIdValidator',
    'OperationNameValidator',
    'AlertNameValidator',
    'HealthScoreValidator',
    'ErrorRateValidator',
    'GridSizeValidator',
    'ServiceNameValidator',
]
