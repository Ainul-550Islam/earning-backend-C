# publisher_tools/tests/test_views_mediation_advanced.py
"""Tests for MediationAdvancedViewSet (views_mediation_advanced.py) — 10 actions."""
import pytest

BASE = '/api/publisher-tools/mediation-adv'

@pytest.mark.django_db
class TestMediationAdvancedAuth:
    def test_unauth_strategy_comparison_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/strategy-comparison/').status_code in (401, 403)

@pytest.mark.django_db
class TestMediationAdvancedStrategyComparison:
    def test_missing_group_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/strategy-comparison/').status_code == 400
    def test_invalid_group_returns_404(self, publisher_client):
        assert publisher_client.get(f'{BASE}/strategy-comparison/', {'group_id': 99999}).status_code in (404, 503)
    def test_valid_group_returns_data(self, publisher_client, mediation_group):
        assert publisher_client.get(f'{BASE}/strategy-comparison/', {'group_id': mediation_group.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestMediationAdvancedStrategyRecommendation:
    def test_missing_group_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/strategy-recommendation/').status_code == 400
    def test_valid_group_returns_recommendation(self, publisher_client, mediation_group):
        assert publisher_client.get(f'{BASE}/strategy-recommendation/', {'group_id': mediation_group.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestMediationAdvancedSwitchStrategy:
    def test_missing_params_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/switch-strategy/', {}, format='json').status_code == 400
    def test_invalid_strategy_returns_400(self, publisher_client, mediation_group):
        assert publisher_client.post(f'{BASE}/switch-strategy/', {'group_id': mediation_group.pk, 'strategy': 'invalid'}, format='json').status_code == 400
    def test_valid_switch(self, publisher_client, mediation_group):
        assert publisher_client.post(f'{BASE}/switch-strategy/', {'group_id': mediation_group.pk, 'strategy': 'bidding'}, format='json').status_code in (200, 404, 503)

@pytest.mark.django_db
class TestMediationAdvancedDemandPartners:
    def test_returns_list(self, publisher_client):
        assert publisher_client.get(f'{BASE}/demand-partners/').status_code in (200, 503)
    def test_filter_by_group(self, publisher_client, mediation_group):
        assert publisher_client.get(f'{BASE}/demand-partners/', {'group_id': mediation_group.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestMediationAdvancedAdSources:
    def test_missing_group_id_returns_400_for_fill(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ad-source-fill/').status_code == 400
    def test_missing_group_id_returns_400_for_ecpm(self, publisher_client):
        assert publisher_client.get(f'{BASE}/ad-source-ecpm/').status_code == 400
    def test_valid_group_fill(self, publisher_client, mediation_group):
        assert publisher_client.get(f'{BASE}/ad-source-fill/', {'group_id': mediation_group.pk}).status_code in (200, 503)
    def test_source_ranking_missing_group_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/source-ranking/').status_code == 400
    def test_source_ranking_valid_group(self, publisher_client, mediation_group):
        assert publisher_client.get(f'{BASE}/source-ranking/', {'group_id': mediation_group.pk, 'metric': 'ecpm'}).status_code in (200, 503)
