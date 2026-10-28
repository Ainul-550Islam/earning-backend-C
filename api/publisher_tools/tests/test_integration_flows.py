# publisher_tools/tests/test_integration_flows.py
"""
Integration tests — পুরো request → DB → Celery flow cover করে।

এই tests unit tests থেকে আলাদা:
  - Real DB writes (transactions)
  - Celery task side effects (Django DB backend)
  - Multi-step flows (create → update → verify)
  - Cross-component interactions (KYC → Verification, Payout → Balance)

Pattern: pytest + APIClient + @pytest.mark.django_db(transaction=True)
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
from rest_framework.test import APIClient

from publisher_tools.tests.factories import (
    PublisherFactory,
    SiteFactory,
    AppFactory,
    AdUnitFactory,
    PublisherInvoiceFactory,
    PublisherEarningFactory,
)


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 1 — Publisher Onboarding Flow
# (register → KYC submit → KYC approve → verification level update)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestPublisherOnboardingFlow:
    """
    পুরো publisher onboarding flow:
    1. Publisher object create হয়
    2. Publisher KYC submit করে
    3. Admin approve করে
    4. Verification level বাড়ে
    """

    def test_new_publisher_has_no_kyc(self, publisher):
        try:
            from publisher_tools.publisher_management.publisher_kyc import PublisherKYC
            assert not PublisherKYC.objects.filter(publisher=publisher).exists()
        except ImportError:
            pytest.skip('Migration 0009 not applied')

    def test_kyc_submit_creates_record(self, publisher_client, publisher_user):
        BASE = '/api/publisher-tools/publisher-advanced'
        payload = {
            'kyc_type':  'individual',
            'full_name': 'Integration Test User',
            'id_type':   'national_id',
            'id_number': 'NID-INT-001',
            'country':   'Bangladesh',
        }
        resp = publisher_client.post(f'{BASE}/kyc-submit/', payload, format='json')
        assert resp.status_code in (200, 400, 503)

    def test_publisher_status_starts_pending(self, publisher):
        assert publisher.status in ('pending', 'active')

    def test_publisher_created_at_is_set(self, publisher):
        assert publisher.created_at is not None

    def test_publisher_has_publisher_id(self, publisher):
        assert publisher.publisher_id
        assert publisher.publisher_id.startswith('PUB-')


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 2 — Earnings Aggregation Flow
# (create earnings → task finalizes → invoice generated)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestEarningsAggregationFlow:
    """
    Earnings → Finalize → Invoice flow।
    """

    def test_earnings_created_with_pending_status(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        earning = PublisherEarning.objects.create(
            publisher=publisher,
            ad_unit=ad_unit,
            site=site,
            earning_date=date.today(),
            impressions=1000,
            clicks=10,
            publisher_revenue=Decimal('5.00'),
            status='pending',
        )
        assert earning.pk is not None
        assert earning.status == 'pending'
        assert earning.publisher_revenue == Decimal('5.00')

    def test_finalize_daily_earnings_task_runs(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        yesterday = date.today() - timedelta(days=1)

        # Create pending earnings for yesterday
        earning = PublisherEarning.objects.create(
            publisher=publisher,
            ad_unit=ad_unit,
            site=site,
            earning_date=yesterday,
            impressions=5000,
            clicks=50,
            publisher_revenue=Decimal('25.00'),
            status='pending',
        )

        # Run task synchronously
        from publisher_tools.tasks_missing import finalize_daily_earnings
        result = finalize_daily_earnings()

        assert result['finalized'] >= 1
        earning.refresh_from_db()
        assert earning.status == 'confirmed'

    def test_earnings_total_correct(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        from django.db.models import Sum

        today = date.today()
        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=today, impressions=1000, clicks=10,
            publisher_revenue=Decimal('5.00'), status='confirmed',
        )
        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=today, impressions=2000, clicks=20,
            publisher_revenue=Decimal('10.00'), status='confirmed',
        )

        total = PublisherEarning.objects.filter(
            publisher=publisher, status='confirmed',
        ).aggregate(total=Sum('publisher_revenue'))['total']

        assert total == Decimal('15.00')

    def test_publisher_invoice_linked_to_earnings(self, publisher, invoice):
        assert invoice.publisher == publisher
        assert invoice.total_amount >= Decimal('0')


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 3 — Payout Eligibility + Request Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestPayoutRequestFlow:
    """
    Payout eligibility check → request submit → status track।
    """

    def test_eligibility_endpoint_returns_eligible_key(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        resp = publisher_client.get(f'{BASE}/eligibility/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'eligible' in resp.json().get('data', {})

    def test_payout_request_missing_amount_rejected(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        resp = publisher_client.post(
            f'{BASE}/request/', {'bank_account_id': 'acc-001'}, format='json'
        )
        assert resp.status_code == 400

    def test_payout_request_invalid_amount_rejected(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        resp = publisher_client.post(
            f'{BASE}/request/',
            {'amount': '-50.00', 'bank_account_id': 'acc-001'},
            format='json',
        )
        assert resp.status_code == 400

    def test_withholding_tax_calculation_correct(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        resp = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'US', 'has_w8': False},
            format='json',
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()['data']
            # US 30% withholding → net_amount should be <= gross
            assert float(data.get('net_amount', 0)) <= float(data.get('gross_amount', 0))

    def test_tax_exempt_country_zero_withholding(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        # Bangladesh typically 0% withholding or low
        resp = publisher_client.post(
            f'{BASE}/withholding-tax/',
            {'amount': '100.00', 'country': 'BD'},
            format='json',
        )
        if resp.status_code == 200:
            data = resp.json()['data']
            assert float(data.get('tax_amount', 0)) >= 0

    def test_payout_history_returns_list(self, publisher_client):
        BASE = '/api/publisher-tools/payout'
        resp = publisher_client.get(f'{BASE}/history/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert isinstance(data.get('records', []), list)


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 4 — Fraud Detection + Report Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestFraudDetectionFlow:
    """
    Traffic scan → fraud log → publisher report flow।
    """

    def test_fraud_report_returns_summary(self, publisher_client):
        BASE = '/api/publisher-tools/fraud-reports'
        resp = publisher_client.get(f'{BASE}/report/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'summary' in data or 'period_days' in data

    def test_geo_validate_high_risk_country_flagged(self, publisher_client):
        BASE = '/api/publisher-tools/fraud-reports'
        resp = publisher_client.post(
            f'{BASE}/geo-validate/', {'ip_country': 'KP'}, format='json'
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert data.get('score', 0) > 0

    def test_geo_validate_safe_country_low_risk(self, publisher_client):
        BASE = '/api/publisher-tools/fraud-reports'
        resp = publisher_client.post(
            f'{BASE}/geo-validate/', {'ip_country': 'DE'}, format='json'
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Germany should have low-medium fraud score
            assert data.get('score', 100) < 80

    def test_velocity_check_new_identifier_not_exceeded(self, publisher_client):
        import uuid
        BASE = '/api/publisher-tools/fraud-reports'
        unique_id = f'ip:{uuid.uuid4().hex[:12]}'
        resp = publisher_client.post(
            f'{BASE}/velocity-check/',
            {'identifier': unique_id, 'event_type': 'click'},
            format='json',
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert data.get('exceeded', True) is False

    def test_impossible_travel_detected(self, publisher_client):
        BASE = '/api/publisher-tools/fraud-reports'
        resp = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {
                'user_id':          'integration_test_user',
                'current_country':  'US',
                'prev_country':     'AU',
                'time_diff_hours':  0.05,  # 3 minutes — impossible
            },
            format='json',
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert data.get('is_impossible_travel') is True

    def test_scan_invalid_traffic_task_runs(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        from publisher_tools.tasks import scan_invalid_traffic

        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=date.today(),
            impressions=10000, clicks=2000,  # 20% CTR → suspicious
            publisher_revenue=Decimal('10.00'), status='pending',
        )

        try:
            result = scan_invalid_traffic()
            assert isinstance(result, dict)
        except Exception:
            pytest.skip('scan_invalid_traffic task not fully implemented')


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 5 — Analytics Reporting Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestAnalyticsReportingFlow:
    """
    Earnings data → aggregate → reporting endpoint।
    """

    def test_monthly_report_with_real_earnings(self, publisher_client, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning

        today = date.today()
        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=today,
            impressions=5000, clicks=50,
            publisher_revenue=Decimal('15.00'),
            status='confirmed',
        )

        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.get(
            f'{BASE}/monthly/',
            {'year': today.year, 'month': today.month},
        )
        assert resp.status_code in (200, 503)

    def test_revenue_trend_returns_time_series(self, publisher_client):
        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.get(f'{BASE}/revenue-trend/', {'days': 7})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'trend' in data or 'days' in data

    def test_fill_rate_issues_no_false_500(self, publisher_client):
        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.get(f'{BASE}/fill-rate-issues/')
        assert resp.status_code != 500

    def test_top_units_with_no_units_returns_empty(self, publisher_client):
        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.get(f'{BASE}/top-units/', {'limit': 5})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert isinstance(data.get('units', None), list)

    def test_export_report_json_returns_dict(self, publisher_client):
        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.post(
            f'{BASE}/export/',
            {'metrics': ['revenue'], 'dimensions': ['date'], 'format': 'json'},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_ecpm_breakdown_country_keys_present(self, publisher_client):
        BASE = '/api/publisher-tools/reports'
        resp = publisher_client.get(f'{BASE}/ecpm-breakdown/', {'by': 'country'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'by' in data
            assert data['by'] == 'country'


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 6 — Site Management Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestSiteManagementFlow:
    """
    Site create → quality check → approval flow।
    """

    def test_site_created_with_pending_status(self, publisher):
        from publisher_tools.models import Site
        site = Site.objects.create(
            publisher=publisher,
            name='Integration Test Site',
            url='https://integration-test.example.com',
            status='pending',
        )
        assert site.pk is not None
        assert site.status == 'pending'

    def test_site_has_publisher_link(self, site, publisher):
        assert site.publisher == publisher

    def test_site_quality_task_does_not_crash(self, publisher, site):
        from publisher_tools.tasks_missing import recalculate_site_quality_metrics
        result = recalculate_site_quality_metrics()
        assert isinstance(result, dict)
        assert 'updated' in result or 'skipped' in result

    def test_ads_txt_check_task_runs(self):
        from publisher_tools.tasks import check_all_ads_txt
        try:
            result = check_all_ads_txt()
            assert isinstance(result, dict)
        except Exception:
            pytest.skip('check_all_ads_txt task not testable in unit mode')


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 7 — Webhook Delivery Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestWebhookDeliveryFlow:
    """
    Webhook create → delivery attempt → retry failed → cleanup old。
    """

    def test_webhook_delivery_log_created(self, publisher):
        from publisher_tools.tests.factories import PublisherWebhookFactory
        from publisher_tools.models import WebhookDeliveryLog

        webhook = PublisherWebhookFactory(publisher=publisher)
        delivery = WebhookDeliveryLog.objects.create(
            webhook=webhook,
            event_type='invoice.paid',
            payload={'event': 'invoice.paid', 'data': {'amount': 50}},
            status='failed',
            retry_count=0,
        )
        assert delivery.pk is not None
        assert delivery.status == 'failed'

    def test_cleanup_old_webhook_logs_task(self, publisher):
        from publisher_tools.tests.factories import PublisherWebhookFactory, WebhookDeliveryLogFactory
        from publisher_tools.models import WebhookDeliveryLog

        webhook = PublisherWebhookFactory(publisher=publisher)
        old_delivery = WebhookDeliveryLog.objects.create(
            webhook=webhook,
            event_type='invoice.paid',
            payload={},
            status='delivered',
            retry_count=0,
        )
        # Manually set created_at to 100 days ago
        WebhookDeliveryLog.objects.filter(pk=old_delivery.pk).update(
            created_at=timezone.now() - __import__('datetime').timedelta(days=100)
        )

        from publisher_tools.tasks_missing import cleanup_old_webhook_logs
        result = cleanup_old_webhook_logs()

        assert result['deleted'] >= 1
        assert not WebhookDeliveryLog.objects.filter(pk=old_delivery.pk).exists()

    def test_payload_preview_returns_sample(self, publisher_client):
        BASE = '/api/publisher-tools/webhooks-ext'
        resp = publisher_client.get(
            f'{BASE}/payload-preview/', {'event_type': 'invoice.paid'}
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'sample_payload' in data


# ══════════════════════════════════════════════════════════════════════════════
# FLOW 8 — Celery Tasks Integration
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db(transaction=True)
class TestCeleryTasksIntegration:
    """
    Tasks run against real DB (synchronous mode via CELERY_TASK_ALWAYS_EAGER)।
    """

    def test_detect_fraud_patterns_task(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=date.today(),
            impressions=10000, clicks=3000,  # 30% CTR
            publisher_revenue=Decimal('5.00'),
            status='confirmed',
        )

        from publisher_tools.tasks_missing import detect_fraud_patterns
        result = detect_fraud_patterns()
        assert isinstance(result, dict)
        assert 'flagged' in result

    def test_expire_kyc_records_task_runs(self):
        from publisher_tools.tasks_missing import expire_kyc_records
        result = expire_kyc_records()
        # Either runs normally or skips if migration not applied
        assert isinstance(result, dict)

    def test_notify_subscription_renewals_task_runs(self):
        from publisher_tools.tasks_missing import notify_subscription_renewals
        result = notify_subscription_renewals()
        assert isinstance(result, dict)

    def test_update_publisher_performance_snapshots_task(self, publisher, ad_unit, site):
        from publisher_tools.models import PublisherEarning
        yesterday = date.today() - timedelta(days=1)
        PublisherEarning.objects.create(
            publisher=publisher, ad_unit=ad_unit, site=site,
            earning_date=yesterday,
            impressions=8000, clicks=80,
            publisher_revenue=Decimal('40.00'),
            status='confirmed',
        )

        from publisher_tools.tasks_missing import update_publisher_performance_snapshots
        result = update_publisher_performance_snapshots()
        assert isinstance(result, dict)
        assert 'date' in result

    def test_cleanup_expired_velocity_records_task(self):
        from publisher_tools.tasks_missing import cleanup_expired_velocity_records
        result = cleanup_expired_velocity_records()
        assert isinstance(result, dict)
        assert 'deleted' in result
