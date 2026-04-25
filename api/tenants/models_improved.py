"""
Tenant Models - Improved Version with Enhanced Security and Features

This module contains comprehensive tenant management models with advanced security,
audit logging, subscription management, and multi-tenant capabilities.
"""

import uuid
import secrets
from datetime import datetime, timedelta
from django.db import models
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser

User = get_user_model()


class TenantManager(models.Manager):
    """
    Custom manager for Tenant model with additional query methods.
    """
    
    def active(self):
        """Return only active tenants."""
        return self.filter(is_active=True, is_deleted=False)
    
    def by_plan(self, plan):
        """Return tenants by plan type."""
        return self.filter(plan=plan, is_active=True, is_deleted=False)
    
    def expiring_soon(self, days=7):
        """Return tenants whose trial/subscription expires soon."""
        cutoff = timezone.now() + timedelta(days=days)
        return self.filter(
            is_active=True,
            is_deleted=False,
            billing__subscription_ends_at__lte=cutoff
        ).distinct()
    
    def with_user_counts(self):
        """Return tenants with user count annotations."""
        return self.annotate(
            user_count=models.Count('users', filter=models.Q(users__is_active=True))
        )


class SoftDeleteManager(models.Manager):
    """
    Manager that excludes soft-deleted objects by default.
    """
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Tenant(models.Model):
    """
    Main Tenant model with comprehensive multi-tenant support.
    
    Represents a tenant organization with billing, settings, and user management.
    """
    
    PLAN_CHOICES = [
        ("basic", _("Basic")),
        ("pro", _("Pro")),
        ("enterprise", _("Enterprise")),
        ("custom", _("Custom")),
    ]
    
    STATUS_CHOICES = [
        ("trial", _("Trial")),
        ("active", _("Active")),
        ("suspended", _("Suspended")),
        ("expired", _("Expired")),
        ("cancelled", _("Cancelled")),
    ]
    
    # Core Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, 
        verbose_name=_("Tenant Name"),
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s\-_\.]+$',
                message=_("Tenant name can only contain letters, numbers, spaces, hyphens, underscores, and dots.")
            )
        ]
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("Unique identifier for URLs and API access")
    )
    domain = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Domain"),
        help_text=_("Custom domain for the tenant")
    )
    
    # Contact Information
    admin_email = models.EmailField(
        verbose_name=_("Admin Email"),
        help_text=_("Primary contact email for tenant administration")
    )
    contact_phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("Contact Phone"),
        validators=[
            RegexValidator(
                regex=r'^\+?[\d\s\-\(\)]+$',
                message=_("Please enter a valid phone number.")
            )
        ]
    )
    support_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name=_("Support Email")
    )
    
    # Branding
    logo = models.ImageField(
        upload_to="tenant_logos/%Y/%m/",
        null=True,
        blank=True,
        verbose_name=_("Logo"),
        help_text=_("Company logo for branding")
    )
    primary_color = models.CharField(
        max_length=7,
        default="#007bff",
        verbose_name=_("Primary Color"),
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message=_("Enter a valid hex color code.")
            )
        ]
    )
    secondary_color = models.CharField(
        max_length=7,
        default="#6c757d",
        verbose_name=_("Secondary Color"),
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message=_("Enter a valid hex color code.")
            )
        ]
    )
    
    # Subscription & Billing
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="basic",
        verbose_name=_("Plan")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="trial",
        verbose_name=_("Status")
    )
    max_users = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Max Users"),
        validators=[MinValueValidator(1)]
    )
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Trial Ends At")
    )
    
    # Security & Access
    api_key = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("API Key")
    )
    api_secret = models.CharField(
        max_length=64,
        default=secrets.token_urlsafe(48),
        editable=False,
        verbose_name=_("API Secret")
    )
    webhook_secret = models.CharField(
        max_length=64,
        default=secrets.token_urlsafe(32),
        editable=False,
        verbose_name=_("Webhook Secret")
    )
    
    # Geographic & Regional
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name=_("Timezone")
    )
    country_code = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        verbose_name=_("Country Code"),
        help_text=_("ISO 3166-1 alpha-2 country code")
    )
    currency_code = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_("Currency Code"),
        help_text=_("ISO 4217 currency code")
    )
    data_region = models.CharField(
        max_length=20,
        default='us-east-1',
        verbose_name=_("Data Region")
    )
    
    # Mobile App Configuration
    android_package_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Android Package Name")
    )
    ios_bundle_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("iOS Bundle ID")
    )
    firebase_server_key = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Firebase Server Key"),
        help_text=_("Server key for Firebase push notifications")
    )
    
    # Metadata & Tracking
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Additional tenant configuration as JSON")
    )
    
    # Soft Delete & Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name=_("Is Deleted")
    )
    is_suspended = models.BooleanField(
        default=False,
        verbose_name=_("Is Suspended")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deleted At")
    )
    
    # Relationships
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_tenants',
        verbose_name=_("Owner")
    )
    parent_tenant = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_tenants',
        verbose_name=_("Parent Tenant"),
        help_text=_("For multi-level tenant hierarchies")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tenants',
        verbose_name=_("Created By")
    )
    
    objects = TenantManager()
    all_objects = models.Manager()  # Includes soft-deleted
    
    class Meta:
        db_table = "tenants"
        verbose_name = _("Tenant")
        verbose_name_plural = _("Tenants")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['domain']),
            models.Index(fields=['api_key']),
            models.Index(fields=['status']),
            models.Index(fields=['plan']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def clean(self):
        """Validate tenant data."""
        super().clean()
        
        # Validate slug uniqueness
        if self.slug:
            existing = Tenant.objects.filter(slug=self.slug).exclude(id=self.id)
            if existing.exists():
                raise ValidationError(_("Tenant slug already exists."))
        
        # Validate domain uniqueness
        if self.domain:
            existing = Tenant.objects.filter(domain=self.domain).exclude(id=self.id)
            if existing.exists():
                raise ValidationError(_("Domain already exists."))
        
        # Validate parent tenant (prevent circular references)
        if self.parent_tenant:
            if self.parent_tenant == self:
                raise ValidationError(_("Tenant cannot be its own parent."))
            
            # Check for circular reference
            parent = self.parent_tenant
            while parent:
                if parent.parent_tenant == self:
                    raise ValidationError(_("Circular parent reference detected."))
                parent = parent.parent_tenant
    
    def save(self, *args, **kwargs):
        """Override save to handle slug generation and soft delete."""
        is_new = self.pk is None
        
        # Generate slug if not provided
        if not self.slug and self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Handle soft delete
        if self.is_deleted and not self.deleted_at:
            self.deleted_at = timezone.now()
            self.is_active = False
        elif not self.is_deleted and self.deleted_at:
            self.deleted_at = None
        
        super().save(*args, **kwargs)
        
        # Create related objects for new tenants
        if is_new:
            self._create_defaults()
    
    def _create_defaults(self):
        """Create default related objects for new tenant."""
        from .signals import create_tenant_defaults
        create_tenant_defaults(sender=self.__class__, instance=self, created=True)
    
    def delete(self, using=None, keep_parents=False):
        """Override delete to implement soft delete."""
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Actually delete the record from database."""
        super().delete(using=using, keep_parents=keep_parents)
    
    # Properties and Methods
    @property
    def is_trial_active(self):
        """Check if trial is still active."""
        if self.status != 'trial' or not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at
    
    @property
    def days_until_trial_expires(self):
        """Days remaining until trial expires."""
        if not self.trial_ends_at:
            return None
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def trial_expired(self):
        """Check if trial has expired."""
        if self.status != 'trial' or not self.trial_ends_at:
            return False
        return timezone.now() > self.trial_ends_at
    
    def get_active_user_count(self):
        """Get count of active users for this tenant."""
        return User.objects.filter(
            tenant=self,
            is_active=True
        ).count()
    
    def get_total_user_count(self):
        """Get total user count including inactive users."""
        return User.objects.filter(tenant=self).count()
    
    def is_user_limit_reached(self):
        """Check if user limit has been reached."""
        return self.get_active_user_count() >= self.max_users
    
    def get_user_limit_remaining(self):
        """Get remaining user slots."""
        return max(0, self.max_users - self.get_active_user_count())
    
    def can_add_user(self):
        """Check if tenant can add more users."""
        return not self.is_user_limit_reached() and self.is_active and not self.is_deleted
    
    def regenerate_api_secret(self):
        """Regenerate API secret."""
        self.api_secret = secrets.token_urlsafe(48)
        self.save(update_fields=['api_secret', 'updated_at'])
        return self.api_secret
    
    def regenerate_webhook_secret(self):
        """Regenerate webhook secret."""
        self.webhook_secret = secrets.token_urlsafe(32)
        self.save(update_fields=['webhook_secret', 'updated_at'])
        return self.webhook_secret
    
    def get_logo_url(self, request=None):
        """Get full URL for logo."""
        if not self.logo:
            return None
        if request:
            return request.build_absolute_uri(self.logo.url)
        return self.logo.url
    
    def get_settings(self):
        """Get tenant settings, create if doesn't exist."""
        from .models import TenantSettings
        settings, created = TenantSettings.objects.get_or_create(tenant=self)
        return settings
    
    def get_billing(self):
        """Get tenant billing, create if doesn't exist."""
        from .models import TenantBilling
        billing, created = TenantBilling.objects.get_or_create(tenant=self)
        return billing
    
    def get_feature_flags(self):
        """Get tenant feature flags."""
        settings = self.get_settings()
        return {
            'enable_referral': settings.enable_referral,
            'enable_offerwall': settings.enable_offerwall,
            'enable_kyc': settings.enable_kyc,
            'enable_leaderboard': settings.enable_leaderboard,
            'enable_chat': settings.enable_chat,
            'enable_push_notifications': settings.enable_push_notifications,
        }
    
    def has_feature(self, feature):
        """Check if tenant has specific feature enabled."""
        flags = self.get_feature_flags()
        return flags.get(feature, False)
    
    def get_usage_stats(self):
        """Get tenant usage statistics."""
        from django.db.models import Count, Sum, Avg
        from ..models.core import UserActivity, Transaction
        
        stats = {
            'users': {
                'total': self.get_total_user_count(),
                'active': self.get_active_user_count(),
                'limit': self.max_users,
                'remaining': self.get_user_limit_remaining(),
                'limit_reached': self.is_user_limit_reached(),
            },
            'billing': {
                'status': self.status,
                'plan': self.plan,
                'trial_active': self.is_trial_active,
                'trial_days_remaining': self.days_until_trial_expires,
                'trial_expired': self.trial_expired,
            }
        }
        
        # Add activity stats if available
        try:
            activity_stats = UserActivity.objects.filter(
                user__tenant=self
            ).aggregate(
                total_activities=Count('id'),
                today_activities=Count('id', filter=models.Q(created_at__date=timezone.now().date())),
                avg_daily=Avg('id')
            )
            stats['activity'] = activity_stats
        except:
            pass
        
        return stats
    
    def audit_log(self, action, details=None, user=None):
        """Create audit log entry."""
        from .models import TenantAuditLog
        return TenantAuditLog.objects.create(
            tenant=self,
            action=action,
            details=details or {},
            user=user,
            ip_address=None  # Will be set by middleware
        )


class TenantSettings(models.Model):
    """
    Tenant-specific settings and configuration.
    
    Stores customizable settings for each tenant including
    feature flags, branding, and business rules.
    """
    
    # App Configuration
    app_name = models.CharField(
        max_length=100,
        default='EarningApp',
        verbose_name=_("App Name")
    )
    app_description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("App Description")
    )
    support_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name=_("Support Email")
    )
    privacy_policy_url = models.URLField(
        null=True,
        blank=True,
        verbose_name=_("Privacy Policy URL")
    )
    terms_url = models.URLField(
        null=True,
        blank=True,
        verbose_name=_("Terms of Service URL")
    )
    about_url = models.URLField(
        null=True,
        blank=True,
        verbose_name=_("About URL")
    )
    
    # Feature Flags
    enable_referral = models.BooleanField(
        default=True,
        verbose_name=_("Enable Referral System")
    )
    enable_offerwall = models.BooleanField(
        default=True,
        verbose_name=_("Enable Offerwall")
    )
    enable_kyc = models.BooleanField(
        default=True,
        verbose_name=_("Enable KYC")
    )
    enable_leaderboard = models.BooleanField(
        default=True,
        verbose_name=_("Enable Leaderboard")
    )
    enable_chat = models.BooleanField(
        default=False,
        verbose_name=_("Enable Chat")
    )
    enable_push_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Enable Push Notifications")
    )
    enable_analytics = models.BooleanField(
        default=True,
        verbose_name=_("Enable Analytics")
    )
    enable_api_access = models.BooleanField(
        default=True,
        verbose_name=_("Enable API Access")
    )
    
    # Payout Configuration
    min_withdrawal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=5.00,
        verbose_name=_("Minimum Withdrawal"),
        validators=[MinValueValidator(0.01)]
    )
    max_withdrawal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10000.00,
        verbose_name=_("Maximum Withdrawal"),
        validators=[MinValueValidator(0.01)]
    )
    withdrawal_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Withdrawal Fee Percent"),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    withdrawal_fee_fixed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Fixed Withdrawal Fee"),
        validators=[MinValueValidator(0)]
    )
    daily_withdrawal_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000.00,
        verbose_name=_("Daily Withdrawal Limit"),
        validators=[MinValueValidator(0.01)]
    )
    
    # Referral Configuration
    referral_bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00,
        verbose_name=_("Referral Bonus Amount"),
        validators=[MinValueValidator(0)]
    )
    referral_bonus_type = models.CharField(
        max_length=20,
        choices=[
            ('fixed', 'Fixed Amount'),
            ('percentage', 'Percentage'),
        ],
        default='fixed',
        verbose_name=_("Referral Bonus Type")
    )
    max_referral_levels = models.PositiveIntegerField(
        default=3,
        verbose_name=_("Max Referral Levels"),
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    referral_percentages = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Referral Percentages"),
        help_text=_("Percentage for each referral level")
    )
    
    # Email Configuration
    email_from_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Email From Name")
    )
    email_from_address = models.EmailField(
        null=True,
        blank=True,
        verbose_name=_("Email From Address")
    )
    email_reply_to = models.EmailField(
        null=True,
        blank=True,
        verbose_name=_("Email Reply To")
    )
    
    # Security Configuration
    require_email_verification = models.BooleanField(
        default=True,
        verbose_name=_("Require Email Verification")
    )
    require_phone_verification = models.BooleanField(
        default=False,
        verbose_name=_("Require Phone Verification")
    )
    enable_two_factor_auth = models.BooleanField(
        default=False,
        verbose_name=_("Enable Two-Factor Authentication")
    )
    password_min_length = models.PositiveIntegerField(
        default=8,
        verbose_name=_("Minimum Password Length"),
        validators=[MinValueValidator(6), MaxValueValidator(128)]
    )
    session_timeout_minutes = models.PositiveIntegerField(
        default=1440,  # 24 hours
        verbose_name=_("Session Timeout (Minutes)"),
        validators=[MinValueValidator(5), MaxValueValidator(10080)]
    )
    
    # Rate Limiting
    api_rate_limit = models.CharField(
        max_length=50,
        default='1000/hour',
        verbose_name=_("API Rate Limit"),
        help_text=_("Rate limit format: number/period (e.g., 1000/hour)")
    )
    login_rate_limit = models.CharField(
        max_length=50,
        default='5/minute',
        verbose_name=_("Login Rate Limit")
    )
    
    # Custom Configuration
    custom_css = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Custom CSS")
    )
    custom_js = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Custom JavaScript")
    )
    custom_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Custom Configuration"),
        help_text=_("Additional configuration as JSON")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    # Relationship
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name=_("Tenant")
    )
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = _("Tenant Settings")
        verbose_name_plural = _("Tenant Settings")
    
    def __str__(self):
        return f"{self.tenant.name} Settings"
    
    def clean(self):
        """Validate settings data."""
        super().clean()
        
        # Validate withdrawal limits
        if self.min_withdrawal > self.max_withdrawal:
            raise ValidationError(_("Minimum withdrawal cannot be greater than maximum withdrawal."))
        
        if self.daily_withdrawal_limit < self.min_withdrawal:
            raise ValidationError(_("Daily withdrawal limit cannot be less than minimum withdrawal."))
        
        # Validate referral percentages
        if self.referral_percentages:
            if len(self.referral_percentages) != self.max_referral_levels:
                raise ValidationError(_("Number of referral percentages must match max referral levels."))
            
            total = sum(self.referral_percentages)
            if self.referral_bonus_type == 'percentage' and total > 100:
                raise ValidationError(_("Total referral percentages cannot exceed 100%."))
    
    def get_referral_percentage_for_level(self, level):
        """Get referral percentage for specific level."""
        if not self.referral_percentages or level < 1 or level > len(self.referral_percentages):
            return 0
        return self.referral_percentages[level - 1]
    
    def calculate_withdrawal_fee(self, amount):
        """Calculate withdrawal fee for given amount."""
        fee = 0
        
        # Fixed fee
        fee += self.withdrawal_fee_fixed
        
        # Percentage fee
        if self.withdrawal_fee_percent > 0:
            fee += amount * (self.withdrawal_fee_percent / 100)
        
        return fee
    
    def get_withdrawable_amount(self, amount):
        """Get amount after withdrawal fees."""
        fee = self.calculate_withdrawal_fee(amount)
        return max(0, amount - fee)
    
    def get_email_config(self):
        """Get email configuration."""
        return {
            'from_name': self.email_from_name or self.tenant.name,
            'from_address': self.email_from_address or self.tenant.admin_email,
            'reply_to': self.email_reply_to or self.tenant.admin_email,
        }
    
    def get_security_config(self):
        """Get security configuration."""
        return {
            'require_email_verification': self.require_email_verification,
            'require_phone_verification': self.require_phone_verification,
            'enable_two_factor_auth': self.enable_two_factor_auth,
            'password_min_length': self.password_min_length,
            'session_timeout_minutes': self.session_timeout_minutes,
        }
    
    def get_rate_limits(self):
        """Get rate limiting configuration."""
        return {
            'api_rate_limit': self.api_rate_limit,
            'login_rate_limit': self.login_rate_limit,
        }


class TenantBilling(models.Model):
    """
    Tenant billing and subscription management.
    
    Handles subscription plans, payments, invoices, and billing lifecycle.
    """
    
    STATUS_CHOICES = [
        ('trial', _('Trial')),
        ('active', _('Active')),
        ('past_due', _('Past Due')),
        ('cancelled', _('Cancelled')),
        ('expired', _('Expired')),
        ('unpaid', _('Unpaid')),
    ]
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
        ('custom', _('Custom')),
    ]
    
    # Subscription Details
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        verbose_name=_("Billing Status")
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        verbose_name=_("Billing Cycle")
    )
    
    # Dates
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Trial Ends At")
    )
    subscription_starts_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Subscription Starts At")
    )
    subscription_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Subscription Ends At")
    )
    last_payment_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Payment At")
    )
    next_payment_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Next Payment At")
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Cancelled At")
    )
    
    # Pricing
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Monthly Price"),
        validators=[MinValueValidator(0)]
    )
    setup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Setup Fee"),
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_("Currency")
    )
    
    # Payment Processing
    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Stripe Customer ID")
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Stripe Subscription ID")
    )
    payment_method_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Payment Method ID")
    )
    
    # Usage Tracking
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Current Period Start")
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Current Period End")
    )
    
    # Metadata
    billing_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Billing Metadata")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    # Relationship
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing',
        verbose_name=_("Tenant")
    )
    
    class Meta:
        db_table = 'tenant_billing'
        verbose_name = _("Tenant Billing")
        verbose_name_plural = _("Tenant Billing")
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['next_payment_at']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.status}"
    
    def clean(self):
        """Validate billing data."""
        super().clean()
        
        # Validate dates
        if self.subscription_starts_at and self.subscription_ends_at:
            if self.subscription_starts_at >= self.subscription_ends_at:
                raise ValidationError(_("Subscription start date must be before end date."))
        
        if self.current_period_start and self.current_period_end:
            if self.current_period_start >= self.current_period_end:
                raise ValidationError(_("Current period start must be before end date."))
    
    @property
    def is_active(self):
        """Check if subscription is active."""
        if self.status == 'trial':
            return self.trial_ends_at and self.trial_ends_at > timezone.now()
        elif self.status == 'active':
            return self.subscription_ends_at and self.subscription_ends_at > timezone.now()
        return False
    
    @property
    def days_until_expiry(self):
        """Days until subscription expires."""
        if not self.subscription_ends_at:
            return None
        delta = self.subscription_ends_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def is_expired(self):
        """Check if subscription has expired."""
        if self.status == 'trial':
            return self.trial_ends_at and timezone.now() > self.trial_ends_at
        elif self.status == 'active':
            return self.subscription_ends_at and timezone.now() > self.subscription_ends_at
        return False
    
    @property
    def is_past_due(self):
        """Check if payment is past due."""
        return self.status == 'past_due' or (
            self.next_payment_at and 
            timezone.now() > self.next_payment_at and 
            self.status == 'active'
        )
    
    def get_current_usage(self):
        """Get current billing period usage."""
        if not self.current_period_start or not self.current_period_end:
            return None
        
        from django.db.models import Count
        User = get_user_model()
        
        return {
            'period_start': self.current_period_start,
            'period_end': self.current_period_end,
            'active_users': User.objects.filter(
                tenant=self.tenant,
                is_active=True,
                date_joined__gte=self.current_period_start,
                date_joined__lte=self.current_period_end
            ).count(),
            'total_users': User.objects.filter(
                tenant=self.tenant,
                date_joined__gte=self.current_period_start,
                date_joined__lte=self.current_period_end
            ).count(),
        }
    
    def extend_trial(self, days):
        """Extend trial by specified days."""
        if self.trial_ends_at:
            self.trial_ends_at += timedelta(days=days)
        else:
            self.trial_ends_at = timezone.now() + timedelta(days=days)
        self.save(update_fields=['trial_ends_at', 'updated_at'])
    
    def activate_subscription(self, plan_price, billing_cycle='monthly'):
        """Activate subscription with given plan."""
        from django.utils import timezone
        
        self.status = 'active'
        self.monthly_price = plan_price
        self.billing_cycle = billing_cycle
        self.subscription_starts_at = timezone.now()
        
        # Calculate subscription end date based on billing cycle
        if billing_cycle == 'monthly':
            self.subscription_ends_at = timezone.now() + timedelta(days=30)
        elif billing_cycle == 'quarterly':
            self.subscription_ends_at = timezone.now() + timedelta(days=90)
        elif billing_cycle == 'yearly':
            self.subscription_ends_at = timezone.now() + timedelta(days=365)
        
        # Set current period
        self.current_period_start = timezone.now()
        self.current_period_end = self.subscription_ends_at
        self.next_payment_at = self.subscription_ends_at
        
        self.save()
    
    def cancel_subscription(self, at_period_end=True):
        """Cancel subscription."""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        
        if not at_period_end:
            self.subscription_ends_at = timezone.now()
            self.current_period_end = timezone.now()
        
        self.save(update_fields=[
            'status', 'cancelled_at', 'subscription_ends_at', 
            'current_period_end', 'updated_at'
        ])
    
    def create_invoice(self, amount, description=None, due_date=None):
        """Create invoice for this tenant."""
        from .models import TenantInvoice
        
        if not due_date:
            due_date = timezone.now() + timedelta(days=7)
        
        return TenantInvoice.objects.create(
            tenant=self.tenant,
            amount=amount,
            description=description or f"Subscription fee - {self.billing_cycle}",
            due_date=due_date,
            currency=self.currency
        )


class TenantInvoice(models.Model):
    """
    Tenant invoices and payment tracking.
    
    Manages billing invoices, payments, and financial records.
    """
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('sent', _('Sent')),
        ('paid', _('Paid')),
        ('partially_paid', _('Partially Paid')),
        ('overdue', _('Overdue')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]
    
    # Invoice Details
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Invoice Number")
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Amount"),
        validators=[MinValueValidator(0.01)]
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Tax Amount"),
        validators=[MinValueValidator(0)]
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Total Amount"),
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_("Currency")
    )
    
    # Description and Items
    description = models.TextField(
        verbose_name=_("Description")
    )
    line_items = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Line Items"),
        help_text=_("Invoice line items as JSON")
    )
    
    # Status and Dates
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name=_("Status")
    )
    issue_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Issue Date")
    )
    due_date = models.DateTimeField(
        verbose_name=_("Due Date")
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Paid At")
    )
    
    # Payment Information
    payment_method = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Payment Method")
    )
    transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Transaction ID")
    )
    payment_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Payment Notes")
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    # Relationship
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_("Tenant")
    )
    
    class Meta:
        db_table = 'tenant_invoices'
        verbose_name = _("Tenant Invoice")
        verbose_name_plural = _("Tenant Invoices")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.name}"
    
    def clean(self):
        """Validate invoice data."""
        super().clean()
        
        # Validate due date
        if self.due_date and self.due_date < self.issue_date:
            raise ValidationError(_("Due date cannot be before issue date."))
        
        # Validate amounts
        if self.amount < 0:
            raise ValidationError(_("Amount cannot be negative."))
        
        if self.tax_amount < 0:
            raise ValidationError(_("Tax amount cannot be negative."))
    
    def save(self, *args, **kwargs):
        """Override save to generate invoice number and calculate total."""
        if not self.invoice_number:
            # Generate unique invoice number
            year = timezone.now().year
            month = timezone.now().month
            count = TenantInvoice.objects.filter(
                created_at__year=year,
                created_at__month=month
            ).count()
            self.invoice_number = f"INV-{year}{month:02d}-{count + 1:04d}"
        
        # Calculate total amount
        self.total_amount = self.amount + self.tax_amount
        
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        if self.status in ['paid', 'cancelled', 'refunded']:
            return False
        return timezone.now() > self.due_date
    
    @property
    def days_overdue(self):
        """Days invoice is overdue."""
        if not self.is_overdue:
            return 0
        delta = timezone.now() - self.due_date
        return delta.days
    
    @property
    def amount_due(self):
        """Amount still due."""
        if self.status == 'paid':
            return 0
        return self.total_amount
    
    def mark_as_paid(self, payment_method=None, transaction_id=None, notes=None):
        """Mark invoice as paid."""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.payment_method = payment_method
        self.transaction_id = transaction_id
        self.payment_notes = notes
        self.save(update_fields=[
            'status', 'paid_at', 'payment_method', 
            'transaction_id', 'payment_notes', 'updated_at'
        ])
    
    def add_line_item(self, description, quantity, unit_price, tax_rate=0):
        """Add line item to invoice."""
        item = {
            'description': description,
            'quantity': quantity,
            'unit_price': float(unit_price),
            'tax_rate': float(tax_rate),
            'subtotal': float(quantity * unit_price),
            'tax_amount': float(quantity * unit_price * (tax_rate / 100)),
            'total': float(quantity * unit_price * (1 + tax_rate / 100))
        }
        
        self.line_items.append(item)
        
        # Update totals
        self.amount += item['subtotal']
        self.tax_amount += item['tax_amount']
        self.total_amount += item['total']
        
        self.save()


class TenantAuditLog(models.Model):
    """
    Audit log for tenant operations and changes.
    
    Tracks all important tenant-related actions for security
    and compliance purposes.
    """
    
    ACTION_CHOICES = [
        ('created', _('Created')),
        ('updated', _('Updated')),
        ('deleted', _('Deleted')),
        ('suspended', _('Suspended')),
        ('activated', _('Activated')),
        ('billing_updated', _('Billing Updated')),
        ('settings_updated', _('Settings Updated')),
        ('user_added', _('User Added')),
        ('user_removed', _('User Removed')),
        ('api_key_regenerated', _('API Key Regenerated')),
        ('feature_enabled', _('Feature Enabled')),
        ('feature_disabled', _('Feature Disabled')),
        ('payment_processed', _('Payment Processed')),
        ('invoice_generated', _('Invoice Generated')),
        ('login_attempt', _('Login Attempt')),
        ('permission_granted', _('Permission Granted')),
        ('permission_revoked', _('Permission Revoked')),
    ]
    
    # Audit Information
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name=_("Action")
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Details"),
        help_text=_("Action details as JSON")
    )
    old_values = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Old Values"),
        help_text=_("Previous values before change")
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("New Values"),
        help_text=_("New values after change")
    )
    
    # User and Request Information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_("User")
    )
    user_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name=_("User Email")
    )
    user_role = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("User Role")
    )
    
    # Request Information
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("User Agent")
    )
    request_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Request ID")
    )
    
    # Geographic Information
    country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        verbose_name=_("Country")
    )
    city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("City")
    )
    
    # Result Information
    success = models.BooleanField(
        default=True,
        verbose_name=_("Success")
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error Message")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    
    # Relationship
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_("Tenant")
    )
    
    class Meta:
        db_table = 'tenant_audit_logs'
        verbose_name = _("Tenant Audit Log")
        verbose_name_plural = _("Tenant Audit Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.action} by {self.user_email or 'System'}"
    
    @classmethod
    def log_action(cls, tenant, action, user=None, details=None, 
                   old_values=None, new_values=None, ip_address=None,
                   user_agent=None, success=True, error_message=None):
        """Create audit log entry."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_email = None
        user_role = None
        
        if user and hasattr(user, 'email'):
            user_email = user.email
            if user.is_superuser:
                user_role = 'superuser'
            elif hasattr(user, 'role'):
                user_role = user.role
            else:
                user_role = 'user'
        elif user and isinstance(user, str):
            user_email = user
            user_role = 'system'
        
        return cls.objects.create(
            tenant=tenant,
            action=action,
            details=details or {},
            old_values=old_values or {},
            new_values=new_values or {},
            user=user if hasattr(user, 'id') else None,
            user_email=user_email,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )


# Signal handlers
@receiver(post_save, sender=Tenant)
def create_tenant_defaults(sender, instance, created, **kwargs):
    """Create default related objects when tenant is created."""
    if created:
        # Create tenant settings
        TenantSettings.objects.get_or_create(tenant=instance)
        
        # Create tenant billing
        billing, created = TenantBilling.objects.get_or_create(
            tenant=instance,
            defaults={
                'status': 'trial',
                'trial_ends_at': timezone.now() + timedelta(days=14),
                'currency': instance.currency_code or 'USD',
            }
        )
        
        # Log creation
        TenantAuditLog.log_action(
            tenant=instance,
            action='created',
            user=instance.created_by,
            details={
                'plan': instance.plan,
                'max_users': instance.max_users,
                'trial_ends_at': billing.trial_ends_at.isoformat() if billing.trial_ends_at else None,
            }
        )


@receiver(pre_save, sender=Tenant)
def tenant_pre_save(sender, instance, **kwargs):
    """Handle tenant pre-save operations."""
    if instance.pk:
        # Get old values for audit logging
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = {
                'name': old_instance.name,
                'plan': old_instance.plan,
                'max_users': old_instance.max_users,
                'is_active': old_instance.is_active,
                'status': old_instance.status,
            }
        except sender.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=Tenant)
def tenant_post_save(sender, instance, created, **kwargs):
    """Handle tenant post-save operations."""
    if not created and hasattr(instance, '_old_values'):
        # Check for changes and log them
        changes = {}
        for field, old_value in instance._old_values.items():
            new_value = getattr(instance, field, None)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
        
        if changes:
            TenantAuditLog.log_action(
                tenant=instance,
                action='updated',
                details={'changes': changes},
                old_values=instance._old_values,
                new_values={field: changes[field]['new'] for field in changes}
            )


@receiver(post_delete, sender=Tenant)
def tenant_post_delete(sender, instance, **kwargs):
    """Handle tenant post-delete operations."""
    TenantAuditLog.log_action(
        tenant=instance,
        action='deleted',
        details={
            'name': instance.name,
            'slug': instance.slug,
            'plan': instance.plan,
        }
    )
