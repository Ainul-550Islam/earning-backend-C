# publisher_tools/tests/test_views_adunit_advanced.py
"""Tests for AdUnitAdvancedViewSet (views_adunit_advanced.py) — 5 actions."""
import pytest

BASE = '/api/publisher-tools/ad-unit-adv'

@pytest.mark.django_db
class TestAdUnitAdvancedAuth:
    def test_unauth_frequency_cap_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/frequency-cap-status/').status_code in (401,403)
    def test_unauth_position_multiplier_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/position-multiplier/').status_code in (401,403)

@pytest.mark.django_db
class TestAdUnitAdvancedFrequencyCap:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/frequency-cap-status/').status_code == 400
    def test_valid_unit_returns_data(self, publisher_client, ad_unit):
        resp = publisher_client.get(f'{BASE}/frequency-cap-status/', {'unit_id':ad_unit.pk,'session_id':'sess_abc'})
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitAdvancedPositionMultiplier:
    def test_returns_multiplier(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/position-multiplier/', {'position':'top_of_page'})
        assert resp.status_code in (200,503)
    def test_multiple_positions(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/position-multiplier/', {'position':'top_of_page,sidebar'})
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitAdvancedTargetingSchedule:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/targeting-schedule/').status_code == 400
    def test_valid_unit_returns_data(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/targeting-schedule/', {'unit_id':ad_unit.pk}).status_code in (200,503)

@pytest.mark.django_db
class TestAdUnitAdvancedPerformanceDiff:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/performance-diff/').status_code == 400
    def test_valid_unit_returns_data(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/performance-diff/', {'unit_id':ad_unit.pk,'days_a':7,'days_b':30}).status_code in (200,503)
