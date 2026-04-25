# api/wallet/signals.py
"""
MERGED: Original signals.py + new world-class signals.
Original: auto_create_wallet, send_wallet_notification
New: validate_wallet_balances, on_withdrawal_change,
     on_kyc_approved, on_security_event, on_transaction_saved
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("wallet.signals")
User = get_user_model()


def safe_task(task_func, *args, **kwargs):
    """Celery task safely — Celery না থাকলে skip."""
    try:
        task_func.delay(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Task call failed (non-critical): {e}")


def safe_cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        pass


def safe_cache_delete_pattern(pattern):
    try:
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern(pattern)
    except Exception:
        pass


# ── Auto-create wallet on user signup ────────────────────────
@receiver(post_save, sender=User)
def auto_create_wallet(sender, instance, created, **kwargs):
    """Signal: ইউজার create হলে automatically wallet তৈরি করো।"""
    if not created:
        return
    try:
        from .models.core import Wallet
        if Wallet.objects.filter(user=instance).exists():
            return
        with transaction.atomic():
            wallet = Wallet.objects.create(
                user=instance,
                currency="BDT",
                current_balance=Decimal("0"),
                pending_balance=Decimal("0"),
                total_earned=Decimal("0"),
                total_withdrawn=Decimal("0"),
            )
            logger.info(f"Wallet auto-created for user: {instance.username}")

            # Setup CPAlead publisher structures
            try:
                from .models_cpalead_extra import PayoutSchedule, PublisherLevel, PointsLedger
                PayoutSchedule.objects.get_or_create(
                    user=instance, wallet=wallet,
                    defaults={"frequency": "net30", "minimum_threshold": Decimal("50"), "hold_days": 30},
                )
                PublisherLevel.objects.get_or_create(user=instance, wallet=wallet)
                PointsLedger.objects.get_or_create(user=instance, wallet=wallet)
            except Exception as e:
                logger.debug(f"Publisher setup skip: {e}")

            # Notify
            try:
                from .tasks import send_wallet_notification
                safe_task(send_wallet_notification, instance.id, "wallet_created", {"balance": 0})
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Failed to create wallet for user {instance.id}: {e}", exc_info=True)


# ── Pre-save: validate balances never go negative ─────────────
try:
    from .models.core import Wallet as _Wallet

    @receiver(pre_save, sender=_Wallet)
    def validate_wallet_balances(sender, instance, **kwargs):
        """Pre-save: clamp all balance fields to >= 0."""
        zero = Decimal("0")
        for field in ["current_balance","pending_balance","frozen_balance",
                      "bonus_balance","reserved_balance","total_earned",
                      "total_withdrawn","total_fees_paid","total_bonuses"]:
            val = getattr(instance, field, zero) or zero
            if val < zero:
                logger.warning(f"Wallet {instance.pk}: {field}={val} clamped to 0")
                setattr(instance, field, zero)
except ImportError:
    pass


# ── Post-save WalletTransaction: clear cache + fire webhook ───
try:
    from .models.core import WalletTransaction as _WalletTxn

    @receiver(post_save, sender=_WalletTxn)
    def on_transaction_saved(sender, instance, created, **kwargs):
        if not created:
            return
        # Clear wallet summary cache
        safe_cache_delete(f"wallet_summary_{instance.wallet_id}")
        safe_cache_delete(f"wallet_balance_{instance.wallet_id}")
        # Fire webhook event
        try:
            from .services_extra import WebhookDeliveryService
            WebhookDeliveryService.fire_event(
                f"wallet.{instance.type}",
                {"txn_id": str(instance.txn_id), "amount": str(instance.amount),
                 "status": instance.status, "wallet_id": instance.wallet_id},
                wallet=instance.wallet,
            )
        except Exception:
            pass
except ImportError:
    pass


# ── Withdrawal status change: clear cache ─────────────────────
try:
    from .models.withdrawal import WithdrawalRequest as _WR

    @receiver(post_save, sender=_WR)
    def on_withdrawal_status_change(sender, instance, created, **kwargs):
        if created:
            return
        safe_cache_delete(f"wallet_summary_{instance.wallet_id}")
        logger.info(f"Withdrawal {instance.withdrawal_id}: status={instance.status}")
except ImportError:
    pass


# ── KYC approved: update wallet daily limit ───────────────────
try:
    from .models_cpalead_extra import KYCVerification as _KYC

    @receiver(post_save, sender=_KYC)
    def on_kyc_approved(sender, instance, **kwargs):
        if instance.status != "approved":
            return
        try:
            instance.wallet.daily_limit = instance.daily_wd_limit
            instance.wallet.save(update_fields=["daily_limit", "updated_at"])
            logger.info(f"KYC approved: {instance.user.username} L{instance.level} → limit={instance.daily_wd_limit}")
        except Exception as e:
            logger.error(f"KYC limit update failed: {e}")
except ImportError:
    pass


# ── Security event: log withdrawal lock ──────────────────────
try:
    from .models_cpalead_extra import SecurityEvent as _SecEvent

    @receiver(post_save, sender=_SecEvent)
    def on_security_event(sender, instance, created, **kwargs):
        if created:
            logger.warning(
                f"Security lock: user={instance.user_id} "
                f"event={instance.event_type} until={instance.lock_until}"
            )
except ImportError:
    pass


# ── Default payment method: ensure only one primary ───────────
try:
    from .models.withdrawal import WithdrawalMethod as _WM

    @receiver(post_save, sender=_WM)
    def ensure_single_default_method(sender, instance, created, **kwargs):
        """Ensure only one payment method is is_default=True per user."""
        if instance.is_default:
            _WM.objects.filter(
                user=instance.user, is_default=True
            ).exclude(pk=instance.pk).update(is_default=False)
except ImportError:
    pass
