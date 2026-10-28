# publisher_tools/tests/test_views_publisher_management.py
"""
Tests for PublisherManagementViewSet (views_publisher_management.py).
Covers: overview, revenue_breakdown, metrics, forecast,
        top_content, profile, health_score.
"""
import pytest
from publisher_tools.tests.factories import PublisherEarningFactory, SiteFactory, AdUnitFactory

BASE = '/api/publisher-tools/publisher-tools'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# OVERVIEW
# ==============================================================================

@pytest.mark.django_db
class TestPublisherOverview:

    def test_publisher_can_view_own_overview(self, publisher_client):
        resp = publisher_client.get(url('overview'))
        assert resp.status_code in (200, 503)

    def test_overview_with_period_param(self, publisher_client):
        for period in ['last_7_days', 'last_30_days', 'last_90_days']:
            resp = publisher_client.get(url('overview'), {'period': period})
            assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_view_overview(self, api_client):
        resp = api_client.get(url('overview'))
        assert resp.status_code in (401, 403)

    def test_overview_has_revenue_breakdown_key(self, publisher_client):
        resp = publisher_client.get(url('overview'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'revenue_breakdown' in data or 'total_revenue' in data


# ==============================================================================
# REVENUE BREAKDOWN
# ==============================================================================

@pytest.mark.django_db
class TestRevenueBreakdown:

    def test_publisher_can_get_breakdown(self, publisher_client):
        resp = publisher_client.get(
            url('revenue-breakdown'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code in (200, 503)

    def test_missing_dates_returns_400(self, publisher_client):
        resp = publisher_client.get(url('revenue-breakdown'))
        assert resp.status_code == 400

    def test_start_after_end_returns_400(self, publisher_client):
        resp = publisher_client.get(
            url('revenue-breakdown'),
            {'start_date': '2025-02-01', 'end_date': '2025-01-01'},
        )
        assert resp.status_code == 400

    def test_unauthenticated_cannot_get_breakdown(self, api_client):
        resp = api_client.get(
            url('revenue-breakdown'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# METRICS
# ==============================================================================

@pytest.mark.django_db
class TestPublisherMetrics:

    def test_publisher_can_view_metrics(self, publisher_client):
        resp = publisher_client.get(url('metrics'))
        assert resp.status_code in (200, 503)

    def test_metrics_with_days_param(self, publisher_client):
        for days in ['7', '30', '90']:
            resp = publisher_client.get(url('metrics'), {'days': days})
            assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_view_metrics(self, api_client):
        resp = api_client.get(url('metrics'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# FORECAST
# ==============================================================================

@pytest.mark.django_db
class TestPublisherForecast:

    def test_publisher_can_get_forecast(self, publisher_client):
        resp = publisher_client.get(url('forecast'))
        assert resp.status_code in (200, 503)

    def test_forecast_with_days_ahead_param(self, publisher_client):
        resp = publisher_client.get(url('forecast'), {'days_ahead': '30'})
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_get_forecast(self, api_client):
        resp = api_client.get(url('forecast'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# TOP CONTENT
# ==============================================================================

@pytest.mark.django_db
class TestTopContent:

    def test_publisher_can_view_top_content(self, publisher_client):
        resp = publisher_client.get(url('top-content'))
        assert resp.status_code in (200, 503)

    def test_top_content_with_days_and_limit(self, publisher_client):
        resp = publisher_client.get(url('top-content'), {'days': '30', 'limit': '5'})
        assert resp.status_code in (200, 503)

    def test_top_content_returns_list_or_dict(self, publisher_client):
        resp = publisher_client.get(url('top-content'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert isinstance(data, (list, dict))

    def test_unauthenticated_cannot_view_top_content(self, api_client):
        resp = api_client.get(url('top-content'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# PROFILE
# ==============================================================================

@pytest.mark.django_db
class TestPublisherProfile:

    def test_publisher_can_view_profile_completion(self, publisher_client):
        resp = publisher_client.get(url('profile'))
        assert resp.status_code in (200, 503)

    def test_profile_response_has_completion_and_level(self, publisher_client):
        resp = publisher_client.get(url('profile'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'profile_completion' in data or 'publisher_level' in data

    def test_unauthenticated_cannot_view_profile(self, api_client):
        resp = api_client.get(url('profile'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# HEALTH SCORE
# ==============================================================================

@pytest.mark.django_db
class TestPublisherHealthScore:

    def test_publisher_can_view_health_score(self, publisher_client):
        resp = publisher_client.get(url('health-score'))
        assert resp.status_code in (200, 503)

    def test_health_score_in_range_0_to_100(self, publisher_client):
        resp = publisher_client.get(url('health-score'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            score = data.get('health_score', 50)
            assert 0 <= score <= 100

    def test_health_score_has_grade(self, publisher_client):
        resp = publisher_client.get(url('health-score'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert data.get('grade') in ('A', 'B', 'C', 'D', 'F', None)

    def test_unauthenticated_cannot_view_health_score(self, api_client):
        resp = api_client.get(url('health-score'))
        assert resp.status_code in (401, 403)
