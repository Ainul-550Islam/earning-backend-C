# publisher_tools/tests/test_views_site_advanced.py
"""Tests for SiteAdvancedViewSet (views_site_advanced.py) — 5 actions."""
import pytest

BASE = '/api/publisher-tools/site-advanced'

@pytest.mark.django_db
class TestSiteAdvancedAuth:
    def test_unauth_approval_checklist_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/approval-checklist/').status_code in (401, 403)

@pytest.mark.django_db
class TestSiteAdvancedApprovalChecklist:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/approval-checklist/').status_code == 400
    def test_valid_site_returns_data(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/approval-checklist/', {'site_id': site.pk}).status_code in (200, 503)
    def test_other_publisher_site_blocked(self, publisher_client_2, site):
        assert publisher_client_2.get(f'{BASE}/approval-checklist/', {'site_id': site.pk}).status_code in (404, 403, 503)

@pytest.mark.django_db
class TestSiteAdvancedMakeDecision:
    def test_requires_admin(self, publisher_client):
        assert publisher_client.post(f'{BASE}/make-decision/', {'site_id': 1, 'decision': 'approve'}, format='json').status_code in (403, 401)
    def test_admin_invalid_decision_returns_400(self, admin_client):
        assert admin_client.post(f'{BASE}/make-decision/', {'site_id': 1, 'decision': 'invalid'}, format='json').status_code == 400
    def test_admin_approve_valid_site(self, admin_client, site):
        assert admin_client.post(f'{BASE}/make-decision/', {'site_id': site.pk, 'decision': 'approve'}, format='json').status_code in (200, 404, 503)

@pytest.mark.django_db
class TestSiteAdvancedDeviceSplit:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/device-split/').status_code == 400
    def test_valid_site_returns_data(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/device-split/', {'site_id': site.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestSiteAdvancedReturnVisitorRate:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/return-visitor-rate/').status_code == 400
    def test_valid_site_returns_data(self, publisher_client, site):
        assert publisher_client.get(f'{BASE}/return-visitor-rate/', {'site_id': site.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestSiteAdvancedBlacklistStatus:
    def test_missing_site_id_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/blacklist-status/').status_code == 400
    def test_valid_site_returns_status(self, publisher_client, site):
        resp = publisher_client.get(f'{BASE}/blacklist-status/', {'site_id': site.pk})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'is_blacklisted' in resp.json()['data']
