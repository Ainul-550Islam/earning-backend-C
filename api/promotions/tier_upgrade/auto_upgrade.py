# =============================================================================
# promotions/tier_upgrade/auto_upgrade.py
# Automatic Publisher Tier Upgrade — runs nightly
# Starter → Bronze → Silver → Gold → Platinum based on 30-day earnings
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

TIER_THRESHOLDS = {
    'starter':  Decimal('0'),
    'bronze':   Decimal('100'),
    'silver':   Decimal('500'),
    'gold':     Decimal('2000'),
    'platinum': Decimal('10000'),
}

TIER_ORDER = ['starter', 'bronze', 'silver', 'gold', 'platinum']


def get_correct_tier(monthly_earnings: Decimal) -> str:
    tier = 'starter'
    for t in TIER_ORDER:
        if monthly_earnings >= TIER_THRESHOLDS[t]:
            tier = t
    return tier


@shared_task
def auto_upgrade_all_publishers():
    """Nightly task: check and upgrade/downgrade publisher tiers."""
    from api.promotions.models import PublisherProfile, PromotionTransaction
    from django.contrib.auth import get_user_model
    User = get_user_model()

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    upgraded = 0
    downgraded = 0

    for profile in PublisherProfile.objects.filter(approval_status='approved').select_related('user'):
        monthly_earnings = PromotionTransaction.objects.filter(
            user=profile.user,
            transaction_type='reward',
            created_at__gte=month_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        correct_tier = get_correct_tier(monthly_earnings)

        if profile.tier != correct_tier:
            old_tier = profile.tier
            profile.tier = correct_tier
            profile.save(update_fields=['tier'])

            if TIER_ORDER.index(correct_tier) > TIER_ORDER.index(old_tier):
                upgraded += 1
                logger.info(f'Publisher {profile.user_id} upgraded: {old_tier} → {correct_tier} (${monthly_earnings}/month)')
                _notify_tier_upgrade(profile.user_id, old_tier, correct_tier)
            else:
                downgraded += 1
                logger.info(f'Publisher {profile.user_id} downgraded: {old_tier} → {correct_tier} (${monthly_earnings}/month)')

    logger.info(f'Tier auto-upgrade complete: {upgraded} upgraded, {downgraded} downgraded')
    return {'upgraded': upgraded, 'downgraded': downgraded}


def _notify_tier_upgrade(user_id: int, old_tier: str, new_tier: str):
    """Send notification when tier changes."""
    try:
        from api.promotions.models import PublisherProfile
        profile = PublisherProfile.objects.get(user_id=user_id)
        if profile.device_token_fcm:
            from api.promotions.notifications.fcm_push import FCMPushNotification
            tier_labels = {
                'bronze': '🥉 Bronze', 'silver': '🥈 Silver',
                'gold': '🥇 Gold', 'platinum': '💎 Platinum',
            }
            FCMPushNotification().send_to_device(
                device_token=profile.device_token_fcm,
                title=f'🎉 Tier Upgrade: {tier_labels.get(new_tier, new_tier)}!',
                body=f'Congratulations! You upgraded from {old_tier.title()} to {new_tier.title()}. Enjoy better benefits!',
                data={'type': 'tier_upgrade', 'new_tier': new_tier},
            )
    except Exception as e:
        logger.error(f'Tier upgrade notification failed: {e}')
