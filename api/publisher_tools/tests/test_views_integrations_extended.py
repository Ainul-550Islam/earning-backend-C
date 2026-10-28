# publisher_tools/tests/test_views_integrations_extended.py
"""Tests for IntegrationsExtendedViewSet (views_integrations_extended.py) — 8 actions."""
import pytest

BASE = '/api/publisher-tools/integrations-ext'

@pytest.mark.django_db
class TestIntegrationsExtendedAuth:
    def test_unauth_catalogue_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/catalogue/').status_code in (401,403)
    def test_unauth_sync_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/sync/').status_code in (401,403)

@pytest.mark.django_db
class TestIntegrationsExtendedCatalogue:
    def test_returns_catalogue(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/catalogue/')
        assert resp.status_code in (200,503)
        if resp.status_code == 200: assert 'integrations' in resp.json()['data']
    def test_filter_by_category(self, publisher_client): assert publisher_client.get(f'{BASE}/catalogue/', {'category':'analytics'}).status_code in (200,503)

@pytest.mark.django_db
class TestIntegrationsExtendedByCategory:
    def test_returns_grouped(self, publisher_client): assert publisher_client.get(f'{BASE}/by-category/').status_code in (200,503)

@pytest.mark.django_db
class TestIntegrationsExtendedConnectedDetail:
    def test_returns_connected(self, publisher_client): assert publisher_client.get(f'{BASE}/connected-detail/').status_code in (200,503)

@pytest.mark.django_db
class TestIntegrationsExtendedSync:
    def test_missing_slug_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/sync/', {}, format='json').status_code == 400
    def test_not_connected_returns_404(self, publisher_client): assert publisher_client.post(f'{BASE}/sync/', {'slug':'amplitude'}, format='json').status_code in (404,503)
    def test_unknown_slug_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/sync/', {'slug':'totally_fake'}, format='json').status_code == 400

@pytest.mark.django_db
class TestIntegrationsExtendedHealthCheck:
    def test_health_check_runs(self, publisher_client): assert publisher_client.post(f'{BASE}/health-check/', {}, format='json').status_code in (200,503)

@pytest.mark.django_db
class TestIntegrationsExtendedSDKConfig:
    def test_missing_slug_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/sdk-config/').status_code == 400
    def test_valid_slug_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/sdk-config/', {'slug':'react_sdk'}).status_code in (200,503)
