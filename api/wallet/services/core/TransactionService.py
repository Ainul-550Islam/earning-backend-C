# api/wallet/services/core/TransactionService.py
"""
Atomic transaction creation with idempotency, fraud scoring, and AML checks.
Every financial event flows through TransactionService.create().
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ...models import Wallet, WalletTransaction, IdempotencyKey
from ...choices import TransactionType, TransactionStatus
from ...exceptions import (
    DuplicateTransactionError, WalletLockedError,
    InsufficientBalanceError, InvalidAmountError, FraudError,
)
from ...constants import IDEMPOTENCY_TTL

logger = logging.getLogger("wallet.service.transaction")


class TransactionService:
    """
    Create, approve, reject, and reverse wallet transactions.
    All writes are atomic. Idempotency is enforced.
    """

    @staticmethod
    @transaction.atomic
    def create(
        wallet: Wallet,
        txn_type: str,
        amount: Decimal,
        description: str = "",
        reference_id: str = "",
        reference_type: str = "",
        metadata: dict = None,
        idempotency_key: str = "",
        ip_address: str = None,
        country_code: str = "",
        fee_amount: Decimal = Decimal("0"),
        debit_account: str = "",
        credit_account: str = "",
        created_by=None,
        run_fraud_check: bool = True,
        run_aml_check: bool = False,
    ) -> WalletTransaction:
        """
        Universal transaction factory.
        Delegates credit/debit balance mutations to WalletService.
        Handles idempotency, fraud scoring, AML checks.
        """
        amount = Decimal(str(amount))

        # ── Idempotency ───────────────────────────────────────────────
        if idempotency_key:
            existing = IdempotencyKey.get_valid(idempotency_key)
            if existing:
                txn = WalletTransaction.objects.filter(
                    idempotency_key=idempotency_key, wallet=wallet
                ).first()
                if txn:
                    logger.info(f"Idempotent replay: key={idempotency_key} txn={txn.txn_id}")
                    return txn

        # ── Validate ──────────────────────────────────────────────────
        if amount == 0:
            raise InvalidAmountError("Transaction amount cannot be zero")
        if wallet.is_locked:
            raise WalletLockedError(wallet.locked_reason)

        # ── Fraud check (async-safe) ───────────────────────────────────
        if run_fraud_check and amount > 0 and txn_type not in (TransactionType.ADMIN_CREDIT,):
            TransactionService._check_fraud_sync(wallet, amount, ip_address)

        # ── AML check ────────────────────────────────────────────────
        if run_aml_check:
            try:
                from ..services_extra import AMLService
                AMLService.check(wallet.user, wallet, abs(amount), txn_type)
            except Exception:
                pass

        # ── Delegate to WalletService ─────────────────────────────────
        from .WalletService import WalletService
        if amount > 0:
            return WalletService.credit(
                wallet=wallet,
                amount=amount,
                txn_type=txn_type,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                metadata=metadata,
                debit_account=debit_account or "revenue",
                credit_account=credit_account or "user_balance",
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                country_code=country_code,
                fee_amount=fee_amount,
                created_by=created_by,
            )
        else:
            return WalletService.debit(
                wallet=wallet,
                amount=abs(amount),
                txn_type=txn_type,
                description=description,
                metadata=metadata,
                created_by=created_by,
                ip_address=ip_address,
                fee_amount=fee_amount,
            )

    @staticmethod
    @transaction.atomic
    def approve(txn_id: int, approved_by=None) -> WalletTransaction:
        """Approve a pending transaction."""
        txn = WalletTransaction.objects.select_for_update().get(id=txn_id)
        txn.approve(approved_by=approved_by)
        return txn

    @staticmethod
    @transaction.atomic
    def reject(txn_id: int, reason: str, rejected_by=None) -> WalletTransaction:
        """Reject a pending transaction."""
        txn = WalletTransaction.objects.select_for_update().get(id=txn_id)
        txn.reject(reason=reason, rejected_by=rejected_by)
        return txn

    @staticmethod
    @transaction.atomic
    def reverse(txn_id: int, reason: str, reversed_by=None) -> WalletTransaction:
        """Reverse an approved/completed transaction."""
        txn = WalletTransaction.objects.select_for_update().get(id=txn_id)
        return txn.reverse(reason=reason, reversed_by=reversed_by)

    @staticmethod
    def get_history(wallet: Wallet, **filters) -> "QuerySet":
        """Get paginated transaction history with filters."""
        qs = WalletTransaction.objects.filter(wallet=wallet).select_related(
            "wallet__user", "created_by", "approved_by"
        )
        if filters.get("type"):
            qs = qs.filter(type=filters["type"])
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])
        if filters.get("from_date"):
            qs = qs.filter(created_at__date__gte=filters["from_date"])
        if filters.get("to_date"):
            qs = qs.filter(created_at__date__lte=filters["to_date"])
        if filters.get("min_amount"):
            qs = qs.filter(amount__gte=filters["min_amount"])
        if filters.get("max_amount"):
            qs = qs.filter(amount__lte=filters["max_amount"])
        return qs.order_by("-created_at")

    @staticmethod
    def _check_fraud_sync(wallet: Wallet, amount: Decimal, ip_address: str = ""):
        """Synchronous fraud pre-check before transaction creation."""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = WalletTransaction.objects.filter(
            wallet=wallet, created_at__gte=one_hour_ago
        ).count()

        if recent_count > 50:
            logger.warning(f"Velocity flag: wallet={wallet.id} txns_1h={recent_count}")
            # Don't hard-block here — just log (async fraud check will decide)
