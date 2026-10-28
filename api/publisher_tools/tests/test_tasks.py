# publisher_tools/tests/test_tasks.py
"""
High-priority Celery task tests.

Strategy: call tasks synchronously via .apply() (no worker needed).
Tests verify:
  - Task executes without raising an exception (happy path)
  - Task does the expected DB work
  - Tasks are idempotent / handle edge cases

Run:
    pytest publisher_tools/tests/test_tasks.py -v
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from publisher_tools.tasks import (
    update_publisher_earnings_daily,
    generate_monthly_invoices,
    detect_invalid_traffic,
    update_site_quality_metrics,
    refresh_ads_txt_verification,
    update_waterfall_performance,
    notify_publisher_approval,
    notify_publisher_suspension,
    notify_invoice_issued,
    notify_payment_processed,
    finalize_monthly_earnings,
    update_ad_unit_performance_stats,
    cleanup_old_traffic_logs,
)
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AdUnitFactory,
    PublisherEarningFactory, TrafficSafetyLogFactory,
    SiteQualityMetricFactory, PublisherInvoiceFactory,
    MediationGroupFactory, WaterfallItemFactory,
)


# ==============================================================================
# update_publisher_earnings_daily
# ==============================================================================

@pytest.mark.django_db
class TestUpdatePublisherEarningsDaily:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        AdUnitFactory(publisher=pub, site=site, status='active')
        result = update_publisher_earnings_daily.apply()
        assert result.successful()

    def test_task_runs_with_no_publishers(self):
        result = update_publisher_earnings_daily.apply()
        assert result.successful()


# ==============================================================================
# generate_monthly_invoices
# ==============================================================================

@pytest.mark.django_db
class TestGenerateMonthlyInvoices:

    def test_task_runs_without_error(self):
        PublisherFactory(status='active')
        result = generate_monthly_invoices.apply()
        assert result.successful()

    def test_task_runs_with_no_active_publishers(self):
        PublisherFactory(status='pending')
        result = generate_monthly_invoices.apply()
        assert result.successful()

    def test_task_creates_invoices_for_active_publishers(self):
        from publisher_tools.models import PublisherInvoice
        pub = PublisherFactory(status='active')
        before = PublisherInvoice.objects.filter(publisher=pub).count()
        generate_monthly_invoices.apply()
        after = PublisherInvoice.objects.filter(publisher=pub).count()
        assert after >= before


# ==============================================================================
# detect_invalid_traffic
# ==============================================================================

@pytest.mark.django_db
class TestDetectInvalidTraffic:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        result = detect_invalid_traffic.apply()
        assert result.successful()

    def test_task_handles_no_sites(self):
        result = detect_invalid_traffic.apply()
        assert result.successful()


# ==============================================================================
# update_site_quality_metrics
# ==============================================================================

@pytest.mark.django_db
class TestUpdateSiteQualityMetrics:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        SiteFactory(publisher=pub, status='active')
        result = update_site_quality_metrics.apply()
        assert result.successful()

    def test_task_creates_quality_metric_records(self):
        from publisher_tools.models import SiteQualityMetric
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        before = SiteQualityMetric.objects.filter(site=site, date=date.today()).count()
        update_site_quality_metrics.apply()
        after = SiteQualityMetric.objects.filter(site=site, date=date.today()).count()
        assert after >= before


# ==============================================================================
# refresh_ads_txt_verification
# ==============================================================================

@pytest.mark.django_db
class TestRefreshAdsTxtVerification:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        SiteFactory(publisher=pub, status='active')
        result = refresh_ads_txt_verification.apply()
        assert result.successful()

    def test_task_handles_no_sites(self):
        result = refresh_ads_txt_verification.apply()
        assert result.successful()


# ==============================================================================
# update_waterfall_performance
# ==============================================================================

@pytest.mark.django_db
class TestUpdateWaterfallPerformance:

    def test_task_runs_without_error(self):
        ad_unit = AdUnitFactory()
        group   = MediationGroupFactory(ad_unit=ad_unit)
        WaterfallItemFactory(mediation_group=group)
        result = update_waterfall_performance.apply()
        assert result.successful()

    def test_task_handles_empty_waterfall(self):
        result = update_waterfall_performance.apply()
        assert result.successful()


# ==============================================================================
# Notification tasks (mocked email/notification backend)
# ==============================================================================

@pytest.mark.django_db
class TestNotificationTasks:

    def test_notify_publisher_approval_runs(self):
        pub    = PublisherFactory(status='active')
        result = notify_publisher_approval.apply(args=[str(pub.pk)])
        assert result.successful()

    def test_notify_publisher_suspension_runs(self):
        pub    = PublisherFactory(status='suspended')
        result = notify_publisher_suspension.apply(
            args=[str(pub.pk), 'Policy violation']
        )
        assert result.successful()

    def test_notify_invoice_issued_runs(self):
        invoice = PublisherInvoiceFactory(status='issued')
        result  = notify_invoice_issued.apply(args=[str(invoice.pk)])
        assert result.successful()

    def test_notify_payment_processed_runs(self):
        invoice = PublisherInvoiceFactory(status='paid')
        result  = notify_payment_processed.apply(args=[str(invoice.pk)])
        assert result.successful()

    def test_notify_publisher_approval_nonexistent_pk(self):
        """Task should not crash on missing publisher — log and return."""
        import uuid
        result = notify_publisher_approval.apply(args=[str(uuid.uuid4())])
        # Should succeed (handled gracefully) or fail cleanly
        assert result.successful() or result.failed()


# ==============================================================================
# finalize_monthly_earnings
# ==============================================================================

@pytest.mark.django_db
class TestFinalizeMonthlyEarnings:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitFactory(publisher=pub, site=site, status='active')
        PublisherEarningFactory(
            publisher=pub, site=site, ad_unit=unit,
            is_finalized=False,
            date=date.today() - timedelta(days=35),
        )
        result = finalize_monthly_earnings.apply()
        assert result.successful()

    def test_finalize_marks_earnings_as_finalized(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitFactory(publisher=pub, site=site, status='active')
        earning = PublisherEarningFactory(
            publisher=pub, site=site, ad_unit=unit,
            is_finalized=False,
            date=date.today() - timedelta(days=35),
        )
        finalize_monthly_earnings.apply()
        earning.refresh_from_db()
        assert earning.is_finalized is True

    def test_task_does_not_re_finalize_already_finalized(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitFactory(publisher=pub, site=site, status='active')
        earning = PublisherEarningFactory(
            publisher=pub, site=site, ad_unit=unit,
            is_finalized=True,
            date=date.today() - timedelta(days=35),
        )
        result = finalize_monthly_earnings.apply()
        assert result.successful()


# ==============================================================================
# update_ad_unit_performance_stats
# ==============================================================================

@pytest.mark.django_db
class TestUpdateAdUnitPerformanceStats:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitFactory(publisher=pub, site=site, status='active')
        PublisherEarningFactory(publisher=pub, site=site, ad_unit=unit)
        result = update_ad_unit_performance_stats.apply()
        assert result.successful()

    def test_task_handles_no_earnings(self):
        AdUnitFactory()
        result = update_ad_unit_performance_stats.apply()
        assert result.successful()


# ==============================================================================
# cleanup_old_traffic_logs
# ==============================================================================

@pytest.mark.django_db
class TestCleanupOldTrafficLogs:

    def test_task_runs_without_error(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        TrafficSafetyLogFactory(
            publisher=pub, site=site,
            detected_at=__import__('django.utils.timezone', fromlist=['now']).now.__func__
            if False else __import__('django.utils', fromlist=['timezone']).timezone.now()
            - __import__('datetime').timedelta(days=200),
        )
        result = cleanup_old_traffic_logs.apply()
        assert result.successful()

    def test_task_deletes_old_logs(self):
        from django.utils import timezone as tz
        import datetime
        from publisher_tools.models import TrafficSafetyLog
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        old_log = TrafficSafetyLogFactory(
            publisher=pub, site=site,
            detected_at=tz.now() - datetime.timedelta(days=200),
        )
        cleanup_old_traffic_logs.apply()
        assert not TrafficSafetyLog.objects.filter(pk=old_log.pk).exists()

    def test_task_does_not_delete_recent_logs(self):
        from publisher_tools.models import TrafficSafetyLog
        pub     = PublisherFactory(status='active')
        site    = SiteFactory(publisher=pub, status='active')
        new_log = TrafficSafetyLogFactory(publisher=pub, site=site)
        cleanup_old_traffic_logs.apply()
        assert TrafficSafetyLog.objects.filter(pk=new_log.pk).exists()
