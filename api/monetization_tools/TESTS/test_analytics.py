"""TESTS/test_analytics.py - Analytics reporting tests."""
from ..A_B_TESTING.hypothesis_tester import HypothesisTester
from ..A_B_TESTING.confidence_calculator import ConfidenceCalculator
from ..ANALYTICS_REPORTING.predictive_analytics import RevenueForecaster
from ..ANALYTICS_REPORTING.custom_report_builder import CustomReportBuilder


class TestHypothesisTester:
    def test_large_difference_significant(self):
        result = HypothesisTester.is_significant(0.10, 10000, 0.15, 10000)
        assert result["significant"] is True

    def test_tiny_difference_not_significant(self):
        result = HypothesisTester.is_significant(0.10, 50, 0.101, 50)
        assert result["significant"] is False

    def test_min_sample_size_positive(self):
        n = HypothesisTester.min_sample_size(0.10, 0.05)
        assert n > 0


class TestConfidenceCalculator:
    def test_proportion_ci_bounds(self):
        result = ConfidenceCalculator.proportion_ci(50, 100)
        assert result["lower"] < result["mean"] < result["upper"]

    def test_empty_trials(self):
        result = ConfidenceCalculator.proportion_ci(0, 0)
        assert result["mean"] == 0


class TestRevenueForecaster:
    def test_linear_regression_slope(self):
        m, b = RevenueForecaster.linear_regression([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(m - 1.0) < 0.01

    def test_forecast_flat_series(self):
        m, b = RevenueForecaster.linear_regression([5.0, 5.0, 5.0])
        assert abs(m) < 0.001


class TestCustomReportBuilder:
    def test_dimensions_list(self):
        assert "date" in CustomReportBuilder.available_dimensions()

    def test_validate_bad_dimension(self):
        errors = CustomReportBuilder.validate(["nonexistent"], ["revenue"])
        assert len(errors) > 0

    def test_validate_good(self):
        errors = CustomReportBuilder.validate(["date"], ["revenue"])
        assert errors == []
