# api/wallet/signals_kb.py
"""
Knowledge Base signals (KB = Knowledge Base).
Rule-based automated actions triggered by wallet events.
Think of these as "business rules engine" — if condition → then action.

Rules:
  - Auto-lock wallet if fraud score >= 85
  - Auto-notify admin if withdrawal > 50,000 BDT
  - Auto-generate statement on month end
  - Auto-expire bonus after 30 days of inactivity
  - Auto-upgrade publisher level when threshold met
  - Auto-flag AML if structuring detected
  - Auto-block withdrawal if 24h security lock active
  - Auto-award streak bonus on milestone days
"""
import logging
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger("wallet.signals_kb")


# ── Rule 1: Auto-lock wallet if fraud score >= threshold ─────
def kb_rule_fraud_auto_lock(sender, instance, created, **kwargs):
    """
    KB Rule: FraudScore >= 85 → auto-lock wallet + notify admin.
    """
    if not created:
        return
    if instance.score < 85:
        return
    try:
        from .models.core import Wallet
        wallet = Wallet.objects.filter(user=instance.user).first()
        if wallet and not wallet.is_locked:
            wallet.lock(f"Auto-lock: fraud score {instance.score}")
            logger.warning(f"KB_RULE: Auto-locked wallet {wallet.id} fraud_score={instance.score}")

        # Notify admin
        from .notifications import WalletNotifier
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for admin in User.objects.filter(is_staff=True, is_active=True)[:3]:
            WalletNotifier.send(
                user_id=admin.id,
                event_type="fraud_detected",
                data={
                    "user": instance.user.username,
                    "score": str(instance.score),
                    "signals": str(instance.signals),
                },
                channels=["in_app", "email"],
            )
    except Exception as e:
        logger.error(f"KB_RULE fraud_auto_lock: {e}")


# ── Rule 2: Auto-notify admin on large withdrawal ────────────
def kb_rule_large_withdrawal_notify(sender, instance, created, **kwargs):
    """
    KB Rule: withdrawal amount >= 50,000 BDT → alert admin.
    """
    if not created:
        return
    THRESHOLD = Decimal("50000")
    if instance.amount < THRESHOLD:
        return
    try:
        from .notifications import WalletNotifier
        from django.contrib.auth import get_user_model
        for admin in get_user_model().objects.filter(is_staff=True, is_active=True)[:3]:
            WalletNotifier.send(
                user_id=admin.id,
                event_type="system",
                data={
                    "title": f"Large Withdrawal Alert: {instance.amount} BDT",
                    "user":  instance.user.username if instance.user else "unknown",
                    "withdrawal_id": str(instance.withdrawal_id),
                },
                channels=["in_app", "email"],
            )
        logger.info(f"KB_RULE: Large withdrawal alert {instance.withdrawal_id} {instance.amount} BDT")
    except Exception as e:
        logger.error(f"KB_RULE large_withdrawal_notify: {e}")


# ── Rule 3: Auto-award streak bonus on milestone ─────────────
def kb_rule_streak_bonus(sender, instance, created, **kwargs):
    """
    KB Rule: EarningStreak reaches milestone → credit bonus to wallet.
    Milestones: 7, 14, 30, 60, 90 days.
    """
    if not created:
        return
    try:
        from .constants import STREAK_BONUSES
        bonus_amount = STREAK_BONUSES.get(instance.current_streak)
        if not bonus_amount:
            return

        from .services.core.WalletService import WalletService
        from .events import StreakMilestone
        from .event_bus import event_bus

        wallet = instance.wallet
        txn = WalletService.credit(
            wallet=wallet,
            amount=bonus_amount,
            txn_type="bonus",
            description=f"Streak bonus: {instance.current_streak} days",
        )

        event_bus.publish(StreakMilestone(
            wallet_id=wallet.id,
            user_id=wallet.user_id,
            streak_days=instance.current_streak,
            bonus_amount=bonus_amount,
        ))

        logger.info(f"KB_RULE: Streak bonus {bonus_amount} BDT for {wallet.user_id} ({instance.current_streak} days)")
    except Exception as e:
        logger.debug(f"KB_RULE streak_bonus: {e}")


# ── Rule 4: Auto-block withdrawal on security lock ───────────
def kb_rule_security_lock_withdrawal_block(sender, instance, created, **kwargs):
    """
    KB Rule: SecurityEvent created → block withdrawals for lock_until.
    """
    if not created:
        return
    if not instance.lock_until:
        return
    try:
        from .models.withdrawal import WithdrawalBlock
        block, created_block = WithdrawalBlock.objects.get_or_create(
            user=instance.user,
            is_active=True,
            defaults={
                "reason":     "security",
                "detail":     f"Security lock: {instance.event_type}",
                "unblock_at": instance.lock_until,
            }
        )
        if created_block:
            logger.info(f"KB_RULE: Withdrawal blocked for {instance.user_id} until {instance.lock_until}")
    except Exception as e:
        logger.debug(f"KB_RULE security_lock: {e}")


# ── Rule 5: Auto-flag AML structuring ────────────────────────
def kb_rule_aml_structuring_check(sender, instance, created, **kwargs):
    """
    KB Rule: Transaction amount just below reporting threshold (9999 BDT)
             occurring 3+ times in 7 days → AML flag.
    """
    if not created:
        return
    if instance.type != "withdrawal":
        return

    THRESHOLD = Decimal("9999")
    if abs(instance.amount) > THRESHOLD:
        return

    try:
        from datetime import timedelta
        from .models.core import WalletTransaction
        from .models_cpalead_extra import AMLFlag

        # Count near-threshold transactions in 7 days
        week_ago = timezone.now() - timedelta(days=7)
        count = WalletTransaction.objects.filter(
            wallet=instance.wallet,
            type="withdrawal",
            amount__gte=-(THRESHOLD + Decimal("500")),
            amount__lte=-THRESHOLD + Decimal("500"),
            created_at__gte=week_ago,
        ).count()

        if count >= 3:
            AMLFlag.objects.get_or_create(
                user=instance.wallet.user,
                flag_type="structuring",
                is_resolved=False,
                defaults={
                    "wallet":             instance.wallet,
                    "suspicious_amount":  abs(instance.amount),
                    "details":            f"Structuring: {count}x near-threshold withdrawals in 7 days",
                    "risk_score":         75,
                }
            )
            logger.warning(f"KB_RULE: AML structuring flag for wallet {instance.wallet_id} count={count}")
    except Exception as e:
        logger.debug(f"KB_RULE aml_structuring: {e}")


# ── Rule 6: Auto-generate monthly statement trigger ──────────
def kb_rule_monthly_statement(sender, instance, **kwargs):
    """
    KB Rule: On 1st of month, queue statement generation for all wallets.
    Triggered by celery_beat, not a Django signal — kept here for reference.
    """
    pass  # Handled by celery_beat_config monthly schedule


# ── Connect all KB rules ──────────────────────────────────────

def connect_kb_signals():
    """Connect all KB (Knowledge Base) rules. Called from apps.py."""

    # Rule 1: Fraud auto-lock
    try:
        from .models_cpalead_extra import FraudScore
        post_save.connect(kb_rule_fraud_auto_lock, sender=FraudScore,
                          dispatch_uid="kb_fraud_auto_lock")
    except ImportError:
        pass

    # Rule 2: Large withdrawal admin notify
    try:
        from .models.withdrawal import WithdrawalRequest
        post_save.connect(kb_rule_large_withdrawal_notify, sender=WithdrawalRequest,
                          dispatch_uid="kb_large_withdrawal_notify")
    except ImportError:
        pass

    # Rule 3: Streak bonus
    try:
        from .models.earning import EarningStreak
        post_save.connect(kb_rule_streak_bonus, sender=EarningStreak,
                          dispatch_uid="kb_streak_bonus")
    except ImportError:
        pass

    # Rule 4: Security lock → withdrawal block
    try:
        from .models_cpalead_extra import SecurityEvent
        post_save.connect(kb_rule_security_lock_withdrawal_block, sender=SecurityEvent,
                          dispatch_uid="kb_security_lock_withdrawal_block")
    except ImportError:
        pass

    # Rule 5: AML structuring check
    try:
        from .models.core import WalletTransaction
        post_save.connect(kb_rule_aml_structuring_check, sender=WalletTransaction,
                          dispatch_uid="kb_aml_structuring_check")
    except ImportError:
        pass

    logger.info("Wallet KB rules connected (fraud, large_wd, streak, security_lock, aml)")
