# api/djoyalty/models/advanced.py
"""
Djoyalty Advanced Models।
LoyaltyNotification, PointsAlert, LoyaltySubscription,
LoyaltyFraudRule, PointsAbuseLog, LoyaltyInsight,
CoalitionEarn।

AUDIT FIX (4): Added Meta.indexes to PointsAlert and LoyaltyFraudRule —
both previously had Meta without indexes, causing full table scans on
every customer-alert lookup and every fraud-rule evaluation.
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class LoyaltyNotification(models.Model):
    """
    Loyalty notification queue।
    Expiry warnings, tier ups, challenge updates, etc।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='loyalty_notifications',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_notifications',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=[
            ('expiry', 'Points Expiry Warning'),
            ('tier_up', 'Tier Upgrade'),
            ('tier_down', 'Tier Downgrade'),
            ('challenge', 'Challenge Update'),
            ('badge', 'Badge Unlocked'),
            ('streak', 'Streak Milestone'),
            ('campaign', 'Campaign'),
            ('general', 'General'),
        ],
        default='general',
        verbose_name='Notification Type',
    )
    title = models.CharField(max_length=200, null=True, blank=True, verbose_name='Title')
    message = models.TextField(verbose_name='Message')

    channel = models.CharField(
        max_length=20,
        choices=[('push', 'Push'), ('email', 'Email'), ('sms', 'SMS'), ('in_app', 'In-App')],
        default='in_app',
        verbose_name='Channel',
    )

    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Scheduled At')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Sent At')
    is_sent = models.BooleanField(default=False, verbose_name='Sent')
    is_read = models.BooleanField(default=False, verbose_name='Read')
    read_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Notification'
        verbose_name_plural = 'Loyalty Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'is_sent']),
            models.Index(fields=['is_sent', 'scheduled_at']),
        ]

    def __str__(self):
        return f'Notification({self.customer.code}: {self.notification_type} [{self.is_sent}])'


class PointsAlert(models.Model):
    """
    Customer points alert thresholds।
    e.g. notify when balance < 100 pts।

    AUDIT FIX (4): Added Meta.indexes.
    (customer, is_active) covers the primary lookup — every polling cycle
    checks active alerts for each customer.  (alert_type,) covers admin
    filter by type without touching the customer FK.
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='points_alerts',
        verbose_name='Customer',
    )
    alert_type = models.CharField(
        max_length=30,
        choices=[
            ('low_balance', 'Low Balance'),
            ('expiry_warning', 'Expiry Warning'),
            ('tier_progress', 'Tier Progress'),
        ],
        verbose_name='Alert Type',
    )
    threshold = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Threshold')
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Alert'
        verbose_name_plural = 'Points Alerts'
        indexes = [
            models.Index(fields=['customer', 'is_active'],
                         name='ptalt_customer_active_idx'),
            models.Index(fields=['alert_type', 'is_active'],
                         name='ptalt_type_active_idx'),
            models.Index(fields=['last_triggered_at'],
                         name='ptalt_last_triggered_idx'),
        ]

    def __str__(self):
        return f'PointsAlert({self.customer.code}: {self.alert_type} @ {self.threshold})'


class LoyaltySubscription(models.Model):
    """
    Premium loyalty subscription plan।
    Monthly fee এর বিনিময়ে extra benefits।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='loyalty_subscriptions',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_subscriptions',
    )

    plan_name = models.CharField(max_length=50, verbose_name='Plan Name')
    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1.5'),
        verbose_name='Points Multiplier',
    )
    monthly_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Monthly Fee',
    )
    bonus_points_monthly = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Monthly Bonus Points',
    )

    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now, verbose_name='Started At')
    next_renewal_at = models.DateTimeField(null=True, blank=True, verbose_name='Next Renewal')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Cancelled At')
    expires_at = models.DateTimeField(null=True, blank=True)

    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    cancel_reason = models.CharField(max_length=500, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Subscription'
        verbose_name_plural = 'Loyalty Subscriptions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['next_renewal_at', 'is_active']),
        ]

    def __str__(self):
        return f'Subscription({self.customer.code}: {self.plan_name} [{self.is_active}])'


class LoyaltyFraudRule(models.Model):
    """
    Fraud detection rule configuration।

    AUDIT FIX (4): Added Meta.indexes.
    (tenant, is_active) covers the primary lookup — every transaction
    evaluation loads all active fraud rules for the tenant.
    (rule_type, is_active) covers type-specific rule queries used in
    fraud engine routing.
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='fraud_rules',
    )
    name = models.CharField(max_length=200, verbose_name='Rule Name')
    rule_type = models.CharField(
        max_length=50,
        choices=[
            ('rapid_transactions', 'Rapid Transactions'),
            ('daily_redemption_cap', 'Daily Redemption Cap'),
            ('velocity_check', 'Velocity Check'),
            ('geo_anomaly', 'Geographic Anomaly'),
        ],
        verbose_name='Rule Type',
    )
    condition = models.CharField(max_length=500, verbose_name='Condition Expression')
    action = models.CharField(
        max_length=20,
        choices=[
            ('flag', 'Flag'), ('block', 'Block'),
            ('reverse', 'Reverse Points'), ('suspend', 'Suspend Account'),
        ],
        default='flag',
        verbose_name='Action',
    )
    threshold = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    cooldown_hours = models.PositiveIntegerField(default=24, verbose_name='Cooldown Hours')
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Fraud Rule'
        verbose_name_plural = 'Loyalty Fraud Rules'
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='fraudrule_tenant_active_idx'),
            models.Index(fields=['rule_type', 'is_active'],
                         name='fraudrule_type_active_idx'),
        ]

    def __str__(self):
        return f'FraudRule({self.name}: {self.action})'


class PointsAbuseLog(models.Model):
    """
    Fraud/abuse detection log।
    High-risk activity এ auto-created।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='abuse_logs',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='abuse_logs',
        verbose_name='Customer',
    )
    rule = models.ForeignKey(
        LoyaltyFraudRule,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='abuse_logs',
        verbose_name='Triggered Rule',
    )

    risk_level = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='high',
        verbose_name='Risk Level',
    )
    action_taken = models.CharField(
        max_length=20,
        choices=[('flag', 'Flagged'), ('block', 'Blocked'), ('reverse', 'Reversed'), ('suspend', 'Suspended')],
        default='flag',
        verbose_name='Action Taken',
    )
    description = models.TextField(verbose_name='Description')
    points_reversed = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Reversed',
    )

    detected_at = models.DateTimeField(default=timezone.now, verbose_name='Detected At')
    is_resolved = models.BooleanField(default=False, verbose_name='Resolved')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=200, null=True, blank=True)
    resolution_note = models.TextField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Points Abuse Log'
        verbose_name_plural = 'Points Abuse Logs'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['customer', 'is_resolved']),
            models.Index(fields=['risk_level', 'is_resolved']),
            models.Index(fields=['detected_at']),
        ]

    def __str__(self):
        return f'AbuseLog({self.customer.code}: {self.risk_level} [{self.action_taken}])'


class LoyaltyInsight(models.Model):
    """
    Daily/weekly/monthly loyalty analytics snapshot।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_insights',
    )
    report_date = models.DateField(verbose_name='Report Date')
    period = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'), ('weekly', 'Weekly'),
            ('monthly', 'Monthly'), ('annual', 'Annual'),
        ],
        default='daily',
        verbose_name='Period',
    )

    total_customers = models.PositiveIntegerField(default=0, verbose_name='Total Customers')
    active_customers = models.PositiveIntegerField(default=0, verbose_name='Active Customers')
    new_customers = models.PositiveIntegerField(default=0, verbose_name='New Customers')

    total_points_issued = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Points Issued',
    )
    total_points_redeemed = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Points Redeemed',
    )
    total_points_expired = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Points Expired',
    )
    total_points_outstanding = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Outstanding Points',
    )

    total_transactions = models.PositiveIntegerField(default=0, verbose_name='Total Transactions')
    total_revenue = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Revenue',
    )

    redemption_rate = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Redemption Rate (%)',
    )
    liability_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Liability Amount (currency value of outstanding pts)',
    )

    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Insight'
        verbose_name_plural = 'Loyalty Insights'
        unique_together = [('tenant', 'report_date', 'period')]
        ordering = ['-report_date']
        indexes = [
            models.Index(fields=['tenant', 'report_date']),
            models.Index(fields=['period', 'report_date']),
        ]

    def __str__(self):
        return f'Insight({self.period}: {self.report_date})'


class CoalitionEarn(models.Model):
    """
    Points earned at a partner merchant (coalition loyalty)।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='coalition_earns',
        verbose_name='Customer',
    )
    partner = models.ForeignKey(
        'djoyalty.PartnerMerchant',
        on_delete=models.CASCADE,
        related_name='earn_records',
        verbose_name='Partner Merchant',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='coalition_earns',
    )

    spend_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Spend Amount')
    points_earned = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points Earned')
    earn_rate_applied = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('1'),
        verbose_name='Earn Rate Applied',
    )
    reference = models.CharField(max_length=100, verbose_name='Reference', unique=True)
    currency = models.CharField(max_length=10, default='BDT')
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('processed', 'Processed'), ('reversed', 'Reversed')],
        default='processed',
    )
    description = models.CharField(max_length=300, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Coalition Earn'
        verbose_name_plural = 'Coalition Earns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'partner']),
            models.Index(fields=['reference']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'CoalitionEarn({self.customer.code} @ {self.partner.name}: {self.points_earned} pts)'
