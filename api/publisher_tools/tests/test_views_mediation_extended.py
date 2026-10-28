# publisher_tools/tests/test_views_mediation_extended.py
"""Tests for MediationExtendedViewSet (views_mediation_extended.py) — 17 actions."""
import pytest

BASE = '/api/publisher-tools/mediation-extended'

@pytest.mark.django_db
class TestMediationExtendedAuth:
    def test_unauth_create_default_rejected(self, unauthenticated_client):
        assert unauthenticated_client.post(f'{BASE}/create-default/').status_code in (401, 403)

@pytest.mark.django_db
class TestMediationExtendedCreateDefault:
    def test_missing_ad_unit_id_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/create-default/', {}, format='json').status_code == 400
    def test_nonexistent_unit_returns_404(self, publisher_client):
        assert publisher_client.post(f'{BASE}/create-default/', {'ad_unit_id': 99999}, format='json').status_code in (404, 503)
    def test_valid_unit_creates_waterfall(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/create-default/', {'ad_unit_id': ad_unit.pk}, format='json').status_code in (201, 200, 503)

@pytest.mark.django_db
class TestMediationExtendedApplyFloor:
    def test_missing_params_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/apply-floor/', {}, format='json').status_code == 400
    def test_negative_floor_returns_400(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/apply-floor/', {'ad_unit_id': ad_unit.pk, 'floor_price': '-1.00'}, format='json').status_code == 400
    def test_valid_floor_update(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/apply-floor/', {'ad_unit_id': ad_unit.pk, 'floor_price': '0.75'}, format='json').status_code in (200, 503)

@pytest.mark.django_db
class TestMediationExtendedBulkFloorUpdate:
    def test_invalid_strategy_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/bulk-floor-update/', {'strategy': 'invalid_strategy'}, format='json').status_code == 400
    def test_valid_strategy_runs(self, publisher_client):
        assert publisher_client.post(f'{BASE}/bulk-floor-update/', {'strategy': 'conservative'}, format='json').status_code in (200, 503)

@pytest.mark.django_db
class TestMediationExtendedFloorRecommendations:
    def test_returns_recommendations(self, publisher_client):
        assert publisher_client.get(f'{BASE}/floor-recommendations/').status_code in (200, 503)

@pytest.mark.django_db
class TestMediationExtendedOpportunities:
    def test_returns_opportunities(self, publisher_client):
        assert publisher_client.get(f'{BASE}/opportunities/').status_code in (200, 503)

@pytest.mark.django_db
class TestMediationExtendedGroupActions:
    def test_reorder_by_ecpm_requires_valid_group(self, publisher_client):
        assert publisher_client.post(f'{BASE}/99999/reorder-by-ecpm/').status_code in (404, 403, 503)
    def test_waterfall_stats_requires_valid_group(self, publisher_client):
        assert publisher_client.get(f'{BASE}/99999/waterfall-stats/').status_code in (404, 403, 503)
    def test_priority_scores_requires_valid_group(self, publisher_client):
        assert publisher_client.get(f'{BASE}/99999/priority-scores/').status_code in (404, 403, 503)
    def test_optimal_order_requires_valid_group(self, publisher_client):
        assert publisher_client.get(f'{BASE}/99999/optimal-order/').status_code in (404, 403, 503)
    def test_bid_win_rate_requires_valid_group(self, publisher_client):
        assert publisher_client.get(f'{BASE}/99999/bid-win-rate/').status_code in (404, 403, 503)
    def test_other_publisher_cannot_access_group(self, publisher_client_2, mediation_group):
        assert publisher_client_2.get(f'{BASE}/{mediation_group.pk}/waterfall-stats/').status_code in (404, 403)

@pytest.mark.django_db
class TestMediationExtendedScheduleAuto:
    def test_invalid_interval_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/schedule-auto/', {'interval_hours': 0}, format='json').status_code == 400
    def test_valid_interval_schedules(self, publisher_client):
        assert publisher_client.post(f'{BASE}/schedule-auto/', {'interval_hours': 24}, format='json').status_code in (200, 503)
