# api/referral/signals.py
# Production-ready signals — use settings.AUTH_USER_MODEL (NOT _get_user_model() at import time)
# ============================================================

import logging
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


# ── Signal: New User Registered ────────────────────────────────────────────────

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_new_user_referral(sender, instance, created, **kwargs):
    """
    নতুন user create হলে referral process করো।
    User এর referred_by field থেকে referrer detect করা হয়।
    """
    if not created:
        return

    referrer = getattr(instance, 'referred_by', None)
    if not referrer:
        return

    def _process():
        try:
            from api.referral.services.ReferralService import ReferralService
            result = ReferralService.process_signup_with_fraud_check(
                new_user=instance,
                referrer=referrer,
                new_user_ip=None,
                referrer_ip=None,
            )
            if result.get('success'):
                logger.info(
                    f"[Signal] Referral processed: "
                    f"{referrer.username} → {instance.username} "
                    f"(bonus_given={result.get('bonus_given')})"
                )
            else:
                logger.warning(
                    f"[Signal] Referral failed: "
                    f"{referrer.username} → {instance.username}: "
                    f"{result.get('reason')}"
                )
        except Exception as e:
            logger.error(f"[Signal] handle_new_user_referral error: {e}")

    transaction.on_commit(_process)


# ── Signal: ReferralEarning Created ───────────────────────────────────────────

@receiver(post_save, sender='referral.ReferralEarning')
def handle_referral_earning_created(sender, instance, created, **kwargs):
    """
    ReferralEarning তৈরি হলে: LTV async recalculate + milestone check।
    """
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
            logger.warning(f"[Signal] LTV recalc task failed: {e}")

        try:
            from api.referral.tasks.notification_tasks import check_milestone_achievements
            check_milestone_achievements.delay(user_id=instance.referrer_id)
        except Exception as e:
            logger.warning(f"[Signal] Milestone check task failed: {e}")

    transaction.on_commit(_process)


# ── Signal: Referral Created ───────────────────────────────────────────────────

@receiver(post_save, sender='referral.Referral')
def handle_referral_created(sender, instance, created, **kwargs):
    """
    নতুন Referral তৈরি হলে: notify referrer + ensure tree।
    """
    if not created:
        return

    def _process():
        try:
            from api.referral.tasks.notification_tasks import notify_new_referral_async
            notify_new_referral_async.delay(
                referrer_id=instance.referrer_id,
                new_user_id=instance.referred_user_id,
            )
        except Exception as e:
            logger.warning(f"[Signal] Notify new referral task failed: {e}")

        try:
            from api.referral.services.ReferralTreeService import ReferralTreeService
            ReferralTreeService.ensure_tree(instance.referrer)
        except Exception as e:
            logger.warning(f"[Signal] Tree ensure failed: {e}")

    transaction.on_commit(_process)


# ── Signal: CommissionLog Created — notify if held ────────────────────────────

@receiver(post_save, sender='referral.CommissionLog')
def handle_commission_log_created(sender, instance, created, **kwargs):
    """Commission hold হলে user কে notify করো।"""
    if not created or instance.status != 'held':
        return

    def _process():
        try:
            from api.referral.services.ReferralNotificationService import ReferralNotificationService
            hold_days = 7
            try:
                if hasattr(instance, 'hold') and instance.hold:
                    hold_days = instance.hold.hold_days
            except Exception:
                pass
            ReferralNotificationService.notify_commission_held(
                user=instance.user,
                amount=float(instance.amount),
                hold_days=hold_days,
            )
        except Exception as e:
            logger.warning(f"[Signal] Commission held notify failed: {e}")

    transaction.on_commit(_process)


# ── Signal: ReferralSettings Saved → clear cache ──────────────────────────────

@receiver(post_save, sender='referral.ReferralSettings')
def handle_settings_saved(sender, instance, **kwargs):
    """Settings save হলে cache clear করো।"""
    try:
        from django.core.cache import cache
        cache.delete('referral_settings')
        cache.delete('referral_active_campaign')
    except Exception as e:
        logger.warning(f"[Signal] Settings cache clear failed: {e}")


# ── Signal: ReferralCampaign Saved → clear cache ──────────────────────────────

@receiver(post_save, sender='referral.ReferralCampaign')
def handle_campaign_saved(sender, instance, **kwargs):
    """Campaign save হলে cache clear করো।"""
    try:
        from django.core.cache import cache
        cache.delete('referral_active_campaign')
        cache.delete('referral_settings')
    except Exception as e:
        logger.warning(f"[Signal] Campaign cache clear failed: {e}")


# ── Signal: SuspiciousReferral → initiate clawback if fraud ───────────────────

@receiver(post_save, sender='referral.SuspiciousReferral')
def handle_suspicious_referral_status_change(sender, instance, **kwargs):
    """Fraud confirmed হলে clawback initiate করো।"""
    if instance.status != 'fraud':
        return

    def _process():
        try:
            from api.referral.tasks.clawback_tasks import initiate_fraud_clawbacks
            initiate_fraud_clawbacks.delay()
        except Exception as e:
            logger.warning(f"[Signal] Clawback initiation failed: {e}")

    transaction.on_commit(_process)