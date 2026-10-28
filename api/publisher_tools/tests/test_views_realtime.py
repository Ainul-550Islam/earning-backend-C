# publisher_tools/tests/test_views_realtime.py
"""
Tests for RealtimeViewSet (views_realtime.py)।

Covers all 7 @action endpoints:
  live_stats, dashboard_summary, realtime_stats, performance_alerts,
  realtime_fill_rate, track_ad_request, daily_report, daily_comparison

Pattern: pytest + APIClient + conftest.py fixtures
Auth:    publisher_client → force_authenticate(user=publisher_user)
"""

import pytest

BASE = '/api/publisher-tools/realtime'


# ══════════════════════════════════════════════════════════════════════════════
# LIVE STATS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLiveStats:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/live/').status_code in (401, 403)

    def test_returns_live_stats(self, publisher_client):
        assert publisher_client.get(f'{BASE}/live/').status_code in (200, 503)

    def test_response_has_today_revenue(self, publisher_client):
        r = publisher_client.get(f'{BASE}/live/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'today_revenue' in data

    def test_response_has_today_impressions(self, publisher_client):
        r = publisher_client.get(f'{BASE}/live/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'today_impressions' in data

    def test_response_has_account_status(self, publisher_client):
        r = publisher_client.get(f'{BASE}/live/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'account_status' in data

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/live/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardSummary:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/dashboard/').status_code in (401, 403)

    def test_default_period_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/dashboard/').status_code in (200, 503)

    def test_last_7_days_period(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/', {'period': 'last_7_days'})
        assert r.status_code in (200, 503)

    def test_last_30_days_period(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/', {'period': 'last_30_days'})
        assert r.status_code in (200, 503)

    def test_this_month_period(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/', {'period': 'this_month'})
        assert r.status_code in (200, 503)

    def test_today_period(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/', {'period': 'today'})
        assert r.status_code in (200, 503)

    def test_invalid_period_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/', {'period': 'totally_invalid'})
        assert r.status_code == 400

    def test_response_is_not_empty_when_200(self, publisher_client):
        r = publisher_client.get(f'{BASE}/dashboard/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert len(data) > 0


# ══════════════════════════════════════════════════════════════════════════════
# REALTIME STATS (last 1 hour aggregate)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRealtimeStats:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/stats/').status_code in (401, 403)

    def test_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/stats/').status_code in (200, 503)

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/stats/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE ALERTS (from RealtimeViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRealtimePerformanceAlerts:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/alerts/').status_code in (401, 403)

    def test_returns_alerts(self, publisher_client):
        assert publisher_client.get(f'{BASE}/alerts/').status_code in (200, 503)

    def test_response_has_alerts_list(self, publisher_client):
        r = publisher_client.get(f'{BASE}/alerts/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'alerts' in data
            assert isinstance(data['alerts'], list)

    def test_response_has_count(self, publisher_client):
        r = publisher_client.get(f'{BASE}/alerts/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'count' in data

    def test_count_matches_alerts_length(self, publisher_client):
        r = publisher_client.get(f'{BASE}/alerts/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert data['count'] == len(data['alerts'])


# ══════════════════════════════════════════════════════════════════════════════
# REALTIME FILL RATE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRealtimeFillRate:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/fill-rate/').status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/fill-rate/').status_code == 400

    def test_valid_unit_id_returns_data(self, publisher_client, ad_unit):
        r = publisher_client.get(f'{BASE}/fill-rate/', {'unit_id': ad_unit.unit_id})
        assert r.status_code in (200, 503)

    def test_nonexistent_unit_returns_404(self, publisher_client):
        r = publisher_client.get(f'{BASE}/fill-rate/', {'unit_id': 'UNIT-NOTEXIST-999'})
        assert r.status_code in (404, 503)

    def test_response_has_fill_rate_pct(self, publisher_client, ad_unit):
        r = publisher_client.get(f'{BASE}/fill-rate/', {'unit_id': ad_unit.unit_id})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'fill_rate_pct' in data

    def test_response_has_unit_id(self, publisher_client, ad_unit):
        r = publisher_client.get(f'{BASE}/fill-rate/', {'unit_id': ad_unit.unit_id})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert data.get('unit_id') == ad_unit.unit_id

    def test_response_has_cache_ttl(self, publisher_client, ad_unit):
        r = publisher_client.get(f'{BASE}/fill-rate/', {'unit_id': ad_unit.unit_id})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'cache_ttl_seconds' in data
            assert data['cache_ttl_seconds'] == 60


# ══════════════════════════════════════════════════════════════════════════════
# TRACK AD REQUEST
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTrackAdRequest:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/track-request/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        r = publisher_client.post(f'{BASE}/track-request/', {}, format='json')
        assert r.status_code == 400

    def test_valid_unit_id_tracked(self, publisher_client, ad_unit):
        r = publisher_client.post(
            f'{BASE}/track-request/', {'unit_id': ad_unit.unit_id}, format='json'
        )
        assert r.status_code in (200, 503)

    def test_nonexistent_unit_returns_404(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/track-request/', {'unit_id': 'UNIT-NOTEXIST-000'}, format='json'
        )
        assert r.status_code in (404, 503)

    def test_response_has_tracked_true(self, publisher_client, ad_unit):
        r = publisher_client.post(
            f'{BASE}/track-request/', {'unit_id': ad_unit.unit_id}, format='json'
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert data.get('tracked') is True

    def test_not_500(self, publisher_client, ad_unit):
        r = publisher_client.post(
            f'{BASE}/track-request/', {'unit_id': ad_unit.unit_id}, format='json'
        )
        assert r.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# DAILY REPORT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDailyReport:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/daily-report/').status_code in (401, 403)

    def test_default_today_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-report/').status_code in (200, 503)

    def test_specific_date_returns_data(self, publisher_client):
        r = publisher_client.get(f'{BASE}/daily-report/', {'date': '2025-06-01'})
        assert r.status_code in (200, 503)

    def test_invalid_date_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/daily-report/', {'date': 'not-a-date'})
        assert r.status_code == 400

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-report/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# DAILY COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDailyComparison:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/daily-comparison/').status_code in (401, 403)

    def test_default_7_days_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-comparison/').status_code in (200, 503)

    def test_custom_days_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/daily-comparison/', {'days': 14})
        assert r.status_code in (200, 503)

    def test_response_has_comparison_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/daily-comparison/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'comparison' in data

    def test_response_has_days_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/daily-comparison/', {'days': 7})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert data.get('days') == 7

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-comparison/').status_code != 500
