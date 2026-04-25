# earning_backend/api/notifications/tasks/insight_tasks.py
"""
Insight tasks — generate daily/weekly analytics, populate NotificationInsight
and DeliveryRate tables.

Schedule via Celery Beat:
    generate_daily_notification_insights  — daily at 01:00 UTC
    generate_weekly_notification_summary  — every Monday at 02:00 UTC
    refresh_delivery_rates                — daily at 01:30 UTC
"""
import logging
from datetime import date, timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_analytics',
    name='notifications.generate_daily_insights',
)
def generate_daily_notification_insights(date_str: str = None):
    """
    Generate NotificationInsight rows for the given date (default: yesterday).

    Args:
        date_str: ISO date string 'YYYY-MM-DD'. Defaults to yesterday.
    """
    from notifications.services.NotificationAnalytics import notification_analytics_service

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()

    result = notification_analytics_service.generate_daily_insights(target_date)
    logger.info(
        f'generate_daily_notification_insights {target_date}: '
        f'channels={result.get("channels_processed", 0)} '
        f'errors={result.get("errors", 0)}'
    )
    return result


@shared_task(
    queue='notifications_analytics',
    name='notifications.generate_weekly_summary',
)
def generate_weekly_notification_summary(week_end_str: str = None):
    """
    Generate a weekly analytics summary.

    Args:
        week_end_str: ISO date string for the week end (Sunday). Defaults to last Sunday.
    """
    from notifications.services.NotificationAnalytics import notification_analytics_service

    if week_end_str:
        week_end = date.fromisoformat(week_end_str)
    else:
        today = timezone.now().date()
        # Last Sunday
        week_end = today - timedelta(days=(today.weekday() + 1) % 7)

    result = notification_analytics_service.generate_weekly_summary(week_end)
    logger.info(f'generate_weekly_notification_summary week_end={week_end}: {result}')
    return result


@shared_task(
    queue='notifications_analytics',
    name='notifications.refresh_delivery_rates',
)
def refresh_delivery_rates(days_back: int = 7):
    """
    Recompute DeliveryRate records from NotificationInsight data for the
    last N days. Runs daily after generate_daily_notification_insights.
    """
    from notifications.models.analytics import NotificationInsight, DeliveryRate

    cutoff = (timezone.now() - timedelta(days=days_back)).date()
    insights = NotificationInsight.objects.filter(date__gte=cutoff)

    updated = 0
    errors = 0
    for insight in insights.iterator(chunk_size=100):
        try:
            DeliveryRate.upsert_from_insight(insight)
            updated += 1
        except Exception as exc:
            logger.warning(f'refresh_delivery_rates insight #{insight.pk}: {exc}')
            errors += 1

    logger.info(f'refresh_delivery_rates: updated={updated} errors={errors}')
    return {'updated': updated, 'errors': errors, 'days_back': days_back}


@shared_task(
    queue='notifications_analytics',
    name='notifications.backfill_insights',
)
def backfill_insights(days_back: int = 30):
    """
    Backfill NotificationInsight rows for the last N days.
    Useful after first deployment or after a gap in task execution.
    """
    from notifications.services.NotificationAnalytics import notification_analytics_service

    today = timezone.now().date()
    results = []
    errors = 0

    for i in range(1, days_back + 1):
        target_date = today - timedelta(days=i)
        try:
            result = notification_analytics_service.generate_daily_insights(target_date)
            results.append({'date': str(target_date), **result})
        except Exception as exc:
            logger.warning(f'backfill_insights {target_date}: {exc}')
            errors += 1

    logger.info(f'backfill_insights: processed={len(results)} errors={errors}')
    return {'processed': len(results), 'errors': errors, 'days_back': days_back}


@shared_task(
    queue='notifications_analytics',
    name='notifications.generate_legacy_daily_analytics',
)
def generate_legacy_daily_analytics(date_str: str = None):
    """
    Also generate the legacy NotificationAnalytics record (from models.py)
    for backward compatibility with existing dashboard queries.
    """
    from notifications.models import NotificationAnalytics

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()

    try:
        analytics = NotificationAnalytics.generate_daily_report(date=target_date)
        if analytics:
            logger.info(
                f'generate_legacy_daily_analytics {target_date}: '
                f'total={analytics.total_notifications}'
            )
            return {'success': True, 'date': str(target_date), 'id': analytics.pk}
        else:
            return {'success': True, 'date': str(target_date), 'message': 'No data for date'}
    except Exception as exc:
        logger.error(f'generate_legacy_daily_analytics {target_date}: {exc}')
        return {'success': False, 'date': str(target_date), 'error': str(exc)}


@shared_task(
    queue='notifications_analytics',
    name='notifications.run_all_daily_analytics',
)
def run_all_daily_analytics(date_str: str = None):
    """
    Master daily analytics task — chains all analytics generation tasks.
    Schedule this via Celery Beat at 01:00 UTC daily.
    """
    from celery import chain

    chain(
        generate_daily_notification_insights.s(date_str),
        generate_legacy_daily_analytics.s() if not date_str else generate_legacy_daily_analytics.s(date_str),
        refresh_delivery_rates.s(7),
    ).apply_async()

    logger.info(f'run_all_daily_analytics: chained tasks for date={date_str or "yesterday"}')
    return {'queued': True, 'date': date_str or 'yesterday'}
