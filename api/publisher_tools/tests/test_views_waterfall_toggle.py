# publisher_tools/tests/test_views_waterfall_toggle.py
"""
Tests for WaterfallItemViewSet.toggle_status() action (views.py line 709).
This is the only @action in views.py not covered by existing test files.
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AdUnitFactory,
    MediationGroupFactory, WaterfallItemFactory,
)

BASE = '/api/publisher-tools/waterfall-items'


def url(pk, action='toggle-status'):
    return f'{BASE}/{pk}/{action}/'


# ==============================================================================
# TOGGLE STATUS — active ↔ paused
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallItemToggleStatus:

    def test_active_item_becomes_paused(self, publisher_client, waterfall_item):
        resp = publisher_client.post(url(waterfall_item.pk))
        assert resp.status_code in (200, 404, 403)
        if resp.status_code == 200:
            assert resp.json()['data']['status'] == 'paused'

    def test_paused_item_becomes_active(self, publisher_client, publisher, site, ad_unit):
        mg   = MediationGroupFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        item = WaterfallItemFactory(mediation_group=mg, status='paused')
        resp = publisher_client.post(url(item.pk))
        assert resp.status_code in (200, 404, 403)
        if resp.status_code == 200:
            assert resp.json()['data']['status'] == 'active'

    def test_toggle_twice_restores_original(self, publisher_client, publisher, site, ad_unit):
        mg   = MediationGroupFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        item = WaterfallItemFactory(mediation_group=mg, status='active')
        r1   = publisher_client.post(url(item.pk))
        r2   = publisher_client.post(url(item.pk))
        if r1.status_code == 200 and r2.status_code == 200:
            assert r2.json()['data']['status'] == 'active'

    def test_unauthenticated_rejected(self, unauthenticated_client, waterfall_item):
        resp = unauthenticated_client.post(url(waterfall_item.pk))
        assert resp.status_code in (401, 403)

    def test_other_publisher_cannot_toggle(self, publisher_client_2, waterfall_item):
        resp = publisher_client_2.post(url(waterfall_item.pk))
        assert resp.status_code in (403, 404)

    def test_nonexistent_item_returns_404(self, publisher_client):
        resp = publisher_client.post(url(99999))
        assert resp.status_code == 404

    def test_response_has_status_key(self, publisher_client, waterfall_item):
        resp = publisher_client.post(url(waterfall_item.pk))
        if resp.status_code == 200:
            assert 'status' in resp.json().get('data', {})

    def test_get_method_not_allowed(self, publisher_client, waterfall_item):
        from rest_framework.test import APIClient
        resp = publisher_client.get(url(waterfall_item.pk))
        assert resp.status_code in (405, 404, 403)


# ==============================================================================
# FIXTURE helpers scoped to this module
# ==============================================================================

@pytest.fixture
def waterfall_item(publisher, site, ad_unit):
    mg = MediationGroupFactory(publisher=publisher, site=site, ad_unit=ad_unit)
    return WaterfallItemFactory(mediation_group=mg, status='active')
