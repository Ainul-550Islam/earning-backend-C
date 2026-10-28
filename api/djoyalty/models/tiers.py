# api/djoyalty/models/tiers.py
"""
Djoyalty Tier Models।
LoyaltyTier, UserTier, TierBenefit, TierHistory, TierConfig।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager, CurrentTierManager

logger = logging.getLogger(__name__)


class LoyaltyTier(models.Model):
    """
    Tier definition -- bronze/silver/gold/platinum/diamond।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_tiers',
    )
    name = models.CharField(
        max_length=30,
        choices=[
            ('bronze', 'Bronze'), ('silver', 'Silver'),
            ('gold', 'Gold'), ('platinum', 'Platinum'), ('diamond', 'Diamond'),
        ],
        verbose_name='Tier Name',
    )
    label = models.CharField(max_length=100, verbose_name='Display Label')
    description = models.TextField(null=True, blank=True)
    min_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Minimum Points Required',
    )
    max_points = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Maximum Points (next tier threshold)',
    )
    earn_multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1.0'),
        verbose_name='Points Earn Multiplier',
    )
    rank = models.PositiveIntegerField(
        default=1,
        verbose_name='Rank',
        help_text='1=lowest, 5=highest',
    )
    color = models.CharField(max_length=20, default='#888888', verbose_name='Color (hex)')
    icon = models.CharField(max_length=50, default='⭐', verbose_name='Icon (emoji or URL)')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    is_active = models.BooleanField(default=True)

    # Perks summary
    perks_summary = models.TextField(null=True, blank=True, verbose_name='Perks Summary')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Tier'
        verbose_name_plural = 'Loyalty Tiers'
        ordering = ['rank']
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['rank']),
        ]

    def __str__(self):
        return f'{self.label} ({self.name})'


class UserTier(models.Model):
    """
    Customer এর tier assignment।
    is_current=True মানে এটি active tier।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='user_tiers',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='user_tiers',
    )
    tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.CASCADE,
        related_name='user_assignments',
        verbose_name='Tier',
    )

    is_current = models.BooleanField(default=True, verbose_name='Is Current Tier')
    points_at_assignment = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points at Assignment',
    )
    achieved_at = models.DateTimeField(default=timezone.now, verbose_name='Achieved At')
    assigned_at = models.DateTimeField(default=timezone.now, verbose_name='Assigned At')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Tier Expires At')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    current = CurrentTierManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'User Tier'
        verbose_name_plural = 'User Tiers'
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['customer', 'is_current']),
            models.Index(fields=['tier', 'is_current']),
        ]

    def __str__(self):
        status = 'current' if self.is_current else 'past'
        return f'UserTier({self.customer.code}: {self.tier.name} [{status}])'


class TierBenefit(models.Model):
    """
    Tier এর সাথে associated benefits/perks।
    """
    tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.CASCADE,
        related_name='benefits',
        verbose_name='Tier',
    )
    title = models.CharField(max_length=200, verbose_name='Benefit Title')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    benefit_type = models.CharField(
        max_length=30,
        choices=[
            ('discount', 'Discount'), ('shipping', 'Free Shipping'),
            ('cashback', 'Cashback'), ('perk', 'Perk'),
            ('access', 'Exclusive Access'), ('points_boost', 'Points Boost'),
        ],
        default='perk',
        verbose_name='Benefit Type',
    )
    value = models.CharField(max_length=100, null=True, blank=True, verbose_name='Value/Amount')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Tier Benefit'
        verbose_name_plural = 'Tier Benefits'
        ordering = ['sort_order']
        # AUDIT FIX (4): (tier, is_active) for active benefits per tier;
        # (tier, benefit_type) for type-filtered benefit lookup.
        indexes = [
            models.Index(fields=['tier', 'is_active'],
                         name='tierbenefit_tier_active_idx'),
            models.Index(fields=['tier', 'benefit_type'],
                         name='tierbenefit_tier_type_idx'),
        ]

    def __str__(self):
        return f'Benefit({self.tier.name}: {self.title})'


class TierHistory(models.Model):
    """
    Customer এর tier change history।
    Audit trail for upgrades, downgrades, initial assignments।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='tier_history',
        verbose_name='Customer',
    )
    from_tier = models.ForeignKey(
        LoyaltyTier,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='tier_from_history',
        verbose_name='From Tier',
    )
    to_tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.CASCADE,
        related_name='tier_to_history',
        verbose_name='To Tier',
    )
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('upgrade', 'Upgrade'), ('downgrade', 'Downgrade'),
            ('initial', 'Initial'), ('manual', 'Manual'),
        ],
        verbose_name='Change Type',
    )
    reason = models.CharField(max_length=500, null=True, blank=True, verbose_name='Reason')
    points_at_change = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points at Change',
    )
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Changed At')
    changed_by = models.CharField(max_length=200, null=True, blank=True, verbose_name='Changed By')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Tier History'
        verbose_name_plural = 'Tier History'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['customer', 'changed_at']),
            models.Index(fields=['change_type']),
        ]

    def __str__(self):
        from_name = self.from_tier.name if self.from_tier else 'none'
        return f'TierHistory({self.customer.code}: {from_name} -> {self.to_tier.name} [{self.change_type}])'


class TierConfig(models.Model):
    """
    Tier system configuration per tenant।
    """
    tenant = models.OneToOneField(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='tier_config',
        verbose_name='Tenant',
    )
    evaluation_period = models.CharField(
        max_length=20,
        choices=[('annual', 'Annual'), ('rolling', 'Rolling 12 months')],
        default='annual',
        verbose_name='Evaluation Period',
    )
    downgrade_grace_days = models.PositiveIntegerField(
        default=90,
        verbose_name='Downgrade Grace Days',
        help_text='Days after tier drop eligibility before actual downgrade',
    )
    downgrade_protection_months = models.PositiveIntegerField(
        default=3,
        verbose_name='Downgrade Protection Months',
    )
    freeze_enabled = models.BooleanField(default=False, verbose_name='Freeze Tier Enabled')
    auto_upgrade = models.BooleanField(default=True, verbose_name='Auto Upgrade')
    auto_downgrade = models.BooleanField(default=True, verbose_name='Auto Downgrade')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Tier Config'
        # AUDIT FIX (4): (auto_upgrade, auto_downgrade) for config engine queries.
        indexes = [
            models.Index(fields=['auto_upgrade', 'auto_downgrade'],
                         name='tierconfig_auto_flags_idx'),
        ]

    def __str__(self):
        return f'TierConfig({self.tenant})'
