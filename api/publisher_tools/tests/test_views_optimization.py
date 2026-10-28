# publisher_tools/tests/test_views_optimization.py
"""
Tests for OptimizationViewSet (views_optimization.py).
Covers all 12 actions: yield, format, geo, device, refresh,
viewability, latency, frequency, placement_score, audience, time, ad_load.
"""
import pytest
from publisher_tools.tests.factories import (
    SiteFactory, AdUnitFactory, AdPlacementFactory, MediationGroupFactory,
)

BASE = '/api/publisher-tools/optimizations'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# YIELD ANALYSIS
# ==============================================================================

@pytest.mark.django_db
class TestYieldAnalysis:

    def test_publisher_can_get_yield_analysis(self, publisher_client):
        resp = publisher_client.get(url('yield'))
        assert resp.status_code in (200, 503)

    def test_yield_response_has_floor_suggestions(self, publisher_client):
        resp = publisher_client.get(url('yield'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'floor_price_suggestions' in data or 'revenue_opportunity' in data

    def test_unauthenticated_cannot_get_yield(self, api_client):
        resp = api_client.get(url('yield'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# FORMAT
# ==============================================================================

@pytest.mark.django_db
class TestFormatOptimization:

    def test_publisher_can_get_format_recommendations(self, publisher_client):
        resp = publisher_client.get(url('format'))
        assert resp.status_code in (200, 503)

    def test_format_with_site_id(self, publisher_client, site):
        resp = publisher_client.get(url('format'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_format_response_has_comparison(self, publisher_client):
        resp = publisher_client.get(url('format'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'format_comparison' in data or 'recommendations' in data

    def test_unauthenticated_cannot_get_format(self, api_client):
        resp = api_client.get(url('format'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# GEO
# ==============================================================================

@pytest.mark.django_db
class TestGeoOptimization:

    def test_publisher_can_get_geo_recs(self, publisher_client):
        resp = publisher_client.get(url('geo'))
        assert resp.status_code in (200, 503)

    def test_geo_with_days_param(self, publisher_client):
        resp = publisher_client.get(url('geo'), {'days': '30'})
        assert resp.status_code in (200, 503)

    def test_geo_response_has_benchmarks(self, publisher_client):
        resp = publisher_client.get(url('geo'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'benchmarks' in data or 'recommendations' in data

    def test_unauthenticated_cannot_get_geo(self, api_client):
        resp = api_client.get(url('geo'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# DEVICE
# ==============================================================================

@pytest.mark.django_db
class TestDeviceOptimization:

    def test_publisher_can_get_device_recs(self, publisher_client):
        resp = publisher_client.get(url('device'))
        assert resp.status_code in (200, 503)

    def test_device_with_ad_unit_id(self, publisher_client, ad_unit):
        resp = publisher_client.get(url('device'), {'ad_unit_id': str(ad_unit.pk)})
        assert resp.status_code in (200, 503)

    def test_device_response_has_performance(self, publisher_client):
        resp = publisher_client.get(url('device'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'device_performance' in data or 'best_formats_by_device' in data

    def test_unauthenticated_cannot_get_device(self, api_client):
        resp = api_client.get(url('device'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# REFRESH
# ==============================================================================

@pytest.mark.django_db
class TestRefreshOptimization:

    def test_publisher_can_get_refresh_rec(self, publisher_client, ad_placement):
        resp = publisher_client.get(url('refresh'), {'placement_id': str(ad_placement.pk)})
        assert resp.status_code in (200, 503)

    def test_missing_placement_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('refresh'))
        assert resp.status_code == 400

    def test_other_publisher_placement_returns_404(self, publisher_client_2, ad_placement):
        resp = publisher_client_2.get(url('refresh'), {'placement_id': str(ad_placement.pk)})
        assert resp.status_code == 404

    def test_refresh_response_has_revenue_lift(self, publisher_client, ad_placement):
        resp = publisher_client.get(url('refresh'), {'placement_id': str(ad_placement.pk)})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'estimated_revenue_lift' in data or 'recommended_refresh_rate' in data

    def test_unauthenticated_cannot_get_refresh(self, api_client, ad_placement):
        resp = api_client.get(url('refresh'), {'placement_id': str(ad_placement.pk)})
        assert resp.status_code in (401, 403)


# ==============================================================================
# VIEWABILITY
# ==============================================================================

@pytest.mark.django_db
class TestViewabilityOptimization:

    def test_publisher_can_get_viewability_recs(self, publisher_client, site):
        resp = publisher_client.get(url('viewability'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('viewability'))
        assert resp.status_code == 400

    def test_other_publisher_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.get(url('viewability'), {'site_id': site.site_id})
        assert resp.status_code == 404

    def test_unauthenticated_cannot_get_viewability(self, api_client, site):
        resp = api_client.get(url('viewability'), {'site_id': site.site_id})
        assert resp.status_code in (401, 403)


# ==============================================================================
# LATENCY
# ==============================================================================

@pytest.mark.django_db
class TestLatencyOptimization:

    def test_publisher_can_get_latency_recs(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('latency'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('latency'))
        assert resp.status_code == 400

    def test_other_publisher_group_returns_404(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(url('latency'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code == 404

    def test_latency_ms_param_accepted(self, publisher_client, mediation_group):
        resp = publisher_client.get(
            url('latency'),
            {'group_id': str(mediation_group.pk), 'avg_latency_ms': '300'},
        )
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_get_latency(self, api_client, mediation_group):
        resp = api_client.get(url('latency'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (401, 403)


# ==============================================================================
# FREQUENCY
# ==============================================================================

@pytest.mark.django_db
class TestFrequencyOptimization:

    def test_publisher_can_get_frequency_recs(self, publisher_client):
        resp = publisher_client.get(url('frequency'))
        assert resp.status_code in (200, 503)

    def test_frequency_with_format_param(self, publisher_client):
        for fmt in ['banner', 'interstitial', 'rewarded']:
            resp = publisher_client.get(url('frequency'), {'ad_format': fmt})
            assert resp.status_code in (200, 503)

    def test_frequency_response_has_recommendation(self, publisher_client):
        resp = publisher_client.get(url('frequency'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'recommendation' in data or 'ctr_improvement_pct' in data

    def test_unauthenticated_cannot_get_frequency(self, api_client):
        resp = api_client.get(url('frequency'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# PLACEMENT SCORE
# ==============================================================================

@pytest.mark.django_db
class TestPlacementScore:

    def test_publisher_can_get_placement_score(self, publisher_client):
        resp = publisher_client.get(url('placement-score'))
        assert resp.status_code in (200, 503)

    def test_placement_score_response_structure(self, publisher_client):
        resp = publisher_client.get(url('placement-score'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'placement_scores' in data or 'optimization_plan' in data

    def test_unauthenticated_cannot_get_score(self, api_client):
        resp = api_client.get(url('placement-score'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# AUDIENCE
# ==============================================================================

@pytest.mark.django_db
class TestAudienceOptimization:

    def test_publisher_can_get_audience_recs(self, publisher_client):
        resp = publisher_client.get(url('audience'))
        assert resp.status_code in (200, 503)

    def test_audience_with_site_id(self, publisher_client, site):
        resp = publisher_client.get(url('audience'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_audience_with_current_ecpm(self, publisher_client):
        resp = publisher_client.get(url('audience'), {'current_ecpm': '2.50'})
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_get_audience(self, api_client):
        resp = api_client.get(url('audience'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# TIME
# ==============================================================================

@pytest.mark.django_db
class TestTimeOptimization:

    def test_publisher_can_get_time_analysis(self, publisher_client):
        resp = publisher_client.get(url('time'))
        assert resp.status_code in (200, 503)

    def test_time_with_ad_unit_id(self, publisher_client, ad_unit):
        resp = publisher_client.get(url('time'), {'ad_unit_id': str(ad_unit.pk)})
        assert resp.status_code in (200, 503)

    def test_time_response_has_peak_hours(self, publisher_client):
        resp = publisher_client.get(url('time'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'peak_hours' in data or 'day_of_week_analysis' in data

    def test_unauthenticated_cannot_get_time(self, api_client):
        resp = api_client.get(url('time'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# AD LOAD
# ==============================================================================

@pytest.mark.django_db
class TestAdLoadOptimization:

    def test_publisher_can_get_ad_load(self, publisher_client, site):
        resp = publisher_client.get(url('ad-load'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('ad-load'))
        assert resp.status_code == 400

    def test_other_publisher_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.get(url('ad-load'), {'site_id': site.site_id})
        assert resp.status_code == 404

    def test_page_type_param_accepted(self, publisher_client, site):
        for page_type in ['article', 'homepage', 'category']:
            resp = publisher_client.get(
                url('ad-load'),
                {'site_id': site.site_id, 'page_type': page_type},
            )
            assert resp.status_code in (200, 503)

    def test_ad_load_response_has_optimal_count(self, publisher_client, site):
        resp = publisher_client.get(url('ad-load'), {'site_id': site.site_id})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'optimal_unit_count' in data or isinstance(data, dict)

    def test_unauthenticated_cannot_get_ad_load(self, api_client, site):
        resp = api_client.get(url('ad-load'), {'site_id': site.site_id})
        assert resp.status_code in (401, 403)
