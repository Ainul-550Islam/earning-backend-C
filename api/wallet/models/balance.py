# api/wallet/models/balance.py
"""
Balance management models.

BalanceHistory  — immutable log of every balance change per balance type
BalanceLock     — temporary lock on part of a balance (e.g. escrow)
BalanceAlert    — user-configured alerts (low balance, large credit, etc.)
BalanceReserve  — reserve a portion of balance for a specific purpose
BalanceBonus    — promotional bonus grants with expiry and claim tracking
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from ..choices import BalanceType, AlertType


class BalanceHistory(models.Model):
    """
    Immutable audit log of every balance-type change on a wallet.

    Created automatically by signals/services whenever a balance field changes.
    Allows reconstruction of any balance at any point in time.
    """

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balancehistory_tenant",
        db_index=True,
    )
    wallet       = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="balance_history",
    )
    balance_type = models.CharField(max_length=10, choices=BalanceType.choices, db_index=True)

    # Before / after values
    previous     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                       help_text="Balance before this change")
    new_value    = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                       help_text="Balance after this change")
    delta        = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                       help_text="new_value − previous (positive=credit, negative=debit)")

    # Cause
    reason       = models.CharField(max_length=200, blank=True,
                                    help_text="Human-readable reason for this change")
    reference_id = models.CharField(max_length=255, blank=True,
                                    help_text="ID of the triggering transaction/event")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balance_changes",
    )
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_balance_history"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["wallet", "balance_type", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        sign = "+" if self.delta >= 0 else ""
        return (f"BalanceHistory wallet={self.wallet_id} "
                f"type={self.balance_type} {sign}{self.delta} → {self.new_value}")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("BalanceHistory is immutable — never update a history record")
        self.delta = self.new_value - self.previous
        super().save(*args, **kwargs)


class BalanceLock(models.Model):
    """
    Temporary hold on a portion of a wallet balance.
    Used for escrow, pending verification, dispute holds, etc.

    When created:    wallet.reserved_balance += locked_amount
    When released:   wallet.reserved_balance -= locked_amount
    When consumed:   wallet.reserved_balance -= locked_amount (funds used)
    """

    STATUS_CHOICES = [
        ("active",   "Active"),
        ("released", "Released"),
        ("consumed", "Consumed — funds used"),
        ("expired",  "Expired"),
    ]

    tenant        = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balancelock_tenant",
        db_index=True,
    )
    lock_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet        = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="balance_locks",
    )
    locked_amount = models.DecimalField(max_digits=20, decimal_places=8)
    balance_type  = models.CharField(max_length=10, choices=BalanceType.choices,
                                     default=BalanceType.CURRENT)
    reason        = models.CharField(max_length=200)
    reference_id  = models.CharField(max_length=255, blank=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)

    # Timing
    expires_at    = models.DateTimeField(null=True, blank=True,
                                         help_text="Auto-release lock after this time")
    locked_at     = models.DateTimeField(default=timezone.now)
    released_at   = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balance_locks_created",
    )
    released_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balance_locks_released",
    )

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_balance_lock"
        ordering  = ["-locked_at"]
        indexes   = [
            models.Index(fields=["wallet", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return (f"BalanceLock {self.lock_id} | wallet={self.wallet_id} "
                f"amount={self.locked_amount} status={self.status}")

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def release(self, released_by=None):
        """Release the lock and restore reserved_balance."""
        if self.status != "active":
            raise ValueError(f"Cannot release lock in status '{self.status}'")
        self.status      = "released"
        self.released_at = timezone.now()
        self.released_by = released_by
        self.save(update_fields=["status", "released_at", "released_by"])

        # Restore reserved balance
        wallet = self.wallet
        wallet.reserved_balance = max(wallet.reserved_balance - self.locked_amount, Decimal("0"))
        wallet.save(update_fields=["reserved_balance", "updated_at"])

    def consume(self):
        """Consume the lock — funds are used (deducted from wallet)."""
        if self.status != "active":
            raise ValueError(f"Cannot consume lock in status '{self.status}'")
        self.status      = "consumed"
        self.released_at = timezone.now()
        self.save(update_fields=["status", "released_at"])


class BalanceAlert(models.Model):
    """
    User-configured alert triggers for balance events.
    E.g. "notify me when balance drops below 500 BDT"
         "notify me when I receive a credit > 1000 BDT"
    """

    tenant        = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balancealert_tenant",
        db_index=True,
    )
    wallet        = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="balance_alerts",
    )
    alert_type    = models.CharField(max_length=20, choices=AlertType.choices, db_index=True)
    threshold     = models.DecimalField(max_digits=20, decimal_places=2,
                                        help_text="Amount threshold that triggers the alert")
    is_active     = models.BooleanField(default=True)

    # Delivery preferences
    notify_email  = models.BooleanField(default=True)
    notify_push   = models.BooleanField(default=True)
    notify_sms    = models.BooleanField(default=False)

    # Cooldown
    cooldown_hours = models.PositiveSmallIntegerField(default=24,
                                                      help_text="Min hours between repeat alerts")
    last_sent     = models.DateTimeField(null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_balance_alert"
        ordering  = ["alert_type"]

    def __str__(self):
        return (f"BalanceAlert wallet={self.wallet_id} "
                f"type={self.alert_type} threshold={self.threshold}")

    def should_trigger(self, current_value: Decimal) -> bool:
        """Return True if alert condition is met and cooldown has passed."""
        if not self.is_active:
            return False
        if self.last_sent:
            from datetime import timedelta
            cooldown_end = self.last_sent + timedelta(hours=self.cooldown_hours)
            if timezone.now() < cooldown_end:
                return False

        if self.alert_type == AlertType.LOW_BALANCE:
            return current_value < self.threshold
        elif self.alert_type == AlertType.HIGH_BALANCE:
            return current_value > self.threshold
        elif self.alert_type in (AlertType.LARGE_CREDIT, AlertType.LARGE_DEBIT):
            return abs(current_value) >= self.threshold
        return False

    def mark_sent(self):
        self.last_sent = timezone.now()
        self.save(update_fields=["last_sent"])


class BalanceReserve(models.Model):
    """
    Reserve a specific amount from a wallet for a specific purpose.
    E.g. "reserve 500 BDT for pending KYC fee"
         "reserve 1000 BDT for contest entry"

    The reserved amount is subtracted from available_balance but stays
    in current_balance until consumed or released.
    """

    STATUS_CHOICES = [
        ("active",   "Active"),
        ("released", "Released"),
        ("consumed", "Consumed"),
        ("expired",  "Expired"),
    ]

    tenant        = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balancereserve_tenant",
        db_index=True,
    )
    reserve_id     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet         = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="balance_reserves",
    )
    reserved_amount = models.DecimalField(max_digits=20, decimal_places=8)
    purpose        = models.CharField(max_length=200)
    reference_id   = models.CharField(max_length=255, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)

    expires_at     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    released_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_balance_reserve"
        ordering  = ["-created_at"]

    def __str__(self):
        return (f"BalanceReserve {self.reserve_id} | wallet={self.wallet_id} "
                f"amount={self.reserved_amount} status={self.status}")

    def release(self):
        """Release reserve — restore to available."""
        if self.status != "active":
            raise ValueError(f"Cannot release reserve in status '{self.status}'")
        self.status      = "released"
        self.released_at = timezone.now()
        self.save(update_fields=["status", "released_at"])

        wallet = self.wallet
        wallet.reserved_balance = max(wallet.reserved_balance - self.reserved_amount, Decimal("0"))
        wallet.save(update_fields=["reserved_balance", "updated_at"])


class BalanceBonus(models.Model):
    """
    Promotional bonus grant to a user's wallet.

    Bonus types:
      signup        — welcome bonus for new users
      referral      — bonus for referring a new user
      promo         — time-limited promotional bonus
      loyalty       — recurring loyalty reward
      contest       — contest prize
      compensation  — admin compensation for service issues
      streak        — daily streak milestone bonus

    Workflow:
      1. Admin/system grants a bonus → status='pending'
      2. User gets notified → status='active' (credited to wallet)
      3. Bonus may expire → status='expired'
      4. User must "claim" some bonus types → status='claimed'
    """

    BONUS_TYPES = [
        ("signup",       "Signup Welcome"),
        ("referral",     "Referral Bonus"),
        ("promo",        "Promotional"),
        ("loyalty",      "Loyalty Reward"),
        ("contest",      "Contest Prize"),
        ("compensation", "Compensation"),
        ("streak",       "Streak Milestone"),
        ("top_earner",   "Top Earner Bonus"),
        ("admin",        "Admin Grant"),
    ]
    STATUS_CHOICES = [
        ("pending",  "Pending — not yet credited"),
        ("active",   "Active — in wallet"),
        ("claimed",  "Claimed by user"),
        ("expired",  "Expired"),
        ("revoked",  "Revoked by admin"),
    ]

    tenant      = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_balancebonus_tenant",
        db_index=True,
    )
    bonus_id    = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet      = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="balance_bonuses",
    )
    amount      = models.DecimalField(max_digits=20, decimal_places=8)
    source      = models.CharField(max_length=20, choices=BONUS_TYPES, default="admin", db_index=True)
    source_id   = models.CharField(max_length=200, blank=True,
                                   help_text="ID of the event that triggered this bonus")
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    description = models.TextField(blank=True)

    # Expiry
    expires_at  = models.DateTimeField(null=True, blank=True)
    granted_at  = models.DateTimeField(default=timezone.now)
    claimed_at  = models.DateTimeField(null=True, blank=True)
    revoked_at  = models.DateTimeField(null=True, blank=True)

    # Audit
    granted_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_bonuses_granted",
    )
    revoked_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_bonuses_revoked",
    )

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_balance_bonus"
        ordering  = ["-granted_at"]
        indexes   = [
            models.Index(fields=["wallet", "status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return (f"Bonus {self.bonus_id} | wallet={self.wallet_id} "
                f"amount={self.amount} source={self.source} status={self.status}")

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def activate(self):
        """Credit bonus to wallet.bonus_balance."""
        if self.status != "pending":
            raise ValueError(f"Cannot activate bonus in status '{self.status}'")
        wallet = self.wallet
        wallet.bonus_balance += self.amount
        wallet.total_bonuses  += self.amount
        wallet.save(update_fields=["bonus_balance", "total_bonuses", "updated_at"])
        self.status = "active"
        self.save(update_fields=["status"])

    def expire(self):
        """Expire an active bonus — deduct from wallet.bonus_balance."""
        if self.status != "active":
            return
        wallet = self.wallet
        wallet.bonus_balance = max(wallet.bonus_balance - self.amount, Decimal("0"))
        wallet.save(update_fields=["bonus_balance", "updated_at"])
        self.status = "expired"
        self.save(update_fields=["status"])

    def revoke(self, revoked_by=None):
        """Admin revokes a bonus."""
        if self.status == "active":
            wallet = self.wallet
            wallet.bonus_balance = max(wallet.bonus_balance - self.amount, Decimal("0"))
            wallet.save(update_fields=["bonus_balance", "updated_at"])
        self.status     = "revoked"
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.save(update_fields=["status", "revoked_at", "revoked_by"])
