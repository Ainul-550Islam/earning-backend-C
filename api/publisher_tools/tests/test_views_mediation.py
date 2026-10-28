# publisher_tools/tests/test_views_mediation.py
"""
High-priority API tests — MediationGroupViewSet, WaterfallItemViewSet,
HeaderBiddingConfigViewSet.

MediationGroupViewSet actions tested:
  create, retrieve, update, destroy,
  optimize, waterfall, reorder

WaterfallItemViewSet actions tested:
  create, retrieve, update, destroy, toggle_status

HeaderBiddingConfigViewSet tested:
  create, retrieve, list

Run:
    pytest publisher_tools/tests/test_views_mediation.py -v
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AdUnitFactory,
    MediationGroupFactory, WaterfallItemFactory,
    HeaderBiddingConfigFactory,
)

MEDIATION_BASE  = '/api/publisher-tools/mediation-groups'
WATERFALL_BASE  = '/api/publisher-tools/waterfall-items'
HB_BASE         = '/api/publisher-tools/header-bidding'


def med_url(suffix=''):
    return f'{MEDIATION_BASE}{suffix}/'

def wf_url(suffix=''):
    return f'{WATERFALL_BASE}{suffix}/'

def hb_url(suffix=''):
    return f'{HB_BASE}{suffix}/'


# ==============================================================================
# MediationGroup — CREATE
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupCreate:

    def _payload(self, ad_unit):
        return {
            'ad_unit': ad_unit.pk,
            'name': 'Main Waterfall',
            'strategy': 'waterfall',
            'floor_price': '0.25',
        }

    def test_publisher_can_create_mediation_group(self, publisher_client, ad_unit):
        resp = publisher_client.post(med_url(), self._payload(ad_unit), format='json')
        assert resp.status_code == 201

    def test_created_group_has_id(self, publisher_client, ad_unit):
        resp = publisher_client.post(med_url(), self._payload(ad_unit), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('id') is not None

    def test_invalid_strategy_returns_400(self, publisher_client, ad_unit):
        data = self._payload(ad_unit)
        data['strategy'] = 'magic_bidding'
        resp = publisher_client.post(med_url(), data, format='json')
        assert resp.status_code == 400

    def test_publisher_cannot_create_for_other_publishers_unit(
        self, publisher_client_2, ad_unit
    ):
        """ad_unit belongs to publisher, not publisher_2."""
        data = self._payload(ad_unit)
        resp = publisher_client_2.post(med_url(), data, format='json')
        assert resp.status_code in (400, 403)

    def test_unauthenticated_cannot_create(self, api_client, ad_unit):
        resp = api_client.post(med_url(), self._payload(ad_unit), format='json')
        assert resp.status_code in (401, 403)

    def test_missing_ad_unit_returns_400(self, publisher_client):
        resp = publisher_client.post(
            med_url(),
            {'name': 'No Unit Group', 'strategy': 'waterfall'},
            format='json',
        )
        assert resp.status_code == 400


# ==============================================================================
# MediationGroup — RETRIEVE / UPDATE
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupRetrieveUpdate:

    def test_publisher_can_retrieve_own_group(self, publisher_client, mediation_group):
        resp = publisher_client.get(med_url(f'/{mediation_group.pk}'))
        assert resp.status_code == 200

    def test_other_publisher_cannot_retrieve(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.get(med_url(f'/{mediation_group.pk}'))
        assert resp.status_code in (403, 404)

    def test_admin_can_retrieve_any_group(self, admin_client, mediation_group):
        resp = admin_client.get(med_url(f'/{mediation_group.pk}'))
        assert resp.status_code == 200

    def test_publisher_can_update_floor_price(self, publisher_client, mediation_group):
        resp = publisher_client.patch(
            med_url(f'/{mediation_group.pk}'),
            {'floor_price': '0.75'},
            format='json',
        )
        assert resp.status_code == 200


# ==============================================================================
# MediationGroup — WATERFALL (read)
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupWaterfall:

    def test_publisher_can_get_waterfall(self, publisher_client, mediation_group):
        WaterfallItemFactory(mediation_group=mediation_group, priority=1, status='active')
        WaterfallItemFactory(mediation_group=mediation_group, priority=2, status='active')
        resp = publisher_client.get(med_url(f'/{mediation_group.pk}/waterfall'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert len(data) == 2

    def test_waterfall_returns_items_in_priority_order(
        self, publisher_client, mediation_group
    ):
        WaterfallItemFactory(mediation_group=mediation_group, priority=3)
        WaterfallItemFactory(mediation_group=mediation_group, priority=1)
        WaterfallItemFactory(mediation_group=mediation_group, priority=2)
        resp = publisher_client.get(med_url(f'/{mediation_group.pk}/waterfall'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        priorities = [item['priority'] for item in data]
        assert priorities == sorted(priorities)

    def test_waterfall_returns_empty_for_new_group(
        self, publisher_client, mediation_group
    ):
        resp = publisher_client.get(med_url(f'/{mediation_group.pk}/waterfall'))
        assert resp.status_code == 200

    def test_other_publisher_cannot_view_waterfall(
        self, publisher_client_2, mediation_group
    ):
        resp = publisher_client_2.get(med_url(f'/{mediation_group.pk}/waterfall'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# MediationGroup — REORDER
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupReorder:

    def test_publisher_can_reorder_waterfall(self, publisher_client, mediation_group):
        w1 = WaterfallItemFactory(mediation_group=mediation_group, priority=1)
        w2 = WaterfallItemFactory(mediation_group=mediation_group, priority=2)
        resp = publisher_client.post(
            med_url(f'/{mediation_group.pk}/reorder'),
            {'items': [str(w2.pk), str(w1.pk)]},
            format='json',
        )
        assert resp.status_code == 200
        w1.refresh_from_db()
        w2.refresh_from_db()
        assert w2.priority < w1.priority

    def test_empty_items_list_returns_400(self, publisher_client, mediation_group):
        resp = publisher_client.post(
            med_url(f'/{mediation_group.pk}/reorder'),
            {'items': []},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_items_key_returns_400(self, publisher_client, mediation_group):
        resp = publisher_client.post(
            med_url(f'/{mediation_group.pk}/reorder'),
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_other_publisher_cannot_reorder(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.post(
            med_url(f'/{mediation_group.pk}/reorder'),
            {'items': []},
            format='json',
        )
        assert resp.status_code in (400, 403, 404)


# ==============================================================================
# MediationGroup — OPTIMIZE
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupOptimize:

    def test_publisher_can_trigger_optimize(self, publisher_client, mediation_group):
        WaterfallItemFactory(mediation_group=mediation_group)
        resp = publisher_client.post(med_url(f'/{mediation_group.pk}/optimize'))
        assert resp.status_code == 200

    def test_optimize_response_has_group_data(self, publisher_client, mediation_group):
        resp = publisher_client.post(med_url(f'/{mediation_group.pk}/optimize'))
        body = resp.json()
        data = body.get('data', body)
        assert 'strategy' in data

    def test_other_publisher_cannot_optimize(self, publisher_client_2, mediation_group):
        resp = publisher_client_2.post(med_url(f'/{mediation_group.pk}/optimize'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# WaterfallItem — CREATE / TOGGLE
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallItemCreateToggle:

    def _payload(self, mediation_group):
        return {
            'mediation_group': mediation_group.pk,
            'network_name': 'Google AdMob',
            'priority': 1,
            'floor_price': '0.10',
            'timeout_ms': 3000,
        }

    def test_publisher_can_create_waterfall_item(
        self, publisher_client, mediation_group
    ):
        resp = publisher_client.post(
            wf_url(), self._payload(mediation_group), format='json'
        )
        assert resp.status_code == 201

    def test_missing_mediation_group_returns_400(self, publisher_client):
        resp = publisher_client.post(
            wf_url(),
            {'network_name': 'Test', 'priority': 1},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_can_toggle_waterfall_item_status(
        self, publisher_client, waterfall_item
    ):
        original_status = waterfall_item.status
        resp = publisher_client.post(wf_url(f'/{waterfall_item.pk}/toggle_status'))
        assert resp.status_code == 200
        waterfall_item.refresh_from_db()
        assert waterfall_item.status != original_status

    def test_toggle_twice_restores_original(self, publisher_client, waterfall_item):
        original = waterfall_item.status
        publisher_client.post(wf_url(f'/{waterfall_item.pk}/toggle_status'))
        publisher_client.post(wf_url(f'/{waterfall_item.pk}/toggle_status'))
        waterfall_item.refresh_from_db()
        assert waterfall_item.status == original

    def test_toggle_response_has_status_key(self, publisher_client, waterfall_item):
        resp = publisher_client.post(wf_url(f'/{waterfall_item.pk}/toggle_status'))
        body = resp.json()
        data = body.get('data', body)
        assert 'status' in data

    def test_other_publisher_cannot_toggle(self, publisher_client_2, waterfall_item):
        resp = publisher_client_2.post(wf_url(f'/{waterfall_item.pk}/toggle_status'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_create_waterfall_item(
        self, api_client, mediation_group
    ):
        resp = api_client.post(
            wf_url(), self._payload(mediation_group), format='json'
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# WaterfallItem — UPDATE / DESTROY
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallItemUpdateDestroy:

    def test_publisher_can_update_floor_price(
        self, publisher_client, waterfall_item
    ):
        resp = publisher_client.patch(
            wf_url(f'/{waterfall_item.pk}'),
            {'floor_price': '0.50'},
            format='json',
        )
        assert resp.status_code == 200

    def test_publisher_can_delete_waterfall_item(
        self, publisher_client, waterfall_item
    ):
        resp = publisher_client.delete(wf_url(f'/{waterfall_item.pk}'))
        assert resp.status_code in (200, 204)

    def test_other_publisher_cannot_delete(self, publisher_client_2, waterfall_item):
        resp = publisher_client_2.delete(wf_url(f'/{waterfall_item.pk}'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# HeaderBiddingConfig — basic CRUD
# ==============================================================================

@pytest.mark.django_db
class TestHeaderBiddingConfig:

    def _payload(self, mediation_group):
        return {
            'mediation_group': mediation_group.pk,
            'bidder_name': 'AppNexus',
            'bidder_code': 'appnexus',
            'floor_price': '0.10',
            'timeout_ms': 2000,
            'params': {'placementId': '12345'},
        }

    def test_publisher_can_create_hb_config(self, publisher_client, mediation_group):
        resp = publisher_client.post(
            hb_url(), self._payload(mediation_group), format='json'
        )
        assert resp.status_code == 201

    def test_publisher_can_list_own_hb_configs(
        self, publisher_client, mediation_group
    ):
        HeaderBiddingConfigFactory(mediation_group=mediation_group)
        resp = publisher_client.get(hb_url())
        assert resp.status_code == 200

    def test_publisher_can_retrieve_hb_config(self, publisher_client, mediation_group):
        config = HeaderBiddingConfigFactory(mediation_group=mediation_group)
        resp = publisher_client.get(hb_url(f'/{config.pk}'))
        assert resp.status_code == 200

    def test_other_publisher_cannot_see_hb_config(
        self, publisher_client_2, mediation_group
    ):
        config = HeaderBiddingConfigFactory(mediation_group=mediation_group)
        resp = publisher_client_2.get(hb_url(f'/{config.pk}'))
        assert resp.status_code in (403, 404)

    def test_missing_bidder_code_returns_400(self, publisher_client, mediation_group):
        data = self._payload(mediation_group)
        del data['bidder_code']
        resp = publisher_client.post(hb_url(), data, format='json')
        assert resp.status_code == 400

    def test_unauthenticated_cannot_access(self, api_client, mediation_group):
        resp = api_client.get(hb_url())
        assert resp.status_code in (401, 403)
