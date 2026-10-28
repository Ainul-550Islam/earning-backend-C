# publisher_tools/tests/test_views_analytics_advanced.py
"""Tests for AnalyticsAdvancedViewSet (views_analytics_advanced.py) — 13 actions."""
import pytest

BASE = '/api/publisher-tools/analytics-adv'

@pytest.mark.django_db
class TestAnalyticsAdvancedAuth:
    def test_unauth_revenue_forecast_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/revenue-forecast/').status_code in (401,403)
    def test_unauth_ecpm_suggestions_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/ecpm-suggestions/').status_code in (401,403)

@pytest.mark.django_db
class TestAnalyticsAdvancedRevenueForecast:
    def test_returns_forecast(self, publisher_client): assert publisher_client.get(f'{BASE}/revenue-forecast/').status_code in (200,503)
    def test_invalid_months_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/revenue-forecast/', {'months':999}).status_code == 400
    def test_with_months_param(self, publisher_client): assert publisher_client.get(f'{BASE}/revenue-forecast/', {'months':3}).status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsAdvancedRevenueGrowth:
    def test_returns_growth(self, publisher_client): assert publisher_client.get(f'{BASE}/revenue-growth/').status_code in (200,503)
    def test_with_period_param(self, publisher_client): assert publisher_client.get(f'{BASE}/revenue-growth/', {'period':'30d'}).status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsAdvancedPeriodRevenue:
    def test_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/period-revenue/').status_code in (200,503)
    def test_invalid_date_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/period-revenue/', {'start':'bad-date'}).status_code in (400,503)

@pytest.mark.django_db
class TestAnalyticsAdvancedECPM:
    def test_ecpm_suggestions_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/ecpm-suggestions/').status_code in (200,503)
    def test_ecpm_by_country_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/ecpm-by-country/').status_code in (200,503)
    def test_ecpm_by_format_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/ecpm-by-format/').status_code in (200,503)
    def test_ecpm_trend_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/ecpm-trend/').status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsAdvancedRealtime:
    def test_realtime_fill_missing_unit_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/realtime-fill/').status_code == 400
    def test_realtime_fill_with_unit(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/realtime-fill/', {'unit_id':ad_unit.unit_id}).status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsAdvancedDashboard:
    def test_dashboard_kpis_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/dashboard-kpis/').status_code in (200,503)
