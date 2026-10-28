# publisher_tools/tests/test_views_mediation_full.py
"""
Tests for MediationToolsViewSet (views_mediation_full.py).
Covers: performance, network_compare, waterfall_report,
        efficiency, hybrid_config, floor_recs,
        full_optimize, bid_analysis.
"""
import pytest
from publisher_tools.tests.factories import (
    MediationGroupFactory, WaterfallItemFactory,
)

BASE = '/api/publisher-tools/mediation-tools'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# PERFORMANCE
# ==============================================================================

@pytest.mark.django_db
class TestMediationPerformance:

    def test_publisher_can_view_performance(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('performance'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('performance'))
        assert resp.status_code == 400

    def test_other_publisher_group_returns_404(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(url('performance'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code == 404

    def test_days_param_accepted(self, publisher_client, mediation_group):
        resp = publisher_client.get(
            url('performance'), {'group_id': str(mediation_group.pk), 'days': '7'}
        )
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_view(self, api_client, mediation_group):
        resp = api_client.get(url('performance'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (401, 403)


# ==============================================================================
# NETWORK COMPARE
# ==============================================================================

@pytest.mark.django_db
class TestNetworkCompare:

    def test_publisher_can_compare_networks(self, publisher_client):
        resp = publisher_client.get(url('network-compare'))
        assert resp.status_code in (200, 503)

    def test_network_compare_with_days_param(self, publisher_client):
        resp = publisher_client.get(url('network-compare'), {'days': '30'})
        assert resp.status_code in (200, 503)

    def test_response_has_comparison_key(self, publisher_client):
        resp = publisher_client.get(url('network-compare'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'comparison' in data or 'roi_report' in data

    def test_unauthenticated_cannot_compare(self, api_client):
        resp = api_client.get(url('network-compare'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# WATERFALL REPORT
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallReport:

    def test_publisher_can_get_waterfall_report(self, publisher_client):
        resp = publisher_client.get(
            url('waterfall-report'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code in (200, 503)

    def test_missing_dates_returns_400(self, publisher_client):
        resp = publisher_client.get(url('waterfall-report'))
        assert resp.status_code == 400

    def test_start_after_end_returns_400(self, publisher_client):
        resp = publisher_client.get(
            url('waterfall-report'),
            {'start_date': '2025-02-01', 'end_date': '2025-01-01'},
        )
        assert resp.status_code == 400

    def test_unauthenticated_cannot_get_report(self, api_client):
        resp = api_client.get(
            url('waterfall-report'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# EFFICIENCY
# ==============================================================================

@pytest.mark.django_db
class TestMediationEfficiency:

    def test_publisher_can_get_efficiency_score(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('efficiency'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_efficiency_has_score_and_grade(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('efficiency'), {'group_id': str(mediation_group.pk)})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'efficiency' in data
            assert data.get('grade') in ('A', 'B', 'C', 'D', None)

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('efficiency'))
        assert resp.status_code == 400

    def test_other_publisher_group_returns_404(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(url('efficiency'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code == 404


# ==============================================================================
# HYBRID CONFIG
# ==============================================================================

@pytest.mark.django_db
class TestHybridConfig:

    def test_publisher_can_get_hybrid_config(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('hybrid-config'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('hybrid-config'))
        assert resp.status_code == 400

    def test_other_publisher_group_returns_404(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(url('hybrid-config'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code == 404


# ==============================================================================
# FLOOR RECOMMENDATIONS
# ==============================================================================

@pytest.mark.django_db
class TestFloorRecommendations:

    def test_publisher_can_get_floor_recs(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('floor-recs'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_floor_recs_has_optimal_floor(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('floor-recs'), {'group_id': str(mediation_group.pk)})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'optimal_floor' in data or 'recommendations' in data

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('floor-recs'))
        assert resp.status_code == 400

    def test_unauthenticated_cannot_get_recs(self, api_client, mediation_group):
        resp = api_client.get(url('floor-recs'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (401, 403)


# ==============================================================================
# FULL OPTIMIZE
# ==============================================================================

@pytest.mark.django_db
class TestFullOptimize:

    def test_publisher_can_trigger_full_optimize(self, publisher_client, mediation_group):
        mediation_group.auto_optimize = True
        mediation_group.save()
        resp = publisher_client.post(url('full-optimize'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_optimize_response_has_count(self, publisher_client):
        resp = publisher_client.post(url('full-optimize'), {}, format='json')
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'optimized_groups' in data

    def test_unauthenticated_cannot_optimize(self, api_client):
        resp = api_client.post(url('full-optimize'), {}, format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# BID ANALYSIS
# ==============================================================================

@pytest.mark.django_db
class TestBidAnalysis:

    def test_publisher_can_get_bid_analysis(self, publisher_client, mediation_group):
        WaterfallItemFactory(mediation_group=mediation_group, priority=1)
        resp = publisher_client.get(url('bid-analysis'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (200, 503)

    def test_bid_analysis_response_structure(self, publisher_client, mediation_group):
        resp = publisher_client.get(url('bid-analysis'), {'group_id': str(mediation_group.pk)})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'lost_bids' in data or 'bid_density' in data

    def test_missing_group_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('bid-analysis'))
        assert resp.status_code == 400

    def test_days_param_accepted(self, publisher_client, mediation_group):
        resp = publisher_client.get(
            url('bid-analysis'), {'group_id': str(mediation_group.pk), 'days': '14'}
        )
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_get_analysis(self, api_client, mediation_group):
        resp = api_client.get(url('bid-analysis'), {'group_id': str(mediation_group.pk)})
        assert resp.status_code in (401, 403)
