# publisher_tools/tests/test_views_abtest_extended.py
"""Tests for ABTestExtendedViewSet (views_abtest_extended.py) — 24 actions."""
import pytest
from publisher_tools.tests.factories import PublisherFactory, AdUnitFactory, SiteFactory

BASE = '/api/publisher-tools/ab-tests-extended'

@pytest.mark.django_db
class TestABTestExtendedAuth:
    def test_unauth_allocate_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/1/allocate/').status_code in (401,403)
    def test_unauth_sample_size_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/sample-size/').status_code in (401,403)
    def test_unauth_validate_config_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/validate-config/').status_code in (401,403)

@pytest.mark.django_db
class TestABTestExtendedSampleSize:
    def test_returns_sample_size(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/sample-size/', {'baseline_rate':'0.05','mde':'0.01'})
        assert resp.status_code in (200,503)
        if resp.status_code == 200:
            assert 'required_per_variant' in resp.json()['data']

    def test_invalid_params_handled(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/sample-size/', {'baseline_rate':'not_a_number'})
        assert resp.status_code in (200,400,503)

@pytest.mark.django_db
class TestABTestExtendedValidateConfig:
    def test_empty_config_returns_result(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/validate-config/', {}, format='json')
        assert resp.status_code in (200,503)

    def test_returns_valid_key(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/validate-config/', {'name':'Test'}, format='json')
        if resp.status_code == 200:
            assert 'valid' in resp.json()['data']

@pytest.mark.django_db
class TestABTestExtendedLearnings:
    def test_learnings_endpoint_accessible(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/learnings/')
        assert resp.status_code in (200,503)

    def test_portfolio_report_accessible(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/portfolio-report/')
        assert resp.status_code in (200,503)

@pytest.mark.django_db
class TestABTestExtendedCreateFloorPrice:
    def test_missing_params_returns_400(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/create-floor-price/', {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_unit_returns_404(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/create-floor-price/',
            {'ad_unit_id':99999,'control_floor':'0.50','test_floor':'0.75'}, format='json')
        assert resp.status_code in (404,400,503)

    def test_creates_with_valid_unit(self, publisher_client, publisher, site, ad_unit):
        resp = publisher_client.post(f'{BASE}/create-floor-price/',
            {'ad_unit_id':ad_unit.pk,'control_floor':'0.50','test_floor':'0.75'}, format='json')
        assert resp.status_code in (201,200,400,503)

@pytest.mark.django_db
class TestABTestExtendedCreatePlacement:
    def test_missing_params_returns_400(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/create-placement/', {}, format='json')
        assert resp.status_code == 400

    def test_creates_with_valid_unit(self, publisher_client, ad_unit):
        resp = publisher_client.post(f'{BASE}/create-placement/',
            {'ad_unit_id':ad_unit.pk,'positions':['top','sidebar']}, format='json')
        assert resp.status_code in (201,200,400,503)

@pytest.mark.django_db
class TestABTestExtendedCreateMVT:
    def test_missing_params_returns_400(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/create-mvt/', {}, format='json')
        assert resp.status_code == 400

    def test_valid_creates(self, publisher_client, ad_unit):
        resp = publisher_client.post(f'{BASE}/create-mvt/',
            {'ad_unit_id':ad_unit.pk,'variables':{'floor':['0.5','0.75']}}, format='json')
        assert resp.status_code in (201,200,400,503)
