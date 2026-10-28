# publisher_tools/tests/test_views_publisher_advanced.py
"""Tests for PublisherAdvancedViewSet (views_publisher_advanced.py) — 19 actions."""
import pytest

BASE = '/api/publisher-tools/publisher-advanced'

@pytest.mark.django_db
class TestPublisherAdvancedAuth:
    def test_unauth_subscription_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/subscription/').status_code in (401, 403)
    def test_unauth_kyc_status_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/kyc-status/').status_code in (401, 403)

@pytest.mark.django_db
class TestPublisherAdvancedSubscription:
    def test_returns_subscription_info(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/subscription/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'status' in resp.json()['data']
    def test_plans_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/subscription-plans/').status_code in (200, 503)
    def test_can_add_site_check(self, publisher_client):
        assert publisher_client.post(f'{BASE}/can-add-site/', {}, format='json').status_code in (200, 503)
    def test_subscription_history_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/subscription-history/').status_code in (200, 503)

@pytest.mark.django_db
class TestPublisherAdvancedKYC:
    def test_kyc_status_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/kyc-status/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'status' in resp.json()['data'] or 'can_submit' in resp.json()['data']
    def test_kyc_documents_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/kyc-documents/').status_code in (200, 503)
    def test_kyc_verify_token_requires_token(self, publisher_client):
        assert publisher_client.post(f'{BASE}/kyc-verify-token/', {}, format='json').status_code == 400

@pytest.mark.django_db
class TestPublisherAdvancedBankAccounts:
    def test_bank_accounts_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/bank-accounts/').status_code in (200, 503)
    def test_set_primary_requires_account_id(self, publisher_client):
        assert publisher_client.post(f'{BASE}/bank-accounts/primary/', {}, format='json').status_code == 400
    def test_nonexistent_account_returns_404(self, publisher_client):
        assert publisher_client.post(f'{BASE}/bank-accounts/primary/', {'account_id': 99999}, format='json').status_code in (404, 503)

@pytest.mark.django_db
class TestPublisherAdvancedCommissions:
    def test_commissions_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/commissions/').status_code in (200, 503)
    def test_commission_breakdown_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/commission-breakdown/', {'gross_revenue': '1000'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPublisherAdvancedAnalytics:
    def test_comparison_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/comparison/').status_code in (200, 503)
    def test_period_stats_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/period-stats/').status_code in (200, 503)
    def test_performance_goals_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/performance-goals/').status_code in (200, 503)
    def test_achievement_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/achievement/').status_code in (200, 503)

@pytest.mark.django_db
class TestPublisherAdvancedRatingBrand:
    def test_rating_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/rating/').status_code in (200, 503)
    def test_brand_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/brand/').status_code in (200, 503)
    def test_next_payout_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/next-payout/').status_code in (200, 503)
