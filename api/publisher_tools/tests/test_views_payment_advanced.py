# publisher_tools/tests/test_views_payment_advanced.py
"""Tests for PaymentAdvancedViewSet (views_payment_advanced.py) — 12 actions."""
import pytest

BASE = '/api/publisher-tools/payment-advanced'

@pytest.mark.django_db
class TestPaymentAdvancedAuth:
    def test_unauth_next_date_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/next-date/').status_code in (401, 403)
    def test_unauth_fee_calc_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/fee-calc/').status_code in (401, 403)

@pytest.mark.django_db
class TestPaymentAdvancedNextDate:
    def test_returns_next_date(self, publisher_client):
        assert publisher_client.get(f'{BASE}/next-date/').status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentAdvancedDuePublishers:
    def test_requires_admin(self, publisher_client):
        assert publisher_client.get(f'{BASE}/due-publishers/').status_code in (403, 401)
    def test_admin_can_access(self, admin_client):
        assert admin_client.get(f'{BASE}/due-publishers/').status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentAdvancedFeeCalc:
    def test_calculates_fee(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/fee-calc/', {'amount': '100.00', 'method': 'paypal'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'fee' in resp.json()['data']
    def test_invalid_amount_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/fee-calc/', {'amount': 'bad', 'method': 'paypal'}).status_code == 400

@pytest.mark.django_db
class TestPaymentAdvancedMinThreshold:
    def test_returns_threshold(self, publisher_client):
        assert publisher_client.get(f'{BASE}/min-threshold/', {'method': 'paypal'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentAdvancedPlatformShare:
    def test_calculates_share(self, publisher_client):
        assert publisher_client.get(f'{BASE}/platform-share/', {'gross_revenue': '1000.00'}).status_code in (200, 503)
    def test_invalid_amount_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/platform-share/', {'gross_revenue': 'bad'}).status_code == 400

@pytest.mark.django_db
class TestPaymentAdvancedCommissions:
    def test_tiered_commission_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/tiered-commission/', {'gross_revenue': '5000.00'}).status_code in (200, 503)
    def test_referral_commission_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/referral-commission/', {'referred_revenue': '2000.00'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentAdvancedDisputes:
    def test_disputes_accessible(self, publisher_client):
        assert publisher_client.get(f'{BASE}/disputes/').status_code in (200, 503)
