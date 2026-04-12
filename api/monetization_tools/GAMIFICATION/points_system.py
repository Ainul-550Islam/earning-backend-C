"""GAMIFICATION/points_system.py — Points/coins management system."""
from decimal import Decimal
from ..services import RewardService


class PointsSystem:
    @classmethod
    def credit(cls, user, amount: Decimal, txn_type: str, description: str = "",
                reference: str = "") -> object:
        return RewardService.credit(user, amount, transaction_type=txn_type,
                                    description=description, reference_id=reference)

    @classmethod
    def debit(cls, user, amount: Decimal, txn_type: str, description: str = "") -> object:
        return RewardService.debit(user, amount, transaction_type=txn_type, description=description)

    @classmethod
    def balance(cls, user) -> Decimal:
        return getattr(user, "coin_balance", Decimal("0"))

    @classmethod
    def history(cls, user, limit: int = 50) -> list:
        from ..models import RewardTransaction
        return list(
            RewardTransaction.objects.filter(user=user)
              .order_by("-created_at")
              .values("amount", "transaction_type", "description", "created_at")[:limit]
        )
