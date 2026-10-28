# api/referral/tasks/cleanup_tasks.py
# Celery tasks: database cleanup and maintenance
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.cleanup_old_insights',
    bind=True,
    max_retries=2,
)
def cleanup_old_insights(self, keep_days: int = 365):
    """
    365 দিনের বেশি পুরনো daily insights delete করো।
    প্রতি মাসে একবার।

    Schedule example:
        'referral-cleanup-insights': {
            'task': 'referral.cleanup_old_insights',
            'schedule': crontab(hour=3, minute=0, day_of_month=15),
        }
    """
    try:
        from api.referral.models import ReferralInsight
        from django.utils import timezone

        cutoff = timezone.now().date() - timedelta(days=keep_days)
        deleted, _ = ReferralInsight.objects.filter(
            date__lt=cutoff
        ).delete()

        logger.info(
            f"[Task] cleanup_old_insights: "
            f"deleted={deleted}, keep_days={keep_days}"
        )

        return {'deleted': deleted}

    except Exception as exc:
        logger.error(f"[Task] cleanup_old_insights failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.cleanup_old_fraud_logs',
    bind=True,
    max_retries=2,
)
def cleanup_old_fraud_logs(self, keep_days: int = 180):
    """
    180 দিনের বেশি পুরনো cleared fraud logs delete করো।
    প্রতি মাসে।

    Schedule example:
        'referral-cleanup-fraud-logs': {
            'task': 'referral.cleanup_old_fraud_logs',
            'schedule': crontab(hour=4, minute=0, day_of_month=1),
        }
    """
    try:
        from api.referral.models import SuspiciousReferral, ReferralFraudLog
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=keep_days)

        # Cleared fraud records
        cleared_deleted, _ = SuspiciousReferral.objects.filter(
            status='cleared',
            reviewed_at__lt=cutoff,
        ).delete()

        # Old fraud logs
        fraud_log_deleted, _ = ReferralFraudLog.objects.filter(
            detected_at__lt=cutoff,
        ).delete()

        logger.info(
            f"[Task] cleanup_old_fraud_logs: "
            f"cleared_deleted={cleared_deleted}, "
            f"fraud_log_deleted={fraud_log_deleted}"
        )

        return {
            'cleared_deleted': cleared_deleted,
            'fraud_log_deleted': fraud_log_deleted,
        }

    except Exception as exc:
        logger.error(f"[Task] cleanup_old_fraud_logs failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.cleanup_old_tree_snapshots',
    bind=True,
    max_retries=2,
)
def cleanup_old_tree_snapshots(self, keep_days: int = 90):
    """
    90 দিনের বেশি পুরনো tree snapshots delete করো।
    Monthly।

    Schedule example:
        'referral-cleanup-tree-snapshots': {
            'task': 'referral.cleanup_old_tree_snapshots',
            'schedule': crontab(hour=5, minute=0, day_of_month=1),
        }
    """
    try:
        from api.referral.models import ReferralTreeSnapshot
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=keep_days)
        deleted, _ = ReferralTreeSnapshot.objects.filter(
            created_at__lt=cutoff,
            period__in=['daily'],  # Keep weekly/monthly longer
        ).delete()

        logger.info(
            f"[Task] cleanup_old_tree_snapshots: deleted={deleted}"
        )

        return {'deleted': deleted}

    except Exception as exc:
        logger.error(f"[Task] cleanup_old_tree_snapshots failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.cleanup_inactive_referral_codes',
    bind=True,
    max_retries=2,
)
def cleanup_inactive_referral_codes(self):
    """
    Expired referral codes deactivate করো।
    Weekly।

    Schedule example:
        'referral-cleanup-codes': {
            'task': 'referral.cleanup_inactive_referral_codes',
            'schedule': crontab(hour=6, minute=0, day_of_week=0),  # Sunday
        }
    """
    try:
        from api.referral.models import ReferralCode
        from django.utils import timezone

        # Expired codes deactivate
        expired = ReferralCode.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now(),
        )

        count = expired.count()
        expired.update(is_active=False)

        logger.info(
            f"[Task] cleanup_inactive_referral_codes: deactivated={count}"
        )

        return {'deactivated': count}

    except Exception as exc:
        logger.error(
            f"[Task] cleanup_inactive_referral_codes failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.cleanup_old_top_referrer_snapshots',
    bind=True,
    max_retries=2,
)
def cleanup_old_top_referrer_snapshots(self, keep_days: int = 365):
    """
    পুরনো daily top referrer snapshots delete করো।
    Monthly।

    Schedule example:
        'referral-cleanup-top-referrer': {
            'task': 'referral.cleanup_old_top_referrer_snapshots',
            'schedule': crontab(hour=3, minute=30, day_of_month=1),
        }
    """
    try:
        from api.referral.models import TopReferrer
        from django.utils import timezone

        cutoff = timezone.now().date() - timedelta(days=keep_days)
        deleted, _ = TopReferrer.objects.filter(
            date__lt=cutoff,
            period='daily',  # Keep weekly/monthly/alltime
        ).delete()

        logger.info(
            f"[Task] cleanup_old_top_referrer_snapshots: deleted={deleted}"
        )

        return {'deleted': deleted}

    except Exception as exc:
        logger.error(
            f"[Task] cleanup_old_top_referrer_snapshots failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.cleanup_cancelled_commission_logs',
    bind=True,
    max_retries=2,
)
def cleanup_cancelled_commission_logs(self, keep_days: int = 90):
    """
    90 দিনের বেশি পুরনো cancelled commission logs delete করো।
    Monthly।

    Schedule example:
        'referral-cleanup-commission-logs': {
            'task': 'referral.cleanup_cancelled_commission_logs',
            'schedule': crontab(hour=4, minute=30, day_of_month=1),
        }
    """
    try:
        from api.referral.models import CommissionLog
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=keep_days)
        deleted, _ = CommissionLog.objects.filter(
            status='cancelled',
            created_at__lt=cutoff,
        ).delete()

        logger.info(
            f"[Task] cleanup_cancelled_commission_logs: deleted={deleted}"
        )

        return {'deleted': deleted}

    except Exception as exc:
        logger.error(
            f"[Task] cleanup_cancelled_commission_logs failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.run_all_cleanups',
    bind=True,
    max_retries=1,
)
def run_all_cleanups(self):
    """
    সব cleanup tasks একসাথে run করো।
    Monthly maintenance task।

    Schedule example:
        'referral-run-all-cleanups': {
            'task': 'referral.run_all_cleanups',
            'schedule': crontab(hour=2, minute=0, day_of_month=1),  # 1st of month
        }
    """
    try:
        cleanup_old_insights.delay()
        cleanup_old_fraud_logs.delay()
        cleanup_old_tree_snapshots.delay()
        cleanup_inactive_referral_codes.delay()
        cleanup_old_top_referrer_snapshots.delay()
        cleanup_cancelled_commission_logs.delay()

        logger.info("[Task] run_all_cleanups: all cleanup tasks queued")

        return {'queued': 6}

    except Exception as exc:
        logger.error(f"[Task] run_all_cleanups failed: {exc}")
        raise self.retry(exc=exc)