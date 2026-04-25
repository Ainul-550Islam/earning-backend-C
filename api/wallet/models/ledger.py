# api/wallet/models/ledger.py
"""
Double-entry bookkeeping ledger models.

Every financial event produces:
  1. A WalletTransaction (user-facing)
  2. A WalletLedger + two LedgerEntries (one debit, one credit) — internal audit

IdempotencyKey prevents duplicate transactions from duplicate API calls.
LedgerSnapshot stores periodic balance checkpoints for fast reconciliation.
LedgerReconciliation records audit runs comparing wallet vs ledger totals.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from ..choices import LedgerEntryType


class WalletLedger(models.Model):
    """
    Container for a double-entry accounting event.
    Each event has exactly 2 LedgerEntries: one debit, one credit.
    Sum(debits) must always equal Sum(credits) — enforced by is_balanced.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_walletledger_tenant",
        db_index=True,
    )

    ledger_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    wallet      = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.PROTECT,
        related_name="ledgers",
    )
    transaction = models.OneToOneField(
        "wallet.WalletTransaction",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="ledger",
    )
    description = models.TextField(blank=True)
    is_balanced = models.BooleanField(default=False,
                                      help_text="True when sum(debits) == sum(credits)")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_ledger"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["wallet", "-created_at"]),
            models.Index(fields=["ledger_id"]),
        ]

    def __str__(self):
        return f"Ledger {self.ledger_id} | wallet={self.wallet_id} | balanced={self.is_balanced}"

    def check_balance(self) -> bool:
        """Verify debit total equals credit total and update is_balanced."""
        entries = self.entries.all()
        debits  = sum(e.amount for e in entries if e.entry_type == LedgerEntryType.DEBIT)
        credits = sum(e.amount for e in entries if e.entry_type == LedgerEntryType.CREDIT)
        self.is_balanced = abs(debits - credits) < Decimal("0.00000001")
        self.save(update_fields=["is_balanced"])
        return self.is_balanced


class LedgerEntry(models.Model):
    """
    Single line in a double-entry ledger.

    IMMUTABLE: never updated after creation.
    Every LedgerEntry is either a DEBIT or a CREDIT.

    Accounts used (examples):
      user_balance        — the user's spendable wallet
      pending_withdrawal  — funds locked awaiting payout
      revenue             — platform revenue account
      bonus_liability     — outstanding bonus obligations
      frozen_funds        — admin-frozen amounts
    """

    ledger     = models.ForeignKey(WalletLedger, on_delete=models.PROTECT, related_name="entries")
    entry_type = models.CharField(max_length=6, choices=LedgerEntryType.choices, db_index=True)
    account    = models.CharField(max_length=60, db_index=True,
                                  help_text="Account name: user_balance, revenue, bonus_liability, etc.")
    amount     = models.DecimalField(max_digits=20, decimal_places=8,
                                     help_text="Always positive — direction set by entry_type")
    balance_after = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                        help_text="Running balance of this account after this entry")

    # Reference chain
    ref_type   = models.CharField(max_length=60, blank=True,
                                  help_text="earning / withdrawal / bonus / reversal / etc.")
    ref_id     = models.CharField(max_length=200, blank=True,
                                  help_text="External ID of the triggering event")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_ledger_entry"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["ledger", "entry_type"]),
            models.Index(fields=["account"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return (f"LedgerEntry [{self.entry_type.upper()}] "
                f"account={self.account} amount={self.amount}")

    def save(self, *args, **kwargs):
        """Enforce immutability after first save."""
        if self.pk:
            raise ValueError("LedgerEntry is immutable — never update a ledger entry")
        if self.amount <= 0:
            raise ValueError("LedgerEntry.amount must be positive")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("LedgerEntry is immutable — never delete a ledger entry")


class LedgerSnapshot(models.Model):
    """
    Periodic balance snapshot of a wallet account.
    Taken every N transactions or weekly by a Celery task.
    Allows fast reconciliation without scanning all entries from genesis.
    """

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_ledgersnapshot_tenant",
        db_index=True,
    )
    wallet       = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="ledger_snapshots",
    )
    snapshot_date = models.DateField(db_index=True)
    account       = models.CharField(max_length=60, db_index=True)
    balance       = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    entry_count   = models.PositiveBigIntegerField(default=0,
                                                   help_text="Number of entries included in this snapshot")
    last_entry_id = models.BigIntegerField(null=True, blank=True,
                                           help_text="LedgerEntry.pk of the last entry included")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_ledger_snapshot"
        unique_together = [("wallet", "snapshot_date", "account")]
        ordering  = ["-snapshot_date"]

    def __str__(self):
        return (f"Snapshot wallet={self.wallet_id} "
                f"date={self.snapshot_date} account={self.account} balance={self.balance}")


class LedgerReconciliation(models.Model):
    """
    Daily audit run — compares wallet.current_balance vs ledger entries.
    Discrepancies trigger alerts and are investigated before being resolved.
    """

    STATUS_CHOICES = [
        ("ok",          "OK — No Discrepancy"),
        ("discrepancy", "Discrepancy Found"),
        ("investigating","Under Investigation"),
        ("fixed",       "Fixed"),
        ("ignored",     "Ignored (known delta)"),
    ]

    tenant            = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_ledgerrecon_tenant",
        db_index=True,
    )
    wallet            = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="reconciliations",
    )
    reconciled_at     = models.DateTimeField(default=timezone.now, db_index=True)
    period_start      = models.DateTimeField()
    period_end        = models.DateTimeField()

    # What we expected vs what we found
    expected_balance  = models.DecimalField(max_digits=20, decimal_places=8,
                                            help_text="wallet.current_balance at reconcile time")
    actual_balance    = models.DecimalField(max_digits=20, decimal_places=8,
                                            help_text="Sum of ledger entries for this wallet")
    discrepancy       = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                            help_text="expected_balance − actual_balance")

    status            = models.CharField(max_length=15, choices=STATUS_CHOICES, default="ok", db_index=True)
    notes             = models.TextField(blank=True)
    resolved_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_reconciliations_resolved",
    )
    resolved_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_ledger_reconciliation"
        ordering  = ["-reconciled_at"]
        indexes   = [
            models.Index(fields=["wallet", "-reconciled_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (f"Reconciliation wallet={self.wallet_id} "
                f"at={self.reconciled_at} status={self.status} Δ={self.discrepancy}")

    def save(self, *args, **kwargs):
        self.discrepancy = self.expected_balance - self.actual_balance
        super().save(*args, **kwargs)

    @property
    def has_discrepancy(self) -> bool:
        return abs(self.discrepancy) > Decimal("0.00000001")


class IdempotencyKey(models.Model):
    """
    Prevents duplicate transactions from repeated / retried API calls.

    Workflow:
      1. Before crediting: check IdempotencyKey.objects.get(key=key)
      2. If found and not expired → return cached response without re-crediting
      3. If not found → execute credit → create IdempotencyKey

    Keys expire after 24 hours (configurable via settings.IDEMPOTENCY_TTL).
    """

    tenant     = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_idempotencykey_tenant",
        db_index=True,
    )
    key        = models.CharField(max_length=255, unique=True, db_index=True)
    wallet     = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="idempotency_keys",
    )
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="wallet_idempotency_keys",
    )
    amount     = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    response_data = models.JSONField(default=dict, blank=True,
                                     help_text="Cached response payload for replay")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_idempotency_key"
        indexes   = [
            models.Index(fields=["key"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"IdempotencyKey: {self.key} | expires={self.expires_at}"

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @classmethod
    def get_valid(cls, key: str) -> "IdempotencyKey | None":
        """Return a valid (non-expired) idempotency key or None."""
        try:
            ikey = cls.objects.get(key=key)
            if ikey.is_expired():
                ikey.delete()
                return None
            return ikey
        except cls.DoesNotExist:
            return None
