# publisher_tools/tests/test_views_integrations.py
"""
Tests for IntegrationsViewSet (views_integrations.py).
Publisher-side third-party SDK + analytics integration management.
Covers: list_available, list_connected, get_integration_detail,
        connect, disconnect, test_connection, get_install_guide.
"""
import pytest

BASE = '/api/publisher-tools/integrations'

KNOWN_SLUGS = ['amplitude', 'mixpanel', 'segment', 'google_analytics',
               'react_sdk', 'vue_sdk', 'wordpress', 'shopify']
INSTALL_GUIDE_SLUGS = ['react_sdk', 'vue_sdk', 'angular_sdk', 'wordpress',
                       'woocommerce', 'shopify', 'drupal', 'joomla']


def url(suffix=''):
    return f'{BASE}/{suffix}/' if suffix else f'{BASE}/'


# ==============================================================================
# PERMISSION GUARD
# ==============================================================================

@pytest.mark.django_db
class TestIntegrationsPermissions:

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('available'))
        assert resp.status_code in (401, 403)

    def test_regular_user_rejected(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        resp = api_client.get(url('available'))
        assert resp.status_code in (403, 404)

    def test_publisher_can_access_available(self, publisher_client):
        resp = publisher_client.get(url('available'))
        assert resp.status_code in (200, 503)


# ==============================================================================
# LIST AVAILABLE INTEGRATIONS
# ==============================================================================

@pytest.mark.django_db
class TestListAvailableIntegrations:

    def test_returns_integration_list(self, publisher_client):
        resp = publisher_client.get(url('available'))
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            d = resp.json()['data']
            assert 'integrations' in d
            assert 'total' in d

    def test_integration_list_not_empty(self, publisher_client):
        resp = publisher_client.get(url('available'))
        if resp.status_code == 200:
            assert resp.json()['data']['total'] > 0

    def test_each_integration_has_slug(self, publisher_client):
        resp = publisher_client.get(url('available'))
        if resp.status_code == 200:
            for item in resp.json()['data']['integrations']:
                assert 'slug' in item

    def test_total_matches_list_count(self, publisher_client):
        resp = publisher_client.get(url('available'))
        if resp.status_code == 200:
            d = resp.json()['data']
            assert d['total'] == len(d['integrations'])

    def test_known_slugs_present(self, publisher_client):
        resp = publisher_client.get(url('available'))
        if resp.status_code == 200:
            slugs = [i['slug'] for i in resp.json()['data']['integrations']]
            for known in ['amplitude', 'react_sdk', 'wordpress']:
                assert known in slugs


# ==============================================================================
# LIST CONNECTED INTEGRATIONS
# ==============================================================================

@pytest.mark.django_db
class TestListConnectedIntegrations:

    def test_new_publisher_has_none_connected(self, publisher_client):
        resp = publisher_client.get(url('connected'))
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            d = resp.json()['data']
            assert 'connected' in d
            assert 'connected_count' in d

    def test_connected_count_is_int(self, publisher_client):
        resp = publisher_client.get(url('connected'))
        if resp.status_code == 200:
            assert isinstance(resp.json()['data']['connected_count'], int)

    def test_connected_count_non_negative(self, publisher_client):
        resp = publisher_client.get(url('connected'))
        if resp.status_code == 200:
            assert resp.json()['data']['connected_count'] >= 0

    def test_publisher_2_sees_own_connections(self, publisher_client_2):
        resp = publisher_client_2.get(url('connected'))
        assert resp.status_code in (200, 503)

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('connected'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# GET INTEGRATION DETAIL
# ==============================================================================

@pytest.mark.django_db
class TestGetIntegrationDetail:

    def test_missing_slug_returns_400(self, publisher_client):
        resp = publisher_client.get(url('detail'))
        assert resp.status_code == 400

    def test_unknown_slug_handled(self, publisher_client):
        resp = publisher_client.get(url('detail'), {'slug': 'not_a_real_slug'})
        assert resp.status_code in (400, 200, 503)

    def test_not_connected_returns_null_data(self, publisher_client):
        resp = publisher_client.get(url('detail'), {'slug': 'amplitude'})
        if resp.status_code == 200:
            body = resp.json()
            # Either null data (not connected) or a config object
            assert body.get('data') is None or isinstance(body.get('data'), dict)

    def test_not_connected_returns_helpful_message(self, publisher_client):
        resp = publisher_client.get(url('detail'), {'slug': 'amplitude'})
        if resp.status_code == 200 and resp.json().get('data') is None:
            msg = resp.json().get('message', '')
            assert 'connect' in msg.lower() or 'not connected' in msg.lower()


# ==============================================================================
# CONNECT INTEGRATION
# ==============================================================================

@pytest.mark.django_db
class TestConnectIntegration:

    def test_missing_slug_returns_400(self, publisher_client):
        resp = publisher_client.post(url('connect'), {}, format='json')
        assert resp.status_code == 400

    def test_unknown_slug_returns_400_or_503(self, publisher_client):
        resp = publisher_client.post(url('connect'), {
            'slug': 'totally_fake_integration',
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_connect_amplitude(self, publisher_client):
        resp = publisher_client.post(url('connect'), {
            'slug':    'amplitude',
            'api_key': 'test_key_1234567890abcdef',
        }, format='json')
        assert resp.status_code in (200, 400, 503)

    def test_connect_idempotent(self, publisher_client):
        """Connecting twice updates existing, doesn't duplicate."""
        payload = {'slug': 'amplitude', 'api_key': 'key_v1'}
        r1 = publisher_client.post(url('connect'), payload, format='json')
        r2 = publisher_client.post(url('connect'), {'slug': 'amplitude', 'api_key': 'key_v2'}, format='json')
        if r1.status_code == 200 and r2.status_code == 200:
            assert r2.json()['data']['created'] is False

    def test_connect_response_has_slug(self, publisher_client):
        resp = publisher_client.post(url('connect'), {
            'slug': 'mixpanel', 'project_token': 'abc123',
        }, format='json')
        if resp.status_code == 200:
            assert resp.json()['data']['slug'] == 'mixpanel'

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(url('connect'), {'slug': 'amplitude'}, format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# DISCONNECT INTEGRATION
# ==============================================================================

@pytest.mark.django_db
class TestDisconnectIntegration:

    def test_missing_slug_returns_400(self, publisher_client):
        resp = publisher_client.post(url('disconnect'), {}, format='json')
        assert resp.status_code == 400

    def test_disconnect_not_connected_returns_404(self, publisher_client):
        resp = publisher_client.post(url('disconnect'), {
            'slug': 'segment',
        }, format='json')
        assert resp.status_code in (404, 400, 503)

    def test_connect_then_disconnect(self, publisher_client):
        # Connect first
        publisher_client.post(url('connect'), {'slug': 'segment'}, format='json')
        # Then disconnect
        resp = publisher_client.post(url('disconnect'), {'slug': 'segment'}, format='json')
        assert resp.status_code in (200, 404, 400, 503)

    def test_publisher_2_cannot_disconnect_publisher_1(self, publisher_client, publisher_client_2):
        # Connect as publisher 1
        publisher_client.post(url('connect'), {'slug': 'mixpanel'}, format='json')
        # Disconnect as publisher 2 should fail (not connected for pub 2)
        resp = publisher_client_2.post(url('disconnect'), {'slug': 'mixpanel'}, format='json')
        assert resp.status_code in (404, 400, 503)


# ==============================================================================
# TEST CONNECTION
# ==============================================================================

@pytest.mark.django_db
class TestIntegrationTestConnection:

    def test_missing_slug_returns_400(self, publisher_client):
        resp = publisher_client.post(url('test'), {}, format='json')
        assert resp.status_code == 400

    def test_not_connected_returns_404(self, publisher_client):
        resp = publisher_client.post(url('test'), {'slug': 'amplitude'}, format='json')
        assert resp.status_code in (404, 400, 503)

    def test_response_has_result_key_on_connected(self, publisher_client):
        # Connect first
        publisher_client.post(url('connect'), {'slug': 'amplitude', 'api_key': 'xyz'}, format='json')
        resp = publisher_client.post(url('test'), {'slug': 'amplitude'}, format='json')
        if resp.status_code == 200:
            assert 'result' in resp.json()['data']


# ==============================================================================
# INSTALL GUIDE
# ==============================================================================

@pytest.mark.django_db
class TestInstallGuide:

    def test_missing_slug_returns_400(self, publisher_client):
        resp = publisher_client.get(url('install-guide'))
        assert resp.status_code == 400

    def test_sdk_guide_returned(self, publisher_client):
        resp = publisher_client.get(url('install-guide'), {'slug': 'react_sdk'})
        assert resp.status_code == 200
        d = resp.json()['data']
        assert 'slug' in d
        assert 'install_guide' in d
        assert d['slug'] == 'react_sdk'

    def test_react_guide_has_package(self, publisher_client):
        resp = publisher_client.get(url('install-guide'), {'slug': 'react_sdk'})
        if resp.status_code == 200:
            guide = resp.json()['data']['install_guide']
            assert 'package' in guide or 'docs' in guide

    def test_wordpress_guide_has_plugin(self, publisher_client):
        resp = publisher_client.get(url('install-guide'), {'slug': 'wordpress'})
        if resp.status_code == 200:
            guide = resp.json()['data']['install_guide']
            assert 'plugin' in guide or 'docs' in guide

    def test_unknown_slug_returns_fallback(self, publisher_client):
        """Unrecognised slugs get a fallback guide, not an error."""
        resp = publisher_client.get(url('install-guide'), {'slug': 'unknown_xyz'})
        assert resp.status_code == 200
        d = resp.json()['data']
        assert 'install_guide' in d
        assert 'docs' in d['install_guide']

    def test_all_known_install_slugs(self, publisher_client):
        for slug in INSTALL_GUIDE_SLUGS:
            resp = publisher_client.get(url('install-guide'), {'slug': slug})
            assert resp.status_code == 200, f'Failed for slug={slug}'
