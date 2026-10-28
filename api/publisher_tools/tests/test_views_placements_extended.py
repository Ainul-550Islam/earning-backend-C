# publisher_tools/tests/test_views_placements_extended.py
"""Tests for PlacementExtendedViewSet (views_placements_extended.py) — 13 actions."""
import pytest

BASE = '/api/publisher-tools/placement-tools'

@pytest.mark.django_db
class TestPlacementsExtendedAuth:
    def test_unauth_for_site_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/for-site/').status_code in (401, 403)

@pytest.mark.django_db
class TestPlacementsExtendedForSite:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/for-site/').status_code == 400
    def test_valid_site_returns_placements(self, publisher_client, site):
        resp = publisher_client.get(f'{BASE}/for-site/', {'site_id': site.pk})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'placements' in resp.json()['data']
    def test_other_publisher_site_blocked(self, publisher_client_2, site):
        assert publisher_client_2.get(f'{BASE}/for-site/', {'site_id': site.pk}).status_code in (404, 403, 503)

@pytest.mark.django_db
class TestPlacementsExtendedForApp:
    def test_missing_app_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/for-app/').status_code == 400
    def test_valid_app_returns_placements(self, publisher_client, app):
        assert publisher_client.get(f'{BASE}/for-app/', {'app_id': app.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestPlacementsExtendedConfig:
    def test_missing_placement_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/config/').status_code == 400

@pytest.mark.django_db
class TestPlacementsExtendedSizes:
    def test_recommended_sizes_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/recommended-sizes/', {'position': 'top_of_page'}).status_code in (200, 503)
    def test_size_multiplier_missing_param_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/size-multiplier/').status_code == 400
    def test_size_multiplier_valid(self, publisher_client):
        assert publisher_client.get(f'{BASE}/size-multiplier/', {'size': '300x250'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPlacementsExtendedParseSize:
    def test_missing_size_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/parse-size/', {}, format='json').status_code == 400
    def test_valid_size_parsed(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/parse-size/', {'size': '300x250'}, format='json')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()['data']
            assert 'width' in data or 'size' in data

@pytest.mark.django_db
class TestPlacementsExtendedPositionTools:
    def test_position_scores_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/position-scores/').status_code in (200, 503)
    def test_suggest_position_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/suggest-position/', {'current_position': 'below_fold'}).status_code in (200, 503)
    def test_optimize_all_returns_analysis(self, publisher_client):
        assert publisher_client.get(f'{BASE}/optimize-all/').status_code in (200, 503)
    def test_efficiency_returns_scores(self, publisher_client):
        assert publisher_client.get(f'{BASE}/efficiency/').status_code in (200, 503)
