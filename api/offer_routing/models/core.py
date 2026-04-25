from django.conf import settings
"""
Core Models for Offer Routing System

This module contains the core models for offer routing, including
OfferRoute, RouteCondition, RouteAction and related models.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import (
    RouteConditionType, RouteOperator, ActionType, OfferStatus,
    RoutingPriority, RoutingDecisionReason
)
from ..constants import DEFAULT_ROUTE_PRIORITY, MAX_OFFERS_PER_ROUTE, MAX_CONDITIONS_PER_ROUTE


def get_user_model_lazy():
    """Lazy get_user_model to avoid Django app loading issues."""
    return get_user_model()


User = get_user_model_lazy()


class OfferRoute(models.Model):
    """
    Main routing configuration for offers.
    
    Defines how offers should be routed to users based on conditions,
    personalization, and business rules.
    """
    
    name = models.CharField(_('Route Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='routes',
        verbose_name=_('tenants.Tenant')
    )
    is_active = models.BooleanField(_('Is Active'), default=True)
    priority = models.IntegerField(_('Priority'), default=DEFAULT_ROUTE_PRIORITY)
    max_offers = models.IntegerField(_('Max Offers'), default=MAX_OFFERS_PER_ROUTE)
    
    # Timing
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_routes'
        verbose_name = _('Offer Route')
        verbose_name_plural = _('Offer Routes')
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1238'),
            models.Index(fields=['priority'], name='idx_priority_1239'),
            models.Index(fields=['created_at'], name='idx_created_at_1240'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.username})"
    
    def clean(self):
        """Validate model data."""
        if self.priority < 1 or self.priority > 10:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Priority must be between 1 and 10'))
        
        if self.max_offers < 1 or self.max_offers > 1000:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Max offers must be between 1 and 1000'))


class RouteCondition(models.Model):
    """
    Conditions for routing rules.
    
    Defines the logic that determines when a route should be applied.
    """
    
    route = models.ForeignKey(
        OfferRoute,
        on_delete=models.CASCADE,
        related_name='conditions',
        verbose_name=_('Route')
    )
    condition_type = models.CharField(
        _('Condition Type'),
        max_length=10,
        choices=RouteConditionType.CHOICES,
        default=RouteConditionType.AND
    )
    operator = models.CharField(
        _('Operator'),
        max_length=20,
        choices=RouteOperator.CHOICES,
        default=RouteOperator.EQUALS
    )
    field_name = models.CharField(_('Field Name'), max_length=50)
    value = models.TextField(_('Value'))
    logic = models.CharField(
        _('Logic'),
        max_length=10,
        choices=RouteConditionType.CHOICES,
        default=RouteConditionType.AND,
        help_text=_('How to combine multiple conditions')
    )
    priority = models.IntegerField(_('Priority'), default=0)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_conditions'
        verbose_name = _('Route Condition')
        verbose_name_plural = _('Route Conditions')
        ordering = ['route', 'priority', 'field_name']
        indexes = [
            models.Index(fields=['route', 'condition_type'], name='idx_route_condition_type_1241'),
            models.Index(fields=['field_name'], name='idx_field_name_1242'),
            models.Index(fields=['created_at'], name='idx_created_at_1243'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.field_name} {self.operator} {self.value}"


class RouteAction(models.Model):
    """
    Actions to be applied when route conditions are met.
    
    Defines what happens when a user matches a route - show, hide,
    boost, cap, or redirect offers.
    """
    
    route = models.ForeignKey(
        OfferRoute,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name=_('Route')
    )
    action_type = models.CharField(
        _('Action Type'),
        max_length=20,
        choices=ActionType.CHOICES,
        default=ActionType.SHOW
    )
    action_value = models.TextField(_('Action Value'), blank=True)
    priority = models.IntegerField(_('Priority'), default=0)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_actions'
        verbose_name = _('Route Action')
        verbose_name_plural = _('Route Actions')
        ordering = ['route', 'priority', 'action_type']
        indexes = [
            models.Index(fields=['route', 'action_type'], name='idx_route_action_type_1244'),
            models.Index(fields=['priority'], name='idx_priority_1245'),
            models.Index(fields=['created_at'], name='idx_created_at_1246'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.action_type}"


class TenantSettings(models.Model):
    """
    Tenant-specific routing settings.
    
    Stores configuration preferences for each tenant's routing system.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='routing_settings',
        verbose_name=_('User')
    )
    max_routing_time_ms = models.IntegerField(
        _('Max Routing Time (ms)'),
        default=50,
        help_text=_('Maximum allowed time for routing decisions in milliseconds')
    )
    cache_enabled = models.BooleanField(_('Cache Enabled'), default=True)
    cache_timeout_seconds = models.IntegerField(
        _('Cache Timeout (seconds)'),
        default=300,
        help_text=_('Cache timeout for routing decisions')
    )
    personalization_enabled = models.BooleanField(_('Personalization Enabled'), default=True)
    ab_testing_enabled = models.BooleanField(_('A/B Testing Enabled'), default=True)
    diversity_enabled = models.BooleanField(_('Diversity Rules Enabled'), default=True)
    
    # Advanced settings
    fallback_enabled = models.BooleanField(_('Fallback Enabled'), default=True)
    rate_limiting_enabled = models.BooleanField(_('Rate Limiting Enabled'), default=True)
    analytics_enabled = models.BooleanField(_('Analytics Enabled'), default=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_tenant_settings'
        verbose_name = _('Tenant Settings')
        verbose_name_plural = _('Tenant Settings')
        indexes = [
            models.Index(fields=['user'], name='idx_user_1247'),
            models.Index(fields=['created_at'], name='idx_created_at_1248'),
        ]
    
    def __str__(self):
        return f"{self.user.username} Settings"


class TenantBilling(models.Model):
    """
    Tenant billing information for routing usage.
    
    Tracks billing status and limits for offer routing services.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='routing_billing',
        verbose_name=_('User')
    )
    plan_name = models.CharField(_('Plan Name'), max_length=50)
    plan_tier = models.CharField(_('Plan Tier'), max_length=20)
    routing_requests_allowed = models.IntegerField(
        _('Routing Requests Allowed'),
        default=10000
    )
    routing_requests_used = models.IntegerField(
        _('Routing Requests Used'),
        default=0
    )
    
    # Billing cycle
    billing_cycle_start = models.DateField(_('Billing Cycle Start'))
    billing_cycle_end = models.DateField(_('Billing Cycle End'))
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_tenant_billing'
        verbose_name = _('Tenant Billing')
        verbose_name_plural = _('Tenant Billing')
        indexes = [
            models.Index(fields=['user'], name='idx_user_1249'),
            models.Index(fields=['billing_cycle_start', 'billing_cycle_end'], name='idx_billing_cycle_start_bi_700'),
            models.Index(fields=['created_at'], name='idx_created_at_1251'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.plan_tier}"


class TenantInvoice(models.Model):
    """
    Invoices for tenant routing services.
    
    Generated invoices for usage-based billing of routing services.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='routing_invoices',
        verbose_name=_('User')
    )
    invoice_number = models.CharField(_('Invoice Number'), max_length=50, unique=True)
    amount = models.DecimalField(_('Amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('Currency'), max_length=3, default='USD')
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled')
        ],
        default='draft'
    )
    
    due_date = models.DateField(_('Due Date'))
    paid_date = models.DateField(_('Paid Date'), null=True, blank=True)
    
    # Billing details
    routing_requests_count = models.IntegerField(_('Routing Requests Count'), default=0)
    cost_per_request = models.DecimalField(_('Cost Per Request'), max_digits=8, decimal_places=4)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_tenant_invoices'
        verbose_name = _('Tenant Invoice')
        verbose_name_plural = _('Tenant Invoices')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_user_status_1252'),
            models.Index(fields=['due_date'], name='idx_due_date_1253'),
            models.Index(fields=['invoice_number'], name='idx_invoice_number_1254'),
            models.Index(fields=['created_at'], name='idx_created_at_1255'),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.user.username}"


class RoutingConfig(models.Model):
    """
    Global routing configuration.
    
    System-wide settings that affect all tenants and routing behavior.
    """
    
    key = models.CharField(_('Config Key'), max_length=100, unique=True)
    value = models.TextField(_('Config Value'))
    description = models.TextField(_('Description'), blank=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_config'
        verbose_name = _('Routing Config')
        verbose_name_plural = _('Routing Configs')
        ordering = ['key']
        indexes = [
            models.Index(fields=['key'], name='idx_key_1256'),
            models.Index(fields=['is_active'], name='idx_is_active_1257'),
            models.Index(fields=['created_at'], name='idx_created_at_1258'),
        ]
    
    def __str__(self):
        return f"{self.key} = {self.value}"


class RoutingTemplate(models.Model):
    """
    Reusable routing templates.
    
    Predefined routing configurations that can be applied to multiple tenants.
    """
    
    name = models.CharField(_('Template Name'), max_length=100)
    description = models.TextField(_('Description'))
    template_data = models.JSONField(_('Template Data'))
    category = models.CharField(_('Category'), max_length=50)
    is_public = models.BooleanField(_('Is Public'), default=False)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='routing_templates',
        verbose_name=_('Created By')
    )
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_templates'
        verbose_name = _('Routing Template')
        verbose_name_plural = _('Routing Templates')
        ordering = ['name', 'category']
        indexes = [
            models.Index(fields=['category'], name='idx_category_1259'),
            models.Index(fields=['is_public'], name='idx_is_public_1260'),
            models.Index(fields=['created_by'], name='idx_created_by_1261'),
            models.Index(fields=['created_at'], name='idx_created_at_1262'),
        ]
    
    def __str__(self):
        return f"{self.name}"
