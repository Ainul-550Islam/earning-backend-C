# api/wallet/models/withdrawal.py
"""
Withdrawal models — complete withdrawal lifecycle.

Models:
  WithdrawalRequest  — user's withdrawal request (pending → approved → completed)
  WithdrawalMethod   — user's saved payout accounts (bKash, Nagad, bank, USDT…)
  WithdrawalLimit    — tier-based daily/monthly limits
  WithdrawalFee      — per-gateway fee configuration (flat / percent / hybrid)
  WithdrawalBatch    — batch multiple withdrawals into a single gateway call
  WithdrawalBlock    — block a user from withdrawing (fraud, AML, dispute)
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from ..choices import GatewayType, WithdrawalStatus, FeeType, WithdrawalBlockReason, UserTier


class WithdrawalMethod(models.Model):
    """
    User's saved payout account — bKash, Nagad, Rocket, bank, USDT, PayPal…
    One user can have multiple methods; exactly one can be is_default=True.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalmethod_tenant",
        db_index=True,
    )
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdrawal_methods",
    )
    method_type = models.CharField(max_length=20, choices=GatewayType.choices, db_index=True)

    # Account identifiers
    account_number = models.CharField(max_length=200)
    account_name   = models.CharField(max_length=150)

    # Bank-specific
    bank_name      = models.CharField(max_length=150, blank=True)
    branch_name    = models.CharField(max_length=150, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code     = models.CharField(max_length=20, blank=True)

    # Card-specific
    card_last_four = models.CharField(max_length=4, blank=True)
    card_expiry    = models.CharField(max_length=7, blank=True)

    # Crypto-specific
    crypto_network = models.CharField(max_length=20, blank=True)
    crypto_address = models.CharField(max_length=200, blank=True)

    # Status
    is_verified    = models.BooleanField(default=False, db_index=True)
    is_default     = models.BooleanField(default=False, db_index=True)
    is_whitelisted = models.BooleanField(default=False,
                                         help_text="Binance-style: address in whitelist (active after 24h)")

    # Audit
    verified_at    = models.DateTimeField(null=True, blank=True)
    verified_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_methods_verified",
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_method"
        ordering  = ["-is_default", "-created_at"]
        unique_together = [("user", "method_type", "account_number")]
        indexes   = [
            models.Index(fields=["user", "is_default"]),
            models.Index(fields=["method_type", "is_verified"]),
        ]

    def __str__(self):
        return (f"{self.user.username} | "
                f"{self.get_method_type_display()} | "
                f"****{self.account_number[-4:] if len(self.account_number) >= 4 else self.account_number}")

    def verify(self, verified_by=None):
        self.is_verified = True
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.save(update_fields=["is_verified", "verified_at", "verified_by", "updated_at"])

    def set_default(self):
        """Set this method as default; clear any existing default."""
        WithdrawalMethod.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        self.is_default = True
        self.save(update_fields=["is_default", "updated_at"])


class WithdrawalRequest(models.Model):
    """
    A single withdrawal request from a user.

    State machine:
      pending → approved → processing → completed
      pending → rejected
      pending/approved/processing → cancelled (by user)
      processing → failed → (admin can retry)

    When created:
      wallet.current_balance  -= amount
      wallet.pending_balance  += amount

    When completed:
      wallet.pending_balance  -= amount
      wallet.total_withdrawn  += amount

    When rejected/cancelled:
      wallet.current_balance  += amount  (refunded)
      wallet.pending_balance  -= amount
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalrequest_tenant",
        db_index=True,
    )

    withdrawal_id  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_withdrawal_requests",
    )
    wallet         = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.PROTECT,
        related_name="withdrawal_requests",
    )
    payment_method = models.ForeignKey(
        WithdrawalMethod,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="withdrawal_requests",
    )
    transaction    = models.OneToOneField(
        "wallet.WalletTransaction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="withdrawal_request",
    )
    batch          = models.ForeignKey(
        "WithdrawalBatch",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="withdrawal_requests",
    )

    # Amounts
    amount         = models.DecimalField(max_digits=20, decimal_places=8)
    fee            = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    net_amount     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    currency       = models.CharField(max_length=10, default="BDT")

    # State
    status         = models.CharField(max_length=15, choices=WithdrawalStatus.choices,
                                      default=WithdrawalStatus.PENDING, db_index=True)
    priority       = models.PositiveSmallIntegerField(default=5,
                                                      help_text="1=highest, 10=lowest")

    # Processing
    processed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawals_processed",
    )
    processed_at   = models.DateTimeField(null=True, blank=True)

    # Rejection / cancellation
    rejection_reason     = models.TextField(blank=True)
    rejected_at          = models.DateTimeField(null=True, blank=True)
    cancellation_reason  = models.TextField(blank=True)
    cancelled_at         = models.DateTimeField(null=True, blank=True)

    # Gateway
    gateway_reference = models.CharField(max_length=200, blank=True, db_index=True)
    gateway_response  = models.JSONField(default=dict, blank=True)
    gateway_status    = models.CharField(max_length=50, blank=True)

    # Security
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    # Admin note
    admin_note      = models.TextField(blank=True)

    # Timestamps
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_request"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["withdrawal_id"]),
            models.Index(fields=["gateway_reference"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self):
        return (f"Withdrawal {self.withdrawal_id} | "
                f"{self.user.username} | {self.amount} {self.currency} | {self.status}")

    def save(self, *args, **kwargs):
        # FIX CRITICAL-7: explicit None check (not falsy — fee=0 is valid)
        if self.net_amount is None or (self.net_amount == 0 and self.amount and self.fee is not None):
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)

    def approve(self, approved_by=None):
        if self.status != WithdrawalStatus.PENDING:
            raise ValueError(f"Cannot approve: status='{self.status}'")
        self.status       = WithdrawalStatus.APPROVED
        self.processed_by = approved_by
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_by", "processed_at", "updated_at"])

    def reject(self, reason: str, rejected_by=None):
        if self.status not in (WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING):
            raise ValueError(f"Cannot reject: status='{self.status}'")
        self.status           = WithdrawalStatus.REJECTED
        self.rejection_reason = reason
        self.rejected_at      = timezone.now()
        self.processed_by     = rejected_by
        self.save(update_fields=["status", "rejection_reason", "rejected_at", "processed_by", "updated_at"])

    def cancel(self, reason: str = ""):
        if self.status in (WithdrawalStatus.COMPLETED, WithdrawalStatus.REJECTED):
            raise ValueError(f"Cannot cancel: status='{self.status}'")
        self.status              = WithdrawalStatus.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at        = timezone.now()
        self.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])

    def complete(self, gateway_ref: str = "", gateway_resp: dict = None):
        self.status           = WithdrawalStatus.COMPLETED
        self.gateway_reference = gateway_ref
        self.gateway_response  = gateway_resp or {}
        self.processed_at     = timezone.now()
        self.save(update_fields=["status", "gateway_reference", "gateway_response", "processed_at", "updated_at"])

    def mark_failed(self, reason: str = ""):
        self.status       = WithdrawalStatus.FAILED
        self.admin_note   += f" | Failed: {reason}"
        self.save(update_fields=["status", "admin_note", "updated_at"])


class WithdrawalLimit(models.Model):
    """
    Tier-based withdrawal limits.
    Checked by WithdrawalLimitService before allowing a withdrawal.
    """

    TIER_CHOICES = UserTier.choices + [("ALL", "All Tiers (default)")]
    PERIOD_CHOICES = [
        ("daily",   "Daily"),
        ("weekly",  "Weekly"),
        ("monthly", "Monthly"),
    ]

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawallimit_tenant",
        db_index=True,
    )
    tier         = models.CharField(max_length=10, choices=TIER_CHOICES, default="ALL", db_index=True)
    gateway      = models.CharField(max_length=20, choices=GatewayType.choices + [("ALL","All Gateways")], default="ALL")
    period       = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="daily")

    # Limits
    limit_amount = models.DecimalField(max_digits=20, decimal_places=2,
                                       help_text="Max total per period")
    min_amount   = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("50"),
                                       help_text="Min single withdrawal")
    max_single   = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("100000"),
                                       help_text="Max single withdrawal amount")
    max_count    = models.PositiveIntegerField(default=10,
                                               help_text="Max number of withdrawals per period")
    is_active    = models.BooleanField(default=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_limit"
        unique_together = [("tier", "gateway", "period")]
        ordering  = ["tier", "period"]

    def __str__(self):
        return (f"Limit tier={self.tier} gateway={self.gateway} "
                f"period={self.period} max={self.limit_amount}")


class WithdrawalFee(models.Model):
    """
    Per-gateway fee configuration.
    FeeType:
      flat    — fixed fee regardless of amount
      percent — percentage of amount
      hybrid  — flat + percentage (e.g. 5 BDT + 1.5%)
    """

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalfee_tenant",
        db_index=True,
    )
    gateway      = models.CharField(max_length=20, choices=GatewayType.choices, db_index=True)
    tier         = models.CharField(max_length=10, choices=UserTier.choices + [("ALL","All")], default="ALL")
    fee_type     = models.CharField(max_length=10, choices=FeeType.choices, default=FeeType.PERCENT)

    # Fee values
    fee_percent  = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("2.0000"),
                                       help_text="Percentage e.g. 2.0 = 2%")
    flat_fee     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"),
                                       help_text="Flat fee in BDT")
    min_fee      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("5"),
                                       help_text="Minimum fee charged")
    max_fee      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Maximum fee cap (None = no cap)")

    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_fee"
        unique_together = [("gateway", "tier")]
        ordering  = ["gateway", "tier"]

    def __str__(self):
        return (f"Fee gateway={self.gateway} tier={self.tier} "
                f"type={self.fee_type} pct={self.fee_percent}% flat={self.flat_fee}")

    def calculate(self, amount: Decimal) -> Decimal:
        """Calculate the fee for a given withdrawal amount."""
        if self.fee_type == FeeType.FLAT:
            fee = self.flat_fee
        elif self.fee_type == FeeType.PERCENT:
            fee = (amount * self.fee_percent / 100).quantize(Decimal("0.01"))
        else:  # HYBRID
            fee = self.flat_fee + (amount * self.fee_percent / 100).quantize(Decimal("0.01"))

        fee = max(fee, self.min_fee)
        if self.max_fee is not None:
            fee = min(fee, self.max_fee)
        return fee


class WithdrawalBatch(models.Model):
    """
    Groups multiple WithdrawalRequests for a single gateway API call.
    E.g. bKash B2C bulk transfer — 100 payments in one API call.
    """

    STATUS_CHOICES = [
        ("pending",    "Pending"),
        ("processing", "Processing"),
        ("completed",  "Completed"),
        ("partial",    "Partial Success"),
        ("failed",     "Failed"),
    ]

    tenant          = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalbatch_tenant",
        db_index=True,
    )
    batch_id        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    gateway         = models.CharField(max_length=20, choices=GatewayType.choices)
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending", db_index=True)

    # Stats
    total_amount    = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    total_count     = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    failed_count    = models.PositiveIntegerField(default=0)

    # Gateway
    gateway_batch_id   = models.CharField(max_length=200, blank=True)
    gateway_response   = models.JSONField(default=dict, blank=True)

    # Timing
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_batches_created",
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    started_at      = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_batch"
        ordering  = ["-created_at"]

    def __str__(self):
        return (f"Batch {self.batch_id} | gateway={self.gateway} "
                f"count={self.total_count} status={self.status}")


class WithdrawalBlock(models.Model):
    """
    Blocks a user from making withdrawal requests.
    Reasons: fraud, AML, dispute, chargebacks, admin hold.
    Auto-expires at unblock_at (or permanent if unblock_at is None).
    """

    tenant      = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalblock_tenant",
        db_index=True,
    )
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdrawal_blocks",
    )
    wallet      = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="withdrawal_blocks",
    )
    reason      = models.CharField(max_length=20, choices=WithdrawalBlockReason.choices)
    detail      = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)

    # Timing
    blocked_at  = models.DateTimeField(default=timezone.now)
    unblock_at  = models.DateTimeField(null=True, blank=True,
                                       help_text="Auto-unblock at this time. None = permanent until admin action.")
    unblocked_at = models.DateTimeField(null=True, blank=True)

    # Audit
    blocked_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_blocks_created",
    )
    unblocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_blocks_released",
    )
    unblock_reason = models.TextField(blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_block"
        ordering  = ["-blocked_at"]
        indexes   = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return (f"Block {self.user.username} | reason={self.reason} "
                f"active={self.is_active} until={self.unblock_at}")

    def is_currently_active(self) -> bool:
        if not self.is_active:
            return False
        if self.unblock_at and timezone.now() >= self.unblock_at:
            # Auto-expire
            self.is_active    = False
            self.unblocked_at = timezone.now()
            self.save(update_fields=["is_active", "unblocked_at"])
            return False
        return True

    def release(self, by=None, reason: str = ""):
        self.is_active      = False
        self.unblocked_at   = timezone.now()
        self.unblocked_by   = by
        self.unblock_reason = reason
        self.save(update_fields=["is_active", "unblocked_at", "unblocked_by", "unblock_reason"])
