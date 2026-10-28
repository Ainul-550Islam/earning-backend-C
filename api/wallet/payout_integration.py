"""
api/wallet/payout_integration.py
=================================
Wallet balance bridge for api.payout_queue.

HOW IT WORKS
------------
services._setup_batch_for_processing() calls deduct_payout_wallet() after
acquiring the batch lock when PAYOUT_WALLET_CHECK_ENABLED=True.

This reserves the batch's total_amount from the platform's payout wallet
before any gateway calls are made. This prevents over-disbursement when
multiple batches are processed concurrently.

On failure (InsufficientFundsError or any exception), the batch is
immediately failed and the lock released — no gateway calls are made.

WALLET MODEL ASSUMPTIONS
-------------------------
This integration assumes your api.wallet app has a model roughly like:

    class WalletAccount(models.Model):
        tenant_id         = models.UUIDField(db_index=True)
        account_type      = models.CharField(max_length=20)  # "PAYOUT"
        available_balance = models.DecimalField(max_digits=14, decimal_places=2)
        is_active         = models.BooleanField(default=True)

    class WalletTransaction(models.Model):
        account          = models.ForeignKey(WalletAccount, ...)
        amount           = models.DecimalField(...)   # negative = debit
        transaction_type = models.CharField(...)       # "PAYOUT_RESERVE"
        reference        = models.CharField(...)       # batch ID

Adjust field names in the functions below to match your actual models.

DISABLE IN DEVELOPMENT
-----------------------
    PAYOUT_WALLET_CHECK_ENABLED=False  (in .env / settings/local.py)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction

logger = logging.getLogger(__name__)


def get_payout_wallet_balance(tenant_id: Any) -> Decimal:
    """
    Returns the current available balance of the tenant's PAYOUT wallet.

    Args:
        tenant_id: UUID of the tenant.

    Returns:
        Decimal available balance (BDT).

    Raises:
        WalletNotFoundError (or ValueError) if no active PAYOUT wallet exists.
    """
    if tenant_id is None:
        raise ValueError("tenant_id must not be None.")
    try:
        from api.wallet.models import WalletAccount
    except ImportError as exc:
        raise ImportError(f"api.wallet.models not available: {exc}") from exc

    account = WalletAccount.objects.filter(
        tenant_id=tenant_id,
        account_type="PAYOUT",
        is_active=True,
    ).first()

    if account is None:
        raise ValueError(
            f"No active PAYOUT wallet found for tenant_id={tenant_id}. "
            f"Create a PAYOUT wallet before processing batches."
        )
    return account.available_balance


@transaction.atomic
def deduct_payout_wallet(
    *,
    tenant_id: Any,
    amount: Decimal,
    reference: str,
) -> None:
    """
    Reserve `amount` from the tenant's PAYOUT wallet before batch processing.

    Uses select_for_update() to prevent concurrent over-deductions.
    Creates a WalletTransaction record for audit purposes.

    Args:
        tenant_id: UUID of the tenant.
        amount:    Total amount to reserve (batch.total_amount, BDT).
        reference: Unique reference for the transaction (batch.id as string).

    Raises:
        InsufficientFundsError: If available_balance < amount.
        ValueError:             If no active PAYOUT wallet exists.
        ImportError:            If api.wallet.models is not available.
    """
    if tenant_id is None:
        raise ValueError("tenant_id must not be None.")
    if not amount or amount <= Decimal("0"):
        raise ValueError(f"amount must be positive, got {amount}.")
    if not reference:
        raise ValueError("reference must not be empty.")

    try:
        from api.wallet.models import WalletAccount, WalletTransaction
    except ImportError as exc:
        raise ImportError(f"api.wallet.models not available: {exc}") from exc

    from api.payout_queue.exceptions import InsufficientFundsError

    account = (
        WalletAccount.objects
        .select_for_update()
        .filter(tenant_id=tenant_id, account_type="PAYOUT", is_active=True)
        .first()
    )
    if account is None:
        raise ValueError(
            f"No active PAYOUT wallet found for tenant_id={tenant_id}."
        )

    if account.available_balance < amount:
        raise InsufficientFundsError(
            f"Payout wallet balance {account.available_balance} BDT "
            f"is less than batch total {amount} BDT "
            f"(tenant={tenant_id})."
        )

    account.available_balance -= amount
    account.save(update_fields=["available_balance", "updated_at"])

    # Record the transaction for audit trail
    try:
        WalletTransaction.objects.create(
            account=account,
            amount=-amount,
            transaction_type="PAYOUT_RESERVE",
            reference=reference,
            description=f"Payout batch reserve — batch_id={reference}",
        )
    except Exception as exc:
        # Transaction record failure should not roll back the deduction
        # (deduction is the critical part; the record is secondary).
        logger.error(
            "deduct_payout_wallet: created deduction but WalletTransaction "
            "record failed: %s. Reference=%s amount=%s",
            exc, reference, amount,
        )

    logger.info(
        "deduct_payout_wallet: reserved %s BDT from tenant=%s wallet. "
        "New balance=%s. Reference=%s",
        amount, tenant_id, account.available_balance, reference,
    )


@transaction.atomic
def refund_payout_wallet(
    *,
    tenant_id: Any,
    amount: Decimal,
    reference: str,
    reason: str = "",
) -> None:
    """
    Refund a previously reserved amount back to the payout wallet.

    Call this when a batch is CANCELLED after deduction, or when the
    failure count means not all reserved funds were disbursed.

    Args:
        tenant_id: UUID of the tenant.
        amount:    Amount to refund (BDT).
        reference: Original batch_id used in deduct_payout_wallet().
        reason:    Human-readable reason for the refund.
    """
    if tenant_id is None or not amount or amount <= Decimal("0"):
        return

    try:
        from api.wallet.models import WalletAccount, WalletTransaction
    except ImportError:
        logger.warning("refund_payout_wallet: api.wallet.models not available.")
        return

    account = (
        WalletAccount.objects
        .select_for_update()
        .filter(tenant_id=tenant_id, account_type="PAYOUT", is_active=True)
        .first()
    )
    if account is None:
        logger.error(
            "refund_payout_wallet: no PAYOUT wallet for tenant=%s — "
            "refund of %s BDT lost!",
            tenant_id, amount,
        )
        return

    account.available_balance += amount
    account.save(update_fields=["available_balance", "updated_at"])

    try:
        WalletTransaction.objects.create(
            account=account,
            amount=amount,
            transaction_type="PAYOUT_REFUND",
            reference=reference,
            description=f"Payout batch refund — {reason or reference}",
        )
    except Exception as exc:
        logger.error(
            "refund_payout_wallet: WalletTransaction record failed: %s", exc
        )

    logger.info(
        "refund_payout_wallet: refunded %s BDT to tenant=%s. "
        "New balance=%s. Reference=%s reason=%r",
        amount, tenant_id, account.available_balance, reference, reason,
    )
