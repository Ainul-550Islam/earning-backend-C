"""
Fallback Models for Offer Routing System

This module contains models for fallback rules, default offer pools,
and empty result handlers when no routes match.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import FallbackType, RoutingPriority
from ..constants import MAX_FALLBACK_RULES_PER_TENANT

User = get_user_model()


class FallbackRule(models.Model):
    """
    Fallback rules for offer routing.
    
    Defines what happens when no primary routes match a user.
    Can be category-based, network-based, or use default offers.
    """
    
    name = models.CharField(_('Rule Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='fallback_rules',
        verbose_name=_('tenants.Tenant')
    )
    fallback_type = models.CharField(
        _('Fallback Type'),
        max_length=20,
        choices=FallbackType.CHOICES,
        default=FallbackType.CATEGORY
    )
    priority = models.IntegerField(_('Priority'), default=RoutingPriority.LOW)
    
    # Fallback configuration
    category = models.CharField(
        _('Category'),
        max_length=50,
        blank=True,
        help_text=_('Category to use for category-based fallback')
    )
    network = models.CharField(
        _('Network'),
        max_length=50,
        blank=True,
        help_text=_('Network to use for network-based fallback')
    )
    default_offer_pool = models.ForeignKey(
        'DefaultOfferPool',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_pools',
        verbose_name=_('Default Offer Pool')
    )
    
    # Action configuration
    action_type = models.CharField(
        _('Action Type'),
        max_length=20,
        choices=[
            ('show_default', _('Show Default Offers')),
            ('show_promo', _('Show Promotional Offers')),
            ('hide_section', _('Hide Section')),
        ],
        default='show_default'
    )
    action_value = models.TextField(_('Action Value'), blank=True)
    
    # Conditions
    conditions = models.JSONField(
        _('Conditions'),
        default=dict,
        blank=True,
        help_text=_('JSON conditions for when this fallback applies')
    )
    
    # Timing
    start_time = models.TimeField(_('Start Time'), null=True, blank=True)
    end_time = models.TimeField(_('End Time'), null=True, blank=True)
    timezone = models.CharField(
        _('Timezone'),
        max_length=50,
        default='UTC',
        help_text=_('Timezone for time-based conditions')
    )
    
    # Metadata
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_fallback_rules'
        verbose_name = _('Fallback Rule')
        verbose_name_plural = _('Fallback Rules')
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1263'),
            models.Index(fields=['priority'], name='idx_priority_1264'),
            models.Index(fields=['fallback_type'], name='idx_fallback_type_1265'),
            models.Index(fields=['created_at'], name='idx_created_at_1266'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.fallback_type})"
    
    def clean(self):
        """Validate model data."""
        if self.priority < 1 or self.priority > 10:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Priority must be between 1 and 10'))
    
    def applies_now(self, current_time=None):
        """Check if this fallback rule applies at current time."""
        if not current_time:
            current_time = timezone.now()
        
        if not self.start_time and not self.end_time:
            return True  # Always applies if no time constraints
        
        # Convert times to comparable format
        current_time = current_time.time()
        start_time = self.start_time.time() if self.start_time else None
        end_time = self.end_time.time() if self.end_time else None
        
        if start_time and end_time:
            # Check if current time is within the range
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                # Handle overnight range (e.g., 22:00 to 06:00)
                return current_time >= start_time or current_time <= end_time
        elif start_time:
            return current_time >= start_time
        elif end_time:
            return current_time <= end_time
        
        return False
    
    def evaluate_conditions(self, user_context):
        """Evaluate if conditions match the user context."""
        if not self.conditions:
            return True
        
        # This would implement complex condition evaluation logic
        # For now, return True as placeholder
        return True


class DefaultOfferPool(models.Model):
    """
    Default pools of offers for fallback routing.
    
    Contains collections of offers to use when no specific routes match.
    Can be categorized by type (general, promotional, seasonal, etc.).
    """
    
    name = models.CharField(_('Pool Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='default_pools',
        verbose_name=_('tenants.Tenant')
    )
    pool_type = models.CharField(
        _('Pool Type'),
        max_length=20,
        choices=[
            ('general', _('General')),
            ('promotional', _('Promotional')),
            ('seasonal', _('Seasonal')),
            ('emergency', _('Emergency')),
        ],
        default='general'
    )
    
    # Offer references
    offers = models.ManyToManyField(
        'OfferRoute',
        related_name='fallback_offers',
        blank=True,
        help_text=_('Offers in this pool')
    )
    
    # Pool configuration
    max_offers = models.IntegerField(
        _('Max Offers'),
        default=10,
        help_text=_('Maximum number of offers to return from this pool')
    )
    rotation_strategy = models.CharField(
        _('Rotation Strategy'),
        max_length=20,
        choices=[
            ('random', _('Random')),
            ('weighted', _('Weighted')),
            ('priority', _('Priority')),
            ('round_robin', _('Round Robin')),
        ],
        default='random'
    )
    
    # Metadata
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_default_pools'
        verbose_name = _('Default Offer Pool')
        verbose_name_plural = _('Default Offer Pools')
        ordering = ['name', 'pool_type']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1267'),
            models.Index(fields=['pool_type'], name='idx_pool_type_1268'),
            models.Index(fields=['created_at'], name='idx_created_at_1269'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.pool_type})"
    
    def get_random_offers(self, limit=None):
        """Get random offers from this pool."""
        if limit is None:
            limit = self.max_offers
        
        return self.offers.order_by('?')[:limit]
    
    def get_weighted_offers(self, limit=None):
        """Get weighted offers from this pool."""
        if limit is None:
            limit = self.max_offers
        
        return self.offers.all()[:limit]  # Would implement actual weighting
    
    def get_priority_offers(self, limit=None):
        """Get priority-sorted offers from this pool."""
        if limit is None:
            limit = self.max_offers
        
        return self.offers.order_by('priority')[:limit]


class EmptyResultHandler(models.Model):
    """
    Handler for when no offers can be shown to a user.
    
    Defines what action to take when routing returns empty results
    (hide section, show promotional message, redirect to URL, etc.).
    """
    
    name = models.CharField(_('Handler Name'), max_length=100)
    description = models.TextField(_('Description'), blank=True)
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='empty_handlers',
        verbose_name=_('tenants.Tenant')
    )
    
    # Action configuration
    action_type = models.CharField(
        _('Action Type'),
        max_length=20,
        choices=[
            ('hide_section', _('Hide Section')),
            ('show_promo', _('Show Promotional Message')),
            ('redirect_url', _('Redirect to URL')),
            ('show_default', _('Show Default Offers')),
            ('custom_message', _('Show Custom Message')),
        ],
        default='hide_section'
    )
    
    # Action details
    action_value = models.TextField(_('Action Value'), blank=True)
    redirect_url = models.URLField(
        _('Redirect URL'),
        max_length=500,
        blank=True,
        help_text=_('URL to redirect to when action is redirect')
    )
    custom_message = models.TextField(_('Custom Message'), blank=True)
    
    # Conditions
    conditions = models.JSONField(
        _('Conditions'),
        default=dict,
        blank=True,
        help_text=_('JSON conditions for when this handler applies')
    )
    
    # Metadata
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_empty_handlers'
        verbose_name = _('Empty Result Handler')
        verbose_name_plural = _('Empty Result Handlers')
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1270'),
            models.Index(fields=['action_type'], name='idx_action_type_1271'),
            models.Index(fields=['created_at'], name='idx_created_at_1272'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.action_type})"
    
    def should_apply(self, user_context):
        """Check if this handler should apply for the given user context."""
        if not self.conditions:
            return True
        
        # This would implement complex condition evaluation logic
        # For now, return True as placeholder
        return True


class FallbackManager(models.Manager):
    """
    Custom manager for fallback-related models with utility methods.
    """
    
    def get_active_rules(self, tenant_id=None):
        """Get all active fallback rules."""
        queryset = self.filter(is_active=True)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by('priority', 'name')
    
    def get_rules_by_type(self, fallback_type):
        """Get rules by fallback type."""
        return self.filter(fallback_type=fallback_type, is_active=True).order_by('priority')
    
    def get_applicable_rules(self, user_context):
        """Get fallback rules that apply to user context."""
        active_rules = self.get_active_rules()
        applicable_rules = []
        
        for rule in active_rules:
            if rule.applies_now(user_context.get('current_time')):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    def get_default_pools(self, tenant_id=None):
        """Get all active default offer pools."""
        queryset = self.filter(is_active=True)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by('name')
    
    def get_empty_handlers(self, tenant_id=None):
        """Get all active empty result handlers."""
        queryset = self.filter(is_active=True)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by('name')
    
    def get_fallback_for_user(self, user_id, user_context):
        """Get the best fallback for a user."""
        applicable_rules = self.get_applicable_rules(user_context)
        
        if not applicable_rules:
            # Try empty handlers
            handlers = self.get_empty_handlers(user_context.get('tenant_id'))
            for handler in handlers:
                if handler.should_apply(user_context):
                    return handler
            return None
        
        # Use highest priority applicable rule
        best_rule = max(applicable_rules, key=lambda x: x.priority)
        return best_rule


# Add custom managers to models
FallbackRule.add_manager_class = FallbackManager
DefaultOfferPool.add_manager_class = FallbackManager
EmptyResultHandler.add_manager_class = FallbackManager
