# publisher_tools/tests/test_views_payout.py
"""
Tests for PayoutViewSet (views_payout.py)।

Covers all 9 @action endpoints:
  eligibility, request_payout, payout_history, payment_history,
  payment_summary, lifetime_stats, withholding_tax,
  tax_rate, tax_exempt_countries

Pattern: pytest + APIClient + conftest.py fixtures
Auth:    publisher_client → force_authenticate(user=publisher_user)
"""

import pytest

BASE = '/api/publisher-tools/payout'


# ══════════════════════════════════════════════════════════════════════════════
# ELIGIBILITY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPayoutEligibility:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/eligibility/').status_code in (401, 403)

    def test_returns_eligibility_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/eligibility/').status_code in (200, 503)

    def test_response_has_eligible_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/eligibility/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'eligible' in data

    def test_eligible_is_boolean_when_200(self, publisher_client):
        r = publisher_client.get(f'{BASE}/eligibility/')
        if r.status_code == 200:
            assert isinstance(r.json()['data']['eligible'], bool)

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/eligibility/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST PAYOUT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRequestPayout:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/request/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/', {'bank_account_id': 'acc-001'}, format='json'
        )
        assert r.status_code == 400

    def test_missing_bank_account_id_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/', {'amount': '50.00'}, format='json'
        )
        assert r.status_code == 400

    def test_negative_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/',
            {'amount': '-10.00', 'bank_account_id': 'acc-001'},
            format='json',
        )
        assert r.status_code == 400

    def test_zero_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/',
            {'amount': '0.00', 'bank_account_id': 'acc-001'},
            format='json',
        )
        assert r.status_code == 400

    def test_non_numeric_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/',
            {'amount': 'abc', 'bank_account_id': 'acc-001'},
            format='json',
        )
        assert r.status_code == 400

    def test_valid_payload_handled(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/request/',
            {'amount': '100.00', 'bank_account_id': 'acc-test-001'},
            format='json',
        )
        # 200 success, 400 if balance insufficient, 503 service error — all valid
        assert r.status_code in (200, 400, 503)

    def test_response_has_reason_on_400(self, publisher_client):
        r = publisher_client.post(f'{BASE}/request/', {}, format='json')
        if r.status_code == 400:
            body = r.json()
            assert 'error' in body or 'detail' in body or 'amount' in body


# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPayoutHistory:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/history/').status_code in (401, 403)

    def test_returns_history(self, publisher_client):
        assert publisher_client.get(f'{BASE}/history/').status_code in (200, 503)

    def test_response_has_records_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/history/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'records' in data

    def test_response_has_count_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/history/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'count' in data

    def test_custom_limit_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/history/', {'limit': 5})
        assert r.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaymentHistory:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/payment-history/').status_code in (401, 403)

    def test_returns_payment_history(self, publisher_client):
        assert publisher_client.get(f'{BASE}/payment-history/').status_code in (200, 503)

    def test_response_has_records_and_count(self, publisher_client):
        r = publisher_client.get(f'{BASE}/payment-history/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'records' in data
            assert 'count' in data

    def test_with_custom_limit(self, publisher_client):
        r = publisher_client.get(f'{BASE}/payment-history/', {'limit': 10})
        assert r.status_code in (200, 503)

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/payment-history/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaymentSummary:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/payment-summary/').status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        assert publisher_client.get(f'{BASE}/payment-summary/').status_code in (200, 503)

    def test_custom_year_param(self, publisher_client):
        r = publisher_client.get(f'{BASE}/payment-summary/', {'year': 2024})
        assert r.status_code in (200, 503)

    def test_invalid_year_returns_400(self, publisher_client):
        r = publisher_client.get(f'{BASE}/payment-summary/', {'year': 'abc'})
        assert r.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# LIFETIME STATS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLifetimeStats:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/lifetime-stats/').status_code in (401, 403)

    def test_returns_lifetime_stats(self, publisher_client):
        assert publisher_client.get(f'{BASE}/lifetime-stats/').status_code in (200, 503)

    def test_response_has_total_paid_or_summary(self, publisher_client):
        r = publisher_client.get(f'{BASE}/lifetime-stats/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'total_paid' in data or 'payout_count' in data or 'currency' in data

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/lifetime-stats/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# WITHHOLDING TAX
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWithholdingTax:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/withholding-tax/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/', {'country': 'US'}, format='json'
        )
        assert r.status_code == 400

    def test_missing_country_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/', {'amount': '100.00'}, format='json'
        )
        assert r.status_code == 400

    def test_invalid_country_code_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'INVALID'},
            format='json',
        )
        assert r.status_code == 400

    def test_zero_amount_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '0.00', 'country': 'US'},
            format='json',
        )
        assert r.status_code == 400

    def test_valid_us_no_w8(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'US', 'has_w8': False},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_valid_us_with_w8(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'US', 'has_w8': True},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_valid_bd_country(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '200.00', 'country': 'BD'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_response_has_tax_keys_when_200(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'US'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'gross_amount' in data
            assert 'tax_amount' in data
            assert 'net_amount' in data
            assert 'tax_rate_pct' in data

    def test_net_amount_not_negative_when_200(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'BD'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert float(data.get('net_amount', 0)) >= 0


# ══════════════════════════════════════════════════════════════════════════════
# TAX RATE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTaxRate:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/tax-rate/').status_code in (401, 403)

    def test_missing_country_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/tax-rate/').status_code == 400

    def test_valid_us_returns_rate(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-rate/', {'country': 'US'})
        assert r.status_code in (200, 503)

    def test_valid_bd_returns_rate(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-rate/', {'country': 'BD'})
        assert r.status_code in (200, 503)

    def test_response_has_rate_pct_and_is_exempt(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-rate/', {'country': 'US'})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'rate_pct' in data
            assert 'is_exempt' in data

    def test_rate_pct_is_float_when_200(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-rate/', {'country': 'BD'})
        if r.status_code == 200:
            assert isinstance(r.json()['data']['rate_pct'], float)


# ══════════════════════════════════════════════════════════════════════════════
# TAX EXEMPT COUNTRIES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTaxExemptCountries:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/tax-exempt/').status_code in (401, 403)

    def test_returns_exempt_countries(self, publisher_client):
        assert publisher_client.get(f'{BASE}/tax-exempt/').status_code in (200, 503)

    def test_response_has_exempt_countries_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-exempt/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'exempt_countries' in data

    def test_response_has_all_rates_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-exempt/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'all_rates' in data

    def test_exempt_countries_is_list(self, publisher_client):
        r = publisher_client.get(f'{BASE}/tax-exempt/')
        if r.status_code == 200:
            exempt = r.json()['data']['exempt_countries']
            assert isinstance(exempt, list)
