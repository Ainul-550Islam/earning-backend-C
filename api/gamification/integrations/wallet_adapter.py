"""
api/gamification/integrations/wallet_adapter.py

Wallet ↔ Gamification adapter।

Wallet credit/withdrawal হলে gamification-এ milestone check করে।
api.wallet.hooks এর "after credit" hook-এ register করা হয়।

Wire-up (api/wallet/apps.py ready() তে):
    from api.gamification.integrations.wallet_adapter import WalletGamificationAdapter
    WalletGamificationAdapter().register_hooks()
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Earning milestones — এগুলো cross হলে achievement দেওয়া হবে
EARNING_MILESTONES = [10, 100, 500, 1000, 5000, 10000]

# Deposit-এর জন্য achievement title map
DEPOSIT_ACHIEVEMENT_TITLES = {
    10:    "First Deposit",
    100:   "Century Depositor",
    500:   "High Roller",
    1000:  "Elite Depositor",
    5000:  "VIP Depositor",
    10000: "Diamond Depositor",
}


class WalletGamificationAdapter:
    """Wallet events থেকে gamification achievements trigger করে।"""

    def on_credited(self, user: Any, amount: float, source: str = "deposit") -> None:
        """
        Wallet credit হলে call করো।

        Logic:
        1. User-এর total credited amount বের করো
        2. নতুন milestone cross হয়েছে কিনা check করো
        3. Cross হলে MILESTONE achievement award করো
        """
        try:
            total = self._get_total_earned(user)
            new_total = total + Decimal(str(amount))

            for milestone in EARNING_MILESTONES:
                if total < milestone <= new_total:
                    self._award_earning_milestone(user, milestone, source)

            # First deposit specific check
            if source == "deposit":
                self._check_first_deposit(user)

            # Analytics track
            self._track(user, "wallet_credited", {
                "amount": float(amount),
                "source": source,
                "new_total": float(new_total),
            })

        except Exception as exc:
            logger.error("[WalletGamificationAdapter] on_credited failed for user=%s: %s",
                         getattr(user, "id", "?"), exc)

    def on_withdrawal(self, user: Any, amount: float, status: str) -> None:
        """
        Withdrawal approved/processed হলে call করো।

        Logic:
        1. First successful withdrawal → MILESTONE achievement
        """
        if status not in ("approved", "processed", "completed"):
            return
        try:
            self._check_first_withdrawal(user)
            self._track(user, "wallet_withdrawal", {
                "amount": float(amount),
                "status": status,
            })
        except Exception as exc:
            logger.error("[WalletGamificationAdapter] on_withdrawal failed for user=%s: %s",
                         getattr(user, "id", "?"), exc)

    def register_hooks(self) -> None:
        """
        api.wallet.hooks.wallet_hooks-এ gamification hooks register করো।
        api/wallet/apps.py এর ready() তে call করো।

        Example:
            class WalletConfig(AppConfig):
                def ready(self):
                    from api.gamification.integrations.wallet_adapter import (
                        WalletGamificationAdapter
                    )
                    WalletGamificationAdapter().register_hooks()
        """
        try:
            from api.wallet.hooks import wallet_hooks

            @wallet_hooks.after("credit")
            def _after_credit(wallet, amount, txn=None, **kwargs):
                self.on_credited(
                    user=wallet.user,
                    amount=float(amount),
                    source=getattr(txn, "purpose", "credit"),
                )

            @wallet_hooks.after("withdrawal")
            def _after_withdrawal(wallet, amount, withdrawal=None, **kwargs):
                status = getattr(withdrawal, "status", "processed")
                self.on_withdrawal(
                    user=wallet.user,
                    amount=float(amount),
                    status=status,
                )

            logger.info("[WalletGamificationAdapter] Hooks registered successfully.")
        except ImportError:
            logger.warning("[WalletGamificationAdapter] api.wallet not available — skipping hooks.")
        except Exception as exc:
            logger.error("[WalletGamificationAdapter] register_hooks failed: %s", exc)

    # ── Private ────────────────────────────────────────────────────────────────

    def _get_total_earned(self, user: Any) -> Decimal:
        """User-এর total credited amount (wallet থেকে)।"""
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.filter(user=user).first()
            if wallet and hasattr(wallet, "total_credited"):
                return Decimal(str(wallet.total_credited or 0))
            # Fallback: transaction sum
            from api.wallet.models import Transaction
            from django.db.models import Sum
            result = Transaction.objects.filter(
                wallet__user=user,
                transaction_type__in=("credit", "deposit"),
                status="completed",
            ).aggregate(total=Sum("amount"))
            return Decimal(str(result.get("total") or 0))
        except Exception:
            return Decimal("0")

    def _award_earning_milestone(self, user: Any, milestone: int, source: str) -> None:
        """Earning milestone achievement award করো।"""
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType

        title = DEPOSIT_ACHIEVEMENT_TITLES.get(milestone, f"Earned ৳{milestone}")
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.MILESTONE,
                title=title,
                description=f"Total wallet earnings ৳{milestone} ছাড়িয়েছেন!",
                points=milestone // 10,  # proportional points
                metadata={
                    "milestone": milestone,
                    "source": source,
                    "milestone_type": "earning",
                },
            )
            logger.info("[WalletGamificationAdapter] Awarded '%s' to user=%s", title, user.pk)
        except Exception as exc:
            # DuplicateAchievementError etc. — log and ignore
            logger.debug("[WalletGamificationAdapter] _award_earning_milestone: %s", exc)

    def _check_first_deposit(self, user: Any) -> None:
        """প্রথম deposit-এর achievement।"""
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.BADGE,
                title="First Deposit",
                description="প্রথম wallet deposit সম্পন্ন!",
                points=10,
                metadata={"badge": "first_deposit"},
            )
        except Exception:
            pass  # Already awarded or duplicate — expected

    def _check_first_withdrawal(self, user: Any) -> None:
        """প্রথম withdrawal-এর achievement।"""
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.MILESTONE,
                title="First Withdrawal",
                description="প্রথম withdrawal সফলভাবে সম্পন্ন!",
                points=20,
                metadata={"milestone": "first_withdrawal"},
            )
        except Exception:
            pass

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
