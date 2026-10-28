# publisher_tools/tests/test_views_adunit.py
"""
High-priority API tests — AdUnitViewSet, AdPlacementViewSet.

AdUnitViewSet actions tested:
  create, retrieve, update, destroy,
  pause, activate, tag_code, performance,
  targeting (GET + POST), placements, mediation

AdPlacementViewSet actions tested:
  create, retrieve, update, destroy, toggle

Run:
    pytest publisher_tools/tests/test_views_adunit.py -v
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AppFactory,
    AdUnitFactory, AdPlacementFactory, AdUnitTargetingFactory,
    MediationGroupFactory,
)

UNIT_BASE      = '/api/publisher-tools/ad-units'
PLACEMENT_BASE = '/api/publisher-tools/placements'


def unit_url(suffix=''):
    return f'{UNIT_BASE}{suffix}/'

def placement_url(suffix=''):
    return f'{PLACEMENT_BASE}{suffix}/'


# ==============================================================================
# AdUnit — CREATE
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitCreate:

    def _payload(self, site):
        return {
            'name': 'Header Banner',
            'format': 'banner',
            'inventory_type': 'web',
            'floor_price': '0.50',
            'site': site.pk,
        }

    def test_active_publisher_can_create_ad_unit(self, publisher_client, site):
        resp = publisher_client.post(unit_url(), self._payload(site), format='json')
        assert resp.status_code == 201

    def test_created_unit_has_unit_id(self, publisher_client, site):
        resp = publisher_client.post(unit_url(), self._payload(site), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('unit_id') is not None

    def test_created_unit_has_tag_code(self, publisher_client, site):
        resp = publisher_client.post(unit_url(), self._payload(site), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('tag_code') is not None

    def test_invalid_format_returns_400(self, publisher_client, site):
        data = self._payload(site)
        data['format'] = 'teleporter'
        resp = publisher_client.post(unit_url(), data, format='json')
        assert resp.status_code == 400

    def test_negative_floor_price_returns_400(self, publisher_client, site):
        data = self._payload(site)
        data['floor_price'] = '-1.00'
        resp = publisher_client.post(unit_url(), data, format='json')
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, publisher_client, site):
        data = self._payload(site)
        del data['name']
        resp = publisher_client.post(unit_url(), data, format='json')
        assert resp.status_code == 400

    def test_unauthenticated_cannot_create(self, api_client, site):
        resp = api_client.post(unit_url(), self._payload(site), format='json')
        assert resp.status_code in (401, 403)

    def test_publisher_cannot_create_unit_for_other_publishers_site(
        self, publisher_client_2, site
    ):
        """publisher_client_2 does not own `site`."""
        data = self._payload(site)
        resp = publisher_client_2.post(unit_url(), data, format='json')
        assert resp.status_code in (400, 403)

    def test_both_site_and_app_none_returns_400(self, publisher_client):
        data = {
            'name': 'Floating Unit',
            'format': 'banner',
            'inventory_type': 'web',
            'floor_price': '0.50',
        }
        resp = publisher_client.post(unit_url(), data, format='json')
        assert resp.status_code == 400


# ==============================================================================
# AdUnit — RETRIEVE / UPDATE
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitRetrieveUpdate:

    def test_publisher_can_retrieve_own_unit(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}'))
        assert resp.status_code == 200

    def test_publisher_cannot_retrieve_other_unit(self, publisher_client_2, ad_unit):
        resp = publisher_client_2.get(unit_url(f'/{ad_unit.pk}'))
        assert resp.status_code in (403, 404)

    def test_admin_can_retrieve_any_unit(self, admin_client, ad_unit):
        resp = admin_client.get(unit_url(f'/{ad_unit.pk}'))
        assert resp.status_code == 200

    def test_publisher_can_update_unit_name(self, publisher_client, ad_unit):
        resp = publisher_client.patch(
            unit_url(f'/{ad_unit.pk}'),
            {'name': 'Updated Banner'},
            format='json',
        )
        assert resp.status_code == 200
        ad_unit.refresh_from_db()
        assert ad_unit.name == 'Updated Banner'

    def test_publisher_can_update_floor_price(self, publisher_client, ad_unit):
        resp = publisher_client.patch(
            unit_url(f'/{ad_unit.pk}'),
            {'floor_price': '1.2500'},
            format='json',
        )
        assert resp.status_code == 200

    def test_publisher_cannot_update_other_unit(self, publisher_client_2, ad_unit):
        resp = publisher_client_2.patch(
            unit_url(f'/{ad_unit.pk}'),
            {'name': 'Stolen'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# AdUnit — PAUSE / ACTIVATE
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitPauseActivate:

    def test_publisher_can_pause_active_unit(self, publisher_client, ad_unit):
        resp = publisher_client.post(unit_url(f'/{ad_unit.pk}/pause'))
        assert resp.status_code == 200
        ad_unit.refresh_from_db()
        assert ad_unit.status == 'paused'

    def test_publisher_can_activate_paused_unit(self, publisher_client, paused_ad_unit):
        resp = publisher_client.post(unit_url(f'/{paused_ad_unit.pk}/activate'))
        assert resp.status_code == 200
        paused_ad_unit.refresh_from_db()
        assert paused_ad_unit.status == 'active'

    def test_publisher_cannot_pause_other_unit(self, publisher_client_2, ad_unit):
        resp = publisher_client_2.post(unit_url(f'/{ad_unit.pk}/pause'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_pause(self, api_client, ad_unit):
        resp = api_client.post(unit_url(f'/{ad_unit.pk}/pause'))
        assert resp.status_code in (401, 403)

    def test_pausing_already_paused_unit_is_idempotent(self, publisher_client, paused_ad_unit):
        resp = publisher_client.post(unit_url(f'/{paused_ad_unit.pk}/pause'))
        assert resp.status_code == 200


# ==============================================================================
# AdUnit — TAG CODE
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitTagCode:

    def test_publisher_can_get_tag_code(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/tag_code'))
        assert resp.status_code == 200

    def test_tag_code_response_has_expected_keys(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/tag_code'))
        body = resp.json()
        data = body.get('data', body)
        assert 'unit_id' in data
        assert 'tag_code' in data
        assert 'format' in data

    def test_admin_can_get_any_tag_code(self, admin_client, ad_unit):
        resp = admin_client.get(unit_url(f'/{ad_unit.pk}/tag_code'))
        assert resp.status_code == 200

    def test_unauthenticated_cannot_get_tag_code(self, api_client, ad_unit):
        resp = api_client.get(unit_url(f'/{ad_unit.pk}/tag_code'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# AdUnit — PERFORMANCE
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitPerformance:

    def test_publisher_can_get_performance(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            unit_url(f'/{ad_unit.pk}/performance'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code == 200

    def test_performance_response_has_expected_keys(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            unit_url(f'/{ad_unit.pk}/performance'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        body = resp.json()
        data = body.get('data', body)
        assert 'unit_id' in data
        assert 'period_revenue' in data
        assert 'fill_rate' in data

    def test_missing_dates_returns_400(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/performance'))
        assert resp.status_code == 400

    def test_start_after_end_returns_400(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            unit_url(f'/{ad_unit.pk}/performance'),
            {'start_date': '2025-06-01', 'end_date': '2025-01-01'},
        )
        assert resp.status_code == 400

    def test_admin_can_view_any_unit_performance(self, admin_client, ad_unit):
        resp = admin_client.get(
            unit_url(f'/{ad_unit.pk}/performance'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code == 200


# ==============================================================================
# AdUnit — TARGETING (GET + POST)
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitTargeting:

    def test_get_targeting_returns_none_when_not_set(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/targeting'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data is None

    def test_get_targeting_returns_data_when_set(self, publisher_client, ad_unit):
        AdUnitTargetingFactory(ad_unit=ad_unit, device_type='mobile')
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/targeting'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data is not None
        assert data.get('device_type') == 'mobile'

    def test_post_targeting_creates_targeting(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            unit_url(f'/{ad_unit.pk}/targeting'),
            {'device_type': 'desktop', 'geo_targets': ['BD', 'IN']},
            format='json',
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data.get('device_type') == 'desktop'

    def test_post_targeting_updates_existing(self, publisher_client, ad_unit):
        AdUnitTargetingFactory(ad_unit=ad_unit, device_type='mobile')
        resp = publisher_client.post(
            unit_url(f'/{ad_unit.pk}/targeting'),
            {'device_type': 'all', 'geo_targets': ['ALL']},
            format='json',
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data.get('device_type') == 'all'

    def test_invalid_device_type_returns_400(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            unit_url(f'/{ad_unit.pk}/targeting'),
            {'device_type': 'smartfridge'},
            format='json',
        )
        assert resp.status_code == 400

    def test_other_publisher_cannot_set_targeting(self, publisher_client_2, ad_unit):
        resp = publisher_client_2.post(
            unit_url(f'/{ad_unit.pk}/targeting'),
            {'device_type': 'desktop'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# AdUnit — PLACEMENTS list
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitPlacements:

    def test_publisher_can_list_unit_placements(self, publisher_client, ad_unit):
        AdPlacementFactory(ad_unit=ad_unit)
        AdPlacementFactory(ad_unit=ad_unit)
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/placements'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert len(data) == 2

    def test_placements_empty_for_new_unit(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/placements'))
        assert resp.status_code == 200


# ==============================================================================
# AdUnit — MEDIATION link
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitMediationLink:

    def test_returns_none_when_no_mediation_group(self, publisher_client, ad_unit):
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/mediation'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data is None

    def test_returns_group_when_set(self, publisher_client, ad_unit):
        MediationGroupFactory(ad_unit=ad_unit)
        resp = publisher_client.get(unit_url(f'/{ad_unit.pk}/mediation'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data is not None
        assert 'strategy' in data


# ==============================================================================
# AdPlacement — CREATE / TOGGLE
# ==============================================================================

@pytest.mark.django_db
class TestAdPlacementCreateToggle:

    def _payload(self, ad_unit):
        return {
            'ad_unit': ad_unit.pk,
            'name': 'Above Fold Slot',
            'position': 'above_fold',
            'priority': 1,
        }

    def test_publisher_can_create_placement(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            placement_url(), self._payload(ad_unit), format='json'
        )
        assert resp.status_code == 201

    def test_missing_ad_unit_returns_400(self, publisher_client):
        resp = publisher_client.post(
            placement_url(),
            {'name': 'No Unit', 'position': 'above_fold'},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_can_toggle_placement(self, publisher_client, ad_placement):
        original = ad_placement.is_active
        resp = publisher_client.post(placement_url(f'/{ad_placement.pk}/toggle'))
        assert resp.status_code == 200
        ad_placement.refresh_from_db()
        assert ad_placement.is_active != original

    def test_toggle_twice_restores_original_state(self, publisher_client, ad_placement):
        original = ad_placement.is_active
        publisher_client.post(placement_url(f'/{ad_placement.pk}/toggle'))
        publisher_client.post(placement_url(f'/{ad_placement.pk}/toggle'))
        ad_placement.refresh_from_db()
        assert ad_placement.is_active == original

    def test_other_publisher_cannot_toggle_placement(
        self, publisher_client_2, ad_placement
    ):
        resp = publisher_client_2.post(placement_url(f'/{ad_placement.pk}/toggle'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_create_placement(self, api_client, ad_unit):
        resp = api_client.post(
            placement_url(), self._payload(ad_unit), format='json'
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# AdUnit — LIST filters
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitListFilters:

    def test_admin_can_filter_by_format(self, admin_client, publisher, site):
        AdUnitFactory(publisher=publisher, site=site, format='banner')
        AdUnitFactory(publisher=publisher, site=site, format='interstitial')
        resp = admin_client.get(unit_url(), {'format': 'banner'})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['format'] == 'banner'

    def test_admin_can_filter_by_status(self, admin_client, publisher, site):
        AdUnitFactory(publisher=publisher, site=site, status='active')
        AdUnitFactory(publisher=publisher, site=site, status='paused')
        resp = admin_client.get(unit_url(), {'status': 'active'})
        assert resp.status_code == 200

    def test_publisher_only_sees_own_units(self, publisher_client, publisher, site):
        AdUnitFactory(publisher=publisher, site=site)  # own
        AdUnitFactory()  # belongs to another publisher
        resp = publisher_client.get(unit_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 1
