# api/djoyalty/models/tiers.py
from django.db import models
from ..choices import TIER_CHOICES
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import CurrentTierManager


class LoyaltyTier(models.Model):
    """Tier definition — Bronze to Diamond।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltytier_tenant', db_index=True,
    )
    name = models.CharField(max_length=32, choices=TIER_CHOICES, db_index=True)
    label = models.CharField(max_length=64, default='')
    min_points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    max_points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, null=True, blank=True)
    earn_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    color = models.CharField(max_length=7, default='#888888')
    icon = models.CharField(max_length=8, default='⭐')
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    rank = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['rank']
        unique_together = [('tenant', 'name')]

    def __str__(self):
        return f'{self.icon} {self.label or self.name}'


class UserTier(models.Model):
    """Customer এর current & history tier।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_usertier_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='user_tiers',
    )
    tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.PROTECT,
        related_name='user_tiers',
    )
    is_current = models.BooleanField(default=True, db_index=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    points_at_assignment = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )

    objects = models.Manager()
    current = CurrentTierManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [models.Index(fields=['customer', 'is_current'], name='idx_customer_is_current_992')]

    def __str__(self):
        return f'{self.customer} → {self.tier} (current={self.is_current})'


class TierBenefit(models.Model):
    """Tier benefits — free shipping, priority support, etc."""

    tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.CASCADE,
        related_name='benefits',
    )
    title = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    benefit_type = models.CharField(max_length=64, default='perk')
    value = models.CharField(max_length=64, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.tier.name} — {self.title}'


class TierHistory(models.Model):
    """Tier upgrade/downgrade history।"""

    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='tier_history',
    )
    from_tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    to_tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.PROTECT,
        related_name='+',
    )
    change_type = models.CharField(
        max_length=16,
        choices=[('upgrade', 'Upgrade'), ('downgrade', 'Downgrade'), ('initial', 'Initial')],
    )
    reason = models.TextField(null=True, blank=True)
    points_at_change = models.DecimalField(
        max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer}: {self.from_tier} → {self.to_tier} [{self.change_type}]'


class TierConfig(models.Model):
    """Tier evaluation configuration per tenant।"""

    tenant = models.OneToOneField(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='djoyalty_tier_config', null=True, blank=True,
    )
    evaluation_period_months = models.PositiveSmallIntegerField(default=12)
    downgrade_protection_months = models.PositiveSmallIntegerField(default=3)
    auto_downgrade = models.BooleanField(default=True)
    notify_on_upgrade = models.BooleanField(default=True)
    notify_on_downgrade = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'TierConfig for {self.tenant}'
