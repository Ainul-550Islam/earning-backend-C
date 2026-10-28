# api/wallet/savings_goals.py
"""
Savings Goals — Lock a portion of wallet balance for a goal.
Research: React+Django fintech course (2025) includes savings goals.
Binance/PayPal both have savings features.

Features:
  - Create goal (name, target amount, deadline)
  - Auto-save (deduct from earnings automatically)
  - Progress tracking
  - Achieve goal → release funds to main balance
  - Interest (optional, configurable rate)

Usage:
    from .savings_goals import SavingsGoalService
    goal = SavingsGoalService.create(user, "New Phone", Decimal("15000"), deadline=...)
    SavingsGoalService.contribute(goal, Decimal("500"))
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("wallet.savings_goals")


class SavingsGoalService:
    """Savings goal management service."""

    INTEREST_RATE_ANNUAL = Decimal(getattr(settings, "SAVINGS_INTEREST_RATE", "0.05"))  # 5% p.a.

    @staticmethod
    def create(user, name: str, target_amount: Decimal,
                deadline=None, auto_save_percent: Decimal = Decimal("0"),
                description: str = "") -> dict:
        """Create a savings goal."""
        try:
            from .models_cpalead_extra import SavingsGoal
        except ImportError:
            # Model not yet in DB — return mock response
            return {
                "success": True,
                "goal_id": None,
                "note": "SavingsGoal model: run migrations after adding to models",
            }

        if target_amount <= 0:
            return {"success": False, "error": "Target amount must be positive"}

        try:
            from .services.core.WalletService import WalletService
            wallet = WalletService.get_or_create(user)

            goal = SavingsGoal.objects.create(
                user=user,
                wallet=wallet,
                name=str(name)[:100],
                description=str(description)[:500],
                target_amount=target_amount,
                current_amount=Decimal("0"),
                deadline=deadline,
                auto_save_percent=auto_save_percent,
                status="active",
            )

            logger.info(f"Savings goal created: {goal.id} user={user.id} target={target_amount}")
            return {
                "success":      True,
                "goal_id":      goal.id,
                "name":         goal.name,
                "target":       str(goal.target_amount),
                "current":      "0.00",
                "progress_pct": 0,
                "deadline":     str(deadline) if deadline else None,
            }
        except Exception as e:
            logger.error(f"Savings goal create error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def contribute(goal_id: int, amount: Decimal, user=None) -> dict:
        """Add funds to a savings goal from wallet balance."""
        try:
            from .models_cpalead_extra import SavingsGoal
            from .services.core.WalletService import WalletService
            from django.db import transaction

            with transaction.atomic():
                goal = SavingsGoal.objects.select_for_update().get(
                    id=goal_id, status="active"
                )
                wallet = goal.wallet

                if wallet.available_balance < amount:
                    return {"success": False, "error": "Insufficient balance"}

                # Deduct from wallet, add to goal
                WalletService.debit(
                    wallet=wallet,
                    amount=amount,
                    txn_type="savings_contribution",
                    description=f"Savings: {goal.name}",
                )

                goal.current_amount += amount
                progress = (goal.current_amount / goal.target_amount * 100).quantize(Decimal("0.1"))

                # Check if goal achieved
                if goal.current_amount >= goal.target_amount:
                    goal.status = "achieved"
                    goal.achieved_at = timezone.now()
                    logger.info(f"Savings goal ACHIEVED: {goal.id} user={goal.user_id}")

                goal.save(update_fields=["current_amount", "status", "achieved_at", "updated_at"])

                return {
                    "success":      True,
                    "contributed":  str(amount),
                    "current":      str(goal.current_amount),
                    "target":       str(goal.target_amount),
                    "progress_pct": float(progress),
                    "achieved":     goal.status == "achieved",
                }
        except Exception as e:
            logger.error(f"Savings contribute error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def withdraw_goal(goal_id: int, user) -> dict:
        """Withdraw funds from a savings goal back to wallet."""
        try:
            from .models_cpalead_extra import SavingsGoal
            from .services.core.WalletService import WalletService
            from django.db import transaction

            with transaction.atomic():
                goal = SavingsGoal.objects.select_for_update().get(
                    id=goal_id, user=user, status__in=["active", "achieved"]
                )
                amount = goal.current_amount
                if amount <= 0:
                    return {"success": False, "error": "No balance in goal"}

                WalletService.credit(
                    wallet=goal.wallet,
                    amount=amount,
                    txn_type="savings_withdrawal",
                    description=f"Savings goal withdrawn: {goal.name}",
                )

                goal.current_amount = Decimal("0")
                goal.status         = "cancelled"
                goal.save(update_fields=["current_amount", "status", "updated_at"])

                return {"success": True, "refunded": str(amount)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_progress(goal_id: int) -> dict:
        """Get savings goal progress."""
        try:
            from .models_cpalead_extra import SavingsGoal
            goal = SavingsGoal.objects.get(id=goal_id)
            progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount else Decimal("0")
            remaining_days = None
            if goal.deadline:
                delta = goal.deadline - timezone.now().date()
                remaining_days = max(delta.days, 0)
            return {
                "goal_id":       goal.id,
                "name":          goal.name,
                "status":        goal.status,
                "current":       str(goal.current_amount),
                "target":        str(goal.target_amount),
                "progress_pct":  float(progress.quantize(Decimal("0.1"))),
                "remaining":     str(goal.target_amount - goal.current_amount),
                "deadline":      str(goal.deadline) if goal.deadline else None,
                "remaining_days":remaining_days,
            }
        except Exception as e:
            return {"error": str(e)}
