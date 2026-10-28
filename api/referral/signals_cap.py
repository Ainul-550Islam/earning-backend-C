# api/referral/signals_cap.py
# Capability-based signal patterns — advanced, optional signal wiring
# Separates core signals (signals.py) from capability signals (this file)
# "cap" = capability extension points
# ============================================================

import logging
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# ── Custom Django Signals ─────────────────────────────────────────────────────
# These can be imported by OTHER modules to subscribe to referral events

# Fired after commission is paid successfully
referral_commission_paid = Signal()
# args: sender, user, amount, level, from_user, source_type

# Fired after referral created + bonus given
referral_signup_completed = Signal()
# args: sender, referrer, referred_user, referral, bonus_amount

# Fired when fraud is detected
referral_fraud_detected = Signal()
# args: sender, referral, fraud_score, flags

# Fired when milestone is reached
referral_milestone_achieved = Signal()
# args: sender, user, milestone_value, bonus_amount, bonus_type

# Fired when commission is held
referral_commission_held = Signal()
# args: sender, user, amount, hold_days, release_at

# Fired when commission is released
referral_commission_released = Signal()
# args: sender, user, amount, commission_id

# Fired when clawback is processed
referral_commission_clawback = Signal()
# args: sender, user, amount, reason

# Fired when user tier upgrades
referral_tier_upgraded = Signal()
# args: sender, user, old_tier, new_tier

# Fired when campaign goes live
referral_campaign_activated = Signal()
# args: sender, campaign

# Fired when contest ends and prizes distributed
referral_contest_concluded = Signal()
# args: sender, contest, winners


# ── Capability: Streak Processing ─────────────────────────────────────────────

def _handle_streak_on_referral(sender, referrer, referred_user, referral, **kwargs):
    """Update referral streak when new referral created."""
    try:
        from api.referral.models import UserStreakTracker
        from django.utils import timezone

        tracker, _ = UserStreakTracker.objects.get_or_create(user=referrer)
        today = timezone.now().date()

        if tracker.last_referral_date:
            from datetime import timedelta
            yesterday = today - timedelta(days=1)
            if tracker.last_referral_date == yesterday:
                tracker.current_streak_days += 1
            elif tracker.last_referral_date < yesterday:
                tracker.current_streak_days = 1
        else:
            tracker.current_streak_days = 1

        if tracker.current_streak_days > tracker.longest_streak_days:
            tracker.longest_streak_days = tracker.current_streak_days

        tracker.last_referral_date = today
        tracker.save(update_fields=[
            'current_streak_days', 'longest_streak_days', 'last_referral_date'
        ])
    except Exception as e:
        logger.debug(f'[SignalsCap] streak update failed: {e}')


# ── Capability: Viral Coefficient Update ──────────────────────────────────────

def _handle_viral_coefficient_update(sender, **kwargs):
    """Trigger viral coefficient recalculation when referral created."""
    try:
        from api.referral.tasks.insight_tasks import update_viral_coefficient
        update_viral_coefficient.delay()
    except Exception as e:
        logger.debug(f'[SignalsCap] viral coefficient update failed: {e}')


# ── Capability: Tier Check on Commission ──────────────────────────────────────

def _handle_tier_check_on_commission(sender, user, amount, **kwargs):
    """Check if user should upgrade tier after commission."""
    try:
        from api.referral.models import UserCommissionTier
        tier_record = UserCommissionTier.objects.filter(user=user).first()
        if tier_record:
            from decimal import Decimal
            from django.db.models import F
            UserCommissionTier.objects.filter(user=user).update(
                total_commission_earned=F('total_commission_earned') + Decimal(str(amount))
            )
    except Exception as e:
        logger.debug(f'[SignalsCap] tier check failed: {e}')


# ── Capability: Credit Balance Update ─────────────────────────────────────────

def _handle_credit_balance_update(sender, user, amount, **kwargs):
    """Update referral credit balance when commission paid."""
    try:
        from api.referral.models import ReferralCreditBalance
        from decimal import Decimal
        from django.db.models import F

        credit_bal, _ = ReferralCreditBalance.objects.get_or_create(user=user)
        from django.utils import timezone
        ReferralCreditBalance.objects.filter(user=user).update(
            balance=F('balance') + Decimal(str(amount)),
            lifetime_earned=F('lifetime_earned') + Decimal(str(amount)),
            last_credit_at=timezone.now(),
        )
    except Exception as e:
        logger.debug(f'[SignalsCap] credit balance update failed: {e}')


# ── Wire Up ────────────────────────────────────────────────────────────────────

def connect_capability_signals():
    """
    Connect capability signals.
    Called from apps.py ready() after core signals.
    """
    referral_signup_completed.connect(_handle_streak_on_referral)
    referral_signup_completed.connect(_handle_viral_coefficient_update)
    referral_commission_paid.connect(_handle_tier_check_on_commission)
    referral_commission_paid.connect(_handle_credit_balance_update)
    logger.info('[SignalsCap] Capability signals connected')