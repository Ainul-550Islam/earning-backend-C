"""
Tests for validators.py — every validator, valid + invalid input.
"""
import pytest
from django.core.exceptions import ValidationError
from ..validators import (
    MetricNameValidator, MetricValueValidator,
    LogLevelValidator, LogMessageValidator,
    TraceIdValidator, OperationNameValidator,
    AlertNameValidator, HealthScoreValidator,
    ErrorRateValidator, GridSizeValidator, ServiceNameValidator,
)


# ── MetricNameValidator ───────────────────────────────────────────────────────

class TestMetricNameValidator:
    validator = MetricNameValidator()

    def test_valid_simple_name(self):
        self.validator('cpu_usage')   # no error

    def test_valid_with_colon(self):
        self.validator('http:request_total')

    def test_valid_with_dot(self):
        self.validator('app.metric.name')

    def test_valid_alphanumeric(self):
        self.validator('metric123')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_spaces(self):
        with pytest.raises(ValidationError):
            self.validator('metric name')

    def test_rejects_slash(self):
        with pytest.raises(ValidationError):
            self.validator('metric/name')

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            self.validator('x' * 256)

    def test_equality(self):
        assert MetricNameValidator() == MetricNameValidator()


# ── MetricValueValidator ──────────────────────────────────────────────────────

class TestMetricValueValidator:
    validator = MetricValueValidator()

    def test_valid_positive(self):
        self.validator(42.5)

    def test_valid_zero(self):
        self.validator(0.0)

    def test_valid_negative(self):
        self.validator(-10.0)

    def test_rejects_none(self):
        with pytest.raises(ValidationError):
            self.validator(None)

    def test_rejects_nan(self):
        import math
        with pytest.raises(ValidationError):
            self.validator(float('nan'))

    def test_rejects_inf(self):
        import math
        with pytest.raises(ValidationError):
            self.validator(float('inf'))

    def test_rejects_neg_inf(self):
        import math
        with pytest.raises(ValidationError):
            self.validator(float('-inf'))


# ── LogLevelValidator ─────────────────────────────────────────────────────────

class TestLogLevelValidator:
    validator = LogLevelValidator()

    @pytest.mark.parametrize("level", ['debug', 'info', 'warning', 'error', 'critical'])
    def test_valid_levels(self, level):
        self.validator(level)

    def test_rejects_invalid_level(self):
        with pytest.raises(ValidationError):
            self.validator('trace')

    def test_rejects_uppercase(self):
        with pytest.raises(ValidationError):
            self.validator('INFO')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')


# ── LogMessageValidator ───────────────────────────────────────────────────────

class TestLogMessageValidator:
    validator = LogMessageValidator()

    def test_valid_message(self):
        self.validator('Request processed successfully.')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            self.validator('   ')


# ── TraceIdValidator ──────────────────────────────────────────────────────────

class TestTraceIdValidator:
    validator = TraceIdValidator()

    def test_valid_uuid_style(self):
        self.validator('abc123-def456-ghi789')

    def test_valid_hex_string(self):
        self.validator('a1b2c3d4e5f6')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_slash(self):
        with pytest.raises(ValidationError):
            self.validator('trace/span')

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            self.validator('a' * 256)


# ── OperationNameValidator ────────────────────────────────────────────────────

class TestOperationNameValidator:
    validator = OperationNameValidator()

    def test_valid_name(self):
        self.validator('GET /api/users')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            self.validator('   ')


# ── AlertNameValidator ────────────────────────────────────────────────────────

class TestAlertNameValidator:
    validator = AlertNameValidator()

    def test_valid_name(self):
        self.validator('High CPU Alert')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            self.validator('x' * 256)


# ── HealthScoreValidator ──────────────────────────────────────────────────────

class TestHealthScoreValidator:
    validator = HealthScoreValidator()

    @pytest.mark.parametrize("score", [0, 50, 100])
    def test_valid_scores(self, score):
        self.validator(score)

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            self.validator(-1)

    def test_rejects_above_100(self):
        with pytest.raises(ValidationError):
            self.validator(101)


# ── ErrorRateValidator ────────────────────────────────────────────────────────

class TestErrorRateValidator:
    validator = ErrorRateValidator()

    @pytest.mark.parametrize("rate", [0.0, 50.0, 100.0])
    def test_valid_rates(self, rate):
        self.validator(rate)

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            self.validator(-0.1)

    def test_rejects_above_100(self):
        with pytest.raises(ValidationError):
            self.validator(100.1)


# ── GridSizeValidator ─────────────────────────────────────────────────────────

class TestGridSizeValidator:
    validator = GridSizeValidator()

    @pytest.mark.parametrize("size", [1, 6, 12])
    def test_valid_sizes(self, size):
        self.validator(size)

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            self.validator(0)

    def test_rejects_above_12(self):
        with pytest.raises(ValidationError):
            self.validator(13)


# ── ServiceNameValidator ──────────────────────────────────────────────────────

class TestServiceNameValidator:
    validator = ServiceNameValidator()

    def test_valid_name(self):
        self.validator('my-service')

    def test_valid_with_dot(self):
        self.validator('api.service.v1')

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            self.validator('')

    def test_rejects_slash(self):
        with pytest.raises(ValidationError):
            self.validator('my/service')

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            self.validator('x' * 256)
