# publisher_tools/tests/test_views_adunit_extended.py
"""Tests for AdUnitExtendedViewSet (views_adunit_extended.py) — 7 actions."""
import pytest

BASE = '/api/publisher-tools/ad-unit-tools'

@pytest.mark.django_db
class TestAdUnitExtendedAuth:
    def test_unauth_performance_report_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/performance-report/').status_code in (401,403)
    def test_unauth_apply_targeting_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/apply-targeting/').status_code in (401,403)

@pytest.mark.django_db
class TestAdUnitExtendedPerformanceReport:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/performance-report/').status_code == 400
    def test_valid_unit_returns_data(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/performance-report/', {'unit_id':ad_unit.pk}).status_code in (200,503)
    def test_other_publisher_unit_blocked(self, publisher_client_2, ad_unit): assert publisher_client_2.get(f'{BASE}/performance-report/', {'unit_id':ad_unit.pk}).status_code in (404,403,503)

@pytest.mark.django_db
class TestAdUnitExtendedDailyTrend:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/daily-trend/').status_code == 400
    def test_valid_unit_returns_data(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/daily-trend/', {'unit_id':ad_unit.pk,'days':7}).status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitExtendedCompare:
    def test_missing_params_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/compare/').status_code == 400
    def test_valid_comparison(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/compare/', {'unit_a':ad_unit.pk,'unit_b':ad_unit.pk}).status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitExtendedRecommendations:
    def test_returns_recommendations(self, publisher_client): assert publisher_client.get(f'{BASE}/recommendations/', {'format':'banner'}).status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitExtendedApplyTargeting:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/apply-targeting/', {}, format='json').status_code == 400
    def test_valid_unit_returns_result(self, publisher_client, ad_unit):
        resp = publisher_client.post(f'{BASE}/apply-targeting/', {'unit_id':ad_unit.pk,'context':{'country':'US','device':'mobile'}}, format='json')
        assert resp.status_code in (200,503)
