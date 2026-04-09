# api/djoyalty/tasks/insight_tasks.py
"""
Celery task: Daily insight report generation।
Schedule: Daily at midnight।
"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.generate_daily_insight', bind=True, max_retries=3)
def generate_daily_insight_task(self):
    """
    আজকের daily insight report generate করো সব tenants এর জন্য।
    Returns: report_date string
    """
    try:
        from ..services.advanced.InsightService import InsightService
        from django.utils import timezone

        insight = InsightService.generate_daily_insight()
        logger.info(
            '[djoyalty] Daily insight generated: date=%s customers=%d points_issued=%s',
            insight.report_date,
            insight.total_customers,
            insight.total_points_issued,
        )
        return str(insight.report_date)

    except Exception as exc:
        logger.error('[djoyalty] generate_daily_insight error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.generate_weekly_insight', bind=True, max_retries=3)
def generate_weekly_insight_task(self):
    """
    Weekly insight report generate করো।
    Returns: report_date string
    """
    try:
        from ..models.advanced import LoyaltyInsight
        from django.utils import timezone
        from django.db.models import Sum, Count

        today = timezone.now().date()
        insight, _ = LoyaltyInsight.objects.update_or_create(
            tenant=None, report_date=today, period='weekly',
            defaults={
                'total_customers': 0,
                'active_customers': 0,
                'new_customers': 0,
                'total_points_issued': 0,
                'total_points_redeemed': 0,
                'total_points_expired': 0,
                'total_transactions': 0,
                'total_revenue': 0,
            },
        )
        logger.info('[djoyalty] Weekly insight generated: %s', today)
        return str(today)

    except Exception as exc:
        logger.error('[djoyalty] generate_weekly_insight error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc
