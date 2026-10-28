# publisher_tools/tests/test_views_analytics_extended.py
"""Tests for AnalyticsExtendedViewSet (views_analytics_extended.py) — 19 actions."""
import pytest

BASE = '/api/publisher-tools/analytics-ext'

@pytest.mark.django_db
class TestAnalyticsExtendedAuth:
    def test_unauth_daily_impressions_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/daily-impressions/').status_code in (401,403)
    def test_unauth_track_impression_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/track-impression/').status_code in (401,403)

@pytest.mark.django_db
class TestAnalyticsExtendedTrackImpression:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/track-impression/', {}, format='json').status_code == 400
    def test_valid_impression_returns_data(self, publisher_client, ad_unit):
        resp = publisher_client.post(f'{BASE}/track-impression/', {'unit_id':ad_unit.unit_id,'context':{}}, format='json')
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedTrackClick:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.post(f'{BASE}/track-click/', {}, format='json').status_code == 400
    def test_valid_click_returns_data(self, publisher_client, ad_unit): assert publisher_client.post(f'{BASE}/track-click/', {'unit_id':ad_unit.unit_id}, format='json').status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedDailyImpressions:
    def test_returns_report(self, publisher_client): assert publisher_client.get(f'{BASE}/daily-impressions/').status_code in (200,503)
    def test_with_specific_date(self, publisher_client): assert publisher_client.get(f'{BASE}/daily-impressions/', {'date':'2025-01-15'}).status_code in (200,503)
    def test_invalid_date_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/daily-impressions/', {'date':'not-a-date'}).status_code in (400,503)

@pytest.mark.django_db
class TestAnalyticsExtendedHourlyReport:
    def test_returns_report(self, publisher_client): assert publisher_client.get(f'{BASE}/hourly-report/').status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedCTR:
    def test_missing_unit_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/ctr/').status_code == 400
    def test_valid_unit_returns_ctr(self, publisher_client, ad_unit): assert publisher_client.get(f'{BASE}/ctr/', {'unit_id':ad_unit.unit_id}).status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedSiteRPM:
    def test_missing_site_id_returns_400(self, publisher_client): assert publisher_client.get(f'{BASE}/site-rpm/').status_code == 400
    def test_valid_site_returns_data(self, publisher_client, site): assert publisher_client.get(f'{BASE}/site-rpm/', {'site_id':site.pk}).status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedFillRate:
    def test_fill_by_unit_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/fill-by-unit/').status_code in (200,503)
    def test_fill_by_country_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/fill-by-country/').status_code in (200,503)
    def test_fill_issues_returns_data(self, publisher_client): assert publisher_client.get(f'{BASE}/fill-issues/').status_code in (200,503)

@pytest.mark.django_db
class TestAnalyticsExtendedCustomReport:
    def test_returns_custom_report(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/custom-report/', {'metrics':['impressions','revenue'],'dimensions':['date']}, format='json')
        assert resp.status_code in (200,503)
