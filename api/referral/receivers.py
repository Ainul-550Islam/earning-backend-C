# api/referral/receivers.py
# Signal receivers — decoupled from signals.py for clarity
# signals.py connects; receivers.py implements the logic
# ============================================================

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def process_signup_referral(sender, instance, created, **kwargs):
    """
    Called when new User is created.
    Checks referred_by field and processes referral signup.
    """
    if not created:
        return
    referrer = getattr(instance, 'referred_by', None)
    if not referrer:
        return

    def _process():
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            get_bridge().on_signup(new_user=instance)
        except Exception as e:
            logger.error(f'[Receivers] signup referral failed: {e}')

    transaction.on_commit(_process)


def on_commission_created(sender, instance, created, **kwargs):
    """Called when ReferralEarning is created — async downstream updates."""
    if not created:
        return

    def _process():
        try:
            from api.referral.tasks.ltv_calculation_tasks import recalculate_single_ltv
            recalculate_single_ltv.delay(
                referrer_id=instance.referrer_id,
                referred_user_id=instance.referred_user_id,
            )
        except Exception as e:
            logger.debug(f'[Receivers] LTV task failed: {e}')

        try:
            from api.referral.tasks.notification_tasks import check_milestone_achievements
            check_milestone_achievements.delay(user_id=instance.referrer_id)
        except Exception as e:
            logger.debug(f'[Receivers] milestone task failed: {e}')

        # Fire event
        try:
            from api.referral.events import ReferralEvents
            ReferralEvents.commission_paid(
                user=instance.referrer,
                amount=instance.amount or 0,
                level=instance.level,
                from_user=instance.referred_user,
                source=instance.source_type,
            )
        except Exception as e:
            logger.debug(f'[Receivers] event fire failed: {e}')

    transaction.on_commit(_process)


def on_settings_changed(sender, instance, **kwargs):
    """Clear cache when ReferralSettings saved."""
    try:
        from django.core.cache import cache
        cache.delete('referral_settings')
        cache.delete('referral_active_campaign')
    except Exception:
        pass


def on_fraud_confirmed(sender, instance, **kwargs):
    """Trigger clawback when SuspiciousReferral marked as fraud."""
    if instance.status != 'fraud':
        return

    def _process():
        try:
            from api.referral.tasks.clawback_tasks import initiate_fraud_clawbacks
            initiate_fraud_clawbacks.delay()
        except Exception as e:
            logger.warning(f'[Receivers] clawback task failed: {e}')

    transaction.on_commit(_process)