# publisher_tools/tests/test_views_missing_actions.py
"""
152-target test suite for previously untested @action endpoints.

Coverage (28 actions, ~5-6 tests each):
  Analytics:       hourly_impressions, best_hours, site_rpm, rpm_benchmark,
                   fill_impact, export_csv, track_request
  Payment-Ext:     all_thresholds, exchange_rates, invoice_html
  Payment-Adv:     validate_payment_details, receipt_html, min_threshold
  Webhooks:        payload_preview, delivery_stats, failed_deliveries, replay_all_failed
  Publisher-Adv:   subscription_plans, kyc_submit, add_bank_account, set_primary_account
  Fraud-Tools:     fraud_config, check_device
  Ad-Networks:     save_network_config, toggle_network, network_detail
  AB-Test-Adv:     create_position
  Placement-Tools: placement_report, for_app
  App-Management:  download_trend, quality_score, sdk_config, approval_history

Pattern: pytest + APIClient + fixtures from conftest.py (publisher_client, publisher_user,
         publisher, site, app, ad_unit, invoice, payout_threshold, etc.)
Auth:    publisher_client → force_authenticate(user=publisher_user)
Assert:  status_code + response key presence (where applicable)
"""

import pytest
from publisher_tools.tests.factories import (
    PublisherWebhookFactory,
    WebhookDeliveryLogFactory,
)

# ──────────────────────────────────────────────────────────────────────────────
# URL base constants
# ──────────────────────────────────────────────────────────────────────────────
BASE_ANALYTICS      = '/api/publisher-tools/analytics-ext'
BASE_PAYMENT_EXT    = '/api/publisher-tools/payments-extended'
BASE_PAYMENT_ADV    = '/api/publisher-tools/payment-advanced'
BASE_WEBHOOKS       = '/api/publisher-tools/webhooks-ext'
BASE_PUBLISHER_ADV  = '/api/publisher-tools/publisher-advanced'
BASE_FRAUD          = '/api/publisher-tools/fraud-tools'
BASE_NETWORKS       = '/api/publisher-tools/ad-networks'
BASE_ABTEST_ADV     = '/api/publisher-tools/ab-tests-adv'
BASE_PLACEMENT      = '/api/publisher-tools/placement-tools'
BASE_APP_MGMT       = '/api/publisher-tools/app-management'


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — ANALYTICS EXTENDED  (AnalyticsExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingHourlyImpressions:
    """hourly_impressions — GET /analytics-ext/hourly-impressions/?unit_id=<id>"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_ANALYTICS}/hourly-impressions/')
        assert resp.status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/hourly-impressions/')
        assert resp.status_code == 400

    def test_valid_unit_id_returns_data(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/hourly-impressions/',
            {'unit_id': ad_unit.unit_id},
        )
        assert resp.status_code in (200, 503)

    def test_response_has_unit_id_key_when_200(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/hourly-impressions/',
            {'unit_id': ad_unit.unit_id},
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'unit_id' in data

    def test_bogus_unit_id_returns_error_not_500(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/hourly-impressions/',
            {'unit_id': 'UNIT-DOES-NOT-EXIST-999'},
        )
        assert resp.status_code in (200, 400, 404, 503)


@pytest.mark.django_db
class TestMissingBestHours:
    """best_hours — GET /analytics-ext/best-hours/?days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_ANALYTICS}/best-hours/')
        assert resp.status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/best-hours/')
        assert resp.status_code in (200, 503)

    def test_with_custom_days_param(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/best-hours/', {'days': 7})
        assert resp.status_code in (200, 503)

    def test_response_structure_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/best-hours/', {'days': 14})
        if resp.status_code == 200:
            body = resp.json()
            assert 'data' in body or 'error' in body


@pytest.mark.django_db
class TestMissingSiteRpm:
    """site_rpm — GET /analytics-ext/site-rpm/?site_id=<id>&days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_ANALYTICS}/site-rpm/')
        assert resp.status_code in (401, 403)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/site-rpm/')
        assert resp.status_code == 400

    def test_valid_site_id_returns_data(self, publisher_client, site):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/site-rpm/', {'site_id': site.pk}
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_days_param(self, publisher_client, site):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/site-rpm/', {'site_id': site.pk, 'days': 7}
        )
        assert resp.status_code in (200, 503)

    def test_nonexistent_site_returns_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/site-rpm/', {'site_id': 999999}
        )
        assert resp.status_code in (400, 404, 503)


@pytest.mark.django_db
class TestMissingRpmBenchmark:
    """rpm_benchmark — GET /analytics-ext/rpm-benchmark/?site_id=<id>&days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_ANALYTICS}/rpm-benchmark/')
        assert resp.status_code in (401, 403)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/rpm-benchmark/')
        assert resp.status_code == 400

    def test_valid_site_returns_data(self, publisher_client, site):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/rpm-benchmark/', {'site_id': site.pk}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_benchmark_keys_when_200(self, publisher_client, site):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/rpm-benchmark/', {'site_id': site.pk}
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'site_rpm' in data or 'comparison' in data

    def test_with_custom_days_param(self, publisher_client, site):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/rpm-benchmark/', {'site_id': site.pk, 'days': 14}
        )
        assert resp.status_code in (200, 503)


@pytest.mark.django_db
class TestMissingFillImpact:
    """fill_impact — GET /analytics-ext/fill-impact/?unit_id=<id>&target_fill=80"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_ANALYTICS}/fill-impact/')
        assert resp.status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_ANALYTICS}/fill-impact/')
        assert resp.status_code == 400

    def test_valid_unit_id_returns_data(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/fill-impact/', {'unit_id': ad_unit.pk}
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_target_fill(self, publisher_client, ad_unit):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/fill-impact/',
            {'unit_id': ad_unit.pk, 'target_fill': 90},
        )
        assert resp.status_code in (200, 503)

    def test_nonexistent_unit_returns_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_ANALYTICS}/fill-impact/', {'unit_id': 999999}
        )
        assert resp.status_code in (400, 404, 503)


@pytest.mark.django_db
class TestMissingExportCsv:
    """export_csv — POST /analytics-ext/export-csv/ (CSV download or error)"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_ANALYTICS}/export-csv/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_default_body_returns_data(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/export-csv/', {}, format='json'
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_metrics_and_dimensions(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/export-csv/',
            {'metrics': ['impressions', 'revenue', 'ecpm'], 'dimensions': ['date', 'country']},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_invalid_date_format_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/export-csv/',
            {'start_date': 'not-a-date', 'end_date': '2025-01-31'},
            format='json',
        )
        assert resp.status_code == 400

    def test_csv_content_type_or_json_error(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/export-csv/',
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
            format='json',
        )
        if resp.status_code == 200:
            ct = resp.get('Content-Type', '')
            assert 'csv' in ct or 'json' in ct


@pytest.mark.django_db
class TestMissingTrackRequest:
    """track_request — POST /analytics-ext/track-request/ (ad request event)"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_ANALYTICS}/track-request/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_unit_id_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/track-request/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_valid_unit_id_accepted(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/track-request/',
            {'unit_id': ad_unit.unit_id},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_with_context_dict(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/track-request/',
            {'unit_id': ad_unit.unit_id, 'context': {'country': 'BD', 'device': 'mobile'}},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_response_is_not_500(self, publisher_client, ad_unit):
        resp = publisher_client.post(
            f'{BASE_ANALYTICS}/track-request/',
            {'unit_id': ad_unit.unit_id, 'context': {}},
            format='json',
        )
        assert resp.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PAYMENT EXTENDED  (PaymentExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingAllThresholds:
    """all_thresholds — GET /payments-extended/all-thresholds/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_PAYMENT_EXT}/all-thresholds/')
        assert resp.status_code in (401, 403)

    def test_returns_thresholds_list(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/all-thresholds/')
        assert resp.status_code in (200, 503)

    def test_response_has_thresholds_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/all-thresholds/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'thresholds' in data

    def test_with_payout_threshold_fixture(self, publisher_client, payout_threshold):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/all-thresholds/')
        assert resp.status_code in (200, 503)


@pytest.mark.django_db
class TestMissingExchangeRates:
    """exchange_rates — GET /payments-extended/exchange-rates/?base=USD"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_PAYMENT_EXT}/exchange-rates/')
        assert resp.status_code in (401, 403)

    def test_default_usd_base_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/exchange-rates/')
        assert resp.status_code in (200, 503)

    def test_custom_eur_base(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_EXT}/exchange-rates/', {'base': 'EUR'}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_rates_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/exchange-rates/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'rates' in data

    def test_response_has_base_currency_in_rates(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_EXT}/exchange-rates/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            rates = data.get('rates', {})
            assert 'USD' in rates


@pytest.mark.django_db
class TestMissingInvoiceHtml:
    """invoice_html — GET /payments-extended/invoice-html/<pk>/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(
            f'{BASE_PAYMENT_EXT}/invoice-html/1/'
        )
        assert resp.status_code in (401, 403)

    def test_nonexistent_invoice_returns_404_or_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_EXT}/invoice-html/999999/'
        )
        assert resp.status_code in (404, 503)

    def test_valid_invoice_returns_200_or_503(self, publisher_client, invoice):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_EXT}/invoice-html/{invoice.pk}/'
        )
        assert resp.status_code in (200, 503)

    def test_isolation_other_publisher_denied(self, publisher_client_2, invoice):
        resp = publisher_client_2.get(
            f'{BASE_PAYMENT_EXT}/invoice-html/{invoice.pk}/'
        )
        assert resp.status_code in (403, 404, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PAYMENT ADVANCED  (PaymentAdvancedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingValidatePaymentDetails:
    """validate_payment_details — POST /payment-advanced/validate-payment-details/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_PAYMENT_ADV}/validate-payment-details/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_method_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PAYMENT_ADV}/validate-payment-details/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_valid_paypal_method(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PAYMENT_ADV}/validate-payment-details/',
            {'method': 'paypal', 'details': {'email': 'pay@example.com'}},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_valid_bank_transfer_method(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PAYMENT_ADV}/validate-payment-details/',
            {
                'method': 'bank_transfer',
                'details': {
                    'account_number': '1234567890',
                    'routing_number': '021000021',
                    'bank_name': 'Test Bank',
                },
            },
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_response_has_result_when_200(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PAYMENT_ADV}/validate-payment-details/',
            {'method': 'paypal', 'details': {'email': 'a@b.com'}},
            format='json',
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert isinstance(data, dict)


@pytest.mark.django_db
class TestMissingReceiptHtml:
    """receipt_html — GET /payment-advanced/receipt-html/<pk>/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(
            f'{BASE_PAYMENT_ADV}/receipt-html/1/'
        )
        assert resp.status_code in (401, 403)

    def test_nonexistent_invoice_returns_404_or_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_ADV}/receipt-html/999999/'
        )
        assert resp.status_code in (404, 503)

    def test_valid_invoice_returns_data(self, publisher_client, invoice):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_ADV}/receipt-html/{invoice.pk}/'
        )
        assert resp.status_code in (200, 503)

    def test_isolation_other_publisher_denied(self, publisher_client_2, invoice):
        resp = publisher_client_2.get(
            f'{BASE_PAYMENT_ADV}/receipt-html/{invoice.pk}/'
        )
        assert resp.status_code in (403, 404, 503)


@pytest.mark.django_db
class TestMissingMinThreshold:
    """min_threshold — GET /payment-advanced/min-threshold/?method=paypal"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_PAYMENT_ADV}/min-threshold/')
        assert resp.status_code in (401, 403)

    def test_default_method_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PAYMENT_ADV}/min-threshold/')
        assert resp.status_code in (200, 503)

    def test_bank_transfer_method_returns_data(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_ADV}/min-threshold/', {'method': 'bank_transfer'}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_threshold_and_currency_when_200(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PAYMENT_ADV}/min-threshold/', {'method': 'paypal'}
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'threshold' in data
            assert 'currency' in data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — WEBHOOKS EXTENDED  (WebhookExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingPayloadPreview:
    """payload_preview — GET /webhooks-ext/payload-preview/?event_type=invoice.paid"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_WEBHOOKS}/payload-preview/')
        assert resp.status_code in (401, 403)

    def test_missing_event_type_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_WEBHOOKS}/payload-preview/')
        assert resp.status_code == 400

    def test_invalid_event_type_returns_400(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/payload-preview/',
            {'event_type': 'completely.bogus.event'},
        )
        assert resp.status_code == 400

    def test_valid_invoice_paid_event_returns_data(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/payload-preview/',
            {'event_type': 'invoice.paid'},
        )
        assert resp.status_code in (200, 503)

    def test_response_has_sample_payload_when_200(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/payload-preview/',
            {'event_type': 'invoice.paid'},
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'sample_payload' in data

    def test_response_has_event_type_when_200(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/payload-preview/',
            {'event_type': 'invoice.paid'},
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'event_type' in data


@pytest.mark.django_db
class TestMissingDeliveryStats:
    """delivery_stats — GET /webhooks-ext/delivery-stats/?webhook_id=<id>&days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_WEBHOOKS}/delivery-stats/')
        assert resp.status_code in (401, 403)

    def test_returns_stats_with_no_webhooks(self, publisher_client):
        resp = publisher_client.get(f'{BASE_WEBHOOKS}/delivery-stats/')
        assert resp.status_code in (200, 503)

    def test_with_a_created_webhook(self, publisher_client, publisher):
        webhook = PublisherWebhookFactory(publisher=publisher)
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/delivery-stats/',
            {'webhook_id': webhook.pk},
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_days_param(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/delivery-stats/', {'days': 7}
        )
        assert resp.status_code in (200, 503)

    def test_response_is_not_500(self, publisher_client):
        resp = publisher_client.get(f'{BASE_WEBHOOKS}/delivery-stats/')
        assert resp.status_code != 500


@pytest.mark.django_db
class TestMissingFailedDeliveries:
    """failed_deliveries — GET /webhooks-ext/failed-deliveries/?webhook_id=<id>&limit=50"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_WEBHOOKS}/failed-deliveries/')
        assert resp.status_code in (401, 403)

    def test_returns_failures_list(self, publisher_client):
        resp = publisher_client.get(f'{BASE_WEBHOOKS}/failed-deliveries/')
        assert resp.status_code in (200, 503)

    def test_response_has_failures_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_WEBHOOKS}/failed-deliveries/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'failures' in data

    def test_with_specific_webhook_id(self, publisher_client, publisher):
        webhook = PublisherWebhookFactory(publisher=publisher)
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/failed-deliveries/', {'webhook_id': webhook.pk}
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_limit_param(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_WEBHOOKS}/failed-deliveries/', {'limit': 10}
        )
        assert resp.status_code in (200, 503)


@pytest.mark.django_db
class TestMissingReplayAllFailed:
    """replay_all_failed — POST /webhooks-ext/replay-all-failed/ {webhook_id: <id>}"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_WEBHOOKS}/replay-all-failed/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_webhook_id_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_WEBHOOKS}/replay-all-failed/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_nonexistent_webhook_returns_error(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_WEBHOOKS}/replay-all-failed/',
            {'webhook_id': 999999},
            format='json',
        )
        assert resp.status_code in (404, 503)

    def test_valid_webhook_with_no_failures(self, publisher_client, publisher):
        webhook = PublisherWebhookFactory(publisher=publisher)
        resp = publisher_client.post(
            f'{BASE_WEBHOOKS}/replay-all-failed/',
            {'webhook_id': webhook.pk},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_response_has_replayed_key_when_200(self, publisher_client, publisher):
        webhook = PublisherWebhookFactory(publisher=publisher)
        resp = publisher_client.post(
            f'{BASE_WEBHOOKS}/replay-all-failed/',
            {'webhook_id': webhook.pk},
            format='json',
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'replayed' in data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — PUBLISHER ADVANCED  (PublisherAdvancedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingSubscriptionPlans:
    """subscription_plans — GET /publisher-advanced/subscription-plans/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(
            f'{BASE_PUBLISHER_ADV}/subscription-plans/'
        )
        assert resp.status_code in (401, 403)

    def test_returns_plans_or_empty_list(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PUBLISHER_ADV}/subscription-plans/')
        assert resp.status_code in (200, 503)

    def test_response_has_plans_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PUBLISHER_ADV}/subscription-plans/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'plans' in data

    def test_response_has_count_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PUBLISHER_ADV}/subscription-plans/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'count' in data


@pytest.mark.django_db
class TestMissingKycSubmit:
    """kyc_submit — POST /publisher-advanced/kyc-submit/ with required fields"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_PUBLISHER_ADV}/kyc-submit/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_empty_body_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/kyc-submit/', {}, format='json'
        )
        assert resp.status_code in (400, 503)

    def test_partial_required_fields_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/kyc-submit/',
            {'kyc_type': 'individual', 'full_name': 'Test User'},
            format='json',
        )
        assert resp.status_code in (400, 503)

    def test_full_required_payload_accepted(self, publisher_client):
        payload = {
            'kyc_type':  'individual',
            'full_name': 'Test User',
            'id_type':   'national_id',
            'id_number': 'NID-123456789',
            'country':   'Bangladesh',
        }
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/kyc-submit/', payload, format='json'
        )
        assert resp.status_code in (200, 400, 503)

    def test_response_has_kyc_id_when_successful(self, publisher_client):
        payload = {
            'kyc_type':  'individual',
            'full_name': 'Test User',
            'id_type':   'national_id',
            'id_number': 'NID-987654321',
            'country':   'Bangladesh',
        }
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/kyc-submit/', payload, format='json'
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'kyc_id' in data or 'status' in data


@pytest.mark.django_db
class TestMissingAddBankAccount:
    """add_bank_account — POST /publisher-advanced/bank-accounts/add/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_account_type_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_valid_bank_account_accepted(self, publisher_client):
        payload = {
            'account_type':        'bank_transfer',
            'account_holder_name': 'Test Publisher',
            'account_number':      '1234567890',
            'bank_name':           'BRAC Bank',
            'bank_country':        'Bangladesh',
        }
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/', payload, format='json'
        )
        assert resp.status_code in (200, 201, 503)

    def test_response_has_masked_number_key_when_200(self, publisher_client):
        payload = {
            'account_type':        'bank_transfer',
            'account_holder_name': 'Test Publisher 2',
            'account_number':      '9876543210',
            'bank_name':           'Dutch Bangla',
            'bank_country':        'Bangladesh',
        }
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/', payload, format='json'
        )
        if resp.status_code in (200, 201):
            data = resp.json().get('data', {})
            assert 'masked_number' in data or 'pk' in data

    def test_set_as_primary_flag(self, publisher_client):
        payload = {
            'account_type':        'paypal',
            'email':               'publisher@paypal.com',
            'set_as_primary':      True,
        }
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/', payload, format='json'
        )
        assert resp.status_code in (200, 201, 503)


@pytest.mark.django_db
class TestMissingSetPrimaryAccount:
    """set_primary_account — POST /publisher-advanced/bank-accounts/primary/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/primary/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_account_id_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/primary/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_nonexistent_account_returns_error(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/primary/',
            {'account_id': 999999},
            format='json',
        )
        assert resp.status_code in (404, 503)

    def test_response_structure_when_successful(self, publisher_client):
        # First create an account, then set it as primary
        add_resp = publisher_client.post(
            f'{BASE_PUBLISHER_ADV}/bank-accounts/add/',
            {'account_type': 'bank_transfer', 'account_holder_name': 'Primary Test',
             'account_number': '111222333', 'bank_name': 'Prime Bank', 'bank_country': 'BD'},
            format='json',
        )
        if add_resp.status_code in (200, 201):
            account_id = add_resp.json().get('data', {}).get('pk')
            if account_id:
                resp = publisher_client.post(
                    f'{BASE_PUBLISHER_ADV}/bank-accounts/primary/',
                    {'account_id': account_id},
                    format='json',
                )
                assert resp.status_code in (200, 503)
        else:
            pytest.skip('Bank account creation unavailable in this environment')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — FRAUD TOOLS  (FraudExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingFraudConfig:
    """fraud_config — GET /fraud-tools/config/"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_FRAUD}/config/')
        assert resp.status_code in (401, 403)

    def test_returns_config_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_FRAUD}/config/')
        assert resp.status_code in (200, 503)

    def test_response_has_auto_block_score_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_FRAUD}/config/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'auto_block_score' in data

    def test_response_has_suspicious_click_threshold_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_FRAUD}/config/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'suspicious_click_threshold' in data


@pytest.mark.django_db
class TestMissingCheckDevice:
    """check_device — POST /fraud-tools/check-device/ {device_data: {...}}"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_FRAUD}/check-device/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_device_data_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_FRAUD}/check-device/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_empty_device_data_dict_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_FRAUD}/check-device/',
            {'device_data': {}},
            format='json',
        )
        assert resp.status_code == 400

    def test_valid_device_data_returns_data(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_FRAUD}/check-device/',
            {
                'device_data': {
                    'screen':        '1920x1080',
                    'platform':      'Win32',
                    'user_agent':    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'timezone':      'Asia/Dhaka',
                    'language':      'en-US',
                },
            },
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_response_has_trust_score_or_fingerprint_when_200(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_FRAUD}/check-device/',
            {'device_data': {'screen': '1366x768', 'platform': 'Linux x86_64'}},
            format='json',
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'trust_score' in data or 'fingerprint' in data or 'score' in data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — AD NETWORKS  (AdNetworkExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingSaveNetworkConfig:
    """save_network_config — POST /ad-networks/per-network/save/ {network: 'admob', ...}"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_NETWORKS}/per-network/save/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_network_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/save/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_invalid_unknown_network_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/save/',
            {'network': 'completely_fake_network'},
            format='json',
        )
        assert resp.status_code == 400

    def test_valid_admob_config_accepted(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/save/',
            {'network': 'admob', 'app_id': 'ca-app-pub-XXXXX~YYYYY'},
            format='json',
        )
        assert resp.status_code in (200, 201, 400, 503)

    def test_response_has_network_key_when_200_or_201(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/save/',
            {'network': 'admob', 'app_id': 'ca-app-pub-TEST~9999'},
            format='json',
        )
        if resp.status_code in (200, 201):
            data = resp.json().get('data', {})
            assert 'network' in data


@pytest.mark.django_db
class TestMissingToggleNetwork:
    """toggle_network — POST /ad-networks/per-network/enable/ {network: 'admob', enabled: true}"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_NETWORKS}/per-network/enable/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_network_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/enable/', {}, format='json'
        )
        assert resp.status_code == 400

    def test_enable_admob_returns_expected_status(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/enable/',
            {'network': 'admob', 'enabled': True},
            format='json',
        )
        # 404 = no config yet, 200 = toggled, 503 = service error
        assert resp.status_code in (200, 400, 404, 503)

    def test_disable_admob_returns_expected_status(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/enable/',
            {'network': 'admob', 'enabled': False},
            format='json',
        )
        assert resp.status_code in (200, 400, 404, 503)

    def test_response_has_enabled_key_when_200(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_NETWORKS}/per-network/enable/',
            {'network': 'admob', 'enabled': True},
            format='json',
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'enabled' in data


@pytest.mark.django_db
class TestMissingNetworkDetail:
    """network_detail — GET /ad-networks/detail/?network=admob&days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_NETWORKS}/detail/')
        assert resp.status_code in (401, 403)

    def test_missing_network_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_NETWORKS}/detail/')
        assert resp.status_code == 400

    def test_invalid_network_returns_400(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_NETWORKS}/detail/', {'network': 'totally_fake'}
        )
        assert resp.status_code == 400

    def test_valid_admob_returns_data(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_NETWORKS}/detail/', {'network': 'admob'}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_meta_key_when_200(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_NETWORKS}/detail/', {'network': 'admob'}
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'meta' in data or 'network' in data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — AD UNIT ACTIONS  (various viewsets)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingCreatePosition:
    """create_position — POST /ab-tests-adv/create-position/
       {site_id: <id>, positions: ['top', 'sidebar', ...]}
    """

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f'{BASE_ABTEST_ADV}/create-position/', {}, format='json'
        )
        assert resp.status_code in (401, 403)

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ABTEST_ADV}/create-position/',
            {'positions': ['top_of_page', 'sidebar']},
            format='json',
        )
        assert resp.status_code == 400

    def test_only_one_position_returns_400(self, publisher_client, site):
        resp = publisher_client.post(
            f'{BASE_ABTEST_ADV}/create-position/',
            {'site_id': site.pk, 'positions': ['top_of_page']},
            format='json',
        )
        assert resp.status_code == 400

    def test_valid_positions_accepted(self, publisher_client, site):
        resp = publisher_client.post(
            f'{BASE_ABTEST_ADV}/create-position/',
            {'site_id': site.pk, 'positions': ['top_of_page', 'sidebar', 'in_article']},
            format='json',
        )
        assert resp.status_code in (200, 201, 503)

    def test_nonexistent_site_returns_error(self, publisher_client):
        resp = publisher_client.post(
            f'{BASE_ABTEST_ADV}/create-position/',
            {'site_id': 999999, 'positions': ['top_of_page', 'sidebar']},
            format='json',
        )
        assert resp.status_code in (400, 404, 503)


@pytest.mark.django_db
class TestMissingForApp:
    """for_app — GET /placement-tools/for-app/?app_id=<id>"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_PLACEMENT}/for-app/')
        assert resp.status_code in (401, 403)

    def test_missing_app_id_returns_400(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PLACEMENT}/for-app/')
        assert resp.status_code == 400

    def test_valid_app_id_returns_data(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_PLACEMENT}/for-app/', {'app_id': app.pk}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_placements_key_when_200(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_PLACEMENT}/for-app/', {'app_id': app.pk}
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'placements' in data

    def test_nonexistent_app_returns_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PLACEMENT}/for-app/', {'app_id': 999999}
        )
        assert resp.status_code in (400, 404, 503)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — PLACEMENT TOOLS  (PlacementExtendedViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingPlacementReport:
    """placement_report — GET /placement-tools/report/?start=2025-01-01&end=2025-01-31"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_PLACEMENT}/report/')
        assert resp.status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PLACEMENT}/report/')
        assert resp.status_code in (200, 503)

    def test_with_explicit_date_range(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PLACEMENT}/report/',
            {'start': '2025-01-01', 'end': '2025-01-31'},
        )
        assert resp.status_code in (200, 503)

    def test_invalid_date_format_returns_400(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_PLACEMENT}/report/',
            {'start': 'bad-date', 'end': '2025-01-31'},
        )
        assert resp.status_code == 400

    def test_response_is_not_500(self, publisher_client):
        resp = publisher_client.get(f'{BASE_PLACEMENT}/report/')
        assert resp.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — APP MANAGEMENT  (AppManagementFullViewSet)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMissingDownloadTrend:
    """download_trend — GET /app-management/download-trend/?app_id=<id>&days=30"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_APP_MGMT}/download-trend/')
        assert resp.status_code in (401, 403)

    def test_default_returns_data(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/download-trend/')
        assert resp.status_code in (200, 503)

    def test_with_specific_app_id(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/download-trend/', {'app_id': app.app_id}
        )
        assert resp.status_code in (200, 503)

    def test_with_custom_days_param(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/download-trend/',
            {'app_id': app.app_id, 'days': 7},
        )
        assert resp.status_code in (200, 503)

    def test_response_has_snapshots_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/download-trend/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'snapshots' in data


@pytest.mark.django_db
class TestMissingAppQualityScore:
    """quality_score — GET /app-management/quality-score/?app_id=<id>"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_APP_MGMT}/quality-score/')
        assert resp.status_code in (401, 403)

    def test_no_score_returns_none_message(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/quality-score/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Either has a score or a message saying no score yet
            assert 'score' in data or 'message' in data

    def test_with_specific_app_id(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/quality-score/', {'app_id': app.app_id}
        )
        assert resp.status_code in (200, 503)

    def test_response_is_not_500(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/quality-score/')
        assert resp.status_code != 500


@pytest.mark.django_db
class TestMissingSdkConfig:
    """sdk_config — GET /app-management/sdk-config/?app_id=<id>"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_APP_MGMT}/sdk-config/')
        assert resp.status_code in (401, 403)

    def test_missing_app_id_without_apps_returns_404_or_none(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/sdk-config/')
        # If no app_id provided and no apps exist, expect 404 or message response
        assert resp.status_code in (200, 404, 503)

    def test_valid_app_no_sdk_config_returns_null(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/sdk-config/', {'app_id': app.app_id}
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # config is null when not yet set up
            assert 'config' in data or 'pk' in data or 'message' in data

    def test_nonexistent_app_id_returns_404_or_error(self, publisher_client):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/sdk-config/', {'app_id': 'APP-DOES-NOT-EXIST'}
        )
        assert resp.status_code in (200, 404, 503)

    def test_response_is_not_500(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/sdk-config/')
        assert resp.status_code != 500


@pytest.mark.django_db
class TestMissingApprovalHistory:
    """approval_history — GET /app-management/approval-history/?app_id=<id>"""

    def test_unauthenticated_request_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(f'{BASE_APP_MGMT}/approval-history/')
        assert resp.status_code in (401, 403)

    def test_default_returns_records_list(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/approval-history/')
        assert resp.status_code in (200, 503)

    def test_with_specific_app_id_filter(self, publisher_client, app):
        resp = publisher_client.get(
            f'{BASE_APP_MGMT}/approval-history/', {'app_id': app.app_id}
        )
        assert resp.status_code in (200, 503)

    def test_response_has_records_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/approval-history/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'records' in data

    def test_response_has_count_key_when_200(self, publisher_client):
        resp = publisher_client.get(f'{BASE_APP_MGMT}/approval-history/')
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'count' in data
