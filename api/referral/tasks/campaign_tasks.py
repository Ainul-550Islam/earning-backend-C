# api/referral/tasks/campaign_tasks.py
# Celery tasks: auto start/end referral campaigns
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.check_campaign_schedules',
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def check_campaign_schedules(self):
    """
    Campaign start_date/end_date check করে auto start/end করো।
    প্রতি ১৫ মিনিটে run হয়।

    Schedule example:
        'referral-campaign-schedules': {
            'task': 'referral.check_campaign_schedules',
            'schedule': crontab(minute='*/15'),
        }
    """
    try:
        from api.referral.services.ReferralCampaignService import (
            ReferralCampaignService,
        )

        result = ReferralCampaignService.check_and_auto_start_campaigns()

        if result['started'] > 0 or result['ended'] > 0:
            logger.info(
                f"[Task] check_campaign_schedules: "
                f"started={result['started']}, ended={result['ended']}"
            )

            # Notify users when campaign starts
            if result['started'] > 0:
                _notify_active_referrers_new_campaign.delay()

        return result

    except Exception as exc:
        logger.error(f"[Task] check_campaign_schedules failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.notify_active_referrers_new_campaign',
    bind=True,
    max_retries=2,
)
def _notify_active_referrers_new_campaign(self):
    """
    Newly started campaigns এর জন্য active referrers দের notify করো।
    """
    try:
        from api.referral.models import ReferralCampaign
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )
        from django.utils import timezone

        # Recently started campaigns (last 30 min)
        cutoff = timezone.now() - timedelta(minutes=30)
        new_campaigns = ReferralCampaign.objects.filter(
            is_active=True,
            start_date__gte=cutoff,
        )

        total_notified = 0
        for campaign in new_campaigns:
            result = ReferralNotificationService.bulk_notify_campaign(
                campaign_id=campaign.id
            )
            total_notified += result.get('notified', 0)

        logger.info(
            f"[Task] notify_active_referrers_new_campaign: "
            f"notified={total_notified}"
        )
        return {'notified': total_notified}

    except Exception as exc:
        logger.error(
            f"[Task] notify_active_referrers_new_campaign failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.check_campaign_budget',
    bind=True,
    max_retries=2,
)
def check_campaign_budget(self):
    """
    Campaign budget exceeded হলে auto-end করো।
    প্রতি ঘণ্টায় run হয়।

    Schedule example:
        'referral-campaign-budget-check': {
            'task': 'referral.check_campaign_budget',
            'schedule': crontab(minute=45),
        }
    """
    try:
        from api.referral.models import ReferralCampaign
        from api.referral.services.ReferralCampaignService import (
            ReferralCampaignService,
        )

        active_campaigns = ReferralCampaign.objects.filter(is_active=True)
        ended = 0

        for campaign in active_campaigns:
            # Budget exceeded check
            if campaign.max_budget and campaign.current_spend >= campaign.max_budget:
                result = ReferralCampaignService.end_campaign(campaign.id)
                if result['success']:
                    ended += 1
                    logger.info(
                        f"Campaign ended (budget exceeded): "
                        f"{campaign.name} "
                        f"(spent ৳{campaign.current_spend} / ৳{campaign.max_budget})"
                    )

            # Max referrals exceeded check
            elif (
                campaign.max_referrals and
                campaign.current_referrals >= campaign.max_referrals
            ):
                result = ReferralCampaignService.end_campaign(campaign.id)
                if result['success']:
                    ended += 1
                    logger.info(
                        f"Campaign ended (max referrals): "
                        f"{campaign.name} "
                        f"({campaign.current_referrals} refs)"
                    )

        return {'campaigns_ended': ended}

    except Exception as exc:
        logger.error(f"[Task] check_campaign_budget failed: {exc}")
        raise self.retry(exc=exc)