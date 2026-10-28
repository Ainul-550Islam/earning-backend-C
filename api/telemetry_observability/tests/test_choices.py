"""
Tests for choices.py — verifies all TextChoices have correct values.
"""
import pytest
from ..choices import (
    MetricTypeChoices, LogLevelChoices, TraceStatusChoices,
    AlertTypeChoices, AlertSeverityChoices, AlertStatusChoices,
    HealthStatusChoices, WidgetTypeChoices, DataSourceChoices,
    EnvironmentChoices, AggregationTypeChoices, TimeWindowChoices,
)


class TestMetricTypeChoices:
    def test_all_values_present(self):
        assert set(MetricTypeChoices.values) == {'counter', 'gauge', 'histogram', 'summary'}

    def test_labels_present(self):
        labels = [label for _, label in MetricTypeChoices.choices]
        assert 'Counter' in labels
        assert 'Gauge' in labels
        assert 'Histogram' in labels
        assert 'Summary' in labels

    def test_counter_value(self):
        assert MetricTypeChoices.COUNTER == 'counter'

    def test_gauge_value(self):
        assert MetricTypeChoices.GAUGE == 'gauge'

    def test_histogram_value(self):
        assert MetricTypeChoices.HISTOGRAM == 'histogram'

    def test_summary_value(self):
        assert MetricTypeChoices.SUMMARY == 'summary'


class TestLogLevelChoices:
    def test_all_values_present(self):
        assert set(LogLevelChoices.values) == {'debug', 'info', 'warning', 'error', 'critical'}

    def test_debug_value(self):
        assert LogLevelChoices.DEBUG == 'debug'

    def test_critical_value(self):
        assert LogLevelChoices.CRITICAL == 'critical'

    def test_ordered_by_severity(self):
        values = LogLevelChoices.values
        assert values.index('debug')    < values.index('info')
        assert values.index('info')     < values.index('warning')
        assert values.index('warning')  < values.index('error')
        assert values.index('error')    < values.index('critical')


class TestTraceStatusChoices:
    def test_all_values_present(self):
        assert set(TraceStatusChoices.values) == {'success', 'error', 'timeout'}

    def test_success_value(self):
        assert TraceStatusChoices.SUCCESS == 'success'

    def test_error_value(self):
        assert TraceStatusChoices.ERROR == 'error'

    def test_timeout_value(self):
        assert TraceStatusChoices.TIMEOUT == 'timeout'


class TestAlertTypeChoices:
    def test_all_values_present(self):
        assert set(AlertTypeChoices.values) == {'metric', 'log', 'trace', 'health', 'custom'}

    def test_metric_value(self):
        assert AlertTypeChoices.METRIC == 'metric'


class TestAlertSeverityChoices:
    def test_all_values_present(self):
        assert set(AlertSeverityChoices.values) == {'info', 'warning', 'error', 'critical'}

    def test_critical_value(self):
        assert AlertSeverityChoices.CRITICAL == 'critical'


class TestAlertStatusChoices:
    def test_all_values_present(self):
        assert set(AlertStatusChoices.values) == {'open', 'acknowledged', 'resolved', 'suppressed'}

    def test_open_value(self):
        assert AlertStatusChoices.OPEN == 'open'

    def test_resolved_value(self):
        assert AlertStatusChoices.RESOLVED == 'resolved'


class TestHealthStatusChoices:
    def test_all_values_present(self):
        assert set(HealthStatusChoices.values) == {'healthy', 'degraded', 'unhealthy', 'unknown'}

    def test_healthy_value(self):
        assert HealthStatusChoices.HEALTHY == 'healthy'

    def test_unhealthy_value(self):
        assert HealthStatusChoices.UNHEALTHY == 'unhealthy'


class TestWidgetTypeChoices:
    def test_contains_ten_types(self):
        assert len(WidgetTypeChoices.values) == 10

    def test_line_chart_present(self):
        assert 'line_chart' in WidgetTypeChoices.values

    def test_metric_card_present(self):
        assert 'metric_card' in WidgetTypeChoices.values


class TestDataSourceChoices:
    def test_all_sources_present(self):
        assert set(DataSourceChoices.values) == {'metric', 'log', 'trace', 'alert', 'health', 'custom'}


class TestEnvironmentChoices:
    def test_all_envs_present(self):
        assert set(EnvironmentChoices.values) == {'development', 'staging', 'production'}


class TestChoicesAreTextChoices:
    """Verify all choice classes are Django TextChoices (model-compatible)."""
    from django.db.models import TextChoices

    def test_metric_type_is_text_choices(self):
        from django.db.models import TextChoices
        assert issubclass(MetricTypeChoices, TextChoices)

    def test_log_level_is_text_choices(self):
        from django.db.models import TextChoices
        assert issubclass(LogLevelChoices, TextChoices)

    def test_alert_severity_is_text_choices(self):
        from django.db.models import TextChoices
        assert issubclass(AlertSeverityChoices, TextChoices)

    def test_health_status_is_text_choices(self):
        from django.db.models import TextChoices
        assert issubclass(HealthStatusChoices, TextChoices)
