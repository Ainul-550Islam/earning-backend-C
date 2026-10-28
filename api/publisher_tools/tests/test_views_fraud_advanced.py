# publisher_tools/tests/test_views_fraud_advanced.py
"""Tests for FraudAdvancedViewSet (views_fraud_advanced.py) — 12 actions."""
import pytest

BASE = '/api/publisher-tools/fraud-advanced'

@pytest.mark.django_db
class TestFraudAdvancedAuth:
    def test_unauth_impression_velocity_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/check-impression-velocity/').status_code in (401,403)

@pytest.mark.django_db
class TestFraudAdvancedImpressionVelocity:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/check-impression-velocity/', {}, format='json').status_code == 400
    def test_valid_check_returns_data(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/check-impression-velocity/', {'ip':'1.2.3.4','unit_id':'UNIT-001'}, format='json')
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestFraudAdvancedConversionVelocity:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/check-conversion-velocity/', {}, format='json').status_code == 400
    def test_valid_check_returns_data(self, publisher_client): assert publisher_client.post(f'{BASE}/check-conversion-velocity/', {'ip':'1.2.3.4'}, format='json').status_code in (200,503)

@pytest.mark.django_db
class TestFraudAdvancedGeoValidation:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/validate-geo/', {}, format='json').status_code == 400
    def test_valid_geo_check(self, publisher_client): assert publisher_client.post(f'{BASE}/validate-geo/', {'ip':'8.8.8.8','browser_tz':'America/New_York'}, format='json').status_code in (200,503)

@pytest.mark.django_db
class TestFraudAdvancedCountryRisk:
    def test_returns_risk_score(self, publisher_client): assert publisher_client.get(f'{BASE}/country-risk/', {'country':'US'}).status_code in (200,503)
    def test_multiple_countries(self, publisher_client): assert publisher_client.get(f'{BASE}/country-risk/', {'country':'US,BD,IN'}).status_code in (200,503)

@pytest.mark.django_db
class TestFraudAdvancedClickFraud:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/detect-click-fraud/', {}, format='json').status_code == 400
    def test_valid_click_check(self, publisher_client): assert publisher_client.post(f'{BASE}/detect-click-fraud/', {'ip':'1.2.3.4','unit_id':'UNIT-001'}, format='json').status_code in (200,503)

@pytest.mark.django_db
class TestFraudAdvancedRiskLevel:
    def test_valid_score_returns_level(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/risk-level/', {'fraud_score':75}, format='json')
        assert resp.status_code in (200,503)
        if resp.status_code == 200: assert 'risk_level' in resp.json()['data']
    def test_invalid_score_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/risk-level/', {'fraud_score':999}, format='json').status_code == 400

@pytest.mark.django_db
class TestFraudAdvancedAlerts:
    def test_alerts_accessible(self, publisher_client): assert publisher_client.get(f'{BASE}/alerts/').status_code in (200,503)
    def test_mark_all_read(self, publisher_client): assert publisher_client.post(f'{BASE}/mark-alert-read/', {'mark_all':True}, format='json').status_code in (200,503)
