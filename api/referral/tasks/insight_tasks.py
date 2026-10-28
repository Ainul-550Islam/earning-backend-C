from datetime import timedelta
# api/referral/tasks/insight_tasks.py
# Celery tasks: daily analytics insight calculation
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.calculate_daily_insights',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def calculate_daily_insights(self):
    """
    আজকের daily insight calculate করো।
    প্রতিদিন মধ্যরাতের পরে (12:05 AM) run হয়।

    Schedule example:
        'referral-daily-insights': {
            'task': 'referral.calculate_daily_insights',
            'schedule': crontab(hour=0, minute=5),
        }
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from django.utils import timezone

        # আজকের insight calculate করো
        today = timezone.now().date()
        insight = ReferralAnalyticsService.calculate_daily_insight(date=today)

        # গতকালের insight ও নিশ্চিত করো
        import datetime
        yesterday = today - datetime.timedelta(days=1)
        ReferralAnalyticsService.calculate_daily_insight(date=yesterday)

        logger.info(
            f"[Task] calculate_daily_insights: "
            f"date={today}, "
            f"new_referrals={insight.new_referrals}, "
            f"commission_paid={insight.commission_paid}"
        )

        return {
            'date': str(today),
            'new_referrals': insight.new_referrals,
            'commission_paid': float(insight.commission_paid),
            'active_referrers': insight.active_referrers,
        }

    except Exception as exc:
        logger.error(f"[Task] calculate_daily_insights failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.update_code_conversion_rates',
    bind=True,
    max_retries=2,
)
def update_code_conversion_rates(self):
    """
    সব active referral codes এর conversion rates update করো।
    প্রতিদিন।

    Schedule example:
        'referral-code-conversion-rates': {
            'task': 'referral.update_code_conversion_rates',
            'schedule': crontab(hour=1, minute=15),
        }
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )

        updated = ReferralAnalyticsService.update_code_conversion_rates()

        logger.info(
            f"[Task] update_code_conversion_rates: updated={updated}"
        )

        return {'updated': updated}

    except Exception as exc:
        logger.error(f"[Task] update_code_conversion_rates failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.backfill_missing_insights',
    bind=True,
    max_retries=1,
)
def backfill_missing_insights(self, days_back: int = 7):
    """
    Missing daily insights backfill করো।
    Manual trigger বা recovery এর জন্য।

    Usage: backfill_missing_insights.delay(days_back=30)
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from api.referral.models import ReferralInsight
        from django.utils import timezone
        import datetime

        today = timezone.now().date()
        backfilled = 0

        for i in range(1, days_back + 1):
            target_date = today - datetime.timedelta(days=i)

            # Already exists?
            if not ReferralInsight.objects.filter(date=target_date).exists():
                ReferralAnalyticsService.calculate_daily_insight(
                    date=target_date
                )
                backfilled += 1
                logger.info(
                    f"Backfilled insight for {target_date}"
                )

        logger.info(
            f"[Task] backfill_missing_insights: "
            f"backfilled={backfilled} of {days_back} days"
        )

        return {'backfilled': backfilled, 'days_checked': days_back}

    except Exception as exc:
        logger.error(f"[Task] backfill_missing_insights failed: {exc}")
        raise self.retry(exc=exc)