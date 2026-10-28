# api/referral/tasks/ltv_calculation_tasks.py
# Celery tasks: weekly LTV recalculation
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.weekly_ltv_recalculation',
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def weekly_ltv_recalculation(self):
    """
    সব referred users এর LTV weekly recalculate করো।
    প্রতি রবিবার রাতে run হয়।

    Schedule example:
        'referral-weekly-ltv-recalc': {
            'task': 'referral.weekly_ltv_recalculation',
            'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Sunday 1AM
        }
    """
    try:
        from api.referral.services.LTVService import LTVService

        result = LTVService.recalculate_all()

        logger.info(
            f"[Task] weekly_ltv_recalculation: "
            f"updated={result['updated']}, errors={result['errors']}"
        )

        return result

    except Exception as exc:
        logger.error(f"[Task] weekly_ltv_recalculation failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.recalculate_ltv_for_referrer',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def recalculate_ltv_for_referrer(self, referrer_id: int):
    """
    Specific referrer এর সব LTV recalculate করো।
    Commission earn হওয়ার পরে async call করা হয়।
    """
    try:
        from django.contrib.auth import get_user_model
        from api.referral.services.LTVService import LTVService

        User = get_user_model()
        try:
            referrer = User.objects.get(id=referrer_id)
        except User.DoesNotExist:
            logger.error(f"Referrer {referrer_id} not found for LTV recalc")
            return {'error': 'Referrer not found'}

        result = LTVService.recalculate_all_for_referrer(referrer)

        logger.debug(
            f"[Task] recalculate_ltv_for_referrer: "
            f"referrer={referrer.username}, "
            f"updated={result['updated']}"
        )

        return result

    except Exception as exc:
        logger.error(
            f"[Task] recalculate_ltv_for_referrer failed "
            f"for referrer_id={referrer_id}: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.recalculate_single_ltv',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def recalculate_single_ltv(self, referrer_id: int, referred_user_id: int):
    """
    Single referrer/referred_user pair এর LTV recalculate করো।
    Commission event trigger করে।
    """
    try:
        from django.contrib.auth import get_user_model
        from api.referral.services.LTVService import LTVService

        User = get_user_model()

        try:
            referrer = User.objects.get(id=referrer_id)
            referred_user = User.objects.get(id=referred_user_id)
        except User.DoesNotExist as e:
            logger.error(f"User not found for LTV recalc: {e}")
            return {'error': str(e)}

        ltv = LTVService.calculate_ltv(
            referrer=referrer, referred_user=referred_user
        )

        return {
            'ltv_id': ltv.id,
            'lifetime_value': float(ltv.lifetime_value),
            'value_category': ltv.value_category,
            'churn_risk': ltv.churn_risk,
        }

    except Exception as exc:
        logger.error(
            f"[Task] recalculate_single_ltv failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.flag_high_churn_risk',
    bind=True,
    max_retries=2,
)
def flag_high_churn_risk(self):
    """
    High churn risk users এর referrers দের notify করো।
    Weekly।

    Schedule example:
        'referral-flag-churn-risk': {
            'task': 'referral.flag_high_churn_risk',
            'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday 9AM
        }
    """
    try:
        from api.referral.models import ReferralLTV
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )

        # Update churn risks
        from django.utils import timezone
        ltvs = ReferralLTV.objects.select_related(
            'user', 'referred_by'
        ).filter(last_activity__isnull=False)

        updated = 0
        for ltv in ltvs:
            new_risk = ltv.calculate_churn_risk()
            if ltv.churn_risk != new_risk:
                ltv.churn_risk = new_risk
                ltv.save(update_fields=['churn_risk'])
                updated += 1

        logger.info(
            f"[Task] flag_high_churn_risk: {updated} churn risks updated"
        )
        return {'updated': updated}

    except Exception as exc:
        logger.error(f"[Task] flag_high_churn_risk failed: {exc}")
        raise self.retry(exc=exc)