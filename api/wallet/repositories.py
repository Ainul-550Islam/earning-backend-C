# api/wallet/repositories.py
"""
Repository pattern — data access layer abstraction.
Separates domain logic from persistence details.

Benefits:
  - Easy to test (mock the repository)
  - Can swap storage backend without changing business logic
  - Consistent data access interface

Usage:
    repo = WalletRepository()
    wallet = repo.get_by_user(user)
    repo.save(wallet)
"""
import logging
from decimal import Decimal
from typing import Optional, List
from django.db import transaction

logger = logging.getLogger("wallet.repositories")


class WalletRepository:
    """Repository for Wallet model."""

    def get_by_user(self, user) -> Optional[object]:
        try:
            from .models.core import Wallet
            return Wallet.objects.select_related("user").get(user=user)
        except Exception:
            return None

    def get_by_id(self, wallet_id: int) -> Optional[object]:
        try:
            from .models.core import Wallet
            return Wallet.objects.select_related("user").get(id=wallet_id)
        except Exception:
            return None

    def get_or_create(self, user) -> tuple:
        from .models.core import Wallet
        return Wallet.objects.get_or_create(user=user, defaults={"currency": "BDT"})

    def save(self, wallet, update_fields: list = None) -> None:
        if update_fields:
            wallet.save(update_fields=update_fields + ["updated_at"])
        else:
            wallet.save()

    def lock(self, wallet, reason: str, locked_by=None) -> None:
        from django.utils import timezone
        wallet.is_locked    = True
        wallet.locked_reason = reason
        wallet.locked_at    = timezone.now()
        wallet.locked_by    = locked_by
        wallet.save(update_fields=["is_locked","locked_reason","locked_at","locked_by","updated_at"])

    def unlock(self, wallet) -> None:
        wallet.is_locked    = False
        wallet.locked_reason = ""
        wallet.locked_at    = None
        wallet.save(update_fields=["is_locked","locked_reason","locked_at","updated_at"])

    def list_all(self) -> object:
        from .models.core import Wallet
        return Wallet.objects.select_related("user").all()

    def list_locked(self) -> object:
        from .models.core import Wallet
        return Wallet.objects.filter(is_locked=True).select_related("user")

    def list_with_pending_balance(self) -> object:
        from .models.core import Wallet
        return Wallet.objects.filter(pending_balance__gt=0).select_related("user")


class TransactionRepository:
    """Repository for WalletTransaction model."""

    def get_by_txn_id(self, txn_id: str) -> Optional[object]:
        try:
            from .models.core import WalletTransaction
            return WalletTransaction.objects.select_related(
                "wallet__user","created_by","approved_by"
            ).get(txn_id=txn_id)
        except Exception:
            return None

    def create(self, **kwargs) -> object:
        from .models.core import WalletTransaction
        return WalletTransaction.objects.create(**kwargs)

    def list_for_wallet(self, wallet, limit: int = 100) -> object:
        from .models.core import WalletTransaction
        return WalletTransaction.objects.filter(
            wallet=wallet
        ).select_related("created_by").order_by("-created_at")[:limit]

    def list_pending(self) -> object:
        from .models.core import WalletTransaction
        return WalletTransaction.objects.filter(status="pending").select_related("wallet__user")

    def mark_reversed(self, txn, reversal, reversed_by=None) -> None:
        from django.utils import timezone
        txn.is_reversed  = True
        txn.reversed_by  = reversal
        txn.reversed_at  = timezone.now()
        txn.save(update_fields=["is_reversed","reversed_by","reversed_at"])


class WithdrawalRepository:
    """Repository for WithdrawalRequest model."""

    def get_by_id(self, withdrawal_id: str) -> Optional[object]:
        try:
            from .models.withdrawal import WithdrawalRequest
            return WithdrawalRequest.objects.select_related(
                "user","wallet","payment_method","processed_by"
            ).get(withdrawal_id=withdrawal_id)
        except Exception:
            return None

    def list_pending(self) -> object:
        from .models.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(status="pending").select_related(
            "user","wallet","payment_method"
        ).order_by("created_at")

    def list_for_user(self, user) -> object:
        from .models.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(user=user).order_by("-created_at")

    def pending_count(self) -> int:
        from .models.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(status="pending").count()

    def save(self, wr, update_fields: list = None) -> None:
        if update_fields:
            wr.save(update_fields=update_fields + ["updated_at"])
        else:
            wr.save()


class PaymentMethodRepository:
    """Repository for WithdrawalMethod model."""

    def get_for_user(self, user, method_id: int) -> Optional[object]:
        try:
            from .models.withdrawal import WithdrawalMethod
            return WithdrawalMethod.objects.get(id=method_id, user=user)
        except Exception:
            return None

    def list_for_user(self, user, verified_only: bool = False) -> object:
        from .models.withdrawal import WithdrawalMethod
        qs = WithdrawalMethod.objects.filter(user=user).order_by("-is_default","-created_at")
        if verified_only:
            qs = qs.filter(is_verified=True)
        return qs

    def get_default(self, user) -> Optional[object]:
        try:
            from .models.withdrawal import WithdrawalMethod
            return WithdrawalMethod.objects.get(user=user, is_default=True)
        except Exception:
            return None


class EarningRepository:
    """Repository for EarningRecord model."""

    def create(self, **kwargs) -> object:
        from .models.earning import EarningRecord
        return EarningRecord.objects.create(**kwargs)

    def list_for_wallet(self, wallet, days: int = 30) -> object:
        from .models.earning import EarningRecord
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return EarningRecord.objects.filter(
            wallet=wallet, earned_at__gte=cutoff
        ).order_by("-earned_at")

    def total_today(self, wallet) -> Decimal:
        from .models.earning import EarningRecord
        from django.utils import timezone
        from django.db.models import Sum
        result = EarningRecord.objects.filter(
            wallet=wallet,
            earned_at__date=timezone.now().date(),
        ).aggregate(t=Sum("amount"))["t"]
        return result or Decimal("0")


# ── Repository container (simple DI) ─────────────────────────
class Repositories:
    """Container for all repositories."""
    wallets      = WalletRepository()
    transactions = TransactionRepository()
    withdrawals  = WithdrawalRepository()
    methods      = PaymentMethodRepository()
    earnings     = EarningRepository()

repos = Repositories()
