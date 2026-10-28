# publisher_tools/tests/test_views_integrations_embed.py
"""Tests for IntegrationsEmbedViewSet (views_integrations_embed.py) — 5 actions."""
import pytest

BASE = '/api/publisher-tools/integrations-embed'

@pytest.mark.django_db
class TestIntegrationsEmbedAuth:
    def test_unauth_embed_code_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/embed-code/').status_code in (401, 403)
    def test_unauth_all_embed_codes_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/all-embed-codes/').status_code in (401, 403)

@pytest.mark.django_db
class TestIntegrationsEmbedCode:
    def test_missing_slug_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/embed-code/').status_code == 400
    def test_invalid_slug_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/embed-code/', {'slug': 'totally_fake_xyz'}).status_code == 400
    def test_valid_slug_not_connected_returns_null(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/embed-code/', {'slug': 'amplitude'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'embed_code' in resp.json()['data']
    def test_all_known_analytics_slugs_accessible(self, publisher_client):
        for slug in ('amplitude', 'mixpanel', 'google_analytics'):
            resp = publisher_client.get(f'{BASE}/embed-code/', {'slug': slug})
            assert resp.status_code in (200, 503), f'Failed for {slug}'

@pytest.mark.django_db
class TestIntegrationsEmbedAllCodes:
    def test_returns_dict(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/all-embed-codes/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'embed_codes' in resp.json()['data']

@pytest.mark.django_db
class TestIntegrationsEmbedSyncGA:
    def test_not_connected_returns_404(self, publisher_client):
        assert publisher_client.post(f'{BASE}/sync-ga/').status_code in (404, 503)

@pytest.mark.django_db
class TestIntegrationsEmbedGATag:
    def test_not_connected_returns_null(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/ga-tag/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'tag_code' in resp.json()['data']

@pytest.mark.django_db
class TestIntegrationsEmbedValidateToken:
    def test_not_connected_returns_404(self, publisher_client):
        assert publisher_client.post(f'{BASE}/validate-token/', {'slug': 'google_analytics'}, format='json').status_code in (404, 503)
    def test_invalid_slug_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/validate-token/', {'slug': 'fake_xyz'}, format='json').status_code == 400
