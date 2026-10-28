# api/referral/tasks/commission_hold_tasks.py
# Celery tasks: manage commission hold/release lifecycle
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.release_expired_commission_holds',
    bind=True,
    max_retries=3,
    default_retry_delay=600,
)
def release_expired_commission_holds(self):
    """
    Hold period পার হয়েছে এমন commission holds release করো।
    প্রতি ঘণ্টায় run হয়।

    Schedule example:
        'referral-release-holds': {
            'task': 'referral.release_expired_commission_holds',
            'schedule': crontab(minute=30),  # every hour at :30
        }
    """
    try:
        from api.referral.services.CommissionService import CommissionService

        result = CommissionService.release_expired_holds(dry_run=False)

        logger.info(
            f"[Task] release_expired_commission_holds: "
            f"released={result['released']}, "
            f"total_amount={result['total_amount']}, "
            f"errors={result['errors']}"
        )

        # Notify released users
        if result['released'] > 0:
            _notify_released_commissions.delay()

        return result

    except Exception as exc:
        logger.error(f"[Task] release_expired_commission_holds failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.notify_released_commissions',
    bind=True,
    max_retries=2,
)
def _notify_released_commissions(self):
    """
    Recently released commissions এর users দের notify করো।
    release_expired_commission_holds এর পরে call হয়।
    """
    try:
        from api.referral.models import CommissionLog
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )
        from django.utils import timezone
        from django.db.models import Sum

        # Last hour released
        cutoff = timezone.now() - timedelta(hours=1)
        # values() returns dicts not objects — cannot use select_related after values()
        recent_releases = CommissionLog.objects.filter(
            status='released',
            updated_at__gte=cutoff,
        ).values('user').annotate(
            total=Sum('amount')
        )[:500]

        notified = 0
        from django.contrib.auth import get_user_model
        User = get_user_model()

        for item in recent_releases:
            try:
                user = User.objects.get(id=item['user'])
                ReferralNotificationService.notify_commission_released(
                    user=user,
                    amount=float(item['total']),
                )
                notified += 1
            except Exception as e:
                logger.warning(f"Notify release failed for user {item['user']}: {e}")

        logger.info(f"[Task] notify_released_commissions: notified={notified}")
        return {'notified': notified}

    except Exception as exc:
        logger.error(f"[Task] notify_released_commissions failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.create_weekly_payouts',
    bind=True,
    max_retries=2,
)
def create_weekly_payouts(self):
    """
    সব users এর released commissions কে weekly payout এ consolidate করো।
    প্রতি সোমবার সকালে run হয়।

    Schedule example:
        'referral-weekly-payouts': {
            'task': 'referral.create_weekly_payouts',
            'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Monday 6AM
        }
    """
    try:
        from api.referral.models import CommissionLog
        from api.referral.services.CommissionService import CommissionService

        # Users with unreleased-to-payout commissions
        user_ids = CommissionLog.objects.filter(
            status='released',
            payouts__isnull=True,
        ).values_list('user_id', flat=True).distinct()

        from django.contrib.auth import get_user_model
        User = get_user_model()

        created = 0
        skipped = 0
        errors = 0

        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                result = CommissionService.create_payout(
                    user=user, period='weekly'
                )
                if result.get('success'):
                    created += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Payout creation error for user {user_id}: {e}")
                errors += 1

        logger.info(
            f"[Task] create_weekly_payouts: "
            f"created={created}, skipped={skipped}, errors={errors}"
        )

        return {'created': created, 'skipped': skipped, 'errors': errors}

    except Exception as exc:
        logger.error(f"[Task] create_weekly_payouts failed: {exc}")
        raise self.retry(exc=exc)