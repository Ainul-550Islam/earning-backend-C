# api/wallet/receivers.py
"""
Signal receivers — separated from signals.py for clarity.
signals.py defines signals; receivers.py handles them.

Pattern: signals.py sends → receivers.py reacts
"""
import logging
from decimal import Decimal
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save, post_delete

logger = logging.getLogger("wallet.receivers")


# ── Wallet receivers ──────────────────────────────────────────

def on_wallet_credit_fire_event(sender, instance, created, **kwargs):
    """Fire WalletCredited domain event after transaction saved."""
    if not created or instance.amount <= 0:
        return
    try:
        from .event_bus import event_bus
        from .events import WalletCredited
        event_bus.publish(WalletCredited(
            wallet_id=instance.wallet_id,
            user_id=instance.wallet.user_id,
            amount=instance.amount,
            txn_type=instance.type,
            txn_id=str(instance.txn_id),
            balance_after=instance.balance_after or Decimal("0"),
            description=instance.description or "",
        ))
    except Exception as e:
        logger.debug(f"on_wallet_credit_fire_event skip: {e}")


def on_withdrawal_status_notify(sender, instance, **kwargs):
    """Notify user when withdrawal status changes."""
    if instance.pk is None:
        return
    try:
        from .integration.data_bridge import NotificationBridge
        if instance.status == "completed":
            NotificationBridge.send(instance.user_id, "withdrawal_completed", {
                "amount": str(instance.amount),
                "gateway_ref": instance.gateway_reference or "",
            })
        elif instance.status == "rejected":
            NotificationBridge.send(instance.user_id, "withdrawal_failed", {
                "amount": str(instance.amount),
                "error": instance.rejection_reason or "Rejected",
            })
    except Exception as e:
        logger.debug(f"on_withdrawal_status_notify skip: {e}")


def on_kyc_approved_set_limit(sender, instance, created, **kwargs):
    """Set wallet daily limit when KYC is approved."""
    if instance.status != "approved":
        return
    try:
        from .constants import KYC_LIMITS
        limits = KYC_LIMITS.get(instance.level, {})
        daily = limits.get("daily")
        if daily and hasattr(instance, "wallet"):
            instance.wallet.daily_limit = daily
            instance.wallet.save(update_fields=["daily_limit", "updated_at"])
    except Exception as e:
        logger.debug(f"on_kyc_approved_set_limit skip: {e}")


def on_earning_update_points(sender, instance, created, **kwargs):
    """Update CPAlead points when earning record is created."""
    if not created:
        return
    try:
        from .models_cpalead_extra import PointsLedger
        pl, _ = PointsLedger.objects.get_or_create(
            user=instance.wallet.user, wallet=instance.wallet
        )
        pl.award(instance.amount)
    except Exception as e:
        logger.debug(f"on_earning_update_points skip: {e}")


def on_bonus_expired_clear_balance(sender, instance, **kwargs):
    """Clear wallet bonus_balance when bonus expires."""
    if instance.status != "expired":
        return
    try:
        wallet = instance.wallet
        wallet.bonus_balance = max(wallet.bonus_balance - instance.amount, Decimal("0"))
        wallet.save(update_fields=["bonus_balance", "updated_at"])
    except Exception as e:
        logger.debug(f"on_bonus_expired_clear_balance skip: {e}")


# ── Auto-register receivers ───────────────────────────────────
def connect_receivers():
    """Connect all receivers. Called from apps.py ready()."""
    try:
        from .models.core import WalletTransaction, Wallet
        post_save.connect(on_wallet_credit_fire_event, sender=WalletTransaction)
    except ImportError:
        pass

    try:
        from .models.withdrawal import WithdrawalRequest
        post_save.connect(on_withdrawal_status_notify, sender=WithdrawalRequest)
    except ImportError:
        pass

    try:
        from .models_cpalead_extra import KYCVerification
        post_save.connect(on_kyc_approved_set_limit, sender=KYCVerification)
    except ImportError:
        pass

    try:
        from .models.earning import EarningRecord
        post_save.connect(on_earning_update_points, sender=EarningRecord)
    except ImportError:
        pass

    try:
        from .models.balance import BalanceBonus
        post_save.connect(on_bonus_expired_clear_balance, sender=BalanceBonus)
    except ImportError:
        pass

    logger.debug("Wallet receivers connected")
