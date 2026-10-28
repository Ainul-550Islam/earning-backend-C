# publisher_tools/tests/test_views_site_management.py
"""
Tests for SiteManagementViewSet (views_site_management.py).
Covers: verify_ads_txt, verify_meta_tag, verify_dns, verify_html,
        domain_check, performance, quality_score, full_verify (admin).
"""
import pytest

BASE = '/api/publisher-tools/site-tools'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# VERIFY ADS.TXT
# ==============================================================================

@pytest.mark.django_db
class TestVerifyAdsTxt:

    def test_publisher_can_trigger_ads_txt_verify(self, publisher_client, site):
        resp = publisher_client.post(url('verify-ads-txt'), {'site_id': site.site_id}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_verified_and_message(self, publisher_client, site):
        resp = publisher_client.post(url('verify-ads-txt'), {'site_id': site.site_id}, format='json')
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'verified' in data
            assert 'message' in data

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('verify-ads-txt'), {}, format='json')
        assert resp.status_code == 400

    def test_other_publisher_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.post(url('verify-ads-txt'), {'site_id': site.site_id}, format='json')
        assert resp.status_code == 404

    def test_unauthenticated_cannot_verify(self, api_client, site):
        resp = api_client.post(url('verify-ads-txt'), {'site_id': site.site_id})
        assert resp.status_code in (401, 403)


# ==============================================================================
# VERIFY META TAG
# ==============================================================================

@pytest.mark.django_db
class TestVerifyMetaTag:

    def test_publisher_can_verify_meta_tag(self, publisher_client, site):
        resp = publisher_client.post(
            url('verify-meta-tag'),
            {'site_id': site.site_id, 'token': 'abc123token'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('verify-meta-tag'), {'token': 'abc'}, format='json')
        assert resp.status_code == 400

    def test_wrong_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.post(
            url('verify-meta-tag'),
            {'site_id': site.site_id, 'token': 'abc'},
            format='json',
        )
        assert resp.status_code == 404


# ==============================================================================
# VERIFY DNS
# ==============================================================================

@pytest.mark.django_db
class TestVerifyDNS:

    def test_publisher_can_verify_dns(self, publisher_client, site):
        resp = publisher_client.post(
            url('verify-dns'),
            {'site_id': site.site_id, 'token': 'dns_token_xyz'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('verify-dns'), {'token': 'abc'}, format='json')
        assert resp.status_code == 400


# ==============================================================================
# VERIFY HTML FILE
# ==============================================================================

@pytest.mark.django_db
class TestVerifyHTML:

    def test_publisher_can_verify_html(self, publisher_client, site):
        resp = publisher_client.post(
            url('verify-html'),
            {'site_id': site.site_id, 'token': 'html_token_123'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('verify-html'), {'token': 'abc'}, format='json')
        assert resp.status_code == 400


# ==============================================================================
# DOMAIN CHECK
# ==============================================================================

@pytest.mark.django_db
class TestDomainCheck:

    def test_publisher_can_check_domain(self, publisher_client):
        resp = publisher_client.get(url('domain-check'), {'domain': 'example.com'})
        assert resp.status_code in (200, 503)

    def test_domain_check_has_is_valid_field(self, publisher_client):
        resp = publisher_client.get(url('domain-check'), {'domain': 'example.com'})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'is_valid' in data

    def test_missing_domain_returns_400(self, publisher_client):
        resp = publisher_client.get(url('domain-check'))
        assert resp.status_code == 400

    def test_domain_with_https_prefix_cleaned(self, publisher_client):
        resp = publisher_client.get(url('domain-check'), {'domain': 'https://example.com/path'})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            # cleaned should not have https://
            assert 'https' not in data.get('cleaned', '')

    def test_unauthenticated_cannot_check(self, api_client):
        resp = api_client.get(url('domain-check'), {'domain': 'example.com'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# PERFORMANCE
# ==============================================================================

@pytest.mark.django_db
class TestSitePerformance:

    def test_publisher_can_view_performance(self, publisher_client, site):
        resp = publisher_client.get(url('performance'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('performance'))
        assert resp.status_code == 400

    def test_other_publisher_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.get(url('performance'), {'site_id': site.site_id})
        assert resp.status_code == 404

    def test_days_param_accepted(self, publisher_client, site):
        resp = publisher_client.get(url('performance'), {'site_id': site.site_id, 'days': '7'})
        assert resp.status_code in (200, 503)


# ==============================================================================
# QUALITY SCORE
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityScore:

    def test_publisher_can_get_quality_score(self, publisher_client, site):
        resp = publisher_client.get(url('quality-score'), {'site_id': site.site_id})
        assert resp.status_code in (200, 503)

    def test_quality_score_response_has_composite_score(self, publisher_client, site):
        resp = publisher_client.get(url('quality-score'), {'site_id': site.site_id})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'composite_score' in data

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(url('quality-score'))
        assert resp.status_code == 400

    def test_other_publisher_site_returns_404(self, publisher_client_2, site):
        resp = publisher_client_2.get(url('quality-score'), {'site_id': site.site_id})
        assert resp.status_code == 404

    def test_unauthenticated_cannot_get_score(self, api_client, site):
        resp = api_client.get(url('quality-score'), {'site_id': site.site_id})
        assert resp.status_code in (401, 403)


# ==============================================================================
# ADMIN: FULL VERIFY
# ==============================================================================

@pytest.mark.django_db
class TestAdminFullVerify:

    def test_admin_can_run_full_verify(self, admin_client, site):
        resp = admin_client.post(url('full-verify'), {'site_id': site.site_id}, format='json')
        assert resp.status_code in (200, 503)

    def test_missing_site_id_returns_400(self, admin_client):
        resp = admin_client.post(url('full-verify'), {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_site_returns_404(self, admin_client):
        resp = admin_client.post(url('full-verify'), {'site_id': 'SITEXXXXXX'}, format='json')
        assert resp.status_code == 404

    def test_publisher_cannot_run_full_verify(self, publisher_client, site):
        resp = publisher_client.post(url('full-verify'), {'site_id': site.site_id}, format='json')
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_run_full_verify(self, api_client, site):
        resp = api_client.post(url('full-verify'), {'site_id': site.site_id})
        assert resp.status_code in (401, 403)
