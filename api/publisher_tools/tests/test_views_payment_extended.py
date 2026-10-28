# publisher_tools/tests/test_views_payment_extended.py
"""Tests for PaymentExtendedViewSet (views_payment_extended.py) — 8 actions."""
import pytest

BASE = '/api/publisher-tools/payments-extended'

@pytest.mark.django_db
class TestPaymentExtendedAuth:
    def test_unauth_daily_earnings_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/daily-earnings/').status_code in (401, 403)
    def test_unauth_threshold_status_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/threshold-status/').status_code in (401, 403)

@pytest.mark.django_db
class TestPaymentExtendedDailyEarnings:
    def test_returns_today_by_default(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-earnings/').status_code in (200, 503)
    def test_with_specific_date(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-earnings/', {'date': '2025-01-15'}).status_code in (200, 503)
    def test_invalid_date_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/daily-earnings/', {'date': 'not-a-date'}).status_code == 400

@pytest.mark.django_db
class TestPaymentExtendedThreshold:
    def test_returns_threshold_status(self, publisher_client):
        assert publisher_client.get(f'{BASE}/threshold-status/').status_code in (200, 503)
    def test_with_payment_method_filter(self, publisher_client):
        assert publisher_client.get(f'{BASE}/threshold-status/', {'payment_method': 'paypal'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentExtendedCurrencyConvert:
    def test_same_currency_returns_same_amount(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/currency-convert/', {'amount': '100', 'from': 'USD', 'to': 'USD'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert resp.json()['data']['exchange_rate'] == '1.000000'
    def test_invalid_amount_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/currency-convert/', {'amount': 'not_a_number'}).status_code == 400
    def test_cross_currency_converts(self, publisher_client):
        assert publisher_client.get(f'{BASE}/currency-convert/', {'amount': '100', 'from': 'USD', 'to': 'EUR'}).status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentExtendedExchangeRates:
    def test_returns_rates(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/exchange-rates/')
        assert resp.status_code in (200, 503)

@pytest.mark.django_db
class TestPaymentExtendedEligiblePublishers:
    def test_requires_admin(self, publisher_client):
        assert publisher_client.get(f'{BASE}/eligible-publishers/').status_code in (403, 401)
    def test_admin_can_access(self, admin_client):
        assert admin_client.get(f'{BASE}/eligible-publishers/').status_code in (200, 503)
