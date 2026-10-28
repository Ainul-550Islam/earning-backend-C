# publisher_tools/tests/test_views_reporting.py
"""
Tests for ReportingViewSet (views_reporting.py)।

Covers all 13 @action endpoints:
  monthly_report, monthly_trend, revenue_forecast, next_month_forecast,
  ecpm_breakdown, ecpm_trend, ecpm_suggestions, chart_data,
  top_units, revenue_trend, revenue_by_dimension,
  fill_rate_issues, fill_impact, fill_rate_by_unit,
  performance_alerts, export_report

Pattern: pytest + APIClient + conftest.py fixtures
Auth:    publisher_client → force_authenticate(user=publisher_user)
"""

import pytest

BASE = '/api/publisher-tools/reports'


# ══════════════════════════════════════════════════════════════════════════════
# MONTHLY REPORT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMonthlyReport:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/monthly/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/monthly/').status_code in (200, 503)

    def test_explicit_year_month(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly/', {'year': 2025, 'month': 1})
        assert r.status_code in (200, 503)

    def test_invalid_month_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly/', {'year': 2025, 'month': 13})
        assert r.status_code == 400

    def test_invalid_year_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly/', {'year': 1899, 'month': 1})
        assert r.status_code == 400

    def test_response_keys_when_200(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'year' in data
            assert 'month' in data


@pytest.mark.django_db
class TestMonthlyTrend:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/monthly-trend/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/monthly-trend/').status_code in (200, 503)

    def test_custom_months_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly-trend/', {'months': 3})
        assert r.status_code in (200, 503)

    def test_response_has_trend_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/monthly-trend/')
        if r.status_code == 200:
            assert 'trend' in r.json().get('data', {})


# ══════════════════════════════════════════════════════════════════════════════
# REVENUE FORECAST
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRevenueForecast:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/revenue-forecast/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/revenue-forecast/').status_code in (200, 503)

    def test_custom_days_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-forecast/', {'days': 7})
        assert r.status_code in (200, 503)

    def test_response_has_forecast_keys(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-forecast/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'days_ahead' in data or 'confidence' in data

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/revenue-forecast/').status_code != 500


@pytest.mark.django_db
class TestNextMonthForecast:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/next-month-forecast/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/next-month-forecast/').status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# eCPM BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEcpmBreakdown:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/ecpm-breakdown/').status_code in (401, 403)

    def test_default_by_country(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ecpm-breakdown/').status_code in (200, 503)

    def test_by_format(self, publisher_client):
        r = publisher_client.get(f'{BASE}/ecpm-breakdown/', {'by': 'format'})
        assert r.status_code in (200, 503)

    def test_invalid_by_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/ecpm-breakdown/', {'by': 'invalid'})
        assert r.status_code == 400

    def test_with_explicit_date_range(self, publisher_client):
        r = publisher_client.get(
            f'{BASE}/ecpm-breakdown/',
            {'start': '2025-01-01', 'end': '2025-01-31', 'by': 'country'},
        )
        assert r.status_code in (200, 503)

    def test_invalid_date_returns_400(self, publisher_client):
        r = publisher_client.get(
            f'{BASE}/ecpm-breakdown/',
            {'start': 'bad-date', 'end': '2025-01-31'},
        )
        assert r.status_code == 400

    def test_response_has_rows_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/ecpm-breakdown/')
        if r.status_code == 200:
            assert 'rows' in r.json().get('data', {})


@pytest.mark.django_db
class TestEcpmTrend:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/ecpm-trend/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ecpm-trend/').status_code in (200, 503)

    def test_with_days_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/ecpm-trend/', {'days': 7})
        assert r.status_code in (200, 503)


@pytest.mark.django_db
class TestEcpmSuggestions:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/ecpm-suggestions/').status_code in (401, 403)

    def test_returns_suggestions_list(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ecpm-suggestions/').status_code in (200, 503)

    def test_response_has_count_and_suggestions(self, publisher_client):
        r = publisher_client.get(f'{BASE}/ecpm-suggestions/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'suggestions' in data
            assert 'count' in data


# ══════════════════════════════════════════════════════════════════════════════
# CHART DATA
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestChartData:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/chart-data/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/chart-data/').status_code in (200, 503)

    def test_invalid_period_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/chart-data/', {'period': 'totally_invalid'})
        assert r.status_code == 400

    def test_invalid_metric_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/chart-data/', {'metric': 'not_a_metric'})
        assert r.status_code == 400

    def test_valid_revenue_metric(self, publisher_client):
        r = publisher_client.get(f'{BASE}/chart-data/', {'metric': 'revenue', 'period': 'last_7_days'})
        assert r.status_code in (200, 503)

    def test_response_has_chart_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/chart-data/')
        if r.status_code == 200:
            assert 'chart' in r.json().get('data', {})


# ══════════════════════════════════════════════════════════════════════════════
# TOP UNITS / REVENUE TREND / REVENUE BY DIMENSION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTopUnits:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/top-units/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/top-units/').status_code in (200, 503)

    def test_custom_limit_and_days(self, publisher_client):
        r = publisher_client.get(f'{BASE}/top-units/', {'days': 7, 'limit': 5})
        assert r.status_code in (200, 503)

    def test_response_has_units_and_count(self, publisher_client):
        r = publisher_client.get(f'{BASE}/top-units/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'units' in data
            assert 'count' in data


@pytest.mark.django_db
class TestRevenueTrend:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/revenue-trend/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/revenue-trend/').status_code in (200, 503)

    def test_with_days_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-trend/', {'days': 14})
        assert r.status_code in (200, 503)


@pytest.mark.django_db
class TestRevenueByDimension:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/revenue-by-dimension/').status_code in (401, 403)

    def test_default_country_dimension(self, publisher_client):
        assert publisher_client.get(f'{BASE}/revenue-by-dimension/').status_code in (200, 503)

    def test_invalid_dimension_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-by-dimension/', {'dimension': 'invalid'})
        assert r.status_code == 400

    def test_format_dimension(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-by-dimension/', {'dimension': 'format'})
        assert r.status_code in (200, 503)

    def test_response_has_rows_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/revenue-by-dimension/')
        if r.status_code == 200:
            assert 'rows' in r.json().get('data', {})


# ══════════════════════════════════════════════════════════════════════════════
# FILL RATE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFillRateIssues:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/fill-rate-issues/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/fill-rate-issues/').status_code in (200, 503)

    def test_with_custom_threshold(self, publisher_client):
        r = publisher_client.get(f'{BASE}/fill-rate-issues/', {'threshold': 70})
        assert r.status_code in (200, 503)

    def test_response_has_issues_and_count(self, publisher_client):
        r = publisher_client.get(f'{BASE}/fill-rate-issues/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'issues' in data
            assert 'count' in data


@pytest.mark.django_db
class TestFillImpact:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/fill-impact/').status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/fill-impact/').status_code == 400

    def test_valid_unit_id(self, publisher_client, ad_unit):
        r = publisher_client.get(
            f'{BASE}/fill-impact/', {'unit_id': ad_unit.unit_id}
        )
        assert r.status_code in (200, 503)

    def test_nonexistent_unit_returns_404(self, publisher_client):
        r = publisher_client.get(
            f'{BASE}/fill-impact/', {'unit_id': 'UNIT-NONEXISTENT-9999'}
        )
        assert r.status_code in (404, 503)

    def test_with_custom_target_fill(self, publisher_client, ad_unit):
        r = publisher_client.get(
            f'{BASE}/fill-impact/', {'unit_id': ad_unit.unit_id, 'target_fill': 90}
        )
        assert r.status_code in (200, 503)


@pytest.mark.django_db
class TestFillRateByUnit:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/fill-rate-by-unit/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/fill-rate-by-unit/').status_code in (200, 503)

    def test_with_days_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/fill-rate-by-unit/', {'days': 14})
        assert r.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE ALERTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReportingPerformanceAlerts:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/alerts/').status_code in (401, 403)

    def test_returns_alerts_list(self, publisher_client):
        assert publisher_client.get(f'{BASE}/alerts/').status_code in (200, 503)

    def test_response_has_alerts_and_count(self, publisher_client):
        r = publisher_client.get(f'{BASE}/alerts/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'alerts' in data
            assert 'count' in data


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT REPORT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestExportReport:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/export/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_default_body_returns_data(self, publisher_client):
        assert publisher_client.post(
            f'{BASE}/export/', {}, format='json'
        ).status_code in (200, 503)

    def test_json_format_returns_json(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/export/',
            {'metrics': ['revenue'], 'dimensions': ['date'], 'format': 'json'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_csv_format_returns_csv_or_error(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/export/',
            {'metrics': ['revenue', 'impressions'], 'dimensions': ['date'], 'format': 'csv'},
            format='json',
        )
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert 'csv' in r.get('Content-Type', '') or 'json' in r.get('Content-Type', '')

    def test_invalid_format_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/export/', {'format': 'xlsx'}, format='json'
        )
        assert r.status_code == 400

    def test_invalid_date_format_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/export/',
            {'start_date': 'not-a-date', 'end_date': '2025-01-31'},
            format='json',
        )
        assert r.status_code == 400

    def test_start_after_end_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/export/',
            {'start_date': '2025-02-01', 'end_date': '2025-01-01'},
            format='json',
        )
        assert r.status_code == 400
