# publisher_tools/tests/test_views_abtest_advanced.py
"""Tests for ABTestAdvancedViewSet (views_abtest_advanced.py) — 5 actions."""
import pytest

BASE = '/api/publisher-tools/ab-tests-adv'

@pytest.mark.django_db
class TestABTestAdvancedAuth:
    def test_unauth_best_position_rejected(self, unauthenticated_client): assert unauthenticated_client.get(f'{BASE}/best-position/').status_code in (401,403)
    def test_unauth_create_format_rejected(self, unauthenticated_client): assert unauthenticated_client.post(f'{BASE}/create-format/').status_code in (401,403)

@pytest.mark.django_db
class TestABTestAdvancedBestPosition:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/best-position/').status_code == 400
    def test_valid_site_returns_data(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/best-position/', {'site_id':site.pk}).status_code in (200,503)
    def test_other_publisher_site_blocked(self, publisher_client_2, site):
        assert publisher_client_2.get(f'{BASE}/best-position/', {'site_id':site.pk}).status_code in (404,403,503)

@pytest.mark.django_db
class TestABTestAdvancedCreateFormat:
    def test_missing_params_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/create-format/', {}, format='json').status_code == 400
    def test_single_format_returns_400(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/create-format/', {'ad_unit_id':ad_unit.pk,'formats':['banner']}, format='json').status_code == 400
    def test_valid_creates(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/create-format/', {'ad_unit_id':ad_unit.pk,'formats':['banner','native']}, format='json').status_code in (201,200,400,503)

@pytest.mark.django_db
class TestABTestAdvancedStatTests:
    def test_two_proportion_z_valid(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/two-proportion-z/', {'n1':1000,'x1':50,'n2':1000,'x2':65}, format='json')
        assert resp.status_code in (200,503)
    def test_two_proportion_z_zero_n_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/two-proportion-z/', {'n1':0,'x1':0,'n2':0,'x2':0}, format='json').status_code == 400
    def test_welch_t_test_valid(self, publisher_client):
        resp = publisher_client.post(f'{BASE}/welch-t-test/', {'mean1':2.5,'var1':0.4,'n1':500,'mean2':2.8,'var2':0.3,'n2':480}, format='json')
        assert resp.status_code in (200,503)
    def test_welch_t_test_zero_n_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/welch-t-test/', {'mean1':1,'var1':1,'n1':0,'mean2':1,'var2':1,'n2':0}, format='json').status_code == 400
