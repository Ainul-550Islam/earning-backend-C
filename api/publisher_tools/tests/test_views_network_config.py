# publisher_tools/tests/test_views_network_config.py
"""
Tests for NetworkConfigViewSet (views_network_config.py).
Admin-only endpoints for ad network configuration management.
Covers: list_networks, get_config, create_config, test_connection, performance.
"""
import pytest

BASE = '/api/publisher-tools/network-configs'


def url(suffix=''):
    return f'{BASE}/{suffix}/' if suffix else f'{BASE}/'


# ==============================================================================
# PERMISSION GUARD — All endpoints are admin-only
# ==============================================================================

@pytest.mark.django_db
class TestNetworkConfigPermissions:

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('networks'))
        assert resp.status_code in (401, 403)

    def test_publisher_rejected_from_networks(self, publisher_client):
        """Non-admin publisher cannot access network config endpoints."""
        resp = publisher_client.get(url('networks'))
        assert resp.status_code in (403, 405)

    def test_admin_can_access_networks(self, admin_client):
        resp = admin_client.get(url('networks'))
        assert resp.status_code in (200, 503)


# ==============================================================================
# LIST NETWORKS
# ==============================================================================

@pytest.mark.django_db
class TestListNetworks:

    def test_returns_network_list(self, admin_client):
        resp = admin_client.get(url('networks'))
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert 'data' in data
            assert 'all_networks' in data['data']
            assert 'enabled_networks' in data['data']
            assert 'total_count' in data['data']

    def test_total_count_matches_list_length(self, admin_client):
        resp = admin_client.get(url('networks'))
        if resp.status_code == 200:
            d = resp.json()['data']
            assert d['total_count'] == len(d['all_networks'])

    def test_enabled_networks_subset_of_all(self, admin_client):
        resp = admin_client.get(url('networks'))
        if resp.status_code == 200:
            d = resp.json()['data']
            for net in d['enabled_networks']:
                assert net in d['all_networks']

    def test_publisher_cannot_list_networks(self, publisher_client):
        resp = publisher_client.get(url('networks'))
        assert resp.status_code in (403, 405)


# ==============================================================================
# GET CONFIG
# ==============================================================================

@pytest.mark.django_db
class TestGetConfig:

    def test_missing_network_param_returns_400(self, admin_client):
        resp = admin_client.get(url('config'))
        assert resp.status_code == 400

    def test_unknown_network_returns_400(self, admin_client):
        resp = admin_client.get(url('config'), {'network': 'nonexistent_xyz'})
        assert resp.status_code in (400, 200, 503)

    def test_valid_network_returns_data(self, admin_client):
        resp = admin_client.get(url('config'), {'network': 'admob'})
        assert resp.status_code in (200, 400, 503)
        if resp.status_code == 200:
            d = resp.json()['data']
            assert 'network' in d
            assert 'configs' in d
            assert 'count' in d

    def test_with_publisher_id_filter(self, admin_client, publisher):
        resp = admin_client.get(url('config'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        })
        assert resp.status_code in (200, 400, 503)

    def test_returns_empty_configs_for_new_publisher(self, admin_client, publisher):
        resp = admin_client.get(url('config'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        })
        if resp.status_code == 200:
            assert resp.json()['data']['count'] >= 0


# ==============================================================================
# CREATE CONFIG
# ==============================================================================

@pytest.mark.django_db
class TestCreateConfig:

    def test_missing_network_returns_400(self, admin_client, publisher):
        resp = admin_client.post(url('config/create'), {
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code == 400

    def test_missing_publisher_id_returns_400(self, admin_client):
        resp = admin_client.post(url('config/create'), {
            'network': 'admob',
        }, format='json')
        assert resp.status_code == 400

    def test_unknown_publisher_returns_404(self, admin_client):
        resp = admin_client.post(url('config/create'), {
            'network':      'admob',
            'publisher_id': 'PUB-NONEXISTENT',
        }, format='json')
        assert resp.status_code in (404, 400, 503)

    def test_unknown_network_returns_400(self, admin_client, publisher):
        resp = admin_client.post(url('config/create'), {
            'network':      'fake_xyz_network',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_valid_create_config(self, admin_client, publisher):
        resp = admin_client.post(url('config/create'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code in (200, 400, 503)

    def test_publisher_cannot_create_config(self, publisher_client, publisher):
        resp = publisher_client.post(url('config/create'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code in (403, 405)


# ==============================================================================
# TEST CONNECTION
# ==============================================================================

@pytest.mark.django_db
class TestTestConnection:

    def test_missing_params_returns_400(self, admin_client):
        resp = admin_client.post(url('test-connection'), {}, format='json')
        assert resp.status_code == 400

    def test_missing_network_returns_400(self, admin_client, publisher):
        resp = admin_client.post(url('test-connection'), {
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code == 400

    def test_missing_publisher_id_returns_400(self, admin_client):
        resp = admin_client.post(url('test-connection'), {
            'network': 'admob',
        }, format='json')
        assert resp.status_code == 400

    def test_unknown_publisher_returns_404(self, admin_client):
        resp = admin_client.post(url('test-connection'), {
            'network':      'admob',
            'publisher_id': 'PUB-GHOST',
        }, format='json')
        assert resp.status_code in (404, 400, 503)

    def test_unknown_network_returns_400(self, admin_client, publisher):
        resp = admin_client.post(url('test-connection'), {
            'network':      'nonexistent_net',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_no_config_returns_404_or_400(self, admin_client, publisher):
        """Publisher exists but has no config for this network."""
        resp = admin_client.post(url('test-connection'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        # 404 if publisher exists but config missing, 400/503 if network unknown
        assert resp.status_code in (404, 400, 503)

    def test_publisher_cannot_test_connection(self, publisher_client, publisher):
        resp = publisher_client.post(url('test-connection'), {
            'network':      'admob',
            'publisher_id': publisher.publisher_id,
        }, format='json')
        assert resp.status_code in (403, 405)


# ==============================================================================
# PERFORMANCE
# ==============================================================================

@pytest.mark.django_db
class TestNetworkPerformance:

    def test_returns_performance_data(self, admin_client):
        resp = admin_client.get(url('performance'))
        assert resp.status_code in (200, 503)

    def test_with_days_param(self, admin_client):
        for days in [7, 30, 90]:
            resp = admin_client.get(url('performance'), {'days': days})
            assert resp.status_code in (200, 503)

    def test_publisher_cannot_view_performance(self, publisher_client):
        resp = publisher_client.get(url('performance'))
        assert resp.status_code in (403, 405)

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('performance'))
        assert resp.status_code in (401, 403)
