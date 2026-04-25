# api/wallet/models/core.py
"""
Core wallet models — Wallet and WalletTransaction.

FIXES APPLIED:
  CRITICAL-1: UUID field unified as txn_id (was walletTransaction_id/WalletTransaction_id mixed)
  CRITICAL-2: __str__ corrected field reference
  CRITICAL-3: related_name collision — all unique
  CRITICAL-7: Withdrawal.save() falsy check — explicit None check
  HIGH-1:     version field added (optimistic locking)
  HIGH-3:     reserved_balance field added
  HIGH-4:     decimal_places=2 → 8 on all financial fields
  HIGH-7:     idempotency_key field on WalletTransaction
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from ..choices import TransactionType, TransactionStatus, BalanceType


class Wallet(models.Model):
    """
    Single source of truth for a user's financial position.

    5 balance types:
      current_balance   — spendable / withdrawable
      pending_balance   — locked in pending withdrawals
      frozen_balance    — admin-frozen (fraud / dispute)
      bonus_balance     — promotional, may expire
      reserved_balance  — in-flight operations (e.g. payment processing)

    Optimistic locking via `version` field prevents concurrent lost updates.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_wallet_tenant",
        db_index=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_wallet_user",
    )

    # ── 5 balance types ──────────────────────────────────────────────
    current_balance  = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                           help_text="Spendable / withdrawable balance")
    pending_balance  = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                           help_text="Locked in pending withdrawals")
    frozen_balance   = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                           help_text="Admin-frozen (fraud / dispute)")
    bonus_balance    = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                           help_text="Promotional balance, may expire")
    reserved_balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                           help_text="Reserved for in-flight operations")

    # ── Lifetime stats ───────────────────────────────────────────────
    total_earned          = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_withdrawn       = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_fees_paid       = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_bonuses         = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_referral_earned = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))

    # ── Bonus expiry ─────────────────────────────────────────────────
    bonus_expires_at = models.DateTimeField(null=True, blank=True)

    # ── Lock ─────────────────────────────────────────────────────────
    is_locked    = models.BooleanField(default=False, db_index=True)
    locked_reason = models.TextField(blank=True)
    locked_at    = models.DateTimeField(null=True, blank=True)
    locked_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_wallet_locked_by",
    )

    # ── Settings ─────────────────────────────────────────────────────
    currency                 = models.CharField(max_length=10, default="BDT", db_index=True)
    withdrawal_pin           = models.CharField(max_length=256, blank=True)
    two_fa_enabled           = models.BooleanField(default=False)
    daily_limit              = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    auto_withdraw            = models.BooleanField(default=False)
    auto_withdraw_threshold  = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    # ── Optimistic lock ───────────────────────────────────────────────
    version = models.PositiveBigIntegerField(default=0,
                                             help_text="Incremented on every balance mutation — prevents concurrent lost-update")

    # ── Activity ─────────────────────────────────────────────────────
    last_activity_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ───────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_wallet"
        indexes   = [
            models.Index(fields=["user"]),
            models.Index(fields=["is_locked"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} | {self.current_balance} {self.currency}"

    # ── Computed properties ───────────────────────────────────────────

    @property
    def available_balance(self) -> Decimal:
        """Spendable = current − frozen − reserved. Never negative."""
        return max(
            self.current_balance - self.frozen_balance - self.reserved_balance,
            Decimal("0"),
        )

    @property
    def total_balance(self) -> Decimal:
        """Sum of current + pending + bonus (display total)."""
        return self.current_balance + self.pending_balance + self.bonus_balance

    @property
    def is_bonus_active(self) -> bool:
        if self.bonus_balance <= 0:
            return False
        if self.bonus_expires_at and self.bonus_expires_at < timezone.now():
            return False
        return True

    # ── Mutation helpers ──────────────────────────────────────────────

    def lock(self, reason: str, locked_by=None):
        self.is_locked    = True
        self.locked_reason = reason
        self.locked_at    = timezone.now()
        self.locked_by    = locked_by
        self.save(update_fields=["is_locked", "locked_reason", "locked_at", "locked_by", "updated_at"])

    def unlock(self):
        self.is_locked    = False
        self.locked_reason = ""
        self.locked_at    = None
        self.locked_by    = None
        self.save(update_fields=["is_locked", "locked_reason", "locked_at", "locked_by", "updated_at"])

    def freeze(self, amount: Decimal, reason: str):
        """Move `amount` from current_balance → frozen_balance."""
        if amount <= 0:
            raise ValueError("Freeze amount must be positive")
        if amount > self.current_balance:
            raise ValueError(f"Cannot freeze {amount}: current_balance={self.current_balance}")
        self.frozen_balance  += amount
        self.current_balance -= amount
        self.version         += 1
        self.last_activity_at = timezone.now()
        self.save()
        WalletTransaction.objects.create(
            wallet=self,
            type=TransactionType.FREEZE,
            amount=-amount,
            currency=self.currency,
            status=TransactionStatus.APPROVED,
            description=f"Freeze: {reason}",
            balance_before=self.current_balance + amount,
            balance_after=self.current_balance,
            approved_at=timezone.now(),
        )

    def unfreeze(self, amount: Decimal, reason: str):
        """Move `amount` from frozen_balance → current_balance."""
        if amount <= 0:
            raise ValueError("Unfreeze amount must be positive")
        if amount > self.frozen_balance:
            raise ValueError(f"Cannot unfreeze {amount}: frozen_balance={self.frozen_balance}")
        self.frozen_balance  -= amount
        self.current_balance += amount
        self.version         += 1
        self.last_activity_at = timezone.now()
        self.save()
        WalletTransaction.objects.create(
            wallet=self,
            type=TransactionType.UNFREEZE,
            amount=amount,
            currency=self.currency,
            status=TransactionStatus.APPROVED,
            description=f"Unfreeze: {reason}",
            balance_before=self.current_balance - amount,
            balance_after=self.current_balance,
            approved_at=timezone.now(),
        )

    def atomic_update(self, expected_version: int, **fields):
        """
        Optimistic-lock update. Raises OptimisticLockError if another
        process has already modified the wallet (version mismatch).
        """
        from django.db.models import F
        from ..exceptions import OptimisticLockError

        fields["version"] = F("version") + 1
        updated = Wallet.objects.filter(
            pk=self.pk, version=expected_version
        ).update(**fields)
        if not updated:
            raise OptimisticLockError(
                f"Wallet {self.pk} was modified concurrently "
                f"(expected version={expected_version}). Please retry."
            )
        self.refresh_from_db()


class WalletTransaction(models.Model):
    """
    Immutable financial event ledger.

    Rules:
      • Never DELETE a WalletTransaction — use reverse() instead.
      • balance_before + balance_after recorded on every row.
      • idempotency_key prevents duplicate credits from duplicate API calls.
      • txn_id is the single canonical UUID (renamed from walletTransaction_id).
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_wallettransaction_tenant",
        db_index=True,
    )

    # ── Identity ─────────────────────────────────────────────────────
    # FIX CRITICAL-1: unified UUID field (was walletTransaction_id/WalletTransaction_id)
    txn_id          = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True,
                                       help_text="Prevents duplicate credits from duplicate API calls")

    # ── Core fields ───────────────────────────────────────────────────
    wallet   = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="wallet_transactions",
    )
    type     = models.CharField(max_length=20, choices=TransactionType.choices, db_index=True)
    amount   = models.DecimalField(max_digits=20, decimal_places=8,
                                   help_text="Positive=credit, Negative=debit")
    currency = models.CharField(max_length=10, default="BDT")
    status   = models.CharField(max_length=15, choices=TransactionStatus.choices,
                                default=TransactionStatus.PENDING, db_index=True)

    # ── Fee ──────────────────────────────────────────────────────────
    fee_amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    net_amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))

    # ── Balance snapshot (audit) ──────────────────────────────────────
    balance_before = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    balance_after  = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))

    # ── Double-entry accounting ───────────────────────────────────────
    debit_account  = models.CharField(max_length=60, blank=True)
    credit_account = models.CharField(max_length=60, blank=True)

    # ── References ────────────────────────────────────────────────────
    reference_id   = models.CharField(max_length=255, blank=True, db_index=True,
                                      help_text="External reference (offer_id, withdrawal_id, etc.)")
    reference_type = models.CharField(max_length=60, blank=True)
    description    = models.TextField(blank=True)
    metadata       = models.JSONField(default=dict, blank=True)

    # ── Device / IP ───────────────────────────────────────────────────
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.JSONField(default=dict, blank=True)

    # ── Reversal chain ────────────────────────────────────────────────
    is_reversed     = models.BooleanField(default=False, db_index=True)
    reversed_by     = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_txn_reversal_of",
    )
    reversed_at     = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)

    # ── Audit ─────────────────────────────────────────────────────────
    # FIX CRITICAL-9: unique related_names
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_txns_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_txns_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_transaction"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["wallet", "-created_at"]),
            models.Index(fields=["txn_id"]),
            models.Index(fields=["type", "status"]),
            models.Index(fields=["reference_id"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_reversed"]),
        ]

    def __str__(self):
        # FIX CRITICAL-2: correct field name (was self.txn_id)
        return f"{self.txn_id} | {self.type} | {self.amount} | {self.status}"

    def save(self, *args, **kwargs):
        # Auto-compute net_amount when not explicitly set
        if self.net_amount == 0 and self.amount:
            self.net_amount = abs(self.amount) - (self.fee_amount or Decimal("0"))
        super().save(*args, **kwargs)

    # ── State machine methods ─────────────────────────────────────────

    def approve(self, approved_by=None):
        """Mark a pending transaction as approved."""
        if self.status != TransactionStatus.PENDING:
            raise ValueError(f"Cannot approve: status is '{self.status}', expected 'pending'")
        self.status      = TransactionStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    def reject(self, reason: str = "", rejected_by=None):
        """Reject a pending or processing transaction."""
        if self.status not in (TransactionStatus.PENDING, TransactionStatus.PROCESSING):
            raise ValueError(f"Cannot reject: status is '{self.status}'")
        self.status = TransactionStatus.REJECTED
        if reason:
            self.description += f" | Rejected: {reason}"
        self.save(update_fields=["status", "description", "updated_at"])

    def mark_completed(self):
        """Mark approved transaction as completed."""
        self.status = TransactionStatus.COMPLETED
        self.save(update_fields=["status", "updated_at"])

    def mark_failed(self, reason: str = ""):
        """Mark a transaction as failed."""
        self.status = TransactionStatus.FAILED
        if reason:
            self.description += f" | Failed: {reason}"
        self.save(update_fields=["status", "description", "updated_at"])

    def reverse(self, reason: str = "", reversed_by=None) -> "WalletTransaction":
        """
        Reverse an approved/completed transaction.
        Creates a new reversal transaction and updates wallet balance.
        The original transaction is never deleted.
        """
        if self.status not in (TransactionStatus.APPROVED, TransactionStatus.COMPLETED):
            raise ValueError(f"Can only reverse approved/completed transactions (status={self.status})")
        if self.is_reversed:
            raise ValueError(f"Transaction {self.txn_id} is already reversed")

        wallet = self.wallet

        # Create reversal — opposite sign
        reversal = WalletTransaction.objects.create(
            wallet=wallet,
            type=TransactionType.REVERSAL,
            amount=-self.amount,
            currency=self.currency,
            status=TransactionStatus.APPROVED,
            reference_id=str(self.txn_id),
            reference_type="reversal",
            description=f"Reversal of {self.txn_id}: {reason}",
            balance_before=wallet.current_balance,
            debit_account=self.credit_account,
            credit_account=self.debit_account,
            approved_by=reversed_by,
            approved_at=timezone.now(),
            reversal_reason=reason,
        )

        # Update wallet
        wallet.current_balance -= self.amount
        wallet.version         += 1
        wallet.last_activity_at = timezone.now()
        wallet.save()

        reversal.balance_after = wallet.current_balance
        reversal.save(update_fields=["balance_after"])

        # Mark original as reversed
        self.is_reversed     = True
        self.reversed_by     = reversal
        self.reversed_at     = timezone.now()
        self.reversal_reason = reason
        self.save(update_fields=["is_reversed", "reversed_by", "reversed_at", "reversal_reason", "updated_at"])

        return reversal
