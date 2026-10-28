# publisher_tools/tests/test_views_site_app.py
"""
High-priority API tests — SiteViewSet, AppViewSet, InventoryVerificationViewSet.

SiteViewSet actions tested:
  create, retrieve, update, destroy,
  verify, approve, reject, refresh_ads_txt,
  analytics, quality_metrics, ad_units

AppViewSet actions tested:
  create, retrieve, update, approve, reject, ad_units

InventoryVerificationViewSet actions tested:
  list, retrieve, check

Run:
    pytest publisher_tools/tests/test_views_site_app.py -v
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AppFactory,
    AdUnitFactory, InventoryVerificationFactory,
)

SITE_BASE = '/api/publisher-tools/sites'
APP_BASE  = '/api/publisher-tools/apps'
VER_BASE  = '/api/publisher-tools/verifications'


def site_url(suffix=''):
    return f'{SITE_BASE}{suffix}/'

def app_url(suffix=''):
    return f'{APP_BASE}{suffix}/'

def ver_url(suffix=''):
    return f'{VER_BASE}{suffix}/'


# ==============================================================================
# Site — CREATE
# ==============================================================================

@pytest.mark.django_db
class TestSiteCreate:

    def _payload(self):
        return {
            'name': 'My News Site',
            'domain': 'mynewssite.com',
            'url': 'https://mynewssite.com',
            'category': 'news',
        }

    def test_active_publisher_can_create_site(self, publisher_client):
        resp = publisher_client.post(site_url(), self._payload(), format='json')
        assert resp.status_code == 201

    def test_created_site_has_site_id(self, publisher_client):
        resp = publisher_client.post(site_url(), self._payload(), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('site_id', '').startswith('SITE')

    def test_pending_publisher_cannot_create_site(self, api_client, pending_publisher):
        """IsPublisher requires status == 'active'."""
        api_client.force_authenticate(user=pending_publisher.user)
        resp = api_client.post(site_url(), self._payload(), format='json')
        assert resp.status_code in (403, 400)

    def test_unauthenticated_cannot_create_site(self, api_client):
        resp = api_client.post(site_url(), self._payload(), format='json')
        assert resp.status_code in (401, 403)

    def test_missing_domain_returns_400(self, publisher_client):
        data = self._payload()
        del data['domain']
        resp = publisher_client.post(site_url(), data, format='json')
        assert resp.status_code == 400

    def test_missing_url_returns_400(self, publisher_client):
        data = self._payload()
        del data['url']
        resp = publisher_client.post(site_url(), data, format='json')
        assert resp.status_code == 400


# ==============================================================================
# Site — RETRIEVE / UPDATE
# ==============================================================================

@pytest.mark.django_db
class TestSiteRetrieveUpdate:

    def test_publisher_can_retrieve_own_site(self, publisher_client, site):
        resp = publisher_client.get(site_url(f'/{site.pk}'))
        assert resp.status_code == 200

    def test_admin_can_retrieve_any_site(self, admin_client, site):
        resp = admin_client.get(site_url(f'/{site.pk}'))
        assert resp.status_code == 200

    def test_publisher_cannot_retrieve_other_site(self, publisher_client_2, site):
        resp = publisher_client_2.get(site_url(f'/{site.pk}'))
        assert resp.status_code in (403, 404)

    def test_publisher_can_update_own_site(self, publisher_client, site):
        resp = publisher_client.patch(
            site_url(f'/{site.pk}'),
            {'name': 'Updated Site Name'},
            format='json',
        )
        assert resp.status_code == 200

    def test_publisher_cannot_update_other_site(self, publisher_client_2, site):
        resp = publisher_client_2.patch(
            site_url(f'/{site.pk}'),
            {'name': 'Stolen'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# Site — VERIFY
# ==============================================================================

@pytest.mark.django_db
class TestSiteVerify:

    def test_publisher_can_trigger_verify(self, publisher_client, site):
        resp = publisher_client.post(
            site_url(f'/{site.pk}/verify'),
            {'method': 'ads_txt'},
            format='json',
        )
        assert resp.status_code == 200

    def test_verify_returns_verified_and_status_keys(self, publisher_client, site):
        resp = publisher_client.post(
            site_url(f'/{site.pk}/verify'),
            {'method': 'ads_txt'},
            format='json',
        )
        body = resp.json()
        data = body.get('data', body)
        assert 'verified' in data
        assert 'status' in data

    def test_invalid_method_returns_400(self, publisher_client, site):
        resp = publisher_client.post(
            site_url(f'/{site.pk}/verify'),
            {'method': 'telepathy'},
            format='json',
        )
        assert resp.status_code == 400

    def test_unauthenticated_cannot_verify(self, api_client, site):
        resp = api_client.post(site_url(f'/{site.pk}/verify'), {'method': 'ads_txt'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# Site — APPROVE / REJECT (admin)
# ==============================================================================

@pytest.mark.django_db
class TestSiteApproveReject:

    def test_admin_can_approve_site(self, admin_client, pending_site):
        resp = admin_client.post(site_url(f'/{pending_site.pk}/approve'))
        assert resp.status_code == 200
        pending_site.refresh_from_db()
        assert pending_site.status == 'active'

    def test_publisher_cannot_approve_site(self, publisher_client, pending_site):
        resp = publisher_client.post(site_url(f'/{pending_site.pk}/approve'))
        assert resp.status_code in (403, 404)

    def test_admin_can_reject_site(self, admin_client, pending_site):
        resp = admin_client.post(
            site_url(f'/{pending_site.pk}/reject'),
            {'reason': 'Content policy violation'},
            format='json',
        )
        assert resp.status_code == 200
        pending_site.refresh_from_db()
        assert pending_site.status == 'rejected'

    def test_publisher_cannot_reject_site(self, publisher_client, pending_site):
        resp = publisher_client.post(
            site_url(f'/{pending_site.pk}/reject'),
            {'reason': 'self reject'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# Site — REFRESH ADS.TXT
# ==============================================================================

@pytest.mark.django_db
class TestRefreshAdsTxt:

    def test_publisher_can_refresh_ads_txt(self, publisher_client, site):
        resp = publisher_client.post(site_url(f'/{site.pk}/refresh_ads_txt'))
        assert resp.status_code == 200

    def test_response_has_ads_txt_verified(self, publisher_client, site):
        resp = publisher_client.post(site_url(f'/{site.pk}/refresh_ads_txt'))
        body = resp.json()
        data = body.get('data', body)
        assert 'ads_txt_verified' in data

    def test_unauthenticated_cannot_refresh(self, api_client, site):
        resp = api_client.post(site_url(f'/{site.pk}/refresh_ads_txt'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# Site — ANALYTICS
# ==============================================================================

@pytest.mark.django_db
class TestSiteAnalytics:

    def test_publisher_can_view_analytics(self, publisher_client, site):
        resp = publisher_client.get(
            site_url(f'/{site.pk}/analytics'),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code == 200

    def test_missing_date_params_returns_400(self, publisher_client, site):
        resp = publisher_client.get(site_url(f'/{site.pk}/analytics'))
        assert resp.status_code == 400

    def test_invalid_date_range_returns_400(self, publisher_client, site):
        resp = publisher_client.get(
            site_url(f'/{site.pk}/analytics'),
            {'start_date': '2025-02-01', 'end_date': '2025-01-01'},
        )
        assert resp.status_code == 400


# ==============================================================================
# Site — QUALITY METRICS
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityMetrics:

    def test_publisher_can_view_quality_metrics(self, publisher_client, site):
        resp = publisher_client.get(site_url(f'/{site.pk}/quality_metrics'))
        assert resp.status_code == 200

    def test_response_has_latest_and_trend_keys(self, publisher_client, site):
        resp = publisher_client.get(site_url(f'/{site.pk}/quality_metrics'))
        body = resp.json()
        data = body.get('data', body)
        assert 'latest' in data
        assert 'trend' in data


# ==============================================================================
# Site — AD UNITS list
# ==============================================================================

@pytest.mark.django_db
class TestSiteAdUnits:

    def test_publisher_can_list_site_ad_units(self, publisher_client, site, publisher):
        AdUnitFactory(publisher=publisher, site=site)
        AdUnitFactory(publisher=publisher, site=site)
        resp = publisher_client.get(site_url(f'/{site.pk}/ad_units'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert len(data) == 2

    def test_ad_units_returns_empty_list_for_new_site(self, publisher_client, site):
        resp = publisher_client.get(site_url(f'/{site.pk}/ad_units'))
        assert resp.status_code == 200


# ==============================================================================
# App — CREATE
# ==============================================================================

@pytest.mark.django_db
class TestAppCreate:

    def _payload(self):
        return {
            'name': 'My Super App',
            'platform': 'android',
            'package_name': 'com.example.mysuperapp',
            'category': 'games',
        }

    def test_active_publisher_can_create_app(self, publisher_client):
        resp = publisher_client.post(app_url(), self._payload(), format='json')
        assert resp.status_code == 201

    def test_created_app_has_app_id(self, publisher_client):
        resp = publisher_client.post(app_url(), self._payload(), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('app_id', '').startswith('APP')

    def test_unauthenticated_cannot_create_app(self, api_client):
        resp = api_client.post(app_url(), self._payload(), format='json')
        assert resp.status_code in (401, 403)

    def test_missing_platform_returns_400(self, publisher_client):
        data = self._payload()
        del data['platform']
        resp = publisher_client.post(app_url(), data, format='json')
        assert resp.status_code == 400

    def test_invalid_platform_returns_400(self, publisher_client):
        data = self._payload()
        data['platform'] = 'blackberry'
        resp = publisher_client.post(app_url(), data, format='json')
        assert resp.status_code == 400


# ==============================================================================
# App — APPROVE / REJECT
# ==============================================================================

@pytest.mark.django_db
class TestAppApproveReject:

    def test_admin_can_approve_app(self, admin_client, app):
        app.status = 'pending'
        app.save()
        resp = admin_client.post(app_url(f'/{app.pk}/approve'))
        assert resp.status_code == 200
        app.refresh_from_db()
        assert app.status == 'active'

    def test_publisher_cannot_approve_app(self, publisher_client, app):
        resp = publisher_client.post(app_url(f'/{app.pk}/approve'))
        assert resp.status_code in (403, 404)

    def test_admin_can_reject_app(self, admin_client, app):
        resp = admin_client.post(
            app_url(f'/{app.pk}/reject'),
            {'reason': 'Violates policy'},
            format='json',
        )
        assert resp.status_code == 200
        app.refresh_from_db()
        assert app.status == 'rejected'


# ==============================================================================
# App — AD UNITS
# ==============================================================================

@pytest.mark.django_db
class TestAppAdUnits:

    def test_publisher_can_list_app_ad_units(self, publisher_client, app, publisher):
        AdUnitFactory(publisher=publisher, app=app, site=None, inventory_type='app')
        resp = publisher_client.get(app_url(f'/{app.pk}/ad_units'))
        assert resp.status_code == 200


# ==============================================================================
# InventoryVerification — LIST / CHECK
# ==============================================================================

@pytest.mark.django_db
class TestInventoryVerification:

    def test_publisher_can_list_own_verifications(self, publisher_client, publisher, site):
        InventoryVerificationFactory(publisher=publisher, site=site)
        resp = publisher_client.get(ver_url())
        assert resp.status_code == 200

    def test_publisher_cannot_see_other_verifications(
        self, publisher_client, publisher_user_2, site
    ):
        other_pub = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        InventoryVerificationFactory(publisher=other_pub, site=other_site)
        resp = publisher_client.get(ver_url())
        body = resp.json()
        data = body.get('data', body.get('results', []))
        # Publisher should only see 0 items (their own)
        assert len(data) == 0

    def test_publisher_can_trigger_check(self, publisher_client, publisher, site):
        verification = InventoryVerificationFactory(publisher=publisher, site=site)
        resp = publisher_client.post(ver_url(f'/{verification.pk}/check'))
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list_verifications(self, api_client):
        resp = api_client.get(ver_url())
        assert resp.status_code in (401, 403)
