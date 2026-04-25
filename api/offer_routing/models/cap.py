"""
Cap Models for Offer Routing System

This module contains models for offer caps and limits,
including per-user and global cap management.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import CapType, RoutingDecisionReason
from ..constants import DEFAULT_CAP_DAILY

User = get_user_model()


class OfferRoutingCap(models.Model):
    """
    Global caps for individual offers.
    
    Defines limits on how many times an offer can be shown
    to users (daily, hourly, total) and across the entire system.
    """
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='caps',
        verbose_name=_('Offer')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='caps',
        verbose_name=_('tenants.Tenant')
    )
    cap_type = models.CharField(
        _('Cap Type'),
        max_length=20,
        choices=CapType.CHOICES,
        default=CapType.DAILY
    )
    cap_value = models.IntegerField(_('Cap Value'), help_text=_('Maximum number allowed'))
    
    # Cap tracking
    current_count = models.IntegerField(_('Current Count'), default=0)
    reset_at = models.DateTimeField(_('Last Reset At'), null=True, blank=True)
    next_reset_at = models.DateTimeField(_('Next Reset At'), null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_caps'
        verbose_name = _('Offer Routing Cap')
        verbose_name_plural = _('Offer Routing Caps')
        ordering = ['offer', 'cap_type', 'tenant']
        indexes = [
            models.Index(fields=['offer', 'cap_type'], name='idx_offer_cap_type_1222'),
            models.Index(fields=['tenant'], name='idx_tenant_1223'),
            models.Index(fields=['created_at'], name='idx_created_at_1224'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.cap_type} ({self.cap_value})"
    
    def is_active(self):
        """Check if cap is currently active."""
        if self.cap_type == CapType.DAILY:
            return self.next_reset_at is None or timezone.now() >= self.next_reset_at
        elif self.cap_type == CapType.HOURLY:
            return True
        elif self.cap_type == CapType.TOTAL:
            return self.current_count < self.cap_value
        return False
    
    def get_remaining_capacity(self):
        """Get remaining capacity for this cap."""
        if self.cap_type == CapType.DAILY:
            if self.next_reset_at and timezone.now() >= self.next_reset_at:
                return self.cap_value  # Reset for new period
            return max(0, self.cap_value - self.current_count)
        elif self.cap_type == CapType.TOTAL:
            return max(0, self.cap_value - self.current_count)
        else:
            return float('inf')  # No limit for other types
    
    def reset_daily_cap(self):
        """Reset daily cap for next day."""
        self.current_count = 0
        self.next_reset_at = timezone.now() + timezone.timedelta(days=1)
        self.save()
    
    def increment_count(self):
        """Increment the current count for this cap."""
        if self.cap_type != CapType.TOTAL:
            self.current_count += 1
            self.save()
    
    def clean(self):
        """Validate model data."""
        if self.cap_value <= 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Cap value must be positive'))
        
        if self.cap_type == CapType.DAILY and self.cap_value > 1000:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Daily cap cannot exceed 1000'))
        
        if self.current_count < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Current count cannot be negative'))


class UserOfferCap(models.Model):
    """
    User-specific offer caps.
    
    Tracks individual user limits for offer exposure,
    preventing spam and ensuring fair distribution.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_caps',
        verbose_name=_('User')
    )
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='user_caps',
        verbose_name=_('Offer')
    )
    cap_type = models.CharField(
        _('Cap Type'),
        max_length=20,
        choices=CapType.CHOICES,
        default=CapType.DAILY
    )
    max_shows_per_day = models.IntegerField(
        _('Max Shows Per Day'),
        default=DEFAULT_CAP_DAILY,
        help_text=_('Maximum times this offer can be shown to this user per day')
    )
    
    # Cap tracking
    shown_today = models.IntegerField(_('Shown Today'), default=0)
    reset_at = models.DateTimeField(_('Last Reset At'), null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_user_caps'
        verbose_name = _('User Offer Cap')
        verbose_name_plural = _('User Offer Caps')
        ordering = ['user', 'offer', 'cap_type']
        indexes = [
            models.Index(fields=['user', 'offer'], name='idx_user_offer_1225'),
            models.Index(fields=['user', 'cap_type'], name='idx_user_cap_type_1226'),
            models.Index(fields=['created_at'], name='idx_created_at_1227'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.name} ({self.cap_type})"
    
    def is_daily_cap_reached(self):
        """Check if daily cap has been reached."""
        return self.shown_today >= self.max_shows_per_day
    
    def can_show_offer(self):
        """Check if user can see this offer."""
        if self.cap_type == CapType.DAILY:
            return not self.is_daily_cap_reached()
        return True
    
    def increment_shown(self):
        """Increment the shown count for today."""
        if self.cap_type == CapType.DAILY:
            self.shown_today += 1
            self.save()
    
    def reset_daily_cap(self):
        """Reset daily cap for next day."""
        self.shown_today = 0
        self.reset_at = timezone.now()
        self.save()
    
    def clean(self):
        """Validate model data."""
        if self.max_shows_per_day <= 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Max shows per day must be positive'))
        
        if self.max_shows_per_day > 1000:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Max shows per day cannot exceed 1000'))
        
        if self.shown_today < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Shown today cannot be negative'))


class CapOverride(models.Model):
    """
    Override for offer caps.
    
    Allows temporary or permanent modifications to standard caps
    for specific tenants, users, or offers.
    """
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='overrides',
        verbose_name=_('Offer')
    )
    tenant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='overrides',
        verbose_name=_('tenants.Tenant')
    )
    
    # Override configuration
    override_cap = models.IntegerField(_('Override Cap'), null=True, blank=True)
    override_type = models.CharField(
        _('Override Type'),
        max_length=20,
        choices=[
            ('increase', _('Increase')),
            ('decrease', _('Decrease')),
            ('replace', _('Replace')),
            ('multiply', _('Multiply')),
            ('disable', _('Disable'))
        ],
        default='increase'
    )
    
    # Override timing
    valid_from = models.DateTimeField(_('Valid From'), null=True, blank=True)
    valid_to = models.DateTimeField(_('Valid To'), null=True, blank=True)
    
    # Reason and metadata
    reason = models.TextField(_('Reason'), blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='overrides_approved_by',
        verbose_name=_('Approved By')
    )
    
    # Status
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_cap_overrides'
        verbose_name = _('Cap Override')
        verbose_name_plural = _('Cap Overrides')
        ordering = ['-created_at', 'offer']
        indexes = [
            models.Index(fields=['offer', 'tenant'], name='idx_offer_tenant_1228'),
            models.Index(fields=['is_active'], name='idx_is_active_1229'),
            models.Index(fields=['valid_from', 'valid_to'], name='idx_valid_from_valid_to_1230'),
            models.Index(fields=['created_at'], name='idx_created_at_1231'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} Override ({self.override_type})"
    
    def is_valid_now(self):
        """Check if override is currently valid."""
        if not self.valid_from or not self.valid_to:
            return True  # No time limit
        
        now = timezone.now()
        return self.valid_from <= now <= self.valid_to
    
    def apply_override(self, original_cap_value):
        """Apply this override to an original cap value."""
        if self.override_type == 'increase':
            return original_cap_value + self.override_cap
        elif self.override_type == 'decrease':
            return max(0, original_cap_value - self.override_cap)
        elif self.override_type == 'multiply':
            return original_cap_value * self.override_cap
        elif self.override_type == 'replace':
            return self.override_cap
        elif self.override_type == 'disable':
            return 0
        return original_cap_value
    
    def clean(self):
        """Validate model data."""
        if self.override_type == 'multiply' and self.override_cap <= 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Override cap must be positive for multiply type'))
        
        if self.override_type == 'decrease' and self.override_cap < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Override cap must be non-negative for decrease type'))
        
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Valid from must be before valid to'))


class CapManager(models.Manager):
    """
    Custom manager for cap-related models with utility methods.
    """
    
    def get_active_caps(self):
        """Get all active caps."""
        return self.filter(is_active=True)
    
    def get_caps_by_type(self, cap_type):
        """Get caps by type."""
        return self.filter(cap_type=cap_type)
    
    def get_user_caps(self, user_id):
        """Get all caps for a specific user."""
        return self.filter(user_id=user_id)
    
    def get_offer_caps(self, offer_id):
        """Get all caps for a specific offer."""
        return self.filter(offer_id=offer_id)
    
    def get_overrides_for_offer(self, offer_id):
        """Get all overrides for a specific offer."""
        return OfferRoutingCap.objects.filter(offer_id=offer_id)
    
    def get_active_overrides(self):
        """Get all currently active overrides."""
        return OfferRoutingCap.objects.filter(is_active=True)
    
    def get_overrides_by_tenant(self, tenant_id):
        """Get all overrides for a specific tenant."""
        return OfferRoutingCap.objects.filter(tenant_id=tenant_id)
    
    def check_user_cap(self, user_id, offer_id, cap_type):
        """Check if user has reached a specific cap."""
        try:
            user_cap = UserOfferCap.objects.get(
                user_id=user_id,
                offer_id=offer_id,
                cap_type=cap_type
            )
            
            if cap_type == CapType.DAILY:
                return user_cap.is_daily_cap_reached()
            else:
                # For other cap types, check against global cap
                global_cap = OfferRoutingCap.objects.filter(
                    offer_id=offer_id,
                    cap_type=cap_type,
                    is_active=True
                ).first()
                
                if global_cap:
                    current_usage = global_cap.current_count
                    return current_usage >= global_cap.cap_value
                
            return False
            
        except UserOfferCap.DoesNotExist:
            return False
    
    def reset_user_daily_caps(self):
        """Reset daily caps for all users."""
        UserOfferCap.objects.filter(cap_type=CapType.DAILY).update(
            shown_today=0,
            reset_at=timezone.now()
        )


# Add custom managers to models
OfferRoutingCap.add_manager_class = CapManager
UserOfferCap.add_manager_class = CapManager
CapOverride.add_manager_class = CapManager
