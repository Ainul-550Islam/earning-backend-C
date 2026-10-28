# publisher_tools/tests/test_views_fraud_extended.py
"""Tests for FraudExtendedViewSet (views_fraud_extended.py) — 10 actions."""
import pytest

BASE = '/api/publisher-tools/fraud-tools'

@pytest.mark.django_db
class TestFraudExtendedAuth:
    def test_unauth_analyze_ua_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/analyze-ua/').status_code in (401,403)
    def test_unauth_ip_reputation_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/ip-reputation/').status_code in (401,403)

@pytest.mark.django_db
class TestFraudExtendedAnalyzeUA:
    def test_missing_ua_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/analyze-ua/', {}, format='json').status_code == 400
    def test_valid_ua_returns_result(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/analyze-ua/', {'user_agent':'Mozilla/5.0 (Googlebot)'}, format='json')
        assert resp.status_code in (200,503)
        if resp.status_code == 200: assert 'is_bot' in resp.json()['data']

@pytest.mark.django_db
class TestFraudExtendedCheckDevice:
    def test_missing_device_data_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/check-device/', {}, format='json').status_code == 400
    def test_valid_device_data_returns_result(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/check-device/', {'device_data':{'screen':'1920x1080','platform':'Win32'}}, format='json')
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestFraudExtendedCheckImpression:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/check-impression/', {}, format='json').status_code == 400
    def test_valid_ip_returns_result(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/check-impression/', {'ip_address':'1.2.3.4','user_agent':'Mozilla/5.0'}, format='json')
        assert resp.status_code in (200,503)
        if resp.status_code == 200: assert 'action' in resp.json()['data']

@pytest.mark.django_db
class TestFraudExtendedIPReputation:
    def test_missing_ip_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/ip-reputation/').status_code == 400
    def test_valid_ip_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/ip-reputation/', {'ip':'8.8.8.8'}).status_code in (200,503)

@pytest.mark.django_db
class TestFraudExtendedConfig:
    def test_config_accessible(self, publisher_client): assert publisher_client.get(f'{BASE}/config/').status_code in (200,503)

@pytest.mark.django_db
class TestFraudExtendedBotList:
    def test_bot_list_requires_admin(self, publisher_client): assert publisher_client.get(f'{BASE}/bot-list/').status_code in (403,401)
    def test_admin_can_access(self, admin_client): assert admin_client.get(f'{BASE}/bot-list/').status_code in (200,503)
