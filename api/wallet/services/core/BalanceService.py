# api/wallet/services/core/BalanceService.py
"""
Manages all 5 balance types on a wallet.

  current_balance  — crediting / debiting
  pending_balance  — funds waiting for withdrawal processing
  frozen_balance   — admin hold (managed via Wallet.freeze/unfreeze)
  bonus_balance    — promotional (managed via BalanceBonus.activate/expire)
  reserved_balance — in-flight ops (BalanceReserve / BalanceLock)

Also handles:
  - Balance alerts (low balance, large transaction)
  - Bonus expiry
  - Reserve management
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ...models import Wallet, BalanceHistory, BalanceAlert, BalanceBonus, BalanceReserve

logger = logging.getLogger("wallet.service.balance")


class BalanceService:

    # ── Reserve / Lock ────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def reserve(wallet: Wallet, amount: Decimal, purpose: str = "",
                reference_id: str = "", expires_at=None) -> BalanceReserve:
        """Reserve amount from current_balance (reduces available_balance)."""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Reserve amount must be positive")
        if amount > wallet.available_balance:
            from ...exceptions import InsufficientBalanceError
            raise InsufficientBalanceError(wallet.available_balance, amount)

        reserve = BalanceReserve.objects.create(
            wallet=wallet,
            reserved_amount=amount,
            purpose=purpose,
            reference_id=reference_id,
            expires_at=expires_at,
            status="active",
        )
        wallet.reserved_balance += amount
        wallet.save(update_fields=["reserved_balance", "updated_at"])

        logger.info(f"Reserved {amount} on wallet={wallet.id} for '{purpose}'")
        return reserve

    @staticmethod
    @transaction.atomic
    def release_reserve(reserve: BalanceReserve):
        """Release a reserve — restore available_balance."""
        reserve.release()
        logger.info(f"Released reserve={reserve.reserve_id} wallet={reserve.wallet_id}")

    # ── Bonus management ─────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def grant_bonus(wallet: Wallet, amount: Decimal, source: str = "admin",
                    source_id: str = "", description: str = "",
                    expires_at=None, granted_by=None) -> BalanceBonus:
        """Grant a bonus to a wallet and immediately activate it."""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Bonus amount must be positive")

        bonus = BalanceBonus.objects.create(
            wallet=wallet,
            amount=amount,
            source=source,
            source_id=source_id,
            description=description,
            expires_at=expires_at,
            granted_by=granted_by,
            status="pending",
        )
        bonus.activate()
        logger.info(f"Bonus granted: wallet={wallet.id} amount={amount} source={source}")
        return bonus

    @staticmethod
    def expire_bonuses() -> int:
        """
        Expire all active bonuses past their expiry datetime.
        Called by bonus_expiry_tasks daily.
        Returns count of expired bonuses.
        """
        now = timezone.now()
        expired_bonuses = BalanceBonus.objects.filter(
            status="active",
            expires_at__lt=now,
        ).select_related("wallet")

        count = 0
        for bonus in expired_bonuses:
            try:
                bonus.expire()
                count += 1
            except Exception as e:
                logger.error(f"Bonus expiry failed bonus={bonus.bonus_id}: {e}")

        logger.info(f"Expired {count} bonuses")
        return count

    # ── Balance alerts ────────────────────────────────────────────────

    @staticmethod
    def check_alerts(wallet: Wallet) -> list:
        """
        Check all active alerts for this wallet and fire any that trigger.
        Returns list of triggered alert types.
        """
        triggered = []
        alerts = BalanceAlert.objects.filter(wallet=wallet, is_active=True)

        for alert in alerts:
            from ...choices import AlertType
            if alert.alert_type == AlertType.LOW_BALANCE:
                value = wallet.current_balance
            elif alert.alert_type == AlertType.HIGH_BALANCE:
                value = wallet.current_balance
            elif alert.alert_type in (AlertType.LARGE_CREDIT, AlertType.LARGE_DEBIT):
                value = wallet.current_balance
            else:
                value = wallet.current_balance

            if alert.should_trigger(value):
                triggered.append(alert.alert_type)
                alert.mark_sent()
                try:
                    from ...tasks.notification_tasks import send_balance_alert
                    send_balance_alert.delay(wallet.user_id, alert.alert_type, float(value), float(alert.threshold))
                except Exception as e:
                    logger.debug(f"Alert notification skip: {e}")

        return triggered

    # ── Stats ─────────────────────────────────────────────────────────

    @staticmethod
    def get_balance_breakdown(wallet: Wallet) -> dict:
        """Return all 5 balance types as a dict."""
        return {
            "current":   str(wallet.current_balance),
            "pending":   str(wallet.pending_balance),
            "frozen":    str(wallet.frozen_balance),
            "bonus":     str(wallet.bonus_balance),
            "reserved":  str(wallet.reserved_balance),
            "available": str(wallet.available_balance),
            "total":     str(wallet.total_balance),
        }

    @staticmethod
    def get_balance_history(wallet: Wallet, balance_type: str = None, days: int = 30):
        """Get balance change history for a wallet."""
        from datetime import timedelta
        qs = BalanceHistory.objects.filter(wallet=wallet)
        if balance_type:
            qs = qs.filter(balance_type=balance_type)
        cutoff = timezone.now() - timedelta(days=days)
        return qs.filter(created_at__gte=cutoff).order_by("-created_at")
