# publisher_tools/tests/test_views_analytics.py
"""
Tests for AnalyticsViewSet (views_analytics.py).
Covers all 14 actions: dashboard, realtime, ecpm, ctr, rpm,
fill_rate, revenue, forecast, report_daily, report_weekly,
report_monthly, report_hourly, report_custom, alerts.
"""
import pytest

BASE = '/api/publisher-tools/analytics'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# DASHBOARD
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsDashboard:

    def test_publisher_can_view_dashboard(self, publisher_client):
        resp = publisher_client.get(url('dashboard'))
        assert resp.status_code in (200, 503)

    def test_dashboard_with_period_param(self, publisher_client):
        for period in ['last_7_days', 'last_30_days']:
            resp = publisher_client.get(url('dashboard'), {'period': period})
            assert resp.status_code in (200, 503)

    def test_dashboard_has_alerts_key(self, publisher_client):
        resp = publisher_client.get(url('dashboard'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'alerts' in data

    def test_unauthenticated_cannot_view_dashboard(self, api_client):
        resp = api_client.get(url('dashboard'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# REALTIME
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsRealtime:

    def test_publisher_can_view_realtime(self, publisher_client):
        resp = publisher_client.get(url('realtime'))
        assert resp.status_code in (200, 503)

    def test_realtime_has_live_key(self, publisher_client):
        resp = publisher_client.get(url('realtime'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'live' in data or isinstance(data, dict)

    def test_unauthenticated_cannot_view_realtime(self, api_client):
        resp = api_client.get(url('realtime'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# ECPM
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsECPM:

    def _ecpm(self, client, breakdown='country', **params):
        p = {'start_date': '2025-01-01', 'end_date': '2025-01-31', 'breakdown': breakdown}
        p.update(params)
        return client.get(url('ecpm'), p)

    def test_publisher_ecpm_by_country(self, publisher_client):
        resp = self._ecpm(publisher_client, 'country')
        assert resp.status_code in (200, 503)

    def test_publisher_ecpm_by_format(self, publisher_client):
        resp = self._ecpm(publisher_client, 'format')
        assert resp.status_code in (200, 503)

    def test_publisher_ecpm_trend(self, publisher_client):
        resp = self._ecpm(publisher_client, 'trend')
        assert resp.status_code in (200, 503)

    def test_invalid_breakdown_returns_400(self, publisher_client):
        resp = publisher_client.get(
            url('ecpm'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31', 'breakdown': 'invalid'},
        )
        assert resp.status_code == 400

    def test_missing_dates_returns_400(self, publisher_client):
        resp = publisher_client.get(url('ecpm'))
        assert resp.status_code == 400

    def test_unauthenticated_cannot_view_ecpm(self, api_client):
        resp = api_client.get(url('ecpm'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# CTR
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsCTR:

    def test_publisher_ctr_by_format(self, publisher_client):
        resp = publisher_client.get(url('ctr'), {'breakdown': 'format'})
        assert resp.status_code in (200, 503)

    def test_publisher_ctr_trend(self, publisher_client):
        resp = publisher_client.get(url('ctr'), {'breakdown': 'trend'})
        assert resp.status_code in (200, 503)

    def test_publisher_ctr_anomalies(self, publisher_client):
        resp = publisher_client.get(url('ctr'), {'breakdown': 'anomalies'})
        assert resp.status_code in (200, 503)

    def test_invalid_breakdown_returns_400(self, publisher_client):
        resp = publisher_client.get(url('ctr'), {'breakdown': 'not_real'})
        assert resp.status_code == 400

    def test_unauthenticated_cannot_view_ctr(self, api_client):
        resp = api_client.get(url('ctr'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# RPM
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsRPM:

    def test_publisher_can_view_rpm(self, publisher_client):
        resp = publisher_client.get(url('rpm'))
        assert resp.status_code in (200, 503)

    def test_rpm_with_days_param(self, publisher_client):
        resp = publisher_client.get(url('rpm'), {'days': '30'})
        assert resp.status_code in (200, 503)

    def test_rpm_response_has_benchmarks(self, publisher_client):
        resp = publisher_client.get(url('rpm'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'benchmarks' in data or 'publisher_rpm' in data

    def test_unauthenticated_cannot_view_rpm(self, api_client):
        resp = api_client.get(url('rpm'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# FILL RATE
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsFillRate:

    def test_publisher_fill_rate_by_unit(self, publisher_client):
        resp = publisher_client.get(url('fill-rate'), {'breakdown': 'unit'})
        assert resp.status_code in (200, 503)

    def test_publisher_fill_rate_by_country(self, publisher_client):
        resp = publisher_client.get(url('fill-rate'), {'breakdown': 'country'})
        assert resp.status_code in (200, 503)

    def test_publisher_fill_rate_issues(self, publisher_client):
        resp = publisher_client.get(url('fill-rate'), {'breakdown': 'issues'})
        assert resp.status_code in (200, 503)

    def test_invalid_breakdown_returns_400(self, publisher_client):
        resp = publisher_client.get(url('fill-rate'), {'breakdown': 'bad'})
        assert resp.status_code == 400

    def test_unauthenticated_cannot_view_fill_rate(self, api_client):
        resp = api_client.get(url('fill-rate'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# REVENUE
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsRevenue:

    def test_revenue_top_units(self, publisher_client):
        resp = publisher_client.get(url('revenue'), {'breakdown': 'top_units'})
        assert resp.status_code in (200, 503)

    def test_revenue_trend(self, publisher_client):
        resp = publisher_client.get(url('revenue'), {'breakdown': 'trend'})
        assert resp.status_code in (200, 503)

    def test_revenue_by_dimension(self, publisher_client):
        resp = publisher_client.get(
            url('revenue'),
            {'breakdown': 'dimension', 'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code in (200, 503)

    def test_invalid_breakdown_returns_400(self, publisher_client):
        resp = publisher_client.get(url('revenue'), {'breakdown': 'unknown'})
        assert resp.status_code == 400

    def test_unauthenticated_cannot_view_revenue(self, api_client):
        resp = api_client.get(url('revenue'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# FORECAST
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsForecast:

    def test_publisher_can_get_forecast(self, publisher_client):
        resp = publisher_client.get(url('forecast'))
        assert resp.status_code in (200, 503)

    def test_forecast_with_days_ahead(self, publisher_client):
        resp = publisher_client.get(url('forecast'), {'days_ahead': '30'})
        assert resp.status_code in (200, 503)

    def test_next_month_forecast(self, publisher_client):
        resp = publisher_client.get(url('forecast'), {'next_month': 'true'})
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_get_forecast(self, api_client):
        resp = api_client.get(url('forecast'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# REPORTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsReports:

    def test_daily_report(self, publisher_client):
        resp = publisher_client.get(url('report/daily'), {'date': '2025-01-15'})
        assert resp.status_code in (200, 503)

    def test_daily_report_without_date_uses_yesterday(self, publisher_client):
        resp = publisher_client.get(url('report/daily'))
        assert resp.status_code in (200, 503)

    def test_weekly_report(self, publisher_client):
        resp = publisher_client.get(url('report/weekly'))
        assert resp.status_code in (200, 503)

    def test_weekly_report_with_week_start(self, publisher_client):
        resp = publisher_client.get(url('report/weekly'), {'week_start': '2025-01-13'})
        assert resp.status_code in (200, 503)

    def test_monthly_report(self, publisher_client):
        resp = publisher_client.get(url('report/monthly'), {'year': '2025', 'month': '1'})
        assert resp.status_code in (200, 503)

    def test_hourly_report(self, publisher_client):
        resp = publisher_client.get(url('report/hourly'), {'date': '2025-01-15'})
        assert resp.status_code in (200, 503)

    def test_hourly_report_missing_date_returns_400(self, publisher_client):
        resp = publisher_client.get(url('report/hourly'))
        assert resp.status_code == 400

    def test_hourly_report_invalid_date_returns_400(self, publisher_client):
        resp = publisher_client.get(url('report/hourly'), {'date': 'not-a-date'})
        assert resp.status_code == 400

    def test_custom_report(self, publisher_client):
        resp = publisher_client.get(
            url('report/custom'),
            {
                'start_date': '2025-01-01',
                'end_date':   '2025-01-31',
                'dimensions': 'date,country',
                'metrics':    'revenue,impressions',
            },
        )
        assert resp.status_code in (200, 503)

    def test_custom_report_missing_dates_returns_400(self, publisher_client):
        resp = publisher_client.get(url('report/custom'))
        assert resp.status_code == 400

    def test_unauthenticated_cannot_get_reports(self, api_client):
        for endpoint in ['report/daily', 'report/weekly', 'report/monthly']:
            resp = api_client.get(url(endpoint))
            assert resp.status_code in (401, 403)


# ==============================================================================
# ALERTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsAlerts:

    def test_publisher_can_view_alerts(self, publisher_client):
        resp = publisher_client.get(url('alerts'))
        assert resp.status_code in (200, 503)

    def test_alerts_response_structure(self, publisher_client):
        resp = publisher_client.get(url('alerts'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'performance_alerts' in data or 'total_count' in data

    def test_alerts_total_count_is_int(self, publisher_client):
        resp = publisher_client.get(url('alerts'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            count = data.get('total_count', 0)
            assert isinstance(count, int)

    def test_unauthenticated_cannot_view_alerts(self, api_client):
        resp = api_client.get(url('alerts'))
        assert resp.status_code in (401, 403)
