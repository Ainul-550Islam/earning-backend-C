# api/referral/models/commission.py
# Commission management models
# CommissionRule, CommissionLog, CommissionPayout, CommissionHold, CommissionClawback
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class CommissionRule(models.Model):
    """
    Flexible commission rules।
    Level + action_type combination অনুযায়ী different rates।
    e.g. signup এ 5%, offer complete এ 10%, withdrawal এ 2%
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    LEVEL_CHOICES = [
        (1, 'Level 1 — Direct'),
        (2, 'Level 2 — Indirect'),
        (3, 'Level 3 — Deep'),
    ]
    level = models.IntegerField(
        choices=LEVEL_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )

    ACTION_TYPE_CHOICES = [
        ('signup', 'Signup'),
        ('offer', 'Offer Complete'),
        ('withdrawal', 'Withdrawal'),
        ('task', 'Task Completion'),
        ('purchase', 'Purchase'),
        ('deposit', 'Deposit'),
        ('any', 'Any Action'),
    ]
    action_type = models.CharField(
        max_length=20, choices=ACTION_TYPE_CHOICES, default='any'
    )

    RATE_TYPE_CHOICES = [
        ('percentage', 'Percentage of earning'),
        ('fixed', 'Fixed amount'),
    ]
    rate_type = models.CharField(
        max_length=15, choices=RATE_TYPE_CHOICES, default='percentage'
    )

    rate_value = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        validators=[MinValueValidator(0)],
        help_text="Percentage (e.g. 10.00) বা fixed amount (e.g. 5.00)"
    )

    # Minimum earning to trigger this rule
    min_trigger_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    # Maximum commission per transaction
    max_commission_per_tx = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Cap per transaction (null = unlimited)"
    )

    # Daily commission cap per user
    daily_cap_per_user = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Daily commission cap per referrer (null = unlimited)"
    )

    description = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority overrides lower. Same level/action → highest priority wins."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-priority', 'level', 'action_type']
        indexes = [
            models.Index(fields=['level', 'action_type', 'is_active']),
        ]

    def __str__(self):
        return (
            f"CommissionRule L{self.level} / {self.action_type}: "
            f"{self.rate_value}"
            f"{'%' if self.rate_type == 'percentage' else ' fixed'}"
        )

    def calculate_commission(self, base_amount: Decimal) -> Decimal:
        """Base amount দিয়ে commission calculate করো।"""
        if self.rate_type == 'percentage':
            commission = (base_amount * self.rate_value / 100).quantize(
                Decimal('0.01')
            )
        else:
            commission = self.rate_value

        if self.max_commission_per_tx and commission > self.max_commission_per_tx:
            commission = self.max_commission_per_tx

        return commission


class CommissionLog(models.Model):
    """
    প্রতিটি commission event এর detailed log।
    CommissionRule থেকে calculate হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # Who earned the commission
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commission_logs_earned'
    )

    # Whose action triggered the commission
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commission_logs_triggered'
    )

    ACTION_TYPE_CHOICES = [
        ('signup', 'Signup'),
        ('offer', 'Offer Complete'),
        ('withdrawal', 'Withdrawal'),
        ('task', 'Task Completion'),
        ('purchase', 'Purchase'),
        ('deposit', 'Deposit'),
        ('any', 'Any Action'),
    ]
    action_type = models.CharField(
        max_length=20, choices=ACTION_TYPE_CHOICES, default='task'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    base_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Original amount that commission was calculated on"
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0
    )

    level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )

    # Rule that was applied
    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='commission_logs'
    )

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('held', 'Held'),
        ('released', 'Released'),
        ('cancelled', 'Cancelled'),
        ('clawed_back', 'Clawed Back'),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )

    # Wallet transaction after release
    wallet_transaction_id = models.CharField(
        max_length=100, null=True, blank=True
    )

    # Reference to source event
    source_reference = models.CharField(
        max_length=200, blank=True, default='',
        help_text="e.g. offer:123, task:456, withdrawal:789"
    )

    # Campaign that was active
    campaign = models.ForeignKey(
        'referral.ReferralCampaign',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['referred_user']),
            models.Index(fields=['status']),
            models.Index(fields=['action_type']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        return (
            f"CommissionLog({self.user.username} ৳{self.amount} "
            f"L{self.level} [{self.status}])"
        )


class CommissionPayout(models.Model):
    """
    Batch commission payout।
    Period (weekly/monthly) অনুযায়ী সব released commission একসাথে পাঠানো।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commission_payouts'
    )

    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('manual', 'Manual'),
    ]
    period = models.CharField(
        max_length=10, choices=PERIOD_CHOICES, default='weekly'
    )

    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )

    # Commission logs included in this payout
    commission_logs = models.ManyToManyField(
        CommissionLog,
        related_name='payouts',
        blank=True
    )

    # Wallet transaction after payout
    wallet_transaction_id = models.CharField(
        max_length=100, null=True, blank=True
    )

    # Who processed this payout
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='processed_commission_payouts'
    )

    failure_reason = models.CharField(max_length=500, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['period', 'period_start']),
        ]

    def __str__(self):
        return (
            f"Payout({self.user.username} "
            f"৳{self.total_amount} [{self.status}])"
        )

    def mark_completed(self, wallet_txn_id: str = ''):
        from django.utils import timezone
        self.status = 'completed'
        self.paid_at = timezone.now()
        if wallet_txn_id:
            self.wallet_transaction_id = wallet_txn_id
        self.save(update_fields=['status', 'paid_at', 'wallet_transaction_id'])


class CommissionHold(models.Model):
    """
    Commission hold mechanism।
    Fraud risk বা fraud review এর সময় commission hold করো।
    Hold period পরে automatically release করা হয় Celery task দিয়ে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    commission = models.OneToOneField(
        CommissionLog,
        on_delete=models.CASCADE,
        related_name='hold'
    )

    hold_days = models.IntegerField(
        default=7,
        help_text="Hold period in days"
    )

    release_at = models.DateTimeField(
        help_text="Datetime when hold expires and commission can be released"
    )

    REASON_CHOICES = [
        ('fraud_review', 'Fraud Review'),
        ('new_user', 'New User Verification'),
        ('high_value', 'High Value Transaction'),
        ('manual', 'Manual Hold by Admin'),
        ('suspicious_activity', 'Suspicious Activity'),
    ]
    reason = models.CharField(
        max_length=30, choices=REASON_CHOICES, default='new_user'
    )

    reason_detail = models.CharField(
        max_length=500, blank=True, default=''
    )

    is_released = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='released_commission_holds'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_released', 'release_at']),
        ]

    def __str__(self):
        return (
            f"Hold(commission={self.commission_id} "
            f"release={self.release_at.date()} "
            f"released={self.is_released})"
        )

    def release(self, released_by=None):
        """Hold release করো এবং commission status update করো।"""
        from django.utils import timezone
        self.is_released = True
        self.released_at = timezone.now()
        self.released_by = released_by
        self.save(update_fields=['is_released', 'released_at', 'released_by'])

        # Commission log status update
        self.commission.status = 'released'
        self.commission.save(update_fields=['status'])

    def is_ready_to_release(self) -> bool:
        from django.utils import timezone
        return not self.is_released and timezone.now() >= self.release_at


class CommissionClawback(models.Model):
    """
    Commission clawback — fraud বা refund এর কারণে commission reverse করা।
    Admin approve করার পরে Celery task process করে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    commission = models.ForeignKey(
        CommissionLog,
        on_delete=models.CASCADE,
        related_name='clawbacks'
    )

    REASON_CHOICES = [
        ('fraud', 'Fraud Detected'),
        ('chargeback', 'Chargeback'),
        ('refund', 'User Refund'),
        ('fake_activity', 'Fake Activity'),
        ('policy_violation', 'Policy Violation'),
        ('manual', 'Manual by Admin'),
    ]
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES, default='fraud'
    )

    reason_detail = models.CharField(
        max_length=500, blank=True, default=''
    )

    clawback_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Amount to claw back (may be partial)"
    )

    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )

    # Admin who approved
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_clawbacks'
    )

    # Wallet deduction transaction
    wallet_transaction_id = models.CharField(
        max_length=100, null=True, blank=True
    )

    clawed_back_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['commission']),
        ]

    def __str__(self):
        return (
            f"Clawback(commission={self.commission_id} "
            f"৳{self.clawback_amount} [{self.status}])"
        )

    def approve(self, admin_user):
        """Admin approve করলে status change করো।"""
        self.status = 'approved'
        self.approved_by = admin_user
        self.save(update_fields=['status', 'approved_by'])

    def reject(self, admin_user):
        """Admin reject করলে।"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.save(update_fields=['status', 'approved_by'])

    def mark_completed(self, wallet_txn_id: str = ''):
        """Clawback process হয়ে গেলে।"""
        from django.utils import timezone
        self.status = 'completed'
        self.clawed_back_at = timezone.now()
        if wallet_txn_id:
            self.wallet_transaction_id = wallet_txn_id
        self.save(update_fields=['status', 'clawed_back_at', 'wallet_transaction_id'])

        # Commission log status update
        self.commission.status = 'clawed_back'
        self.commission.save(update_fields=['status'])