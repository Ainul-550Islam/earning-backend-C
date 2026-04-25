# api/djoyalty/models/advanced.py
from django.db import models
from ..choices import (
    NOTIFICATION_TYPE_CHOICES, NOTIFICATION_CHANNEL_CHOICES,
    FRAUD_RISK_CHOICES, FRAUD_ACTION_CHOICES,
)
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import (
    UnreadNotificationManager, PendingNotificationManager,
    HighRiskFraudManager, UnresolvedFraudManager,
)


class LoyaltyNotification(models.Model):
    """Loyalty notification to customers।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltynotification_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='loyalty_notifications',
    )
    notification_type = models.CharField(max_length=32, choices=NOTIFICATION_TYPE_CHOICES, db_index=True)
    channel = models.CharField(max_length=16, choices=NOTIFICATION_CHANNEL_CHOICES, default='email')
    title = models.CharField(max_length=256)
    body = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    is_sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    unread = UnreadNotificationManager()
    pending_send = PendingNotificationManager()

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['customer', 'is_read'], name='idx_customer_is_read_966')]

    def __str__(self):
        return f'{self.notification_type} → {self.customer} (sent={self.is_sent})'


class PointsAlert(models.Model):
    """Points expiry alert log।"""

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='points_alerts',
    )
    points_expiring = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    expires_at = models.DateTimeField()
    alert_sent_at = models.DateTimeField(auto_now_add=True)
    channel = models.CharField(max_length=16, choices=NOTIFICATION_CHANNEL_CHOICES, default='email')

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-alert_sent_at']

    def __str__(self):
        return f'Alert: {self.points_expiring} pts expiring {self.expires_at} for {self.customer}'


class LoyaltySubscription(models.Model):
    """Premium loyalty subscription।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltysubscription_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='loyalty_subscriptions',
    )
    plan_name = models.CharField(max_length=128)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bonus_points_monthly = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    earn_multiplier_bonus = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    next_renewal_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.customer} — {self.plan_name} (active={self.is_active})'


class LoyaltyFraudRule(models.Model):
    """Fraud detection rule।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltyfraudrule_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    rule_type = models.CharField(max_length=64)
    threshold_value = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    window_minutes = models.PositiveIntegerField(default=60)
    risk_level = models.CharField(max_length=16, choices=FRAUD_RISK_CHOICES, default='medium')
    action = models.CharField(max_length=16, choices=FRAUD_ACTION_CHOICES, default='flag')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.name} [{self.risk_level}] → {self.action}'


class PointsAbuseLog(models.Model):
    """Points abuse / fraud log।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_pointsabuselog_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='abuse_logs',
    )
    fraud_rule = models.ForeignKey(
        'LoyaltyFraudRule', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='abuse_logs',
    )
    risk_level = models.CharField(max_length=16, choices=FRAUD_RISK_CHOICES, db_index=True)
    action_taken = models.CharField(max_length=16, choices=FRAUD_ACTION_CHOICES)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.CharField(max_length=128, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    objects = models.Manager()
    high_risk = HighRiskFraudManager()
    unresolved = UnresolvedFraudManager()

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['risk_level', 'is_resolved'], name='idx_risk_level_is_resolved_967')]

    def __str__(self):
        return f'Fraud [{self.risk_level}] {self.customer} — {self.action_taken}'


class LoyaltyInsight(models.Model):
    """Daily/weekly loyalty insight report।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltyinsight_tenant', db_index=True,
    )
    report_date = models.DateField(db_index=True)
    period = models.CharField(
        max_length=8,
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        default='daily',
    )
    total_customers = models.PositiveIntegerField(default=0)
    active_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    total_points_issued = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    total_points_redeemed = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    total_points_expired = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    total_transactions = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tier_distribution = models.JSONField(default=dict)
    top_earners = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('tenant', 'report_date', 'period')]
        ordering = ['-report_date']

    def __str__(self):
        return f'Insight {self.period} {self.report_date} — {self.tenant}'


class CoalitionEarn(models.Model):
    """Cross-partner earn transaction।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_coalitionearn_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='coalition_earns',
    )
    partner = models.ForeignKey(
        'PartnerMerchant', on_delete=models.CASCADE,
        related_name='coalition_earns',
    )
    spend_amount = models.DecimalField(max_digits=10, decimal_places=2)
    points_earned = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reference = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer} earned {self.points_earned} pts via {self.partner}'
