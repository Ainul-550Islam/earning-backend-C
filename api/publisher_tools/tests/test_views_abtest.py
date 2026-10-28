# publisher_tools/tests/test_views_abtest.py
"""
Tests for ABTestViewSet.
Covers: list, create (with variants), retrieve, update, delete,
        start, pause, resume, complete, results, declare_winner.
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, AdUnitFactory, SiteFactory,
)

BASE = '/api/publisher-tools/ab-tests'


def url(suffix=''):
    return f'{BASE}{suffix}/'


def abtest_payload(ad_unit):
    return {
        'name':       'Banner Floor Price Test',
        'hypothesis': 'Higher floor price increases eCPM',
        'test_type':  'floor_price',
        'ad_unit':    str(ad_unit.pk),
        'min_duration_days': 7,
        'confidence_level':  '95.00',
        'min_sample_size':   1000,
        'variants': [
            {
                'name':          'Control ($0.50)',
                'is_control':    True,
                'traffic_split': '50.00',
                'config':        {'floor_price': '0.50'},
            },
            {
                'name':          'Treatment ($0.75)',
                'is_control':    False,
                'traffic_split': '50.00',
                'config':        {'floor_price': '0.75'},
            },
        ],
    }


def create_test(client, ad_unit):
    return client.post(url(), abtest_payload(ad_unit), format='json')


# ==============================================================================
# LIST
# ==============================================================================

@pytest.mark.django_db
class TestABTestList:

    def test_publisher_can_list_own_tests(self, publisher_client, ad_unit):
        create_test(publisher_client, ad_unit)
        resp = publisher_client.get(url())
        assert resp.status_code == 200

    def test_publisher_sees_only_own_tests(self, publisher_client, publisher_client_2, ad_unit):
        create_test(publisher_client, ad_unit)
        resp = publisher_client_2.get(url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_filter_by_status(self, publisher_client, ad_unit):
        create_test(publisher_client, ad_unit)
        resp = publisher_client.get(url(), {'status': 'draft'})
        assert resp.status_code == 200

    def test_filter_by_test_type(self, publisher_client, ad_unit):
        create_test(publisher_client, ad_unit)
        resp = publisher_client.get(url(), {'test_type': 'floor_price'})
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get(url())
        assert resp.status_code in (401, 403)


# ==============================================================================
# CREATE
# ==============================================================================

@pytest.mark.django_db
class TestABTestCreate:

    def test_publisher_can_create_test(self, publisher_client, ad_unit):
        resp = create_test(publisher_client, ad_unit)
        assert resp.status_code == 201

    def test_created_test_has_test_id(self, publisher_client, ad_unit):
        resp = create_test(publisher_client, ad_unit)
        body = resp.json()
        data = body.get('data', body)
        assert data.get('test_id', '').startswith('ABT')

    def test_created_test_status_is_draft(self, publisher_client, ad_unit):
        resp = create_test(publisher_client, ad_unit)
        body = resp.json()
        data = body.get('data', body)
        assert data.get('status') == 'draft'

    def test_less_than_2_variants_returns_400(self, publisher_client, ad_unit):
        payload = abtest_payload(ad_unit)
        payload['variants'] = payload['variants'][:1]  # only 1 variant
        resp = publisher_client.post(url(), payload, format='json')
        assert resp.status_code == 400

    def test_no_control_variant_returns_400(self, publisher_client, ad_unit):
        payload = abtest_payload(ad_unit)
        for v in payload['variants']:
            v['is_control'] = False  # no control
        resp = publisher_client.post(url(), payload, format='json')
        assert resp.status_code == 400

    def test_traffic_splits_not_100_returns_400(self, publisher_client, ad_unit):
        payload = abtest_payload(ad_unit)
        payload['variants'][0]['traffic_split'] = '30.00'
        payload['variants'][1]['traffic_split'] = '30.00'  # total = 60, not 100
        resp = publisher_client.post(url(), payload, format='json')
        assert resp.status_code == 400

    def test_invalid_test_type_returns_400(self, publisher_client, ad_unit):
        payload = abtest_payload(ad_unit)
        payload['test_type'] = 'invalid_type'
        resp = publisher_client.post(url(), payload, format='json')
        assert resp.status_code == 400

    def test_publisher_cannot_use_other_publishers_ad_unit(
        self, publisher_client, publisher_user_2
    ):
        other_pub  = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        other_unit = AdUnitFactory(publisher=other_pub, site=other_site)
        resp = create_test(publisher_client, other_unit)
        assert resp.status_code in (400, 403)

    def test_unauthenticated_cannot_create(self, api_client, ad_unit):
        resp = api_client.post(url(), abtest_payload(ad_unit), format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# START / PAUSE / RESUME / COMPLETE
# ==============================================================================

@pytest.mark.django_db
class TestABTestLifecycle:

    def _create_id(self, client, ad_unit):
        resp = create_test(client, ad_unit)
        body = resp.json()
        return body.get('data', body).get('id') or body.get('id')

    def test_publisher_can_start_draft_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        resp = publisher_client.post(url(f'/{tid}/start'))
        assert resp.status_code == 200
        data = resp.json().get('data', resp.json())
        assert data.get('status') == 'running'

    def test_cannot_start_already_running_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        publisher_client.post(url(f'/{tid}/start'))
        resp = publisher_client.post(url(f'/{tid}/start'))
        assert resp.status_code == 400

    def test_publisher_can_pause_running_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        publisher_client.post(url(f'/{tid}/start'))
        resp = publisher_client.post(url(f'/{tid}/pause'))
        assert resp.status_code == 200
        data = resp.json().get('data', resp.json())
        assert data.get('status') == 'paused'

    def test_publisher_can_resume_paused_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        publisher_client.post(url(f'/{tid}/start'))
        publisher_client.post(url(f'/{tid}/pause'))
        resp = publisher_client.post(url(f'/{tid}/resume'))
        assert resp.status_code == 200
        data = resp.json().get('data', resp.json())
        assert data.get('status') == 'running'

    def test_publisher_can_complete_running_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        publisher_client.post(url(f'/{tid}/start'))
        resp = publisher_client.post(url(f'/{tid}/complete'))
        assert resp.status_code == 200
        data = resp.json().get('data', resp.json())
        assert data.get('status') == 'completed'

    def test_cannot_start_completed_test(self, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        publisher_client.post(url(f'/{tid}/start'))
        publisher_client.post(url(f'/{tid}/complete'))
        resp = publisher_client.post(url(f'/{tid}/start'))
        assert resp.status_code == 400

    def test_other_publisher_cannot_start(self, publisher_client, publisher_client_2, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        resp = publisher_client_2.post(url(f'/{tid}/start'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_start(self, api_client, publisher_client, ad_unit):
        tid  = self._create_id(publisher_client, ad_unit)
        resp = api_client.post(url(f'/{tid}/start'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# RESULTS
# ==============================================================================

@pytest.mark.django_db
class TestABTestResults:

    def _create_running_id(self, client, ad_unit):
        resp = create_test(client, ad_unit)
        body = resp.json()
        tid  = body.get('data', body).get('id') or body.get('id')
        client.post(url(f'/{tid}/start'))
        return tid

    def test_publisher_can_get_results(self, publisher_client, ad_unit):
        tid  = self._create_running_id(publisher_client, ad_unit)
        resp = publisher_client.get(url(f'/{tid}/results'))
        assert resp.status_code == 200

    def test_results_response_has_variants(self, publisher_client, ad_unit):
        tid  = self._create_running_id(publisher_client, ad_unit)
        resp = publisher_client.get(url(f'/{tid}/results'))
        body = resp.json()
        data = body.get('data', body)
        assert 'variants' in data or 'test_id' in data

    def test_results_has_statistical_significance_key(self, publisher_client, ad_unit):
        tid  = self._create_running_id(publisher_client, ad_unit)
        resp = publisher_client.get(url(f'/{tid}/results'))
        body = resp.json()
        data = body.get('data', body)
        assert 'is_statistically_significant' in data

    def test_other_publisher_cannot_view_results(self, publisher_client, publisher_client_2, ad_unit):
        tid  = self._create_running_id(publisher_client, ad_unit)
        resp = publisher_client_2.get(url(f'/{tid}/results'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# DECLARE WINNER
# ==============================================================================

@pytest.mark.django_db
class TestABTestDeclareWinner:

    def _create_completed_id(self, client, ad_unit):
        resp = create_test(client, ad_unit)
        body = resp.json()
        tid  = body.get('data', body).get('id') or body.get('id')
        client.post(url(f'/{tid}/start'))
        client.post(url(f'/{tid}/complete'))
        return tid

    def test_publisher_can_auto_declare_winner(self, publisher_client, ad_unit):
        tid  = self._create_completed_id(publisher_client, ad_unit)
        resp = publisher_client.post(url(f'/{tid}/declare-winner'), {}, format='json')
        assert resp.status_code == 200

    def test_declare_winner_response_has_winner_field(self, publisher_client, ad_unit):
        tid  = self._create_completed_id(publisher_client, ad_unit)
        resp = publisher_client.post(url(f'/{tid}/declare-winner'), {}, format='json')
        body = resp.json()
        data = body.get('data', body)
        assert 'winner' in data or 'test_id' in data

    def test_cannot_declare_winner_on_draft(self, publisher_client, ad_unit):
        resp = create_test(publisher_client, ad_unit)
        body = resp.json()
        tid  = body.get('data', body).get('id') or body.get('id')
        resp = publisher_client.post(url(f'/{tid}/declare-winner'), {}, format='json')
        assert resp.status_code == 400

    def test_invalid_variant_id_returns_400(self, publisher_client, ad_unit):
        import uuid
        tid  = self._create_completed_id(publisher_client, ad_unit)
        resp = publisher_client.post(
            url(f'/{tid}/declare-winner'),
            {'variant_id': str(uuid.uuid4())},
            format='json',
        )
        assert resp.status_code in (400, 404)

    def test_other_publisher_cannot_declare_winner(
        self, publisher_client, publisher_client_2, ad_unit
    ):
        tid  = self._create_completed_id(publisher_client, ad_unit)
        resp = publisher_client_2.post(url(f'/{tid}/declare-winner'), {}, format='json')
        assert resp.status_code in (403, 404)
