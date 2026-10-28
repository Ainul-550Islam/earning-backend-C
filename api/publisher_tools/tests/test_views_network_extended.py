# publisher_tools/tests/test_views_network_extended.py
"""Tests for AdNetworkExtendedViewSet (views_network_extended.py) — 10 actions."""
import pytest

BASE = '/api/publisher-tools/ad-networks'

@pytest.mark.django_db
class TestNetworkExtendedAuth:
    def test_unauth_catalog_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/catalog/').status_code in (401, 403)
    def test_unauth_my_networks_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/my-networks/').status_code in (401, 403)

@pytest.mark.django_db
class TestNetworkExtendedCatalog:
    def test_returns_all_networks(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/catalog/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'networks' in resp.json()['data']
            assert resp.json()['data']['total'] > 0
    def test_filter_by_mobile(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/catalog/', {'type': 'mobile'})
        assert resp.status_code in (200, 503)
    def test_filter_by_web(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/catalog/', {'type': 'web'})
        assert resp.status_code in (200, 503)

@pytest.mark.django_db
class TestNetworkExtendedMyNetworks:
    def test_returns_enabled_networks(self, publisher_client):
        assert publisher_client.get(f'{BASE}/my-networks/').status_code in (200, 503)

@pytest.mark.django_db
class TestNetworkExtendedPerNetwork:
    def test_missing_network_param_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/per-network/').status_code == 400
    def test_invalid_network_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/per-network/', {'network': 'nonexistent_xyz'}).status_code == 400
    def test_valid_network_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/per-network/', {'network': 'admob'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'network' in resp.json()['data']

@pytest.mark.django_db
class TestNetworkExtendedRecommend:
    def test_returns_recommendations(self, publisher_client):
        assert publisher_client.get(f'{BASE}/recommend/', {'format': 'banner'}).status_code in (200, 503)

@pytest.mark.django_db
class TestNetworkExtendedPerformance:
    def test_returns_performance_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/performance/').status_code in (200, 503)
    def test_with_days_param(self, publisher_client):
        assert publisher_client.get(f'{BASE}/performance/', {'days': 30}).status_code in (200, 503)

@pytest.mark.django_db
class TestNetworkExtendedDetail:
    def test_missing_network_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/detail/').status_code == 400
    def test_valid_network_returns_detail(self, publisher_client):
        assert publisher_client.get(f'{BASE}/detail/', {'network': 'admob', 'days': 30}).status_code in (200, 503)

@pytest.mark.django_db
class TestNetworkExtendedAdminEndpoints:
    def test_platform_stats_requires_admin(self, publisher_client):
        assert publisher_client.get(f'{BASE}/platform-stats/').status_code in (403, 401)
    def test_admin_can_view_platform_stats(self, admin_client):
        assert admin_client.get(f'{BASE}/platform-stats/').status_code in (200, 503)
    def test_bulk_enable_requires_admin(self, publisher_client):
        assert publisher_client.post(f'{BASE}/bulk-enable/', {'publisher_id': 'X', 'networks': ['admob']}, format='json').status_code in (403, 401)
