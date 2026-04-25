"""
Reseller Models

This module contains reseller management models for
multi-level tenant hierarchies and commission tracking.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class ResellerConfig(TimeStampedModel, SoftDeleteModel):
    """
    Reseller configuration for multi-level tenant hierarchies.
    
    This model manages reseller configurations including
    commission rates, tenant limits, and hierarchy settings.
    """
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('suspended', _('Suspended')),
        ('pending', _('Pending')),
    ]
    
    COMMISSION_TYPE_CHOICES = [
        ('percentage', _('Percentage')),
        ('fixed', _('Fixed Amount')),
        ('tiered', _('Tiered')),
        ('hybrid', _('Hybrid')),
    ]
    
    parent_tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='reseller_config',
        verbose_name=_('Parent Tenant'),
        help_text=_('The tenant acting as reseller')
    )
    
    # Reseller information
    reseller_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Reseller ID'),
        help_text=_('Unique reseller identifier')
    )
    company_name = models.CharField(
        max_length=255,
        verbose_name=_('Company Name'),
        help_text=_('Reseller company name')
    )
    contact_email = models.EmailField(
        verbose_name=_('Contact Email'),
        help_text=_('Primary contact email')
    )
    contact_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Contact Phone'),
        help_text=_('Primary contact phone')
    )
    
    # Status and verification
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status'),
        help_text=_('Current reseller status')
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_('Is Verified'),
        help_text=_('Whether reseller is verified')
    )
    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Verified At'),
        help_text=_('When reseller was verified')
    )
    
    # Commission configuration
    commission_type = models.CharField(
        max_length=20,
        choices=COMMISSION_TYPE_CHOICES,
        default='percentage',
        verbose_name=_('Commission Type'),
        help_text=_('Type of commission calculation')
    )
    commission_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.0,
        verbose_name=_('Commission Percentage'),
        help_text=_('Commission percentage for reseller')
    )
    fixed_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Fixed Commission'),
        help_text=_('Fixed commission amount per referral')
    )
    
    # Tier configuration (for tiered commission)
    commission_tiers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Commission Tiers'),
        help_text=_('Commission tiers for volume-based pricing')
    )
    
    # Limits and quotas
    max_child_tenants = models.IntegerField(
        default=100,
        verbose_name=_('Max Child Tenants'),
        help_text=_('Maximum number of child tenants allowed')
    )
    max_monthly_signups = models.IntegerField(
        default=50,
        verbose_name=_('Max Monthly Signups'),
        help_text=_('Maximum new tenants per month')
    )
    min_monthly_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Min Monthly Revenue'),
        help_text=_('Minimum monthly revenue requirement')
    )
    
    # Billing and payments
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', _('Monthly')),
            ('quarterly', _('Quarterly')),
            ('yearly', _('Yearly')),
        ],
        default='monthly',
        verbose_name=_('Billing Cycle'),
        help_text=_('Commission payout frequency')
    )
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('bank_transfer', _('Bank Transfer')),
            ('paypal', _('PayPal')),
            ('stripe', _('Stripe')),
            ('check', _('Check')),
        ],
        default='bank_transfer',
        verbose_name=_('Payment Method'),
        help_text=_('How commissions are paid')
    )
    payment_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Payment Details'),
        help_text=_('Payment method details')
    )
    
    # Branding and customization
    can_brand = models.BooleanField(
        default=True,
        verbose_name=_('Can Brand'),
        help_text=_('Whether reseller can brand child tenant sites')
    )
    custom_pricing = models.BooleanField(
        default=False,
        verbose_name=_('Custom Pricing'),
        help_text=_('Whether reseller can set custom pricing')
    )
    white_label = models.BooleanField(
        default=False,
        verbose_name=_('White Label'),
        help_text=_('Whether reseller operates as white label')
    )
    
    # Support and training
    support_level = models.CharField(
        max_length=20,
        choices=[
            ('basic', _('Basic')),
            ('standard', _('Standard')),
            ('premium', _('Premium')),
            ('enterprise', _('Enterprise')),
        ],
        default='standard',
        verbose_name=_('Support Level'),
        help_text=_('Level of support provided to reseller')
    )
    training_required = models.BooleanField(
        default=True,
        verbose_name=_('Training Required'),
        help_text=_('Whether reseller requires training')
    )
    training_completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Training Completed At'),
        help_text=_('When reseller completed training')
    )
    
    # Contract and legal
    contract_start = models.DateField(
        verbose_name=_('Contract Start'),
        help_text=_('Reseller contract start date')
    )
    contract_end = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Contract End'),
        help_text=_('Reseller contract end date')
    )
    contract_terms = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Contract Terms'),
        help_text=_('Specific contract terms and conditions')
    )
    
    # Performance tracking
    total_referrals = models.IntegerField(
        default=0,
        verbose_name=_('Total Referrals'),
        help_text=_('Total number of referred tenants')
    )
    active_referrals = models.IntegerField(
        default=0,
        verbose_name=_('Active Referrals'),
        help_text=_('Number of currently active referrals')
    )
    total_commission_earned = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_('Total Commission Earned'),
        help_text=_('Total commission earned to date')
    )
    
    class Meta:
        db_table = 'reseller_configs'
        verbose_name = _('Reseller Config')
        verbose_name_plural = _('Reseller Configs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['parent_tenant'], name='idx_parent_tenant_1831'),
            models.Index(fields=['reseller_id'], name='idx_reseller_id_1832'),
            models.Index(fields=['status'], name='idx_status_1833'),
            models.Index(fields=['is_verified'], name='idx_is_verified_1834'),
            models.Index(fields=['contract_start'], name='idx_contract_start_1835'),
        ]
    
    def __str__(self):
        return f"Reseller {self.company_name} ({self.reseller_id})"
    
    def clean(self):
        super().clean()
        if self.commission_pct < 0 or self.commission_pct > 100:
            raise ValidationError(_('Commission percentage must be between 0 and 100.'))
        
        if self.max_child_tenants <= 0:
            raise ValidationError(_('Max child tenants must be greater than 0.'))
        
        if self.contract_end and self.contract_end <= self.contract_start:
            raise ValidationError(_('Contract end must be after contract start.'))
    
    def activate(self):
        """Activate the reseller account."""
        self.status = 'active'
        self.save(update_fields=['status'])
    
    def suspend(self):
        """Suspend the reseller account."""
        self.status = 'suspended'
        self.save(update_fields=['status'])
    
    def verify(self):
        """Verify the reseller account."""
        from django.utils import timezone
        self.is_verified = True
        self.verified_at = timezone.now()
        self.status = 'active'
        self.save(update_fields=['is_verified', 'verified_at', 'status'])
    
    def calculate_commission(self, revenue):
        """Calculate commission based on revenue."""
        if self.commission_type == 'percentage':
            return revenue * (self.commission_pct / 100)
        elif self.commission_type == 'fixed':
            return self.fixed_commission
        elif self.commission_type == 'tiered':
            return self.calculate_tiered_commission(revenue)
        elif self.commission_type == 'hybrid':
            return (revenue * (self.commission_pct / 100)) + self.fixed_commission
        return 0
    
    def calculate_tiered_commission(self, revenue):
        """Calculate tiered commission based on revenue."""
        if not self.commission_tiers:
            return 0
        
        commission = 0
        remaining_revenue = revenue
        
        for tier in sorted(self.commission_tiers, key=lambda x: x.get('min_revenue', 0)):
            tier_min = tier.get('min_revenue', 0)
            tier_max = tier.get('max_revenue', float('inf'))
            tier_rate = tier.get('rate', 0)
            
            if remaining_revenue <= 0:
                break
            
            if revenue > tier_min:
                tier_revenue = min(remaining_revenue, tier_max - tier_min)
                commission += tier_revenue * (tier_rate / 100)
                remaining_revenue -= tier_revenue
        
        return commission
    
    def can_add_child_tenant(self):
        """Check if reseller can add more child tenants."""
        return (
            self.status == 'active' and
            self.is_verified and
            self.total_referrals < self.max_child_tenants
        )
    
    def update_referral_stats(self):
        """Update referral statistics."""
        from django.db.models import Count, Q, Sum
        
        child_tenants = self.parent_tenant.child_tenants.filter(is_deleted=False)
        self.total_referrals = child_tenants.count()
        self.active_referrals = child_tenants.filter(status='active').count()
        
        # Calculate total commission earned
        total_commission = 0
        for invoice in ResellerInvoice.objects.filter(reseller=self, status='paid'):
            total_commission += invoice.commission_amount
        
        self.total_commission_earned = total_commission
        self.save(update_fields=['total_referrals', 'active_referrals', 'total_commission_earned'])
    
    @property
    def is_contract_expired(self):
        """Check if reseller contract has expired."""
        if not self.contract_end:
            return False
        return timezone.now().date() > self.contract_end
    
    @property
    def days_until_contract_expiry(self):
        """Days until contract expires."""
        if not self.contract_end:
            return None
        
        delta = self.contract_end - timezone.now().date()
        return max(0, delta.days)


class ResellerInvoice(TimeStampedModel, SoftDeleteModel):
    """
    Commission invoices for resellers.
    
    This model tracks commission payments and invoices
    for reseller referral activities.
    """
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('paid', _('Paid')),
        ('overdue', _('Overdue')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]
    
    reseller = models.ForeignKey(
        ResellerConfig,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('Reseller'),
        help_text=_('The reseller this invoice belongs to')
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
    
    # Period information
    period_start = models.DateField(
        verbose_name=_('Period Start'),
        help_text=_('Start of commission period')
    )
    period_end = models.DateField(
        verbose_name=_('Period End'),
        help_text=_('End of commission period')
    )
    
    # Financial details
    commission_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Commission Amount'),
        help_text=_('Total commission amount')
    )
    bonus_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_('Bonus Amount'),
        help_text=_('Bonus or incentive amount')
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_('Tax Amount'),
        help_text=_('Tax amount deducted')
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Total Amount'),
        help_text=_('Total amount payable')
    )
    
    # Payment information
    due_date = models.DateField(
        verbose_name=_('Due Date'),
        help_text=_('Date payment is due')
    )
    paid_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Paid Date'),
        help_text=_('Date payment was made')
    )
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
    
    # Referral breakdown
    referral_count = models.IntegerField(
        default=0,
        verbose_name=_('Referral Count'),
        help_text=_('Number of referrals in this period')
    )
    active_referrals = models.IntegerField(
        default=0,
        verbose_name=_('Active Referrals'),
        help_text=_('Number of active referrals')
    )
    referral_details = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Referral Details'),
        help_text=_('Detailed breakdown of referrals')
    )
    
    # Notes and metadata
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Internal notes about the invoice')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional invoice metadata')
    )
    
    class Meta:
        db_table = 'reseller_invoices'
        verbose_name = _('Reseller Invoice')
        verbose_name_plural = _('Reseller Invoices')
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['reseller', 'status'], name='idx_reseller_status_1836'),
            models.Index(fields=['invoice_number'], name='idx_invoice_number_1837'),
            models.Index(fields=['period_start'], name='idx_period_start_1838'),
            models.Index(fields=['due_date'], name='idx_due_date_1839'),
            models.Index(fields=['status'], name='idx_status_1840'),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.reseller.company_name}"
    
    def calculate_totals(self):
        """Calculate invoice totals."""
        self.total_amount = self.commission_amount + self.bonus_amount - self.tax_amount
        return self.total_amount
    
    def approve(self):
        """Approve the invoice for payment."""
        self.status = 'approved'
        self.save(update_fields=['status'])
    
    def mark_as_paid(self, payment_method=None, transaction_id=None):
        """Mark invoice as paid."""
        from django.utils import timezone
        
        self.status = 'paid'
        self.paid_date = timezone.now().date()
        
        if payment_method:
            self.payment_method = payment_method
        if transaction_id:
            self.transaction_id = transaction_id
        
        self.save(update_fields=['status', 'paid_date', 'payment_method', 'transaction_id'])
    
    def cancel(self, reason=None):
        """Cancel the invoice."""
        self.status = 'cancelled'
        if reason:
            self.notes = reason
        self.save(update_fields=['status', 'notes'])
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        if self.status in ['paid', 'cancelled', 'refunded']:
            return False
        
        from django.utils import timezone
        return timezone.now().date() > self.due_date
    
    @property
    def days_overdue(self):
        """Days invoice is overdue."""
        if not self.is_overdue:
            return 0
        
        from django.utils import timezone
        delta = timezone.now().date() - self.due_date
        return delta.days
    
    def generate_referral_details(self):
        """Generate detailed referral breakdown."""
        from django.db.models import Sum
        
        child_tenants = self.reseller.parent_tenant.child_tenants.filter(
            is_deleted=False,
            created_at__date__range=[self.period_start, self.period_end]
        )
        
        self.referral_count = child_tenants.count()
        self.active_referrals = child_tenants.filter(status='active').count()
        
        # Generate detailed breakdown
        details = []
        for tenant in child_tenants:
            # Calculate revenue for this tenant in the period
            # This would involve querying tenant invoices/revenue
            tenant_revenue = 0  # Placeholder
            
            details.append({
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'created_at': tenant.created_at.isoformat(),
                'status': tenant.status,
                'revenue': tenant_revenue,
                'commission': self.reseller.calculate_commission(tenant_revenue)
            })
        
        self.referral_details = details
        self.save(update_fields=['referral_count', 'active_referrals', 'referral_details'])
        
        return details
