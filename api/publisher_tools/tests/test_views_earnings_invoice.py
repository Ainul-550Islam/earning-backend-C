# publisher_tools/tests/test_views_earnings_invoice.py
"""
High-priority API tests — PublisherEarningViewSet, PayoutThresholdViewSet,
PublisherInvoiceViewSet.

PublisherEarningViewSet:
  list (with date-range, country, site, ad_unit filters),
  summary, by_country, by_ad_unit

PayoutThresholdViewSet:
  create, retrieve, update, destroy,
  set_primary, verify (admin only)

PublisherInvoiceViewSet:
  list, retrieve,
  generate (admin), issue (admin), mark_paid (admin),
  dispute (publisher)

Run:
    pytest publisher_tools/tests/test_views_earnings_invoice.py -v
"""
import pytest
from decimal import Decimal
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AdUnitFactory,
    PublisherEarningFactory, PayoutThresholdFactory,
    PublisherInvoiceFactory,
)

EARNING_BASE   = '/api/publisher-tools/earnings'
THRESHOLD_BASE = '/api/publisher-tools/payout-thresholds'
INVOICE_BASE   = '/api/publisher-tools/invoices'


def earn_url(suffix=''):
    return f'{EARNING_BASE}{suffix}/'

def thr_url(suffix=''):
    return f'{THRESHOLD_BASE}{suffix}/'

def inv_url(suffix=''):
    return f'{INVOICE_BASE}{suffix}/'


# ==============================================================================
# Earning — LIST (read-only)
# ==============================================================================

@pytest.mark.django_db
class TestEarningList:

    def test_publisher_can_list_own_earnings(
        self, publisher_client, publisher, ad_unit, site
    ):
        PublisherEarningFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        PublisherEarningFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        resp = publisher_client.get(earn_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 2

    def test_publisher_cannot_see_other_publisher_earnings(
        self, publisher_client, publisher_user_2, site
    ):
        other_pub = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        other_unit = AdUnitFactory(publisher=other_pub, site=other_site)
        PublisherEarningFactory(publisher=other_pub, site=other_site, ad_unit=other_unit)
        resp = publisher_client.get(earn_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_unauthenticated_cannot_list_earnings(self, api_client):
        resp = api_client.get(earn_url())
        assert resp.status_code in (401, 403)

    def test_post_is_not_allowed(self, publisher_client):
        """EarningViewSet is read-only (http_method_names = ['get', ...])."""
        resp = publisher_client.post(earn_url(), {}, format='json')
        assert resp.status_code == 405

    def test_date_range_filter(self, publisher_client, publisher, ad_unit, site):
        from datetime import date
        PublisherEarningFactory(
            publisher=publisher, site=site, ad_unit=ad_unit,
            date=date(2025, 1, 15)
        )
        PublisherEarningFactory(
            publisher=publisher, site=site, ad_unit=ad_unit,
            date=date(2025, 3, 1)
        )
        resp = publisher_client.get(
            earn_url(),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 1

    def test_granularity_filter(self, publisher_client, publisher, ad_unit, site):
        PublisherEarningFactory(
            publisher=publisher, site=site, ad_unit=ad_unit, granularity='daily'
        )
        PublisherEarningFactory(
            publisher=publisher, site=site, ad_unit=ad_unit, granularity='hourly'
        )
        resp = publisher_client.get(earn_url(), {'granularity': 'daily'})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['granularity'] == 'daily'


# ==============================================================================
# Earning — SUMMARY / BY_COUNTRY / BY_AD_UNIT
# ==============================================================================

@pytest.mark.django_db
class TestEarningSummary:

    def test_publisher_can_get_summary(self, publisher_client, publisher, ad_unit, site):
        PublisherEarningFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        resp = publisher_client.get(earn_url('summary'), {'period': 'last_30_days'})
        assert resp.status_code == 200

    def test_summary_returns_dict(self, publisher_client, publisher, ad_unit, site):
        resp = publisher_client.get(earn_url('summary'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, dict)

    def test_user_without_publisher_profile_gets_error(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        resp = api_client.get(earn_url('summary'))
        assert resp.status_code in (400, 404)

    def test_by_country_returns_list(self, publisher_client, publisher, ad_unit, site):
        PublisherEarningFactory(
            publisher=publisher, site=site, ad_unit=ad_unit, country='BD'
        )
        resp = publisher_client.get(earn_url('by_country'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_by_ad_unit_returns_list(self, publisher_client, publisher, ad_unit, site):
        PublisherEarningFactory(publisher=publisher, site=site, ad_unit=ad_unit)
        resp = publisher_client.get(earn_url('by_ad_unit'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_by_country_respects_period_param(
        self, publisher_client, publisher, ad_unit, site
    ):
        resp = publisher_client.get(earn_url('by_country'), {'period': 'last_7_days'})
        assert resp.status_code == 200

    def test_unauthenticated_cannot_view_summary(self, api_client):
        resp = api_client.get(earn_url('summary'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# PayoutThreshold — CREATE / RETRIEVE / SET_PRIMARY / VERIFY
# ==============================================================================

@pytest.mark.django_db
class TestPayoutThreshold:

    def _payload(self):
        return {
            'payment_method': 'bank_transfer',
            'threshold_amount': '100.00',
            'currency': 'USD',
            'account_name': 'John Doe',
            'account_details': {'bank': 'Test Bank', 'account': '123456'},
        }

    def test_publisher_can_create_threshold(self, publisher_client):
        resp = publisher_client.post(thr_url(), self._payload(), format='json')
        assert resp.status_code == 201

    def test_created_threshold_not_verified_by_default(self, publisher_client):
        resp = publisher_client.post(thr_url(), self._payload(), format='json')
        body = resp.json()
        data = body.get('data', body)
        assert data.get('is_verified') is False

    def test_missing_payment_method_returns_400(self, publisher_client):
        data = self._payload()
        del data['payment_method']
        resp = publisher_client.post(thr_url(), data, format='json')
        assert resp.status_code == 400

    def test_invalid_payment_method_returns_400(self, publisher_client):
        data = self._payload()
        data['payment_method'] = 'cryptocurrency'
        resp = publisher_client.post(thr_url(), data, format='json')
        assert resp.status_code == 400

    def test_publisher_can_list_own_thresholds(self, publisher_client, payout_threshold):
        resp = publisher_client.get(thr_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) >= 1

    def test_publisher_cannot_see_other_thresholds(
        self, publisher_client_2, payout_threshold
    ):
        resp = publisher_client_2.get(thr_url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_publisher_can_set_primary(self, publisher_client, publisher):
        t1 = PayoutThresholdFactory(publisher=publisher, is_primary=True)
        t2 = PayoutThresholdFactory(publisher=publisher, is_primary=False)
        resp = publisher_client.post(thr_url(f'/{t2.pk}/set_primary'))
        assert resp.status_code == 200
        t2.refresh_from_db()
        t1.refresh_from_db()
        assert t2.is_primary is True
        assert t1.is_primary is False

    def test_set_primary_unsets_others(self, publisher_client, publisher):
        """Only one threshold should be primary at a time."""
        thresholds = [
            PayoutThresholdFactory(publisher=publisher, is_primary=True)
            for _ in range(3)
        ]
        resp = publisher_client.post(thr_url(f'/{thresholds[-1].pk}/set_primary'))
        assert resp.status_code == 200
        for t in thresholds[:-1]:
            t.refresh_from_db()
            assert t.is_primary is False

    def test_admin_can_verify_threshold(self, admin_client, payout_threshold):
        resp = admin_client.post(thr_url(f'/{payout_threshold.pk}/verify'))
        assert resp.status_code == 200
        payout_threshold.refresh_from_db()
        assert payout_threshold.is_verified is True

    def test_publisher_cannot_self_verify_threshold(
        self, publisher_client, payout_threshold
    ):
        resp = publisher_client.post(thr_url(f'/{payout_threshold.pk}/verify'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_create_threshold(self, api_client):
        resp = api_client.post(thr_url(), self._payload(), format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# Invoice — LIST / RETRIEVE
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceListRetrieve:

    def test_publisher_can_list_own_invoices(self, publisher_client, invoice):
        resp = publisher_client.get(inv_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) >= 1

    def test_publisher_cannot_see_other_publisher_invoices(
        self, publisher_client_2, invoice
    ):
        resp = publisher_client_2.get(inv_url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_admin_can_list_all_invoices(self, admin_client, invoice):
        resp = admin_client.get(inv_url())
        assert resp.status_code == 200

    def test_admin_can_filter_by_status(self, admin_client, invoice):
        resp = admin_client.get(inv_url(), {'status': 'draft'})
        assert resp.status_code == 200

    def test_admin_can_filter_by_publisher_id(self, admin_client, publisher, invoice):
        resp = admin_client.get(inv_url(), {'publisher_id': str(publisher.publisher_id)})
        assert resp.status_code == 200

    def test_publisher_can_retrieve_own_invoice(self, publisher_client, invoice):
        resp = publisher_client.get(inv_url(f'/{invoice.pk}'))
        assert resp.status_code == 200

    def test_publisher_cannot_retrieve_other_invoice(self, publisher_client_2, invoice):
        resp = publisher_client_2.get(inv_url(f'/{invoice.pk}'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_list_invoices(self, api_client):
        resp = api_client.get(inv_url())
        assert resp.status_code in (401, 403)


# ==============================================================================
# Invoice — GENERATE (admin)
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceGenerate:

    def test_admin_can_generate_invoice(self, admin_client, publisher):
        resp = admin_client.post(
            inv_url('generate'),
            {
                'publisher_id': str(publisher.publisher_id),
                'year': 2025,
                'month': 1,
            },
            format='json',
        )
        assert resp.status_code == 201

    def test_generate_returns_invoice_data(self, admin_client, publisher):
        resp = admin_client.post(
            inv_url('generate'),
            {'publisher_id': str(publisher.publisher_id), 'year': 2025, 'month': 1},
            format='json',
        )
        body = resp.json()
        data = body.get('data', body)
        assert 'status' in data
        assert 'payable_amount' in data

    def test_publisher_cannot_generate_invoice(self, publisher_client, publisher):
        resp = publisher_client.post(
            inv_url('generate'),
            {'publisher_id': str(publisher.publisher_id), 'year': 2025, 'month': 1},
            format='json',
        )
        assert resp.status_code in (403, 404)

    def test_nonexistent_publisher_returns_error(self, admin_client):
        resp = admin_client.post(
            inv_url('generate'),
            {'publisher_id': 'PUB999999', 'year': 2025, 'month': 1},
            format='json',
        )
        assert resp.status_code in (400, 404)

    def test_unauthenticated_cannot_generate(self, api_client, publisher):
        resp = api_client.post(
            inv_url('generate'),
            {'publisher_id': str(publisher.publisher_id), 'year': 2025, 'month': 1},
            format='json',
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# Invoice — ISSUE (admin)
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceIssue:

    def test_admin_can_issue_draft_invoice(self, admin_client, invoice):
        resp = admin_client.post(inv_url(f'/{invoice.pk}/issue'))
        assert resp.status_code == 200
        invoice.refresh_from_db()
        assert invoice.status == 'issued'

    def test_publisher_cannot_issue_invoice(self, publisher_client, invoice):
        resp = publisher_client.post(inv_url(f'/{invoice.pk}/issue'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_issue(self, api_client, invoice):
        resp = api_client.post(inv_url(f'/{invoice.pk}/issue'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# Invoice — MARK_PAID (admin)
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceMarkPaid:

    def test_admin_can_mark_invoice_paid(self, admin_client, issued_invoice):
        resp = admin_client.post(
            inv_url(f'/{issued_invoice.pk}/mark_paid'),
            {'payment_reference': 'TXN-20250201-001'},
            format='json',
        )
        assert resp.status_code == 200
        issued_invoice.refresh_from_db()
        assert issued_invoice.status == 'paid'

    def test_mark_paid_without_reference_returns_400(self, admin_client, issued_invoice):
        resp = admin_client.post(
            inv_url(f'/{issued_invoice.pk}/mark_paid'),
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_cannot_mark_paid(self, publisher_client, issued_invoice):
        resp = publisher_client.post(
            inv_url(f'/{issued_invoice.pk}/mark_paid'),
            {'payment_reference': 'TXN-HACK'},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# Invoice — DISPUTE (publisher)
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceDispute:

    def test_publisher_can_dispute_own_invoice(self, publisher_client, issued_invoice):
        resp = publisher_client.post(
            inv_url(f'/{issued_invoice.pk}/dispute'),
            {'reason': 'Revenue figures do not match my records.'},
            format='json',
        )
        assert resp.status_code == 200
        issued_invoice.refresh_from_db()
        assert issued_invoice.status == 'disputed'

    def test_dispute_without_reason_returns_400(self, publisher_client, issued_invoice):
        resp = publisher_client.post(
            inv_url(f'/{issued_invoice.pk}/dispute'),
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_other_publisher_cannot_dispute(self, publisher_client_2, issued_invoice):
        resp = publisher_client_2.post(
            inv_url(f'/{issued_invoice.pk}/dispute'),
            {'reason': 'Theft attempt'},
            format='json',
        )
        assert resp.status_code in (403, 404)

    def test_dispute_sets_publisher_notes(self, publisher_client, issued_invoice):
        reason = 'eCPM numbers are 30% lower than my ad server reports.'
        publisher_client.post(
            inv_url(f'/{issued_invoice.pk}/dispute'),
            {'reason': reason},
            format='json',
        )
        issued_invoice.refresh_from_db()
        assert issued_invoice.publisher_notes == reason

    def test_unauthenticated_cannot_dispute(self, api_client, issued_invoice):
        resp = api_client.post(
            inv_url(f'/{issued_invoice.pk}/dispute'),
            {'reason': 'anonymous dispute'},
            format='json',
        )
        assert resp.status_code in (401, 403)
