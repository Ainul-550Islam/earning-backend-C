# api/wallet/models/analytics.py
"""
Analytics models — pre-computed daily insights and reports.

Never computed live — always populated by Celery tasks.

WalletInsight     — per-wallet daily stats
WithdrawalInsight — platform-wide withdrawal analytics
EarningInsight    — platform-wide earning analytics
LiabilityReport   — daily financial liability snapshot
"""
from decimal import Decimal
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone


class WalletInsight(models.Model):
    """
    Per-wallet daily stats snapshot.
    Computed nightly by compute_wallet_insights Celery task.
    Allows fast dashboard rendering without aggregating raw transactions.
    """

    tenant          = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_walletinsight_tenant",
        db_index=True,
    )
    wallet          = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="daily_insights",
    )
    date            = models.DateField(db_index=True)

    # Balance snapshot at end of day
    opening_balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    closing_balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    peak_balance    = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))

    # Credits
    total_credits    = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_credit_count = models.PositiveIntegerField(default=0)

    # Debits
    total_debits     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_debit_count = models.PositiveIntegerField(default=0)

    # Activity counts
    txn_count        = models.PositiveIntegerField(default=0, help_text="All transactions")
    wd_count         = models.PositiveIntegerField(default=0, help_text="Withdrawal requests")
    earn_count       = models.PositiveIntegerField(default=0, help_text="Earning events")
    bonus_count      = models.PositiveIntegerField(default=0)
    reversal_count   = models.PositiveIntegerField(default=0)

    # By source breakdown
    earnings_by_source = models.JSONField(default=dict, blank=True,
                                          help_text='{"task":10.5, "referral":5.0}')

    computed_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_wallet_insight"
        unique_together = [("wallet", "date")]
        ordering  = ["-date"]
        indexes   = [
            models.Index(fields=["wallet", "-date"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return (f"WalletInsight wallet={self.wallet_id} "
                f"date={self.date} closing={self.closing_balance}")


class WithdrawalInsight(models.Model):
    """
    Platform-wide withdrawal analytics per day.
    How much was requested, how much processed, average processing time.
    """

    tenant              = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_withdrawalinsight_tenant",
        db_index=True,
    )
    date                = models.DateField(unique=True, db_index=True)
    currency            = models.CharField(max_length=10, default="BDT")

    # Volume
    total_requested     = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    total_processed     = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    total_rejected      = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    total_fees_collected= models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    # Counts
    request_count       = models.PositiveIntegerField(default=0)
    completed_count     = models.PositiveIntegerField(default=0)
    rejected_count      = models.PositiveIntegerField(default=0)
    pending_count       = models.PositiveIntegerField(default=0)

    # Timing
    avg_time_to_process = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"),
                                               help_text="Average minutes from request to completion")

    # By gateway breakdown
    by_gateway          = models.JSONField(default=dict, blank=True,
                                           help_text='{"bkash":{"count":10,"amount":5000}, ...}')

    computed_at         = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_withdrawal_insight"
        ordering  = ["-date"]

    def __str__(self):
        return (f"WithdrawalInsight date={self.date} "
                f"requested={self.total_requested} processed={self.total_processed}")


class EarningInsight(models.Model):
    """
    Platform-wide earning analytics per day.
    Total earned, top earning source, average per active user.
    """

    tenant           = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_earninginsight_tenant",
        db_index=True,
    )
    date             = models.DateField(unique=True, db_index=True)
    currency         = models.CharField(max_length=10, default="BDT")

    # Volume
    total_earned     = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    total_events     = models.PositiveIntegerField(default=0)
    active_users     = models.PositiveIntegerField(default=0,
                                                   help_text="Unique users who earned today")

    # Averages
    avg_per_user     = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    avg_per_event    = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))

    # Top source
    top_source       = models.CharField(max_length=20, blank=True,
                                        help_text="EarningSourceType with highest total today")
    top_source_amount= models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    # By source breakdown
    by_source        = models.JSONField(default=dict, blank=True,
                                        help_text='{"task":{"count":100,"amount":500.0}, ...}')

    # Bonuses
    total_streak_bonuses  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total_referral_earned = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    computed_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_earning_insight"
        ordering  = ["-date"]

    def __str__(self):
        return (f"EarningInsight date={self.date} "
                f"total={self.total_earned} users={self.active_users}")


class LiabilityReport(models.Model):
    """
    Daily financial liability snapshot — the platform's obligations to users.

    Total liability = current_balance + pending_balance + frozen_balance + bonus_balance
    (all money the platform "owes" to users)

    Used by finance team to:
      - Ensure sufficient funds in payment gateway accounts
      - Spot unusual liability spikes (potential fraud)
      - Regulatory reporting
    """

    tenant               = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_liabilityreport_tenant",
        db_index=True,
    )
    report_date          = models.DateField(unique=True, db_index=True)
    currency             = models.CharField(max_length=10, default="BDT")

    # Balance liabilities
    total_current        = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Sum of all current_balance")
    total_pending        = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Sum of all pending_balance (pending withdrawals)")
    total_frozen         = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Sum of all frozen_balance")
    total_bonus          = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Sum of all bonus_balance")
    total_reserved       = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Sum of all reserved_balance")
    total_liability      = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"),
                                               help_text="Total = current+pending+frozen+bonus")

    # Withdrawal queue stats
    pending_wd_count     = models.PositiveIntegerField(default=0,
                                                        help_text="Pending withdrawal request count")
    pending_wd_amount    = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal("0"))

    # Wallet population
    total_wallets        = models.PositiveIntegerField(default=0)
    active_wallets       = models.PositiveIntegerField(default=0,
                                                        help_text="Wallets with balance > 0")
    locked_wallets       = models.PositiveIntegerField(default=0)

    # Flags
    has_anomaly          = models.BooleanField(default=False,
                                               help_text="True if liability changed unusually vs previous day")
    anomaly_notes        = models.TextField(blank=True)

    generated_at         = models.DateTimeField(default=timezone.now)
    generated_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_liability_reports_generated",
    )

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_liability_report"
        ordering  = ["-report_date"]
        indexes   = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["currency"]),
        ]

    def __str__(self):
        return (f"LiabilityReport date={self.report_date} "
                f"total={self.total_liability} {self.currency}")

    def save(self, *args, **kwargs):
        # Auto-compute total liability
        self.total_liability = (
            self.total_current
            + self.total_pending
            + self.total_frozen
            + self.total_bonus
        )
        super().save(*args, **kwargs)
