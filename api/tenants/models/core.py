"""
Core Tenant Models

This module contains the core tenant models that form the foundation
of the multi-tenant architecture.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class Tenant(TimeStampedModel, SoftDeleteModel):
    """
    Core tenant model representing a multi-tenant organization.
    
    This model represents a single tenant/organization in the multi-tenant
    system. Each tenant has its own isolated data, settings, billing,
    and configuration.
    """
    
    TIER_CHOICES = [
        ('free', _('Free')),
        ('basic', _('Basic')),
        ('pro', _('Pro')),
        ('enterprise', _('Enterprise')),
        ('custom', _('Custom')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('suspended', _('Suspended')),
        ('trial', _('Trial')),
        ('pending', _('Pending')),
        ('cancelled', _('Cancelled')),
    ]
    
    DATA_REGION_CHOICES = [
        ('us-east-1', _('US East')),
        ('us-west-2', _('US West')),
        ('eu-west-1', _('EU West')),
        ('ap-southeast-1', _('Asia Pacific')),
        ('ap-northeast-1', _('Asia Pacific North')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        verbose_name=_('Tenant Name'),
        help_text=_('The display name of the tenant organization')
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_('Slug'),
        help_text=_('URL-friendly identifier for the tenant')
    )
    domain = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_('Custom Domain'),
        help_text=_('Custom domain for the tenant (optional)')
    )
    
    # Plan and Tier
    plan = models.ForeignKey(
        'tenants.Plan',
        on_delete=models.PROTECT,
        related_name='tenants',
        verbose_name=_('Plan'),
        help_text=_('Current subscription plan')
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free',
        verbose_name=_('Tier'),
        help_text=_('Service tier level')
    )
    
    # Status and Suspension
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        verbose_name=_('Status'),
        help_text=_('Current tenant status')
    )
    is_suspended = models.BooleanField(
        default=False,
        verbose_name=_('Is Suspended'),
        help_text=_('Whether the tenant is currently suspended')
    )
    suspension_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Suspension Reason'),
        help_text=_('Reason for suspension if applicable')
    )
    suspended_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Suspended At'),
        help_text=_('When the tenant was suspended')
    )
    
    # Hierarchy
    parent_tenant = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='child_tenants',
        verbose_name=_('Parent Tenant'),
        help_text=_('For multi-level tenant hierarchies')
    )
    
    # Geographic and Localization
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name=_('Timezone'),
        help_text=_('Default timezone for the tenant')
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        verbose_name=_('Country'),
        help_text=_('Primary country of operation (2-letter code)')
    )
    currency_code = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Currency'),
        help_text=_('Default currency for billing')
    )
    data_region = models.CharField(
        max_length=20,
        choices=DATA_REGION_CHOICES,
        default='us-east-1',
        verbose_name=_('Data Region'),
        help_text=_('Geographic region for data storage')
    )
    
    # Owner and Contact
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_tenants',
        verbose_name=_('Owner'),
        help_text=_('Primary owner of the tenant')
    )
    contact_email = models.EmailField(
        verbose_name=_('Contact Email'),
        help_text=_('Primary contact email for the tenant')
    )
    contact_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Contact Phone'),
        help_text=_('Primary contact phone number')
    )
    
    # Trial and Billing
    trial_ends_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Trial Ends At'),
        help_text=_('When the trial period ends')
    )
    billing_cycle_start = models.DateField(
        verbose_name=_('Billing Cycle Start'),
        help_text=_('Day of month when billing cycle starts'),
        null=True, blank=True
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional tenant metadata as JSON')
    )
    
    # Usage tracking
    last_activity_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Activity At'),
        help_text=_('Last recorded activity timestamp')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_tenants',
        verbose_name=_('Created By'),
        help_text=_('User who created this tenant')
    )
    
    class Meta:
        db_table = 'tenants'
        verbose_name = _('Tenant')
        verbose_name_plural = _('Tenants')
        indexes = [
            models.Index(fields=['slug'], name='idx_slug_1785'),
            models.Index(fields=['domain'], name='idx_domain_1786'),
            models.Index(fields=['status'], name='idx_status_1787'),
            models.Index(fields=['tier'], name='idx_tier_1788'),
            models.Index(fields=['is_suspended'], name='idx_is_suspended_1789'),
            models.Index(fields=['created_at'], name='idx_created_at_1790'),
            models.Index(fields=['trial_ends_at'], name='idx_trial_ends_at_1791'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def clean(self):
        super().clean()
        if self.parent_tenant == self:
            raise ValidationError(_('A tenant cannot be its own parent.'))
        
        if self.trial_ends_at and self.trial_ends_at <= self.created_at:
            raise ValidationError(_('Trial end date must be after creation date.'))
    
    @property
    def is_trial_expired(self):
        """Check if trial period has expired."""
        if not self.trial_ends_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.trial_ends_at
    
    @property
    def days_until_trial_expiry(self):
        """Days remaining in trial."""
        if not self.trial_ends_at:
            return None
        from django.utils import timezone
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)
    
    def suspend(self, reason=None):
        """Suspend the tenant."""
        from django.utils import timezone
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspended_at = timezone.now()
        self.status = 'suspended'
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'status'])
    
    def unsuspend(self):
        """Unsuspend the tenant."""
        self.is_suspended = False
        self.suspension_reason = None
        self.suspended_at = None
        self.status = 'active'
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 'status'])
    
    def update_last_activity(self):
        """Update the last activity timestamp."""
        from django.utils import timezone
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])


class TenantSettings(TimeStampedModel):
    """
    Tenant-specific settings and configuration.
    
    This model stores various settings that control tenant behavior,
    feature availability, and preferences.
    """
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name=_('Tenant'),
        help_text=_('The tenant these settings belong to')
    )
    
    # Feature toggles
    enable_smartlink = models.BooleanField(
        default=True,
        verbose_name=_('Enable Smartlink'),
        help_text=_('Enable smartlink functionality')
    )
    enable_ai_engine = models.BooleanField(
        default=True,
        verbose_name=_('Enable AI Engine'),
        help_text=_('Enable AI-powered features')
    )
    enable_publisher_tools = models.BooleanField(
        default=True,
        verbose_name=_('Enable Publisher Tools'),
        help_text=_('Enable publisher management tools')
    )
    enable_advertiser_portal = models.BooleanField(
        default=True,
        verbose_name=_('Enable Advertiser Portal'),
        help_text=_('Enable advertiser self-service portal')
    )
    enable_coalition = models.BooleanField(
        default=False,
        verbose_name=_('Enable Coalition'),
        help_text=_('Enable coalition/affiliate network features')
    )
    
    # Limits and quotas
    max_withdrawal_per_day = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000.00,
        verbose_name=_('Max Withdrawal Per Day'),
        help_text=_('Maximum daily withdrawal amount')
    )
    require_kyc_for_withdrawal = models.BooleanField(
        default=True,
        verbose_name=_('Require KYC for Withdrawal'),
        help_text=_('Require KYC verification for withdrawals')
    )
    max_users = models.IntegerField(
        default=10,
        verbose_name=_('Max Users'),
        help_text=_('Maximum number of users allowed')
    )
    max_publishers = models.IntegerField(
        default=100,
        verbose_name=_('Max Publishers'),
        help_text=_('Maximum number of publishers allowed')
    )
    max_smartlinks = models.IntegerField(
        default=1000,
        verbose_name=_('Max Smartlinks'),
        help_text=_('Maximum number of smartlinks allowed')
    )
    api_calls_per_day = models.IntegerField(
        default=10000,
        verbose_name=_('API Calls Per Day'),
        help_text=_('Daily API call limit')
    )
    storage_gb = models.IntegerField(
        default=10,
        verbose_name=_('Storage (GB)'),
        help_text=_('Storage limit in gigabytes')
    )
    
    # Localization defaults
    default_language = models.CharField(
        max_length=10,
        default='en',
        choices=settings.LANGUAGES,
        verbose_name=_('Default Language'),
        help_text=_('Default language for the tenant')
    )
    default_currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Default Currency'),
        help_text=_('Default currency for financial operations')
    )
    default_timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name=_('Default Timezone'),
        help_text=_('Default timezone for the tenant')
    )
    
    # Push notification settings
    apns_key_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('APNS Key ID'),
        help_text=_('Apple Push Notification Service key ID')
    )
    apns_team_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('APNS Team ID'),
        help_text=_('Apple developer team ID')
    )
    apns_bundle_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('APNS Bundle ID'),
        help_text=_('App bundle identifier for push notifications')
    )
    fcm_server_key = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('FCM Server Key'),
        help_text=_('Firebase Cloud Messaging server key')
    )
    
    # Email settings
    email_from_name = models.CharField(
        max_length=255,
        default='Support',
        verbose_name=_('Email From Name'),
        help_text=_('Default sender name for emails')
    )
    email_from_address = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Email From Address'),
        help_text=_('Default sender email address')
    )
    
    # Security settings
    enable_two_factor_auth = models.BooleanField(
        default=False,
        verbose_name=_('Enable 2FA'),
        help_text=_('Require two-factor authentication')
    )
    session_timeout_minutes = models.IntegerField(
        default=480,
        verbose_name=_('Session Timeout (minutes)'),
        help_text=_('User session timeout in minutes')
    )
    password_min_length = models.IntegerField(
        default=8,
        verbose_name=_('Password Min Length'),
        help_text=_('Minimum password length requirement')
    )
    
    # Notification preferences
    enable_email_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Enable Email Notifications'),
        help_text=_('Send email notifications')
    )
    enable_push_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Enable Push Notifications'),
        help_text=_('Send push notifications')
    )
    enable_sms_notifications = models.BooleanField(
        default=False,
        verbose_name=_('Enable SMS Notifications'),
        help_text=_('Send SMS notifications')
    )
    
    # Advanced settings
    custom_css = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Custom CSS'),
        help_text=_('Custom CSS for tenant branding')
    )
    custom_js = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Custom JavaScript'),
        help_text=_('Custom JavaScript for tenant functionality')
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Custom Headers'),
        help_text=_('Custom HTTP headers for tenant requests')
    )
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = _('Tenant Settings')
        verbose_name_plural = _('Tenant Settings')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"


class TenantBilling(TimeStampedModel):
    """
    Tenant billing and payment information.
    
    This model handles billing cycles, payment methods, and
    financial information for each tenant.
    """
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
        ('custom', _('Custom')),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('card', _('Credit Card')),
        ('bank_transfer', _('Bank Transfer')),
        ('paypal', _('PayPal')),
        ('stripe', _('Stripe')),
        ('crypto', _('Cryptocurrency')),
        ('invoice', _('Invoice')),
    ]
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this billing information belongs to')
    )
    
    # Stripe integration
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stripe Customer ID'),
        help_text=_('Stripe customer identifier')
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stripe Subscription ID'),
        help_text=_('Stripe subscription identifier')
    )
    
    # Billing cycle
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        verbose_name=_('Billing Cycle'),
        help_text=_('Billing frequency')
    )
    billing_cycle_start = models.DateField(
        verbose_name=_('Billing Cycle Start'),
        help_text=_('Day of month when billing cycle starts'),
        null=True, blank=True
    )
    next_billing_date = models.DateField(
        verbose_name=_('Next Billing Date'),
        help_text=_('Date of next billing charge')
    )
    
    # Payment method
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='card',
        verbose_name=_('Payment Method'),
        help_text=_('Primary payment method')
    )
    
    # Pricing and discounts
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Base Price'),
        help_text=_('Base monthly price')
    )
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Discount Percentage'),
        help_text=_('Discount percentage applied')
    )
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Final Price'),
        help_text=_('Final monthly price after discounts')
    )
    
    # Dunning management
    dunning_count = models.IntegerField(
        default=0,
        verbose_name=_('Dunning Count'),
        help_text=_('Number of failed payment attempts')
    )
    dunning_last_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Dunning Attempt'),
        help_text=_('Timestamp of last payment failure')
    )
    max_dunning_attempts = models.IntegerField(
        default=3,
        verbose_name=_('Max Dunning Attempts'),
        help_text=_('Maximum failed payment attempts before suspension')
    )
    
    # Contact information
    billing_email = models.EmailField(
        verbose_name=_('Billing Email'),
        help_text=_('Email for billing communications')
    )
    billing_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Billing Phone'),
        help_text=_('Phone number for billing communications')
    )
    
    # Billing address
    billing_address = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Billing Address'),
        help_text=_('Billing address information')
    )
    
    # Tax information
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Tax ID'),
        help_text=_('Tax identification number')
    )
    tax_exempt = models.BooleanField(
        default=False,
        verbose_name=_('Tax Exempt'),
        help_text=_('Whether the tenant is tax exempt')
    )
    vat_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('VAT Number'),
        help_text=_('Value Added Tax number')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional billing metadata')
    )
    
    class Meta:
        db_table = 'tenant_billing'
        verbose_name = _('Tenant Billing')
        verbose_name_plural = _('Tenant Billing')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_customer_id'], name='idx_stripe_customer_id_1792'),
            models.Index(fields=['stripe_subscription_id'], name='idx_stripe_subscription_id_001'),
            models.Index(fields=['next_billing_date'], name='idx_next_billing_date_1794'),
            models.Index(fields=['dunning_count'], name='idx_dunning_count_1795'),
        ]
    
    def __str__(self):
        return f"Billing for {self.tenant.name}"
    
    def calculate_final_price(self):
        """Calculate final price after discounts."""
        discount_amount = self.base_price * (self.discount_pct / 100)
        self.final_price = self.base_price - discount_amount
        return self.final_price
    
    def increment_dunning(self):
        """Increment dunning count and update timestamp."""
        from django.utils import timezone
        self.dunning_count += 1
        self.dunning_last_at = timezone.now()
        self.save(update_fields=['dunning_count', 'dunning_last_at'])
    
    def reset_dunning(self):
        """Reset dunning count after successful payment."""
        self.dunning_count = 0
        self.dunning_last_at = None
        self.save(update_fields=['dunning_count', 'dunning_last_at'])
    
    def is_overdue(self):
        """Check if billing is overdue."""
        from django.utils import timezone
        return timezone.now().date() > self.next_billing_date and self.dunning_count >= self.max_dunning_attempts


class TenantInvoice(TimeStampedModel):
    """
    Tenant invoices and billing records.
    
    This model tracks all invoices generated for a tenant,
    including payment status and line items.
    """
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('sent', _('Sent')),
        ('paid', _('Paid')),
        ('overdue', _('Overdue')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this invoice belongs to')
    )
    
    # Invoice details
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Invoice Number'),
        help_text=_('Unique invoice identifier')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name=_('Status'),
        help_text=_('Current invoice status')
    )
    
    # Dates
    issue_date = models.DateField(
        verbose_name=_('Issue Date'),
        help_text=_('Date invoice was issued')
    )
    due_date = models.DateField(
        verbose_name=_('Due Date'),
        help_text=_('Date payment is due')
    )
    paid_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Paid Date'),
        help_text=_('Date invoice was paid')
    )
    
    # Amounts
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Subtotal'),
        help_text=_('Amount before taxes and discounts')
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Tax Amount'),
        help_text=_('Tax amount applied')
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Discount Amount'),
        help_text=_('Discount amount applied')
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Total Amount'),
        help_text=_('Final amount due')
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Amount Paid'),
        help_text=_('Amount already paid')
    )
    
    # Payment information
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Payment Method'),
        help_text=_('Method used for payment')
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Transaction ID'),
        help_text=_('Payment transaction identifier')
    )
    
    # Billing period
    billing_period_start = models.DateField(
        verbose_name=_('Billing Period Start'),
        help_text=_('Start of billing period'),
        null=True, blank=True
    )
    billing_period_end = models.DateField(
        verbose_name=_('Billing Period End'),
        help_text=_('End of billing period'),
        null=True, blank=True
    )
    
    # Additional information
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Invoice description or notes')
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Internal notes about the invoice')
    )
    
    # Line items (stored as JSON for flexibility)
    line_items = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Line Items'),
        help_text=_('Invoice line items')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional invoice metadata')
    )
    
    class Meta:
        db_table = 'tenant_invoices'
        verbose_name = _('Tenant Invoice')
        verbose_name_plural = _('Tenant Invoices')
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['invoice_number'], name='idx_invoice_number_1796'),
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_1797'),
            models.Index(fields=['issue_date'], name='idx_issue_date_1798'),
            models.Index(fields=['due_date'], name='idx_due_date_1799'),
            models.Index(fields=['status'], name='idx_status_1800'),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.tenant.name}"
    
    def calculate_totals(self):
        """Calculate invoice totals from line items."""
        self.subtotal = sum(item.get('amount', 0) for item in self.line_items)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        return self.total_amount
    
    @property
    def balance_due(self):
        """Calculate remaining balance."""
        return self.total_amount - self.amount_paid
    
    @property
    def is_paid(self):
        """Check if invoice is fully paid."""
        return self.amount_paid >= self.total_amount
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        from django.utils import timezone
        return not self.is_paid and timezone.now().date() > self.due_date
    
    def mark_as_paid(self, amount=None, payment_method=None, transaction_id=None):
        """Mark invoice as paid."""
        if amount is None:
            amount = self.balance_due
        
        self.amount_paid += amount
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
            from django.utils import timezone
            self.paid_date = timezone.now().date()
        
        if payment_method:
            self.payment_method = payment_method
        if transaction_id:
            self.transaction_id = transaction_id
        
        self.save()
