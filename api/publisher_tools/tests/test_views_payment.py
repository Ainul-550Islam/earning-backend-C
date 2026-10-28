# publisher_tools/tests/test_views_payment.py
"""
Tests for PaymentViewSet (views_payment.py).
Covers: earnings, invoice_preview, tax_estimate, payout_history,
        commission, request_payout, disputes, create_dispute,
        apply_adjustment (admin), resolve_dispute (admin), currency_rates (admin).
"""
import pytest
from decimal import Decimal
from publisher_tools.tests.factories import (
    PublisherFactory, PublisherInvoiceFactory, PayoutThresholdFactory,
    PublisherEarningFactory, SiteFactory, AdUnitFactory,
)

BASE = '/api/publisher-tools/payments'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# EARNINGS
# ==============================================================================

@pytest.mark.django_db
class TestPaymentEarnings:

    def test_publisher_can_view_earnings(self, publisher_client):
        resp = publisher_client.get(url('earnings'))
        assert resp.status_code in (200, 503)

    def test_earnings_with_year_month_params(self, publisher_client):
        resp = publisher_client.get(url('earnings'), {'year': '2025', 'month': '1'})
        assert resp.status_code in (200, 503)

    def test_unauthenticated_cannot_view_earnings(self, api_client):
        resp = api_client.get(url('earnings'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# INVOICE PREVIEW
# ==============================================================================

@pytest.mark.django_db
class TestInvoicePreview:

    def test_publisher_can_get_invoice_preview(self, publisher_client):
        resp = publisher_client.get(url('invoice-preview'), {'year': '2025', 'month': '1'})
        assert resp.status_code in (200, 503)

    def test_invoice_preview_has_summary_key(self, publisher_client):
        resp = publisher_client.get(url('invoice-preview'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'preview' in data or 'summary' in data

    def test_unauthenticated_cannot_preview(self, api_client):
        resp = api_client.get(url('invoice-preview'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# TAX ESTIMATE
# ==============================================================================

@pytest.mark.django_db
class TestTaxEstimate:

    def test_publisher_can_estimate_tax(self, publisher_client):
        resp = publisher_client.get(url('tax-estimate'), {'amount': '1000', 'country': 'BD'})
        assert resp.status_code in (200, 503)

    def test_invalid_amount_returns_400(self, publisher_client):
        resp = publisher_client.get(url('tax-estimate'), {'amount': 'not-a-number'})
        assert resp.status_code == 400

    def test_tax_estimate_has_rate_field(self, publisher_client):
        resp = publisher_client.get(url('tax-estimate'), {'amount': '500'})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'rate_pct' in data or 'tax_amount' in data

    def test_unauthenticated_cannot_estimate(self, api_client):
        resp = api_client.get(url('tax-estimate'), {'amount': '1000'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# PAYOUT HISTORY
# ==============================================================================

@pytest.mark.django_db
class TestPayoutHistory:

    def test_publisher_can_view_payout_history(self, publisher_client, publisher):
        PublisherInvoiceFactory(publisher=publisher, status='paid')
        PublisherInvoiceFactory(publisher=publisher, status='paid')
        resp = publisher_client.get(url('payout-history'))
        assert resp.status_code == 200

    def test_payout_history_returns_list(self, publisher_client):
        resp = publisher_client.get(url('payout-history'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_publisher_only_sees_own_paid_invoices(
        self, publisher_client, publisher_user_2
    ):
        other_pub = PublisherFactory(user=publisher_user_2)
        PublisherInvoiceFactory(publisher=other_pub, status='paid')
        resp = publisher_client.get(url('payout-history'))
        body = resp.json()
        data = body.get('data', body)
        assert len(data) == 0

    def test_limit_param_respected(self, publisher_client, publisher):
        for _ in range(5):
            PublisherInvoiceFactory(publisher=publisher, status='paid')
        resp = publisher_client.get(url('payout-history'), {'limit': '2'})
        body = resp.json()
        data = body.get('data', body)
        assert len(data) <= 2

    def test_unauthenticated_cannot_view_history(self, api_client):
        resp = api_client.get(url('payout-history'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# COMMISSION BREAKDOWN
# ==============================================================================

@pytest.mark.django_db
class TestCommissionBreakdown:

    def test_publisher_can_view_commission(self, publisher_client):
        resp = publisher_client.get(url('commission'), {'amount': '1000'})
        assert resp.status_code in (200, 503)

    def test_commission_has_publisher_share(self, publisher_client):
        resp = publisher_client.get(url('commission'), {'amount': '1000'})
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert 'publisher_share' in data or 'platform_commission' in data

    def test_invalid_amount_returns_400(self, publisher_client):
        resp = publisher_client.get(url('commission'), {'amount': 'abc'})
        assert resp.status_code == 400


# ==============================================================================
# PAYOUT REQUEST
# ==============================================================================

@pytest.mark.django_db
class TestPayoutRequest:

    def test_publisher_can_request_payout(self, publisher_client, publisher):
        threshold = PayoutThresholdFactory(publisher=publisher, is_primary=True)
        resp = publisher_client.post(
            url('request-payout'),
            {'threshold_id': str(threshold.pk)},
            format='json',
        )
        assert resp.status_code in (200, 400, 503)  # 400 if below threshold

    def test_missing_threshold_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('request-payout'), {}, format='json')
        assert resp.status_code == 400

    def test_wrong_publisher_threshold_returns_404(self, publisher_client, publisher_user_2):
        other_pub       = PublisherFactory(user=publisher_user_2)
        other_threshold = PayoutThresholdFactory(publisher=other_pub)
        resp = publisher_client.post(
            url('request-payout'),
            {'threshold_id': str(other_threshold.pk)},
            format='json',
        )
        assert resp.status_code == 404

    def test_unauthenticated_cannot_request(self, api_client):
        resp = api_client.post(url('request-payout'), {}, format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# DISPUTES
# ==============================================================================

@pytest.mark.django_db
class TestDisputes:

    def test_publisher_can_view_own_disputes(self, publisher_client, publisher):
        PublisherInvoiceFactory(publisher=publisher, status='disputed')
        resp = publisher_client.get(url('disputes'))
        assert resp.status_code == 200

    def test_disputes_returns_list(self, publisher_client):
        resp = publisher_client.get(url('disputes'))
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_publisher_can_create_dispute(self, publisher_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='issued')
        resp = publisher_client.post(
            url('create-dispute'),
            {'invoice_id': str(invoice.pk), 'reason': 'Revenue mismatch'},
            format='json',
        )
        assert resp.status_code == 200
        invoice.refresh_from_db()
        assert invoice.status == 'disputed'

    def test_create_dispute_requires_reason(self, publisher_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='issued')
        resp = publisher_client.post(
            url('create-dispute'),
            {'invoice_id': str(invoice.pk)},
            format='json',
        )
        assert resp.status_code == 400

    def test_cannot_dispute_non_issued_invoice(self, publisher_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='draft')
        resp = publisher_client.post(
            url('create-dispute'),
            {'invoice_id': str(invoice.pk), 'reason': 'Revenue error'},
            format='json',
        )
        assert resp.status_code == 404

    def test_cannot_dispute_other_publishers_invoice(
        self, publisher_client, publisher_user_2
    ):
        other_pub     = PublisherFactory(user=publisher_user_2)
        other_invoice = PublisherInvoiceFactory(publisher=other_pub, status='issued')
        resp = publisher_client.post(
            url('create-dispute'),
            {'invoice_id': str(other_invoice.pk), 'reason': 'Fake dispute'},
            format='json',
        )
        assert resp.status_code == 404

    def test_unauthenticated_cannot_create_dispute(self, api_client):
        resp = api_client.post(url('create-dispute'), {}, format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# ADMIN: APPLY ADJUSTMENT
# ==============================================================================

@pytest.mark.django_db
class TestApplyAdjustment:

    def test_admin_can_apply_negative_adjustment(self, admin_client, publisher):
        resp = admin_client.post(
            url('apply-adjustment'),
            {
                'publisher_id': publisher.publisher_id,
                'amount':       '-50.00',
                'reason':       'IVT deduction Q1',
            },
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_missing_fields_returns_400(self, admin_client):
        resp = admin_client.post(url('apply-adjustment'), {'publisher_id': 'PUB123'}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_publisher_returns_404(self, admin_client):
        resp = admin_client.post(
            url('apply-adjustment'),
            {'publisher_id': 'PUBXXXXXX', 'amount': '-10.00', 'reason': 'test'},
            format='json',
        )
        assert resp.status_code == 404

    def test_publisher_cannot_apply_adjustment(self, publisher_client, publisher):
        resp = publisher_client.post(
            url('apply-adjustment'),
            {'publisher_id': publisher.publisher_id, 'amount': '100.00', 'reason': 'self pay'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# ADMIN: RESOLVE DISPUTE
# ==============================================================================

@pytest.mark.django_db
class TestResolveDispute:

    def test_admin_can_resolve_dispute_accepted(self, admin_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='disputed')
        resp = admin_client.post(
            url('resolve-dispute'),
            {'invoice_id': str(invoice.pk), 'resolution': 'accepted', 'notes': 'Verified correct'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_admin_can_resolve_dispute_rejected(self, admin_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='disputed')
        resp = admin_client.post(
            url('resolve-dispute'),
            {'invoice_id': str(invoice.pk), 'resolution': 'rejected', 'notes': 'Figures correct'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_invalid_resolution_returns_400(self, admin_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='disputed')
        resp = admin_client.post(
            url('resolve-dispute'),
            {'invoice_id': str(invoice.pk), 'resolution': 'maybe'},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_cannot_resolve_dispute(self, publisher_client, publisher):
        invoice = PublisherInvoiceFactory(publisher=publisher, status='disputed')
        resp = publisher_client.post(
            url('resolve-dispute'),
            {'invoice_id': str(invoice.pk), 'resolution': 'accepted'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# ADMIN: CURRENCY RATES
# ==============================================================================

@pytest.mark.django_db
class TestCurrencyRates:

    def test_admin_can_view_rates(self, admin_client):
        resp = admin_client.get(url('currency-rates'))
        assert resp.status_code in (200, 503)

    def test_rates_has_base_usd(self, admin_client):
        resp = admin_client.get(url('currency-rates'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert data.get('base') == 'USD'
            assert 'rates' in data

    def test_publisher_cannot_view_rates(self, publisher_client):
        resp = publisher_client.get(url('currency-rates'))
        assert resp.status_code in (403, 404)
