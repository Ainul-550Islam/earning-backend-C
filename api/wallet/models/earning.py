# api/wallet/models/earning.py
"""
Earning models — all user income tracking.

EarningSource   — offer/task/referral source configuration
EarningRecord   — individual earning event (immutable)
EarningSummary  — aggregated stats per period per user
EarningStreak   — consecutive daily earning streak tracking
EarningCap      — daily earning cap per source to prevent abuse
"""
import uuid
from decimal import Decimal
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone

from ..choices import EarningSourceType


class EarningSource(models.Model):
    """
    Configuration for an earning source — what it pays and under what conditions.
    E.g. "Task: video watch → 0.50 BDT" or "Offer: app install → 5.00 BDT"
    """

    PAYOUT_MODEL = [
        ("fixed",   "Fixed amount per action"),
        ("dynamic", "Dynamic — calculated at runtime"),
        ("range",   "Range — random between min and max"),
    ]

    tenant         = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earningsource_tenant",
        db_index=True,
    )
    source_type    = models.CharField(max_length=20, choices=EarningSourceType.choices, db_index=True)
    name           = models.CharField(max_length=200)
    description    = models.TextField(blank=True)

    # Payout config
    payout_model   = models.CharField(max_length=10, choices=PAYOUT_MODEL, default="fixed")
    base_reward    = models.DecimalField(max_digits=14, decimal_places=8, default=Decimal("0"),
                                         help_text="Base reward per action in BDT")
    min_reward     = models.DecimalField(max_digits=14, decimal_places=8, default=Decimal("0"))
    max_reward     = models.DecimalField(max_digits=14, decimal_places=8, default=Decimal("0"))

    # GEO / Tier multiplier stored externally via GeoRate and UserTier
    multiplier     = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("1.0000"),
                                          help_text="Applied on top of GEO and tier multipliers")

    # Caps
    max_per_user_per_day = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_per_user_total   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # Availability
    is_active      = models.BooleanField(default=True, db_index=True)
    starts_at      = models.DateTimeField(null=True, blank=True)
    ends_at        = models.DateTimeField(null=True, blank=True)

    # External
    external_id    = models.CharField(max_length=200, blank=True,
                                      help_text="ID in external ad network / offer system")

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_source"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"EarningSource [{self.source_type}] {self.name} → {self.base_reward} BDT"

    def is_available(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


class EarningRecord(models.Model):
    """
    Immutable record of a single earning event.
    Created whenever a user earns from any source.
    Linked to the WalletTransaction that credited the wallet.
    """

    tenant        = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earningrecord_tenant",
        db_index=True,
    )
    wallet        = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="earning_records",
    )
    source        = models.ForeignKey(
        EarningSource,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="earning_records",
    )
    transaction   = models.OneToOneField(
        "wallet.WalletTransaction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="earning_record",
    )

    # What / how much
    source_type   = models.CharField(max_length=20, choices=EarningSourceType.choices, db_index=True)
    source_ref_id = models.CharField(max_length=200, blank=True,
                                     help_text="Offer ID, task ID, referral user ID, etc.")
    amount        = models.DecimalField(max_digits=20, decimal_places=8,
                                        help_text="Amount credited to wallet (after multipliers)")
    original_amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"),
                                          help_text="Base amount before multipliers")
    bonus_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"),
                                         help_text="Tier / geo / streak bonus applied (%)")

    # Context
    country_code  = models.CharField(max_length=3, blank=True)
    device_type   = models.CharField(max_length=20, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    metadata      = models.JSONField(default=dict, blank=True)

    earned_at     = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_record"
        ordering  = ["-earned_at"]
        indexes   = [
            models.Index(fields=["wallet", "-earned_at"]),
            models.Index(fields=["source_type"]),
            models.Index(fields=["source_ref_id"]),
            models.Index(fields=["earned_at"]),
        ]

    def __str__(self):
        return (f"EarningRecord wallet={self.wallet_id} "
                f"type={self.source_type} amount={self.amount} at={self.earned_at}")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("EarningRecord is immutable — never update an earning record")
        super().save(*args, **kwargs)


class EarningSummary(models.Model):
    """
    Pre-aggregated earning stats per user per period.
    Computed nightly by Celery tasks — never computed on-the-fly.
    """

    PERIOD_CHOICES = [("daily","Daily"),("weekly","Weekly"),("monthly","Monthly")]

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earningsummary_tenant",
        db_index=True,
    )
    wallet       = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="earning_summaries",
    )
    period       = models.CharField(max_length=10, choices=PERIOD_CHOICES, db_index=True)
    period_start = models.DateField(db_index=True)
    period_end   = models.DateField()

    # Totals
    total_earned  = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_count   = models.PositiveIntegerField(default=0)

    # Breakdown by source type — stored as JSON for flexibility
    by_source     = models.JSONField(default=dict, blank=True,
                                     help_text='{"task": 50.0, "referral": 20.0, ...}')

    computed_at   = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_summary"
        unique_together = [("wallet", "period", "period_start")]
        ordering  = ["-period_start"]

    def __str__(self):
        return (f"EarningSummary wallet={self.wallet_id} "
                f"{self.period} {self.period_start}→{self.period_end} total={self.total_earned}")


class EarningStreak(models.Model):
    """
    Tracks consecutive daily earning streaks.
    Broken if user doesn't earn on any given calendar day.

    Streak bonuses configured in constants.STREAK_BONUSES:
      7 days  → 10 BDT bonus
      14 days → 25 BDT bonus
      30 days → 100 BDT bonus
    """

    tenant          = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earningstreak_tenant",
        db_index=True,
    )
    wallet          = models.OneToOneField(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="earning_streak",
    )
    current_streak  = models.PositiveIntegerField(default=0,
                                                  help_text="Current consecutive day streak")
    longest_streak  = models.PositiveIntegerField(default=0,
                                                  help_text="All-time longest streak")
    last_earn_date  = models.DateField(null=True, blank=True,
                                       help_text="Last calendar date user earned anything")
    total_streak_bonuses = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"),
                                               help_text="Total BDT earned from streak milestones")

    # Milestone tracking — which milestones have been rewarded this streak run
    milestones_awarded = models.JSONField(default=list, blank=True,
                                          help_text="List of day counts already rewarded [7, 14, ...]")
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_streak"

    def __str__(self):
        return (f"EarningStreak wallet={self.wallet_id} "
                f"current={self.current_streak} longest={self.longest_streak}")

    def update_streak(self, earn_date: date = None) -> dict:
        """
        Update streak for today's earning. Returns dict with bonus info.
        Call this whenever a user earns.
        """
        today = earn_date or date.today()
        result = {"streak": self.current_streak, "bonus": Decimal("0"), "milestone": None}

        if self.last_earn_date is None:
            # First ever earning
            self.current_streak = 1
        elif (today - self.last_earn_date).days == 1:
            # Consecutive day
            self.current_streak += 1
        elif (today - self.last_earn_date).days == 0:
            # Same day — no change
            return result
        else:
            # Streak broken
            self.current_streak = 1
            self.milestones_awarded = []

        self.last_earn_date = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

        # Check streak milestones
        from ..constants import STREAK_BONUSES
        for milestone_days, bonus_amount in sorted(STREAK_BONUSES.items()):
            if (self.current_streak >= milestone_days
                    and milestone_days not in self.milestones_awarded):
                self.milestones_awarded.append(milestone_days)
                result["bonus"]     = bonus_amount
                result["milestone"] = milestone_days
                self.total_streak_bonuses += bonus_amount
                break  # Only one milestone per day

        result["streak"] = self.current_streak
        self.save()
        return result


class EarningCap(models.Model):
    """
    Daily earning caps per source type and per user tier.
    Prevents abuse and runaway reward costs.

    Global caps apply to all users.
    User-specific caps override global caps when both exist.

    Reset daily at midnight by Celery task (earning_cap_reset_tasks).
    """

    CAP_SCOPE = [
        ("global",  "Global — applies to all users"),
        ("tier",    "Tier-specific"),
        ("user",    "User-specific override"),
    ]

    tenant       = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earningcap_tenant",
        db_index=True,
    )
    wallet       = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="earning_caps",
        help_text="Null = global or tier-level cap",
    )
    source       = models.ForeignKey(
        EarningSource,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="earning_caps",
        help_text="Null = cap applies to ALL sources",
    )
    cap_type     = models.CharField(max_length=10, choices=CAP_SCOPE, default="global")
    tier         = models.CharField(max_length=10, blank=True,
                                    help_text="Applies only to users of this tier (if cap_type=tier)")

    cap_amount   = models.DecimalField(max_digits=14, decimal_places=2,
                                        help_text="Max BDT per day from this source")
    is_active    = models.BooleanField(default=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_cap"
        ordering  = ["cap_type", "tier"]

    def __str__(self):
        scope = f"wallet={self.wallet_id}" if self.wallet else f"tier={self.tier or 'ALL'}"
        source = self.source.name if self.source else "ALL"
        return f"EarningCap [{scope}] source={source} max={self.cap_amount}/day"
