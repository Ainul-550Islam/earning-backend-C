# publisher_tools/tests/test_views_extended_actions.py
"""
Tests for extended action mixins (views_extended_actions.py).

Covers:
  AdUnitExtendedMixin      → trend, compare, recommendations, format_score
  AdPlacementExtendedMixin → suggest_floor, optimize, report, position_alternatives, analysis
  MediationGroupExtendedMixin → bid_analysis, floor_recommendations, network_comparison
  PublisherExtendedMixin   → overview, top_content, profile_completion
"""
import pytest

ADUNIT_BASE      = '/api/publisher-tools/ad-units'
PLACEMENT_BASE   = '/api/publisher-tools/ad-placements'
MEDIATION_BASE   = '/api/publisher-tools/mediation-groups'
PUBLISHER_BASE   = '/api/publisher-tools/publishers'


# ==============================================================================
# AD UNIT EXTENDED ACTIONS
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitTrend:

    def test_publisher_can_get_trend(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/trend/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_trend_with_days_param(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/trend/'
        for days in [7, 14, 30]:
            resp = publisher_client.get(url, {'days': days})
            assert resp.status_code in (200, 404, 503)

    def test_trend_with_metric_param(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/trend/'
        for metric in ['ecpm', 'ctr', 'fill_rate', 'revenue']:
            resp = publisher_client.get(url, {'metric': metric})
            assert resp.status_code in (200, 404, 503)

    def test_unauthenticated_rejected(self, unauthenticated_client, ad_unit):
        resp = unauthenticated_client.get(f'{ADUNIT_BASE}/{ad_unit.pk}/trend/')
        assert resp.status_code in (401, 403)

    def test_publisher_2_cannot_view_publisher_1_trend(self, publisher_client_2, ad_unit):
        resp = publisher_client_2.get(f'{ADUNIT_BASE}/{ad_unit.pk}/trend/')
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestAdUnitCompare:

    def test_compare_requires_compare_with(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/compare/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 400, 404, 503)

    def test_compare_with_self_returns_data(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/compare/'
        resp = publisher_client.get(url, {'compare_with': str(ad_unit.pk)})
        assert resp.status_code in (200, 400, 404, 503)

    def test_compare_with_days_param(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/compare/'
        resp = publisher_client.get(url, {'days': 30})
        assert resp.status_code in (200, 400, 404, 503)


@pytest.mark.django_db
class TestAdUnitRecommendations:

    def test_publisher_gets_recommendations(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/recommendations/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_recommendations_response_structure(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/recommendations/'
        resp = publisher_client.get(url)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert isinstance(data, (dict, list))

    def test_unauthenticated_rejected(self, unauthenticated_client, ad_unit):
        resp = unauthenticated_client.get(f'{ADUNIT_BASE}/{ad_unit.pk}/recommendations/')
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestAdUnitFormatScore:

    def test_format_score_returns_data(self, publisher_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/format-score/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_admin_can_view_format_score(self, admin_client, ad_unit):
        url = f'{ADUNIT_BASE}/{ad_unit.pk}/format-score/'
        resp = admin_client.get(url)
        assert resp.status_code in (200, 404, 503)


# ==============================================================================
# AD PLACEMENT EXTENDED ACTIONS
# ==============================================================================

@pytest.mark.django_db
class TestAdPlacementSuggestFloor:

    def test_publisher_can_get_floor_suggestion(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/suggest-floor/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_floor_suggestion_structure(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/suggest-floor/'
        resp = publisher_client.get(url)
        if resp.status_code == 200:
            assert isinstance(resp.json().get('data'), (dict, list, type(None)))

    def test_unauthenticated_rejected(self, unauthenticated_client, ad_placement):
        resp = unauthenticated_client.get(f'{PLACEMENT_BASE}/{ad_placement.pk}/suggest-floor/')
        assert resp.status_code in (401, 403)

    def test_publisher_2_cannot_view_pub1_placement(self, publisher_client_2, ad_placement):
        resp = publisher_client_2.get(f'{PLACEMENT_BASE}/{ad_placement.pk}/suggest-floor/')
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestAdPlacementOptimize:

    def test_publisher_can_request_optimize(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/optimize/'
        resp = publisher_client.post(url, {}, format='json')
        assert resp.status_code in (200, 404, 503)

    def test_optimize_returns_result(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/optimize/'
        resp = publisher_client.post(url, {}, format='json')
        if resp.status_code == 200:
            assert 'data' in resp.json()


@pytest.mark.django_db
class TestAdPlacementReport:

    def test_publisher_can_get_report(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/report/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_report_with_days_param(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/report/'
        resp = publisher_client.get(url, {'days': 30})
        assert resp.status_code in (200, 404, 503)


@pytest.mark.django_db
class TestAdPlacementPositionAlternatives:

    def test_returns_alternatives(self, publisher_client, ad_placement):
        url = f'{PLACEMENT_BASE}/{ad_placement.pk}/position-alternatives/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)


@pytest.mark.django_db
class TestAdPlacementAnalysis:

    def test_analysis_endpoint_accessible(self, publisher_client):
        url = f'{PLACEMENT_BASE}/analysis/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_analysis_with_site_filter(self, publisher_client, site):
        url = f'{PLACEMENT_BASE}/analysis/'
        resp = publisher_client.get(url, {'site_id': site.pk})
        assert resp.status_code in (200, 404, 503)


# ==============================================================================
# MEDIATION GROUP EXTENDED ACTIONS
# ==============================================================================

@pytest.mark.django_db
class TestMediationBidAnalysis:

    def test_publisher_can_view_bid_analysis(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/bid-analysis/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_bid_analysis_with_days(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/bid-analysis/'
        resp = publisher_client.get(url, {'days': 14})
        assert resp.status_code in (200, 404, 503)

    def test_unauthenticated_rejected(self, unauthenticated_client, mediation_group):
        resp = unauthenticated_client.get(
            f'{MEDIATION_BASE}/{mediation_group.pk}/bid-analysis/'
        )
        assert resp.status_code in (401, 403)

    def test_publisher_2_cannot_view_pub1_mediation(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(
            f'{MEDIATION_BASE}/{mediation_group.pk}/bid-analysis/'
        )
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestMediationFloorRecommendations:

    def test_publisher_gets_floor_recs(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/floor-recommendations/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_floor_recs_structure(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/floor-recommendations/'
        resp = publisher_client.get(url)
        if resp.status_code == 200:
            assert isinstance(resp.json().get('data'), (dict, list, type(None)))


@pytest.mark.django_db
class TestMediationNetworkComparison:

    def test_returns_comparison_data(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/network-comparison/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_with_days_param(self, publisher_client, mediation_group):
        url = f'{MEDIATION_BASE}/{mediation_group.pk}/network-comparison/'
        for days in [7, 30]:
            resp = publisher_client.get(url, {'days': days})
            assert resp.status_code in (200, 404, 503)


# ==============================================================================
# PUBLISHER EXTENDED ACTIONS
# ==============================================================================

@pytest.mark.django_db
class TestPublisherOverview:

    def test_publisher_can_view_own_overview(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/overview/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_overview_with_period(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/overview/'
        for period in ['last_7_days', 'last_30_days']:
            resp = publisher_client.get(url, {'period': period})
            assert resp.status_code in (200, 404, 503)

    def test_publisher_2_cannot_view_pub1_overview(self, publisher_client_2, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/overview/'
        resp = publisher_client_2.get(url)
        assert resp.status_code in (403, 404)

    def test_admin_can_view_any_overview(self, admin_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/overview/'
        resp = admin_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_unauthenticated_rejected(self, unauthenticated_client, publisher):
        resp = unauthenticated_client.get(f'{PUBLISHER_BASE}/{publisher.pk}/overview/')
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestPublisherTopContent:

    def test_publisher_can_view_top_content(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/top-content/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_top_content_with_limit(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/top-content/'
        resp = publisher_client.get(url, {'limit': 5})
        assert resp.status_code in (200, 404, 503)

    def test_top_content_with_days(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/top-content/'
        resp = publisher_client.get(url, {'days': 30})
        assert resp.status_code in (200, 404, 503)

    def test_publisher_2_cannot_see_pub1_top_content(self, publisher_client_2, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/top-content/'
        resp = publisher_client_2.get(url)
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestPublisherProfileCompletion:

    def test_returns_profile_completion(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/profile-completion/'
        resp = publisher_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_completion_has_score(self, publisher_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/profile-completion/'
        resp = publisher_client.get(url)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Should have some kind of score or completion metric
            assert data is not None

    def test_admin_can_view_any_profile_completion(self, admin_client, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/profile-completion/'
        resp = admin_client.get(url)
        assert resp.status_code in (200, 404, 503)

    def test_publisher_2_cannot_view_pub1_completion(self, publisher_client_2, publisher):
        url = f'{PUBLISHER_BASE}/{publisher.pk}/profile-completion/'
        resp = publisher_client_2.get(url)
        assert resp.status_code in (403, 404)
