"""
Plan Models

This module contains subscription plan models that define
pricing tiers, features, and usage quotas.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class Plan(TimeStampedModel, SoftDeleteModel):
    """
    Subscription plan model defining pricing tiers and features.
    
    This model represents different subscription plans available
    to tenants, with associated pricing, limits, and features.
    """
    
    PLAN_TYPE_CHOICES = [
        ('free', _('Free')),
        ('basic', _('Basic')),
        ('pro', _('Professional')),
        ('enterprise', _('Enterprise')),
        ('custom', _('Custom')),
    ]
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', _('Monthly')),
        ('yearly', _('Yearly')),
        ('custom', _('Custom')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        verbose_name=_('Plan Name'),
        help_text=_('Display name of the plan')
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_('Slug'),
        help_text=_('URL-friendly identifier')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Detailed description of the plan')
    )
    
    # Plan type and billing
    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPE_CHOICES,
        verbose_name=_('Plan Type'),
        help_text=_('Type of subscription plan')
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        verbose_name=_('Billing Cycle'),
        help_text=_('Billing frequency')
    )
    
    # Pricing
    price_monthly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Monthly Price'),
        help_text=_('Price per month')
    )
    price_yearly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Yearly Price'),
        help_text=_('Price per year (if applicable)')
    )
    setup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Setup Fee'),
        help_text=_('One-time setup fee')
    )
    
    # User and resource limits
    max_users = models.IntegerField(
        default=1,
        verbose_name=_('Max Users'),
        help_text=_('Maximum number of users allowed')
    )
    max_publishers = models.IntegerField(
        default=10,
        verbose_name=_('Max Publishers'),
        help_text=_('Maximum number of publishers allowed')
    )
    max_smartlinks = models.IntegerField(
        default=100,
        verbose_name=_('Max Smartlinks'),
        help_text=_('Maximum number of smartlinks allowed')
    )
    max_campaigns = models.IntegerField(
        default=10,
        verbose_name=_('Max Campaigns'),
        help_text=_('Maximum number of campaigns allowed')
    )
    
    # API and storage limits
    api_calls_per_day = models.IntegerField(
        default=1000,
        verbose_name=_('API Calls Per Day'),
        help_text=_('Daily API call limit')
    )
    api_calls_per_hour = models.IntegerField(
        default=100,
        verbose_name=_('API Calls Per Hour'),
        help_text=_('Hourly API call limit')
    )
    storage_gb = models.IntegerField(
        default=1,
        verbose_name=_('Storage (GB)'),
        help_text=_('Storage limit in gigabytes')
    )
    bandwidth_gb_per_month = models.IntegerField(
        default=100,
        verbose_name=_('Bandwidth (GB/Month)'),
        help_text=_('Monthly bandwidth limit in gigabytes')
    )
    
    # Features and capabilities
    features = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Features'),
        help_text=_('Plan features as key-value pairs')
    )
    feature_flags = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Feature Flags'),
        help_text=_('Feature flag settings')
    )
    
    # Plan visibility and availability
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether the plan is currently available')
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Is Public'),
        help_text=_('Whether the plan is visible to all tenants')
    )
    is_upgrade_only = models.BooleanField(
        default=False,
        verbose_name=_('Is Upgrade Only'),
        help_text=_('Whether plan is only available as an upgrade')
    )
    
    # Ordering and display
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order'),
        help_text=_('Display order for plans')
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_('Is Featured'),
        help_text=_('Whether to highlight this plan')
    )
    badge_text = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Badge Text'),
        help_text=_('Text to display on plan badge')
    )
    
    # Trial settings
    trial_days = models.IntegerField(
        default=0,
        verbose_name=_('Trial Days'),
        help_text=_('Number of trial days offered')
    )
    trial_requires_payment = models.BooleanField(
        default=False,
        verbose_name=_('Trial Requires Payment'),
        help_text=_('Whether payment method is required for trial')
    )
    
    # Upgrade/downgrade rules
    can_downgrade = models.BooleanField(
        default=True,
        verbose_name=_('Can Downgrade'),
        help_text=_('Whether tenants can downgrade from this plan')
    )
    can_upgrade = models.BooleanField(
        default=True,
        verbose_name=_('Can Upgrade'),
        help_text=_('Whether tenants can upgrade from this plan')
    )
    downgrade_to_plans = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='upgrade_from_plans',
        verbose_name=_('Allowed Downgrade Plans'),
        help_text=_('Plans tenants can downgrade to')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional plan metadata')
    )
    
    class Meta:
        db_table = 'plans'
        verbose_name = _('Plan')
        verbose_name_plural = _('Plans')
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug'], name='idx_slug_1814'),
            models.Index(fields=['plan_type'], name='idx_plan_type_1815'),
            models.Index(fields=['is_active'], name='idx_is_active_1816'),
            models.Index(fields=['is_public'], name='idx_is_public_1817'),
            models.Index(fields=['sort_order'], name='idx_sort_order_1818'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.plan_type})"
    
    def clean(self):
        super().clean()
        if self.price_monthly < 0 or self.price_yearly < 0 or self.setup_fee < 0:
            raise ValidationError(_('Prices cannot be negative.'))
        
        if self.trial_days < 0:
            raise ValidationError(_('Trial days cannot be negative.'))
    
    @property
    def yearly_discount_percentage(self):
        """Calculate yearly discount percentage."""
        if self.price_monthly <= 0:
            return 0
        yearly_monthly_equivalent = self.price_yearly / 12
        discount = ((self.price_monthly - yearly_monthly_equivalent) / self.price_monthly) * 100
        return round(discount, 2)
    
    @property
    def has_trial(self):
        """Check if plan offers trial."""
        return self.trial_days > 0
    
    def can_tenant_downgrade_to(self, tenant):
        """Check if tenant can downgrade to this plan."""
        if not self.can_downgrade:
            return False
        
        # Check if tenant's current plan allows downgrading to this plan
        current_plan = tenant.plan
        return self in current_plan.downgrade_to_plans.all()
    
    def get_feature_value(self, feature_key, default=None):
        """Get feature value by key."""
        return self.features.get(feature_key, default)
    
    def has_feature(self, feature_key):
        """Check if plan has a specific feature."""
        return feature_key in self.features and self.features[feature_key]


class PlanFeature(TimeStampedModel):
    """
    Individual features that can be associated with plans.
    
    This model defines specific features that can be included
    in subscription plans.
    """
    
    FEATURE_TYPE_CHOICES = [
        ('boolean', _('Boolean')),
        ('number', _('Number')),
        ('string', _('String')),
        ('json', _('JSON')),
        ('enum', _('Enum')),
    ]
    
    name = models.CharField(
        max_length=255,
        verbose_name=_('Feature Name'),
        help_text=_('Name of the feature')
    )
    key = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_('Feature Key'),
        help_text=_('Unique identifier for the feature')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Description of what the feature does')
    )
    
    # Feature type and validation
    feature_type = models.CharField(
        max_length=20,
        choices=FEATURE_TYPE_CHOICES,
        default='boolean',
        verbose_name=_('Feature Type'),
        help_text=_('Data type of the feature value')
    )
    default_value = models.JSONField(
        default=None,
        blank=True,
        null=True,
        verbose_name=_('Default Value'),
        help_text=_('Default value for the feature')
    )
    
    # Validation rules
    min_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Min Value'),
        help_text=_('Minimum allowed value (for numeric types)')
    )
    max_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Max Value'),
        help_text=_('Maximum allowed value (for numeric types)')
    )
    allowed_values = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Allowed Values'),
        help_text=_('List of allowed values (for enum type)')
    )
    
    # Display settings
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Display Name'),
        help_text=_('Human-readable display name')
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Icon'),
        help_text=_('Icon class or identifier')
    )
    
    # Category and grouping
    category = models.CharField(
        max_length=100,
        default='general',
        verbose_name=_('Category'),
        help_text=_('Category for grouping features')
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order'),
        help_text=_('Display order within category')
    )
    
    # Visibility
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether the feature is currently available')
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Is Public'),
        help_text=_('Whether the feature is visible to users')
    )
    
    class Meta:
        db_table = 'plan_features'
        verbose_name = _('Plan Feature')
        verbose_name_plural = _('Plan Features')
        ordering = ['category', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['key'], name='idx_key_1819'),
            models.Index(fields=['category'], name='idx_category_1820'),
            models.Index(fields=['is_active'], name='idx_is_active_1821'),
        ]
    
    def __str__(self):
        return f"{self.display_name or self.name}"
    
    def clean(self):
        super().clean()
        if self.feature_type == 'enum' and not self.allowed_values:
            raise ValidationError(_('Enum type must have allowed values defined.'))
        
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValidationError(_('Min value cannot be greater than max value.'))
    
    def validate_value(self, value):
        """Validate a value against the feature's rules."""
        if self.feature_type == 'boolean':
            if not isinstance(value, bool):
                raise ValidationError(_('Boolean feature requires a boolean value.'))
        
        elif self.feature_type == 'number':
            try:
                num_value = float(value)
                if self.min_value is not None and num_value < self.min_value:
                    raise ValidationError(_('Value is below minimum.'))
                if self.max_value is not None and num_value > self.max_value:
                    raise ValidationError(_('Value is above maximum.'))
            except (ValueError, TypeError):
                raise ValidationError(_('Numeric feature requires a numeric value.'))
        
        elif self.feature_type == 'enum':
            if value not in self.allowed_values:
                raise ValidationError(_('Value not in allowed values list.'))
        
        elif self.feature_type == 'string':
            if not isinstance(value, str):
                raise ValidationError(_('String feature requires a string value.'))
        
        return True


class PlanUpgrade(TimeStampedModel):
    """
    Records of plan upgrades for tenants.
    
    This model tracks when tenants upgrade their plans,
    including pricing and reason information.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='plan_upgrades',
        verbose_name=_('Tenant'),
        help_text=_('The tenant that upgraded')
    )
    
    from_plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        null=True,
        related_name='upgrade_from_records',
        verbose_name=_('From Plan'),
        help_text=_('Previous plan')
    )
    to_plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='upgrade_to_records',
        verbose_name=_('To Plan'),
        help_text=_('New plan')
    )
    
    # Timing
    upgraded_at = models.DateTimeField(
        verbose_name=_('Upgraded At'),
        help_text=_('When the upgrade occurred')
    )
    effective_from = models.DateTimeField(
        verbose_name=_('Effective From'),
        help_text=_('When new plan takes effect')
    )
    
    # Pricing information
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Old Price'),
        help_text=_('Previous plan price')
    )
    new_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('New Price'),
        help_text=_('New plan price')
    )
    price_difference = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Price Difference'),
        help_text=_('Difference in price')
    )
    
    # Reason and notes
    reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Reason'),
        help_text=_('Reason for the upgrade')
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about the upgrade')
    )
    
    # Process information
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_plan_upgrades',
        verbose_name=_('Processed By'),
        help_text=_('User who processed the upgrade')
    )
    is_automatic = models.BooleanField(
        default=False,
        verbose_name=_('Is Automatic'),
        help_text=_('Whether upgrade was automatic')
    )
    
    # Payment information
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Payment Method'),
        help_text=_('Payment method used')
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Transaction ID'),
        help_text=_('Payment transaction ID')
    )
    
    class Meta:
        db_table = 'plan_upgrades'
        verbose_name = _('Plan Upgrade')
        verbose_name_plural = _('Plan Upgrades')
        ordering = ['-upgraded_at']
        indexes = [
            models.Index(fields=['tenant', 'upgraded_at'], name='idx_tenant_upgraded_at_1822'),
            models.Index(fields=['from_plan'], name='idx_from_plan_1823'),
            models.Index(fields=['to_plan'], name='idx_to_plan_1824'),
            models.Index(fields=['upgraded_at'], name='idx_upgraded_at_1825'),
        ]
    
    def __str__(self):
        return f"{self.tenant.name}: {self.from_plan} -> {self.to_plan}"
    
    def clean(self):
        super().clean()
        if self.from_plan == self.to_plan:
            raise ValidationError(_('From plan and to plan cannot be the same.'))
    
    def calculate_price_difference(self):
        """Calculate the price difference."""
        if self.old_price and self.new_price:
            self.price_difference = self.new_price - self.old_price
        return self.price_difference


class PlanUsage(TimeStampedModel):
    """
    Tracks plan usage metrics for tenants.
    
    This model monitors how tenants use their allocated
    resources and quotas.
    """
    
    PERIOD_CHOICES = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('yearly', _('Yearly')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='plan_usage',
        verbose_name=_('Tenant'),
        help_text=_('The tenant being tracked')
    )
    
    # Period information
    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default='monthly',
        verbose_name=_('Period'),
        help_text=_('Usage tracking period')
    )
    period_start = models.DateField(
        verbose_name=_('Period Start'),
        help_text=_('Start of the tracking period')
    )
    period_end = models.DateField(
        verbose_name=_('Period End'),
        help_text=_('End of the tracking period')
    )
    
    # Usage metrics
    api_calls_used = models.IntegerField(
        default=0,
        verbose_name=_('API Calls Used'),
        help_text=_('Number of API calls used in period')
    )
    storage_used_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Storage Used (GB)'),
        help_text=_('Storage used in gigabytes')
    )
    bandwidth_used_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Bandwidth Used (GB)'),
        help_text=_('Bandwidth used in gigabytes')
    )
    users_used = models.IntegerField(
        default=0,
        verbose_name=_('Users Used'),
        help_text=_('Number of active users')
    )
    publishers_used = models.IntegerField(
        default=0,
        verbose_name=_('Publishers Used'),
        help_text=_('Number of active publishers')
    )
    smartlinks_used = models.IntegerField(
        default=0,
        verbose_name=_('Smartlinks Used'),
        help_text=_('Number of smartlinks created')
    )
    campaigns_used = models.IntegerField(
        default=0,
        verbose_name=_('Campaigns Used'),
        help_text=_('Number of active campaigns')
    )
    
    # Additional metrics (JSON for flexibility)
    additional_metrics = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metrics'),
        help_text=_('Additional usage metrics')
    )
    
    # Limits for comparison
    api_calls_limit = models.IntegerField(
        default=0,
        verbose_name=_('API Calls Limit'),
        help_text=_('API calls limit for the period')
    )
    storage_limit_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Storage Limit (GB)'),
        help_text=_('Storage limit in gigabytes')
    )
    bandwidth_limit_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Bandwidth Limit (GB)'),
        help_text=_('Bandwidth limit in gigabytes')
    )
    users_limit = models.IntegerField(
        default=0,
        verbose_name=_('Users Limit'),
        help_text=_('User limit for the period')
    )
    publishers_limit = models.IntegerField(
        default=0,
        verbose_name=_('Publishers Limit'),
        help_text=_('Publisher limit for the period')
    )
    smartlinks_limit = models.IntegerField(
        default=0,
        verbose_name=_('Smartlinks Limit'),
        help_text=_('Smartlinks limit for the period')
    )
    campaigns_limit = models.IntegerField(
        default=0,
        verbose_name=_('Campaigns Limit'),
        help_text=_('Campaigns limit for the period')
    )
    
    class Meta:
        db_table = 'plan_usage'
        verbose_name = _('Plan Usage')
        verbose_name_plural = _('Plan Usage')
        ordering = ['-period_start', 'tenant']
        unique_together = ['tenant', 'period', 'period_start']
        indexes = [
            models.Index(fields=['tenant', 'period', 'period_start'], name='idx_tenant_period_period_s_001'),
            models.Index(fields=['period_start'], name='idx_period_start_1827'),
            models.Index(fields=['period_end'], name='idx_period_end_1828'),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} usage ({self.period}: {self.period_start})"
    
    @property
    def api_calls_percentage(self):
        """Calculate API calls usage percentage."""
        if self.api_calls_limit == 0:
            return 0
        return (self.api_calls_used / self.api_calls_limit) * 100
    
    @property
    def storage_percentage(self):
        """Calculate storage usage percentage."""
        if self.storage_limit_gb == 0:
            return 0
        return (self.storage_used_gb / self.storage_limit_gb) * 100
    
    @property
    def bandwidth_percentage(self):
        """Calculate bandwidth usage percentage."""
        if self.bandwidth_limit_gb == 0:
            return 0
        return (self.bandwidth_used_gb / self.bandwidth_limit_gb) * 100
    
    @property
    def users_percentage(self):
        """Calculate users usage percentage."""
        if self.users_limit == 0:
            return 0
        return (self.users_used / self.users_limit) * 100
    
    def is_over_limit(self, metric):
        """Check if a specific metric is over limit."""
        metric_map = {
            'api_calls': (self.api_calls_used, self.api_calls_limit),
            'storage': (self.storage_used_gb, self.storage_limit_gb),
            'bandwidth': (self.bandwidth_used_gb, self.bandwidth_limit_gb),
            'users': (self.users_used, self.users_limit),
            'publishers': (self.publishers_used, self.publishers_limit),
            'smartlinks': (self.smartlinks_used, self.smartlinks_limit),
            'campaigns': (self.campaigns_used, self.campaigns_limit),
        }
        
        if metric not in metric_map:
            return False
        
        used, limit = metric_map[metric]
        return limit > 0 and used > limit


class PlanQuota(TimeStampedModel):
    """
    Defines quota limits for plan features.
    
    This model sets specific limits and quotas for different
    features within subscription plans.
    """
    
    QUOTA_TYPE_CHOICES = [
        ('hard', _('Hard Limit')),
        ('soft', _('Soft Limit')),
        ('warning', _('Warning Only')),
    ]
    
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name='quotas',
        verbose_name=_('Plan'),
        help_text=_('The plan this quota belongs to')
    )
    
    feature_key = models.CharField(
        max_length=255,
        verbose_name=_('Feature Key'),
        help_text=_('Key of the feature this quota applies to')
    )
    
    # Quota limits
    hard_limit = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Hard Limit'),
        help_text=_('Hard limit that cannot be exceeded')
    )
    soft_limit = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Soft Limit'),
        help_text=_('Soft limit with warnings')
    )
    warning_threshold = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Warning Threshold'),
        help_text=_('Percentage at which to show warnings')
    )
    
    # Quota behavior
    quota_type = models.CharField(
        max_length=20,
        choices=QUOTA_TYPE_CHOICES,
        default='hard',
        verbose_name=_('Quota Type'),
        help_text=_('Type of quota enforcement')
    )
    overage_allowed = models.BooleanField(
        default=False,
        verbose_name=_('Overage Allowed'),
        help_text=_('Whether usage over limit is allowed')
    )
    overage_price_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name=_('Overage Price Per Unit'),
        help_text=_('Price per unit for overage usage')
    )
    
    # Reset behavior
    reset_period = models.CharField(
        max_length=20,
        choices=PlanUsage.PERIOD_CHOICES,
        default='monthly',
        verbose_name=_('Reset Period'),
        help_text=_('When quota resets')
    )
    reset_day_of_month = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Reset Day of Month'),
        help_text=_('Day of month when quota resets')
    )
    
    # Display settings
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Display Name'),
        help_text=_('Human-readable name for display')
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Unit'),
        help_text=_('Unit of measurement (e.g., calls, GB, users)')
    )
    
    class Meta:
        db_table = 'plan_quotas'
        verbose_name = _('Plan Quota')
        verbose_name_plural = _('Plan Quotas')
        ordering = ['plan', 'feature_key']
        unique_together = ['plan', 'feature_key']
        indexes = [
            models.Index(fields=['plan', 'feature_key'], name='idx_plan_feature_key_1829'),
            models.Index(fields=['quota_type'], name='idx_quota_type_1830'),
        ]
    
    def __str__(self):
        return f"{self.plan.name} - {self.feature_key} quota"
    
    def clean(self):
        super().clean()
        if self.hard_limit is not None and self.soft_limit is not None:
            if self.soft_limit > self.hard_limit:
                raise ValidationError(_('Soft limit cannot exceed hard limit.'))
        
        if self.reset_day_of_month is not None:
            if self.reset_day_of_month < 1 or self.reset_day_of_month > 31:
                raise ValidationError(_('Reset day must be between 1 and 31.'))
    
    def is_over_limit(self, current_usage):
        """Check if current usage exceeds quota limits."""
        if self.quota_type == 'hard' and self.hard_limit:
            return current_usage > self.hard_limit
        elif self.quota_type == 'soft' and self.soft_limit:
            return current_usage > self.soft_limit
        return False
    
    def should_warn(self, current_usage):
        """Check if warning should be shown for current usage."""
        if not self.warning_threshold:
            return False
        
        limit = self.soft_limit or self.hard_limit
        if not limit:
            return False
        
        percentage = (current_usage / limit) * 100
        return percentage >= self.warning_threshold
    
    def calculate_overage_cost(self, current_usage):
        """Calculate cost for overage usage."""
        if not self.overage_allowed or not self.overage_price_per_unit:
            return 0
        
        limit = self.hard_limit or self.soft_limit
        if not limit or current_usage <= limit:
            return 0
        
        overage_units = current_usage - limit
        return overage_units * self.overage_price_per_unit
