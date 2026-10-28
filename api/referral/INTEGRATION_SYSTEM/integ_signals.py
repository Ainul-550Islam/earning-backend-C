# api/referral/INTEGRATION_SYSTEM/integ_signals.py
# Django signal connections — referral listens to signals from other modules
# ============================================================

import logging
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Custom Signals ────────────────────────────────────────────────────────────
# Other modules can import and use these signals directly

referral_commission_paid    = Signal()  # args: user, amount, level, from_user
referral_commission_held    = Signal()  # args: user, amount, hold_days
referral_commission_released = Signal() # args: user, amount
referral_created            = Signal()  # args: referrer, referred_user, referral
referral_fraud_flagged      = Signal()  # args: referral, fraud_score, flags
milestone_reached           = Signal()  # args: user, milestone_value, bonus_amount
campaign_activated          = Signal()  # args: campaign


# ── Signal: User Registered (via referred_by field) ──────────────────────────

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def on_user_created_check_referral(sender, instance, created, **kwargs):
    """
    When a new user is created:
    1. Check if user.referred_by is set
    2. If yes, process referral signup
    3. Generate primary referral code for this user
    """
    if not created:
        return

    def _process():
        # Generate referral code for new user (if they don't have one)
        _ensure_user_referral_code(instance)

        # Process referral if referred_by is set
        referrer = getattr(instance, 'referred_by', None)
        if not referrer:
            return

        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_user_registered
            )
            handle_user_registered(
                new_user=instance,
                referral_code='',  # referred_by already set on user
            )
        except Exception as e:
            logger.error(f'[IntegSignals] User referral processing error: {e}')

    transaction.on_commit(_process)


# ── Signal: Task Completion ───────────────────────────────────────────────────

@receiver(post_save, sender='tasks.UserTaskCompletion')
def on_task_completion_commission(sender, instance, created, **kwargs):
    """
    When UserTaskCompletion is saved as completed:
    → Process referral commission for all ancestors.

    Integration: api/tasks/models.py → UserTaskCompletion
    """
    if not created:
        return
    if getattr(instance, 'status', '') not in ('approved', 'completed', 'paid'):
        return

    earned = getattr(instance, 'coins_earned', None) or \
             getattr(instance, 'reward_amount', None) or \
             getattr(instance, 'amount', None)

    if not earned or float(earned) <= 0:
        return

    def _process():
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_task_completed
            )
            handle_task_completed(
                user=instance.user,
                task=getattr(instance, 'task', None),
                earned_amount=float(earned),
                completion=instance,
            )
        except Exception as e:
            logger.error(f'[IntegSignals] Task commission error: {e}')

    transaction.on_commit(_process)


# ── Signal: Offer/Conversion Approved ────────────────────────────────────────

@receiver(post_save, sender='offer_inventory.Conversion')
def on_conversion_approved_commission(sender, instance, created, **kwargs):
    """
    When offer conversion is approved:
    → Process referral commission.

    Integration: api/offer_inventory/signals.py → on_conversion_approved
    This signal fires AFTER the offer_inventory signal to avoid double processing.
    """
    if created:
        return

    # Check if just approved
    status_name = ''
    if hasattr(instance, 'status'):
        s = instance.status
        status_name = s.name if hasattr(s, 'name') else str(s)
    if status_name not in ('approved', 'APPROVED'):
        return

    user_reward = getattr(instance, 'user_net_reward', None) or \
                  getattr(instance, 'payout', None) or \
                  getattr(instance, 'reward', None)

    if not user_reward or float(user_reward) <= 0:
        return

    def _process():
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_offer_completed
            )
            handle_offer_completed(
                user=instance.user,
                conversion=instance,
                user_net_reward=float(user_reward),
                offer_id=str(getattr(instance, 'offer_id', '')),
            )
        except Exception as e:
            logger.error(f'[IntegSignals] Offer commission error: {e}')

    transaction.on_commit(_process)


# ── Signal: Wallet Withdrawal Approved ───────────────────────────────────────

@receiver(post_save, sender='wallet.Withdrawal')
def on_withdrawal_approved_commission(sender, instance, created, **kwargs):
    """
    When withdrawal is approved:
    → Process withdrawal-based referral commission (if configured).

    Integration: api/wallet/services.py → WalletService.approve_withdrawal()
    """
    if created:
        return

    status = getattr(instance, 'status', '')
    if str(status) not in ('approved', 'APPROVED', 'completed'):
        return

    amount = getattr(instance, 'amount', None)
    if not amount or float(amount) <= 0:
        return

    def _process():
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_withdrawal_approved
            )
            handle_withdrawal_approved(
                user=instance.wallet.user if hasattr(instance, 'wallet') else instance.user,
                amount=float(amount),
                transaction_id=str(getattr(instance, 'id', '')),
            )
        except Exception as e:
            logger.debug(f'[IntegSignals] Withdrawal commission skipped: {e}')

    transaction.on_commit(_process)


# ── Signal: Fraud Detection Confirmed ────────────────────────────────────────

@receiver(post_save, sender='fraud_detection.FraudAttemptLog')
def on_fraud_confirmed_clawback(sender, instance, created, **kwargs):
    """
    When fraud is confirmed by fraud_detection module:
    → Trigger referral clawback.

    Integration: api/fraud_detection → FraudAttemptLog
    """
    if not created:
        return

    severity = getattr(instance, 'severity', '')
    action = getattr(instance, 'action_taken', '')

    if str(severity) not in ('HIGH', 'CRITICAL') or 'BAN' not in str(action).upper():
        return

    def _process():
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_fraud_confirmed
            )
            handle_fraud_confirmed(
                user=getattr(instance, 'user', None),
                fraud_score=getattr(instance, 'risk_score', 100),
            )
        except Exception as e:
            logger.debug(f'[IntegSignals] Fraud clawback skipped: {e}')

    transaction.on_commit(_process)


# ── Signal: ReferralEarning saved → trigger downstream ───────────────────────

@receiver(post_save, sender='referral.ReferralEarning')
def on_referral_earning_downstream(sender, instance, created, **kwargs):
    """
    After commission is recorded:
    1. Update LTV async
    2. Check milestones
    3. Update djoyalty points
    4. Update analytics
    """
    if not created:
        return

    def _process():
        user_id = instance.referrer_id
        referred_id = instance.referred_user_id

        # Async LTV recalc
        try:
            from api.referral.tasks.ltv_calculation_tasks import (
                recalculate_single_ltv
            )
            recalculate_single_ltv.delay(
                referrer_id=user_id, referred_user_id=referred_id
            )
        except Exception as e:
            logger.debug(f'[IntegSignals] LTV task skipped: {e}')

        # Milestone check
        try:
            from api.referral.tasks.notification_tasks import (
                check_milestone_achievements
            )
            check_milestone_achievements.delay(user_id=user_id)
        except Exception as e:
            logger.debug(f'[IntegSignals] Milestone task skipped: {e}')

        # Fire outbound signal
        referral_commission_paid.send(
            sender=sender,
            user=instance.referrer,
            amount=instance.amount,
            level=instance.level,
            from_user=instance.referred_user,
        )

    transaction.on_commit(_process)


# ── Signal: SuspiciousReferral confirmed as fraud ────────────────────────────

@receiver(post_save, sender='referral.SuspiciousReferral')
def on_suspicious_fraud_confirmed(sender, instance, **kwargs):
    """Fraud confirmed → auto-trigger clawback initiation."""
    if instance.status != 'fraud':
        return

    def _process():
        try:
            from api.referral.tasks.clawback_tasks import initiate_fraud_clawbacks
            initiate_fraud_clawbacks.delay()
        except Exception as e:
            logger.warning(f'[IntegSignals] Clawback task failed: {e}')

    transaction.on_commit(_process)


# ── Signal: ReferralSettings saved → cache invalidation ──────────────────────

@receiver(post_save, sender='referral.ReferralSettings')
def on_settings_saved_clear_cache(sender, instance, **kwargs):
    try:
        from django.core.cache import cache
        from api.referral.INTEGRATION_SYSTEM.integ_constants import (
            CACHE_REFERRAL_SETTINGS, CACHE_ACTIVE_CAMPAIGN
        )
        cache.delete(CACHE_REFERRAL_SETTINGS)
        cache.delete(CACHE_ACTIVE_CAMPAIGN)
    except Exception as e:
        logger.debug(f'[IntegSignals] Settings cache clear failed: {e}')


# ── Signal: ReferralCampaign saved → cache + notify ──────────────────────────

@receiver(post_save, sender='referral.ReferralCampaign')
def on_campaign_saved(sender, instance, created, **kwargs):
    try:
        from django.core.cache import cache
        from api.referral.INTEGRATION_SYSTEM.integ_constants import (
            CACHE_ACTIVE_CAMPAIGN, CACHE_REFERRAL_SETTINGS
        )
        cache.delete(CACHE_ACTIVE_CAMPAIGN)
        cache.delete(CACHE_REFERRAL_SETTINGS)
    except Exception:
        pass

    if created and instance.is_active:
        campaign_activated.send(sender=sender, campaign=instance)


# ── Private Helper ────────────────────────────────────────────────────────────

def _ensure_user_referral_code(user) -> None:
    """Make sure user has a primary ReferralCode record."""
    try:
        from api.referral.services.ReferralCodeService import ReferralCodeService
        # Use user.referral_code (CharField on User model) if it exists
        existing_code = getattr(user, 'referral_code', None)
        if existing_code:
            from api.referral.models import ReferralCode
            if not ReferralCode.objects.filter(
                user=user, is_primary=True
            ).exists():
                ReferralCode.objects.create(
                    user=user,
                    code=existing_code,
                    is_primary=True,
                    is_active=True,
                )
        else:
            ReferralCodeService.get_or_create_primary_code(user)
    except Exception as e:
        logger.debug(f'[IntegSignals] _ensure_user_referral_code skipped: {e}')