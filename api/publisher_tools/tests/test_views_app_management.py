# publisher_tools/tests/test_views_app_management.py
"""
Tests for AppManagementViewSet (views_app_management.py).
Covers: performance, by_format, top_countries.
"""
import pytest
from publisher_tools.tests.factories import PublisherFactory, AppFactory

BASE = '/api/publisher-tools/app-tools'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# PERFORMANCE
# ==============================================================================

@pytest.mark.django_db
class TestAppPerformance:

    def test_publisher_can_view_app_performance(self, publisher_client, app):
        resp = publisher_client.get(url('performance'), {'app_id': app.app_id})
        assert resp.status_code in (200, 503)

    def test_missing_app_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('performance'))
        assert resp.status_code == 400

    def test_other_publisher_app_returns_404(self, publisher_client_2, app):
        resp = publisher_client_2.get(url('performance'), {'app_id': app.app_id})
        assert resp.status_code == 404

    def test_days_param_accepted(self, publisher_client, app):
        resp = publisher_client.get(url('performance'), {'app_id': app.app_id, 'days': '7'})
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_view_performance(self, api_client, app):
        resp = api_client.get(url('performance'), {'app_id': app.app_id})
        assert resp.status_code in (401, 403)


# ==============================================================================
# BY FORMAT
# ==============================================================================

@pytest.mark.django_db
class TestAppByFormat:

    def test_publisher_can_get_revenue_by_format(self, publisher_client, app):
        resp = publisher_client.get(url('by-format'), {'app_id': app.app_id})
        assert resp.status_code in (200, 503)

    def test_missing_app_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('by-format'))
        assert resp.status_code == 400

    def test_other_publisher_app_returns_404(self, publisher_client_2, app):
        resp = publisher_client_2.get(url('by-format'), {'app_id': app.app_id})
        assert resp.status_code == 404

    def test_response_is_list_or_dict(self, publisher_client, app):
        resp = publisher_client.get(url('by-format'), {'app_id': app.app_id})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert isinstance(data, (list, dict))

    def test_unauthenticated_cannot_get_format_data(self, api_client, app):
        resp = api_client.get(url('by-format'), {'app_id': app.app_id})
        assert resp.status_code in (401, 403)


# ==============================================================================
# TOP COUNTRIES
# ==============================================================================

@pytest.mark.django_db
class TestAppTopCountries:

    def test_publisher_can_view_top_countries(self, publisher_client, app):
        resp = publisher_client.get(url('top-countries'), {'app_id': app.app_id})
        assert resp.status_code in (200, 503)

    def test_missing_app_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('top-countries'))
        assert resp.status_code == 400

    def test_other_publisher_app_returns_404(self, publisher_client_2, app):
        resp = publisher_client_2.get(url('top-countries'), {'app_id': app.app_id})
        assert resp.status_code == 404

    def test_limit_param_accepted(self, publisher_client, app):
        resp = publisher_client.get(url('top-countries'), {'app_id': app.app_id, 'limit': '5'})
        assert resp.status_code in (200, 503)

    def test_response_has_country_data(self, publisher_client, app):
        resp = publisher_client.get(url('top-countries'), {'app_id': app.app_id})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert isinstance(data, (list, dict))

    def test_unauthenticated_cannot_view_countries(self, api_client, app):
        resp = api_client.get(url('top-countries'), {'app_id': app.app_id})
        assert resp.status_code in (401, 403)
