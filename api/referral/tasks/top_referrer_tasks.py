from datetime import timedelta
# api/referral/tasks/top_referrer_tasks.py
# Celery tasks: daily top referrer leaderboard snapshot
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.daily_top_referrer_snapshot',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def daily_top_referrer_snapshot(self):
    """
    Daily top referrers snapshot নাও।
    প্রতিদিন রাত ১১:৫৫ তে run হয়।

    Schedule example:
        'referral-daily-top-referrer': {
            'task': 'referral.daily_top_referrer_snapshot',
            'schedule': crontab(hour=23, minute=55),
        }
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from django.utils import timezone

        today = timezone.now().date()
        count = ReferralAnalyticsService.snapshot_top_referrers(
            period='daily', date=today
        )

        logger.info(
            f"[Task] daily_top_referrer_snapshot: "
            f"date={today}, snapshots={count}"
        )

        return {'date': str(today), 'snapshots': count}

    except Exception as exc:
        logger.error(f"[Task] daily_top_referrer_snapshot failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.weekly_top_referrer_snapshot',
    bind=True,
    max_retries=2,
)
def weekly_top_referrer_snapshot(self):
    """
    Weekly top referrers snapshot নাও।
    প্রতি সোমবার ভোরে।

    Schedule example:
        'referral-weekly-top-referrer': {
            'task': 'referral.weekly_top_referrer_snapshot',
            'schedule': crontab(hour=5, minute=0, day_of_week=1),
        }
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from django.utils import timezone

        today = timezone.now().date()
        count = ReferralAnalyticsService.snapshot_top_referrers(
            period='weekly', date=today
        )

        logger.info(
            f"[Task] weekly_top_referrer_snapshot: "
            f"date={today}, snapshots={count}"
        )

        return {'date': str(today), 'period': 'weekly', 'snapshots': count}

    except Exception as exc:
        logger.error(f"[Task] weekly_top_referrer_snapshot failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.monthly_top_referrer_snapshot',
    bind=True,
    max_retries=2,
)
def monthly_top_referrer_snapshot(self):
    """
    Monthly top referrers snapshot।
    প্রতি মাসের ১ তারিখে।

    Schedule example:
        'referral-monthly-top-referrer': {
            'task': 'referral.monthly_top_referrer_snapshot',
            'schedule': crontab(hour=5, minute=30, day_of_month=1),
        }
    """
    try:
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from django.utils import timezone

        today = timezone.now().date()
        count = ReferralAnalyticsService.snapshot_top_referrers(
            period='monthly', date=today
        )

        logger.info(
            f"[Task] monthly_top_referrer_snapshot: "
            f"date={today}, snapshots={count}"
        )

        return {'date': str(today), 'period': 'monthly', 'snapshots': count}

    except Exception as exc:
        logger.error(f"[Task] monthly_top_referrer_snapshot failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.compute_rank_changes',
    bind=True,
    max_retries=2,
)
def compute_rank_changes(self, period: str = 'daily'):
    """
    Rank change (vs previous period) calculate করো।
    Daily snapshot নেওয়ার পরে call করা হয়।

    Schedule example:
        'referral-rank-changes': {
            'task': 'referral.compute_rank_changes',
            'schedule': crontab(hour=0, minute=10),  # After midnight snapshot
        }
    """
    try:
        from api.referral.models import TopReferrer
        from django.utils import timezone
        import datetime

        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)

        # Today's snapshots
        today_snaps = {
            snap.user_id: snap
            for snap in TopReferrer.objects.filter(date=today, period=period)
        }

        # Yesterday's snapshots
        yesterday_snaps = {
            snap.user_id: snap.rank
            for snap in TopReferrer.objects.filter(date=yesterday, period=period)
        }

        updated = 0
        for user_id, snap in today_snaps.items():
            prev_rank = yesterday_snaps.get(user_id)
            if prev_rank is not None:
                rank_change = prev_rank - snap.rank  # Positive = improved
                if snap.rank_change != rank_change:
                    snap.rank_change = rank_change
                    snap.save(update_fields=['rank_change'])
                    updated += 1

        logger.info(
            f"[Task] compute_rank_changes: "
            f"period={period}, updated={updated}"
        )

        return {'updated': updated, 'period': period}

    except Exception as exc:
        logger.error(f"[Task] compute_rank_changes failed: {exc}")
        raise self.retry(exc=exc)