"""
Tests for Real-time Dashboard Backend utility functions.
"""
import pytest
from api.realtime_dashboard.utils import (
    format_metric_value,
    calculate_metric_delta,
    calculate_metric_percentage,
    check_metric_thresholds,
    aggregate_metrics,
    validate_widget_configuration,
    sanitize_dashboard_name,
)


class TestFormatMetricValue:
    def test_with_unit(self):
        assert format_metric_value(42.0, '%') == '42.0 %'

    def test_without_unit(self):
        assert format_metric_value(42.0, '') == '42.0'

    def test_zero(self):
        assert format_metric_value(0.0, 'ms') == '0.0 ms'


class TestCalculateMetricDelta:
    def test_positive_delta(self):
        assert calculate_metric_delta(100.0, 80.0) == pytest.approx(20.0)

    def test_negative_delta(self):
        assert calculate_metric_delta(80.0, 100.0) == pytest.approx(-20.0)

    def test_none_previous(self):
        assert calculate_metric_delta(100.0, None) == 0.0

    def test_zero_delta(self):
        assert calculate_metric_delta(50.0, 50.0) == 0.0


class TestCalculateMetricPercentage:
    def test_increase(self):
        assert calculate_metric_percentage(120.0, 100.0) == pytest.approx(20.0)

    def test_decrease(self):
        assert calculate_metric_percentage(80.0, 100.0) == pytest.approx(-20.0)

    def test_none_previous(self):
        assert calculate_metric_percentage(100.0, None) == 0.0

    def test_zero_previous(self):
        assert calculate_metric_percentage(100.0, 0) == 0.0


class TestCheckMetricThresholds:
    def test_critical(self):
        assert check_metric_thresholds(95.0, warning=80.0, critical=90.0) == 'critical'

    def test_warning(self):
        assert check_metric_thresholds(85.0, warning=80.0, critical=90.0) == 'warning'

    def test_normal(self):
        assert check_metric_thresholds(50.0, warning=80.0, critical=90.0) == 'normal'

    def test_no_thresholds(self):
        assert check_metric_thresholds(999.0) == 'normal'

    def test_exactly_at_critical(self):
        assert check_metric_thresholds(90.0, warning=80.0, critical=90.0) == 'critical'

    def test_exactly_at_warning(self):
        assert check_metric_thresholds(80.0, warning=80.0, critical=90.0) == 'warning'


class TestAggregateMetrics:
    def test_basic_aggregation(self):
        metrics = [{'value': 10.0}, {'value': 20.0}, {'value': 30.0}]
        result = aggregate_metrics(metrics)
        assert result['sum'] == pytest.approx(60.0)
        assert result['avg'] == pytest.approx(20.0)
        assert result['count'] == 3
        assert result['min'] == pytest.approx(10.0)
        assert result['max'] == pytest.approx(30.0)

    def test_empty_list(self):
        assert aggregate_metrics([]) == {}

    def test_single_metric(self):
        result = aggregate_metrics([{'value': 42.0}])
        assert result['sum'] == pytest.approx(42.0)
        assert result['min'] == result['max'] == pytest.approx(42.0)


class TestValidateWidgetConfiguration:
    def test_valid_chart_config(self):
        config = {'type': 'chart', 'data': [], 'chartType': 'line'}
        assert validate_widget_configuration(config) is True

    def test_chart_missing_required_fields(self):
        assert validate_widget_configuration({'type': 'chart'}) is False

    def test_non_chart_type_always_valid(self):
        assert validate_widget_configuration({'type': 'table'}) is True

    def test_empty_dict(self):
        assert validate_widget_configuration({}) is True

    def test_not_a_dict(self):
        assert validate_widget_configuration([1, 2, 3]) is False


class TestSanitizeDashboardName:
    def test_removes_special_chars(self):
        result = sanitize_dashboard_name('My<Dashboard>!')
        assert '<' not in result
        assert '>' not in result
        assert '!' not in result

    def test_keeps_alphanumeric_and_spaces(self):
        result = sanitize_dashboard_name('My Dashboard 2024')
        assert 'My' in result
        assert 'Dashboard' in result

    def test_strips_whitespace(self):
        result = sanitize_dashboard_name('  trimmed  ')
        assert result == result.strip()

    def test_empty_string(self):
        assert sanitize_dashboard_name('') == ''
