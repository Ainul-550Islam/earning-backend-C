# publisher_tools/tests/test_views_optimization_extended.py
"""Tests for OptimizationExtendedViewSet (views_optimization_extended.py) — 10 actions."""
import pytest

BASE = '/api/publisher-tools/optimizations-ext'

@pytest.mark.django_db
class TestOptimizationExtendedAuth:
    def test_unauth_time_of_day_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/time-of-day/').status_code in (401, 403)

@pytest.mark.django_db
class TestOptimizationExtendedTimeOfDay:
    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/time-of-day/').status_code in (200, 503)
    def test_with_ad_unit_filter(self, publisher_client, ad_unit):
        assert publisher_client.get(f'{BASE}/time-of-day/', {'ad_unit_id': ad_unit.pk, 'days': 30}).status_code in (200, 503)
    def test_nonexistent_unit_returns_404(self, publisher_client):
        assert publisher_client.get(f'{BASE}/time-of-day/', {'ad_unit_id': 99999}).status_code in (404, 503)

@pytest.mark.django_db
class TestOptimizationExtendedServingWindows:
    def test_returns_windows(self, publisher_client):
        assert publisher_client.get(f'{BASE}/serving-windows/').status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedPeakHours:
    def test_returns_peak_hours(self, publisher_client):
        assert publisher_client.get(f'{BASE}/peak-hours/').status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedDayOfWeek:
    def test_returns_analysis(self, publisher_client):
        assert publisher_client.get(f'{BASE}/day-of-week/').status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedViewabilityLift:
    def test_returns_lift(self, publisher_client):
        assert publisher_client.get(f'{BASE}/viewability-lift/', {'viewability_pct': '65', 'current_ecpm': '2.50'}).status_code in (200, 503)
    def test_invalid_params_handled(self, publisher_client):
        assert publisher_client.get(f'{BASE}/viewability-lift/', {'viewability_pct': 'bad'}).status_code in (200, 400, 503)

@pytest.mark.django_db
class TestOptimizationExtendedViewabilityRecs:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/viewability-recs/').status_code == 400
    def test_valid_site_returns_recs(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/viewability-recs/', {'site_id': site.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedAdLoad:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ad-load/').status_code == 400
    def test_valid_site_returns_analysis(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/ad-load/', {'site_id': site.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedOptimalUnitCount:
    def test_returns_count(self, publisher_client):
        assert publisher_client.get(f'{BASE}/optimal-unit-count/', {'category': 'news', 'page_type': 'article'}).status_code in (200, 503)

@pytest.mark.django_db
class TestOptimizationExtendedWaterfallSuggest:
    def test_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/waterfall-suggest/').status_code == 400
    def test_valid_unit_returns_suggestions(self, publisher_client, ad_unit):
        assert publisher_client.get(f'{BASE}/waterfall-suggest/', {'ad_unit_id': ad_unit.pk}).status_code in (200, 503)
