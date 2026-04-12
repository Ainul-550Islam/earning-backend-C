# api/publisher_tools/tasks.py
"""
Publisher Tools — Celery Async Tasks।
Background jobs যেগুলো sync করা যায় না।
"""
from decimal import Decimal
from datetime import date, timedelta
import logging

from django.utils import timezone
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)

# Celery task decorator — production-এ @shared_task ব্যবহার করো
try:
    from celery import shared_task
except ImportError:
    # Celery না থাকলে fallback decorator
    def shared_task(func):
        func.delay = func
        func.apply_async = lambda *a, **k: func(*a, **k)
        return func


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.send_publisher_welcome_notification')
def send_publisher_welcome_notification(publisher_id: str):
    """
    Publisher-কে welcome notification পাঠায়।
    Registration-এর পরপরই background-এ চলে।
    """
    try:
        from .models import Publisher
        publisher = Publisher.objects.get(id=publisher_id)
        logger.info(f'Sending welcome notification to publisher: {publisher.publisher_id}')
        # production: email / push notification send করো
    except Exception as e:
        logger.error(f'Failed to send welcome notification: {e}')


@shared_task(name='publisher_tools.send_publisher_approved_notification')
def send_publisher_approved_notification(publisher_id: str):
    """Publisher approval notification পাঠায়"""
    try:
        from .models import Publisher
        publisher = Publisher.objects.get(id=publisher_id)
        logger.info(f'Sending approval notification to: {publisher.publisher_id}')
        # production: email পাঠাও
    except Exception as e:
        logger.error(f'Failed to send approval notification: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# SITE TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.check_all_ads_txt')
def check_all_ads_txt():
    """
    সব active site-এর ads.txt চেক করে।
    Daily cron job হিসেবে run হয়।
    """
    from .models import Site
    from .services import SiteService

    sites = Site.objects.filter(status='active').only('id', 'domain', 'url')
    success_count = 0
    fail_count = 0

    for site in sites:
        try:
            result = SiteService.refresh_ads_txt(site)
            if result:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f'ads.txt check failed for {site.domain}: {e}')
            fail_count += 1

    logger.info(f'ads.txt check complete: {success_count} OK, {fail_count} failed')
    return {'success': success_count, 'failed': fail_count}


@shared_task(name='publisher_tools.update_site_quality_metrics')
def update_site_quality_metrics():
    """
    সব active site-এর quality metrics update করে।
    Daily cron job।
    """
    from .models import Site, SiteQualityMetric
    from .services import QualityMetricService

    sites = Site.objects.filter(status='active').only('id', 'domain', 'quality_score')
    updated_count = 0

    for site in sites:
        try:
            # Simplified metrics — production-এ real viewability data আসবে
            metrics_data = {
                'viewability_rate': Decimal('65.00'),
                'content_score': site.quality_score,
                'invalid_traffic_percentage': Decimal('3.50'),
                'page_speed_score': 70,
                'ads_txt_present': site.ads_txt_verified,
                'ads_txt_valid': site.ads_txt_verified,
            }
            QualityMetricService.update_daily_metrics(site, metrics_data)
            updated_count += 1
        except Exception as e:
            logger.error(f'Quality metric update failed for {site.domain}: {e}')

    logger.info(f'Quality metrics updated for {updated_count} sites')
    return {'updated': updated_count}


# ──────────────────────────────────────────────────────────────────────────────
# EARNING TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.aggregate_hourly_earnings')
def aggregate_hourly_earnings():
    """
    প্রতি ঘণ্টায় earning data aggregate করে daily record-এ merge করে।
    """
    from .models import PublisherEarning
    from django.db.models import Sum

    now = timezone.now()
    current_hour = now.hour
    today = now.date()

    hourly_records = PublisherEarning.objects.filter(
        date=today,
        granularity='hourly',
        hour=current_hour - 1,  # Last hour
        status='estimated',
    ).values('publisher', 'ad_unit', 'earning_type', 'country').annotate(
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_gross=Sum('gross_revenue'),
        total_publisher=Sum('publisher_revenue'),
    )

    updated = 0
    for record in hourly_records:
        PublisherEarning.objects.filter(
            publisher_id=record['publisher'],
            date=today,
            granularity='daily',
            earning_type=record['earning_type'],
            country=record['country'],
        ).update(
            impressions=Sum('impressions') + record['total_impressions'],
            gross_revenue=Sum('gross_revenue') + record['total_gross'],
            publisher_revenue=Sum('publisher_revenue') + record['total_publisher'],
        )
        updated += 1

    logger.info(f'Hourly earnings aggregated: {updated} records')
    return {'aggregated': updated}


@shared_task(name='publisher_tools.finalize_previous_month_earnings')
def finalize_previous_month_earnings():
    """
    গত মাসের সব earnings confirm → finalize করে।
    মাসের প্রথম দিনে চলে।
    """
    from .models import Publisher
    from .services import EarningService

    now = timezone.now()
    # Previous month
    first_of_month = now.date().replace(day=1)
    prev_month_end = first_of_month - timedelta(days=1)
    prev_month_year  = prev_month_end.year
    prev_month_month = prev_month_end.month

    publishers = Publisher.objects.filter(status='active')
    count = 0
    for publisher in publishers:
        try:
            EarningService.finalize_monthly_earnings(publisher, prev_month_year, prev_month_month)
            count += 1
        except Exception as e:
            logger.error(f'Finalize earnings failed for {publisher.publisher_id}: {e}')

    logger.info(f'Previous month earnings finalized for {count} publishers')
    return {'finalized': count}


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.generate_monthly_invoices')
def generate_monthly_invoices():
    """
    সব eligible publisher-এর monthly invoice generate করে।
    মাসের ২য় দিনে চলে (earnings finalize-এর পর)।
    """
    from .models import Publisher
    from .services import InvoiceService

    now = timezone.now()
    first_of_month = now.date().replace(day=1)
    prev_month_end = first_of_month - timedelta(days=1)
    year  = prev_month_end.year
    month = prev_month_end.month

    publishers = Publisher.objects.filter(
        status='active',
        is_kyc_verified=True,
    )

    generated = 0
    errors = 0

    for publisher in publishers:
        try:
            # Skip if invoice already exists
            from .models import PublisherInvoice
            exists = PublisherInvoice.objects.filter(
                publisher=publisher,
                period_start__year=year,
                period_start__month=month,
            ).exists()

            if not exists:
                invoice = InvoiceService.generate_monthly_invoice(publisher, year, month)
                # Auto-issue if above threshold
                eligibility = InvoiceService.check_payout_eligibility(publisher)
                if eligibility.get('eligible'):
                    InvoiceService.issue_invoice(invoice)
                generated += 1
        except Exception as e:
            logger.error(f'Invoice generation failed for {publisher.publisher_id}: {e}')
            errors += 1

    logger.info(f'Monthly invoices: {generated} generated, {errors} errors')
    return {'generated': generated, 'errors': errors}


@shared_task(name='publisher_tools.send_overdue_invoice_reminders')
def send_overdue_invoice_reminders():
    """Overdue invoice-এর জন্য publisher-কে reminder পাঠায়"""
    from .models import PublisherInvoice

    today = timezone.now().date()
    overdue = PublisherInvoice.objects.filter(
        status='issued',
        due_date__lt=today,
    ).select_related('publisher')

    count = 0
    for invoice in overdue:
        try:
            logger.info(f'Sending overdue reminder for invoice {invoice.invoice_number}')
            # production: email পাঠাও
            count += 1
        except Exception as e:
            logger.error(f'Reminder failed for {invoice.invoice_number}: {e}')

    return {'reminders_sent': count}


# ──────────────────────────────────────────────────────────────────────────────
# FRAUD DETECTION TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.scan_invalid_traffic')
def scan_invalid_traffic():
    """
    সব active publisher-এর IVT rate scan করে।
    High IVT হলে auto-action নেয়।
    Daily cron job।
    """
    from .models import Publisher
    from .services import FraudDetectionService
    from .constants import MAX_IVT_PERCENTAGE, CRITICAL_IVT_THRESHOLD

    publishers = Publisher.objects.filter(status='active')
    warnings = 0
    suspensions = 0

    for publisher in publishers:
        try:
            ivt_rate = FraudDetectionService.calculate_publisher_ivt_rate(publisher, days=7)

            if ivt_rate >= CRITICAL_IVT_THRESHOLD:
                # Auto-suspend
                from .services import PublisherService
                PublisherService.suspend_publisher(
                    publisher,
                    f'IVT rate {ivt_rate:.1f}% exceeds critical threshold {CRITICAL_IVT_THRESHOLD}%'
                )
                suspensions += 1
                logger.warning(f'Publisher {publisher.publisher_id} suspended: IVT {ivt_rate:.1f}%')

            elif ivt_rate >= MAX_IVT_PERCENTAGE:
                # Warning
                publisher.internal_notes += f'\n[{timezone.now().date()}] IVT Warning: {ivt_rate:.1f}%'
                publisher.save(update_fields=['internal_notes', 'updated_at'])
                warnings += 1
                logger.warning(f'Publisher {publisher.publisher_id} IVT warning: {ivt_rate:.1f}%')

        except Exception as e:
            logger.error(f'IVT scan failed for {publisher.publisher_id}: {e}')

    logger.info(f'IVT scan: {warnings} warnings, {suspensions} suspensions')
    return {'warnings': warnings, 'suspensions': suspensions}


@shared_task(name='publisher_tools.cleanup_old_traffic_logs')
def cleanup_old_traffic_logs():
    """
    90 দিনের পুরনো IVT logs cleanup করে।
    Weekly cron job।
    """
    from .models import TrafficSafetyLog

    cutoff = timezone.now() - timedelta(days=90)
    deleted_count, _ = TrafficSafetyLog.objects.filter(
        detected_at__lt=cutoff,
        is_false_positive=True,
        action_taken__in=['no_action', 'flagged'],
    ).delete()

    logger.info(f'Cleaned up {deleted_count} old traffic safety logs')
    return {'deleted': deleted_count}


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION OPTIMIZATION TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.auto_optimize_waterfalls')
def auto_optimize_waterfalls():
    """
    auto_optimize=True এমন সব MediationGroup-এর waterfall optimize করে।
    Every 6 hours চলে।
    """
    from .models import MediationGroup
    from .services import MediationService
    from .constants import WATERFALL_OPTIMIZE_INTERVAL

    cutoff = timezone.now() - timedelta(hours=WATERFALL_OPTIMIZE_INTERVAL)
    groups = MediationGroup.objects.filter(
        auto_optimize=True,
        is_active=True,
    ).filter(
        Q(last_optimized_at__isnull=True) | Q(last_optimized_at__lt=cutoff)
    )

    optimized = 0
    for group in groups:
        try:
            MediationService.optimize_waterfall(group)
            optimized += 1
        except Exception as e:
            logger.error(f'Waterfall optimization failed for group {group.id}: {e}')

    logger.info(f'Auto-optimized {optimized} waterfall groups')
    return {'optimized': optimized}


# ──────────────────────────────────────────────────────────────────────────────
# REPORTING TASKS
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(name='publisher_tools.generate_daily_earning_report')
def generate_daily_earning_report(publisher_id: str = None):
    """
    Daily earning report generate করে।
    নির্দিষ্ট publisher_id দিলে শুধু তারটা, না দিলে সবার।
    """
    from .models import Publisher
    from .services import EarningService

    yesterday = timezone.now().date() - timedelta(days=1)

    if publisher_id:
        publishers = Publisher.objects.filter(publisher_id=publisher_id)
    else:
        publishers = Publisher.objects.filter(status='active')

    reports_generated = 0
    for publisher in publishers:
        try:
            report = EarningService.get_earnings_report(publisher, yesterday, yesterday)
            # production: email পাঠাও বা S3-এ save করো
            logger.info(f'Daily report generated for {publisher.publisher_id}: ${report["summary"].get("total_publisher") or 0:.4f}')
            reports_generated += 1
        except Exception as e:
            logger.error(f'Daily report failed for {publisher.publisher_id}: {e}')

    return {'reports_generated': reports_generated, 'date': str(yesterday)}


@shared_task(name='publisher_tools.update_publisher_revenue_totals')
def update_publisher_revenue_totals():
    """
    সব publisher-এর revenue totals recalculate করে।
    Data consistency check-এর জন্য daily run করা উচিত।
    """
    from .models import Publisher, PublisherEarning
    from django.db.models import Sum

    publishers = Publisher.objects.filter(status='active')
    updated = 0

    for publisher in publishers:
        try:
            agg = PublisherEarning.objects.filter(
                publisher=publisher,
                status__in=['confirmed', 'finalized'],
            ).aggregate(total=Sum('publisher_revenue'))

            new_total = agg.get('total') or Decimal('0')
            if publisher.total_revenue != new_total:
                publisher.total_revenue = new_total
                publisher.save(update_fields=['total_revenue', 'updated_at'])
                updated += 1
        except Exception as e:
            logger.error(f'Revenue total update failed for {publisher.publisher_id}: {e}')

    logger.info(f'Revenue totals updated for {updated} publishers')
    return {'updated': updated}
