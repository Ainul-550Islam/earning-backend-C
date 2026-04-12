import logging
import datetime
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger('smartlink.tasks.reports')
User = get_user_model()


@shared_task(name='smartlink.send_daily_publisher_reports', queue='email')
def send_daily_publisher_reports():
    """
    Daily at 08:00 UTC: Send performance summary email to each active publisher.
    """
    from ..models import SmartLink
    from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService

    svc = SmartLinkAnalyticsService()
    yesterday = timezone.now().date() - datetime.timedelta(days=1)

    publishers = User.objects.filter(
        is_active=True,
        smartlinks__isnull=False,
    ).distinct()

    sent = 0
    for publisher in publishers:
        try:
            totals = svc.get_publisher_totals(publisher, days=1)
            if totals['clicks'] == 0:
                continue  # Skip if no traffic yesterday

            _send_publisher_report_email(publisher, totals, yesterday)
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send report to publisher#{publisher.pk}: {e}")

    logger.info(f"Daily reports sent: {sent} publishers")
    return {'sent': sent}


@shared_task(name='smartlink.send_weekly_publisher_reports', queue='email')
def send_weekly_publisher_reports():
    """Weekly on Monday: Send 7-day performance summary."""
    from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService

    svc = SmartLinkAnalyticsService()
    publishers = User.objects.filter(is_active=True, smartlinks__isnull=False).distinct()

    sent = 0
    for publisher in publishers:
        try:
            totals = svc.get_publisher_totals(publisher, days=7)
            if totals['clicks'] == 0:
                continue
            _send_publisher_report_email(publisher, totals, period='weekly')
            sent += 1
        except Exception as e:
            logger.error(f"Weekly report failed for publisher#{publisher.pk}: {e}")

    return {'sent': sent}


@shared_task(name='smartlink.alert_cap_nearly_reached', queue='email')
def alert_cap_nearly_reached():
    """
    Every hour: Alert publishers when an offer cap is at 80%+ usage.
    """
    from ..models import OfferPoolEntry
    from ..services.rotation.CapTrackerService import CapTrackerService

    svc = CapTrackerService()
    entries = OfferPoolEntry.objects.filter(is_active=True, cap_per_day__isnull=False)

    alerted = 0
    for entry in entries:
        try:
            usage = svc.get_usage(entry)
            daily_pct = (usage['daily_used'] / usage['daily_cap'] * 100) if usage['daily_cap'] else 0
            if 80 <= daily_pct < 100 and not usage['is_daily_capped']:
                publisher = entry.pool.smartlink.publisher
                logger.info(
                    f"Cap alert: offer#{entry.offer_id} sl={entry.pool.smartlink.slug} "
                    f"at {daily_pct:.0f}% of daily cap"
                )
                alerted += 1
        except Exception:
            pass

    return {'alerted': alerted}


def _send_publisher_report_email(publisher, totals: dict, date=None, period: str = 'daily'):
    """Helper: compose and send report email via Django's email framework."""
    from django.core.mail import send_mail
    from django.conf import settings

    subject = f"[SmartLink] Your {'Daily' if period == 'daily' else 'Weekly'} Performance Report"
    clicks = totals.get('clicks', 0)
    revenue = totals.get('revenue', 0)
    epc = totals.get('epc', 0)
    conversions = totals.get('conversions', 0)

    body = (
        f"Hi {publisher.username},\n\n"
        f"Your SmartLink performance summary:\n\n"
        f"  Total Clicks:       {clicks:,}\n"
        f"  Unique Clicks:      {totals.get('unique_clicks', 0):,}\n"
        f"  Conversions:        {conversions:,}\n"
        f"  Revenue:            ${revenue:,.4f}\n"
        f"  EPC:                ${epc:.4f}\n\n"
        f"Login to your dashboard for full details.\n\n"
        f"— SmartLink Platform"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@smartlink.io'),
            recipient_list=[publisher.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f"Email send failed for {publisher.email}: {e}")
