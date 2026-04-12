"""
Billing Database Model

This module contains Billing model and related models
for managing billing, payments, and financial transactions.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from ..models import *
from ..enums import *
from ..utils import *
from ..validators import *


class BillingProfile(AdvertiserPortalBaseModel, AuditModel):
    """
    Main billing profile model for managing advertiser billing information.
    
    This model stores billing details, payment methods,
    and financial settings for advertisers.
    """
    
    # Basic Information
    advertiser = models.OneToOneField(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='billing_profile',
        help_text="Associated advertiser"
    )
    company_name = models.CharField(
        max_length=255,
        help_text="Company legal name"
    )
    trade_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Trade name or DBA"
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax identification number"
    )
    vat_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="VAT number"
    )
    
    # Contact Information
    billing_email = models.EmailField(
        help_text="Primary billing email"
    )
    billing_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Billing phone number"
    )
    billing_contact = models.CharField(
        max_length=255,
        help_text="Primary billing contact person"
    )
    billing_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Billing contact title"
    )
    
    # Address Information
    billing_address_line1 = models.CharField(
        max_length=255,
        help_text="Billing address line 1"
    )
    billing_address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Billing address line 2"
    )
    billing_city = models.CharField(
        max_length=100,
        help_text="Billing city"
    )
    billing_state = models.CharField(
        max_length=100,
        help_text="Billing state/province"
    )
    billing_country = models.CharField(
        max_length=2,
        help_text="Billing country code (ISO 3166-1 alpha-2)"
    )
    billing_postal_code = models.CharField(
        max_length=20,
        help_text="Billing postal code"
    )
    
    # Billing Settings
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annually', 'Annually'),
            ('prepaid', 'Prepaid')
        ],
        default='monthly',
        help_text="Billing cycle"
    )
    payment_terms = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text="Payment terms in days"
    )
    auto_charge = models.BooleanField(
        default=False,
        help_text="Enable automatic charging"
    )
    auto_charge_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Auto-charge threshold amount"
    )
    
    # Credit and Limits
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Credit limit"
    )
    credit_available = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Available credit"
    )
    spending_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monthly spending limit"
    )
    
    # Tax Information
    tax_exempt = models.BooleanField(
        default=False,
        help_text="Whether billing is tax exempt"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1.0000'))],
        help_text="Tax rate"
    )
    tax_region = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tax region"
    )
    
    # Currency and Pricing
    default_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Default currency code"
    )
    pricing_model = models.CharField(
        max_length=50,
        choices=[
            ('cpc', 'Cost Per Click'),
            ('cpm', 'Cost Per Mille'),
            ('cpa', 'Cost Per Action'),
            ('cpcv', 'Cost Per Completed View'),
            ('hybrid', 'Hybrid Model')
        ],
        default='cpc',
        help_text="Pricing model"
    )
    
    # Status and Verification
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether billing profile is verified"
    )
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when profile was verified"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('restricted', 'Restricted'),
            ('closed', 'Closed')
        ],
        default='active',
        help_text="Billing status"
    )
    
    # Notification Settings
    email_notifications = models.BooleanField(
        default=True,
        help_text="Enable email notifications"
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text="Enable SMS notifications"
    )
    notification_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional notification emails"
    )
    
    # Integration Settings
    integration_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration settings"
    )
    
    class Meta:
        db_table = 'billing_profiles'
        verbose_name = 'Billing Profile'
        verbose_name_plural = 'Billing Profiles'
        indexes = [
            models.Index(fields=['advertiser']),
            models.Index(fields=['status']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['billing_country']),
        ]
    
    def __str__(self) -> str:
        return f"{self.company_name} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate email format
        if self.billing_email:
            from django.core.validators import EmailValidator
            validator = EmailValidator()
            validator(self.billing_email)
        
        # Validate phone format
        if self.billing_phone:
            if not re.match(r'^\+?1?\d{9,15}$', self.billing_phone.replace('-', '').replace(' ', '')):
                raise ValidationError("Invalid phone number format")
        
        # Validate country code
        if len(self.billing_country) != 2:
            raise ValidationError("Country code must be 2 characters")
        
        # Validate tax rate
        if self.tax_rate < 0 or self.tax_rate > 1:
            raise ValidationError("Tax rate must be between 0 and 1")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Update credit available
        if self.credit_limit > 0:
            used_credit = self.credit_limit - self.credit_available
            total_spend = self.advertiser.total_spend
            self.credit_available = max(Decimal('0'), self.credit_limit - total_spend)
        
        # Set verification date if verified and not set
        if self.is_verified and not self.verification_date:
            self.verification_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_full_address(self) -> str:
        """Get full billing address."""
        address_parts = [self.billing_address_line1]
        
        if self.billing_address_line2:
            address_parts.append(self.billing_address_line2)
        
        address_parts.extend([
            self.billing_city,
            self.billing_state,
            self.billing_postal_code,
            self.billing_country
        ])
        
        return ', '.join(filter(None, address_parts))
    
    def calculate_tax(self, amount: Decimal) -> Decimal:
        """Calculate tax amount for given amount."""
        if self.tax_exempt:
            return Decimal('0')
        
        return amount * self.tax_rate
    
    def get_total_with_tax(self, amount: Decimal) -> Decimal:
        """Get total amount including tax."""
        tax = self.calculate_tax(amount)
        return amount + tax
    
    def can_charge(self, amount: Decimal) -> bool:
        """Check if profile can charge specified amount."""
        if self.auto_charge:
            return amount >= self.auto_charge_threshold
        
        if self.credit_limit > 0:
            return self.credit_available >= amount
        
        return True  # Prepaid or unlimited
    
    def get_billing_summary(self) -> Dict[str, Any]:
        """Get billing profile summary."""
        return {
            'company_info': {
                'company_name': self.company_name,
                'trade_name': self.trade_name,
                'tax_id': self.tax_id,
                'vat_number': self.vat_number
            },
            'contact_info': {
                'billing_email': self.billing_email,
                'billing_phone': self.billing_phone,
                'billing_contact': self.billing_contact,
                'billing_title': self.billing_title
            },
            'address': self.get_full_address(),
            'settings': {
                'billing_cycle': self.billing_cycle,
                'payment_terms': self.payment_terms,
                'auto_charge': self.auto_charge,
                'auto_charge_threshold': float(self.auto_charge_threshold),
                'default_currency': self.default_currency,
                'pricing_model': self.pricing_model
            },
            'credit': {
                'credit_limit': float(self.credit_limit),
                'credit_available': float(self.credit_available),
                'credit_used': float(self.credit_limit - self.credit_available),
                'spending_limit': float(self.spending_limit) if self.spending_limit else None
            },
            'tax': {
                'tax_exempt': self.tax_exempt,
                'tax_rate': float(self.tax_rate),
                'tax_region': self.tax_region
            },
            'status': {
                'status': self.status,
                'is_verified': self.is_verified,
                'verification_date': self.verification_date.isoformat() if self.verification_date else None
            }
        }


class PaymentMethod(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing payment methods.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='payment_methods',
        help_text="Associated advertiser"
    )
    payment_method_type = models.CharField(
        max_length=50,
        choices=[
            ('credit_card', 'Credit Card'),
            ('debit_card', 'Debit Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('paypal', 'PayPal'),
            ('stripe', 'Stripe'),
            ('crypto', 'Cryptocurrency'),
            ('wire', 'Wire Transfer')
        ],
        help_text="Payment method type"
    )
    method_name = models.CharField(
        max_length=100,
        help_text="Display name for payment method"
    )
    
    # Card Information (for credit/debit cards)
    card_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('visa', 'Visa'),
            ('mastercard', 'Mastercard'),
            ('amex', 'American Express'),
            ('discover', 'Discover'),
            ('jcb', 'JCB'),
            ('diners', 'Diners Club')
        ],
        help_text="Card type"
    )
    card_last4 = models.CharField(
        max_length=4,
        blank=True,
        help_text="Last 4 digits of card"
    )
    card_expiry_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Card expiry month"
    )
    card_expiry_year = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(2020), MaxValueValidator(2050)],
        help_text="Card expiry year"
    )
    
    # Bank Information (for bank transfers)
    bank_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bank name"
    )
    bank_account_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('checking', 'Checking'),
            ('savings', 'Savings'),
            ('business', 'Business')
        ],
        help_text="Bank account type"
    )
    bank_account_last4 = models.CharField(
        max_length=4,
        blank=True,
        help_text="Last 4 digits of bank account"
    )
    bank_routing_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Bank routing number"
    )
    
    # External Payment Information
    external_payment_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External payment method ID"
    )
    external_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="External payment provider"
    )
    
    # Settings and Status
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default payment method"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether payment method is active"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether payment method is verified"
    )
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when method was verified"
    )
    
    # Limits and Restrictions
    daily_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Daily transaction limit"
    )
    monthly_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monthly transaction limit"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment method metadata"
    )
    
    class Meta:
        db_table = 'payment_methods'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        indexes = [
            models.Index(fields=['advertiser', 'is_default']),
            models.Index(fields=['advertiser', 'is_active']),
            models.Index(fields=['payment_method_type']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self) -> str:
        return f"{self.method_name} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate card expiry
        if self.card_expiry_month and self.card_expiry_year:
            current_date = timezone.now().date()
            expiry_date = date(self.card_expiry_year, self.card_expiry_month, 1)
            
            # Move to last day of month
            if self.card_expiry_month in [4, 6, 9, 11]:
                expiry_date = date(self.card_expiry_year, self.card_expiry_month, 30)
            else:
                expiry_date = date(self.card_expiry_year, self.card_expiry_month, 31)
            
            if expiry_date <= current_date:
                raise ValidationError("Card has expired")
        
        # Validate payment method specific fields
        if self.payment_method_type in ['credit_card', 'debit_card']:
            if not self.card_type or not self.card_last4:
                raise ValidationError("Card type and last 4 digits are required for card payments")
        
        if self.payment_method_type == 'bank_transfer':
            if not self.bank_name or not self.bank_account_last4:
                raise ValidationError("Bank name and account last 4 digits are required for bank transfers")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Ensure only one default payment method per advertiser
        if self.is_default:
            PaymentMethod.objects.filter(
                advertiser=self.advertiser,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        # Set verification date if verified and not set
        if self.is_verified and not self.verification_date:
            self.verification_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def is_expired(self) -> bool:
        """Check if payment method is expired."""
        if not self.card_expiry_year or not self.card_expiry_month:
            return False
        
        current_date = timezone.now().date()
        expiry_date = date(self.card_expiry_year, self.card_expiry_month, 1)
        
        return expiry_date <= current_date
    
    def get_display_info(self) -> Dict[str, Any]:
        """Get display information for payment method."""
        info = {
            'method_name': self.method_name,
            'payment_method_type': self.payment_method_type,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'is_verified': self.is_verified
        }
        
        if self.payment_method_type in ['credit_card', 'debit_card']:
            info.update({
                'card_type': self.card_type,
                'card_last4': self.card_last4,
                'card_expiry': f"{self.card_expiry_month:02d}/{self.card_expiry_year}",
                'is_expired': self.is_expired()
            })
        
        elif self.payment_method_type == 'bank_transfer':
            info.update({
                'bank_name': self.bank_name,
                'bank_account_type': self.bank_account_type,
                'bank_account_last4': self.bank_account_last4
            })
        
        elif self.payment_method_type in ['paypal', 'stripe']:
            info.update({
                'external_provider': self.external_provider,
                'external_payment_id': self.external_payment_id
            })
        
        return info


class Invoice(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing invoices.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text="Associated advertiser"
    )
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique invoice number"
    )
    invoice_type = models.CharField(
        max_length=50,
        choices=[
            ('standard', 'Standard Invoice'),
            ('credit', 'Credit Invoice'),
            ('adjustment', 'Adjustment Invoice'),
            ('proforma', 'Proforma Invoice')
        ],
        default='standard',
        help_text="Invoice type"
    )
    
    # Date Information
    issue_date = models.DateField(
        db_index=True,
        help_text="Invoice issue date"
    )
    due_date = models.DateField(
        db_index=True,
        help_text="Invoice due date"
    )
    period_start = models.DateField(
        help_text="Billing period start date"
    )
    period_end = models.DateField(
        help_text="Billing period end date"
    )
    
    # Amount Information
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Invoice subtotal"
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Tax amount"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Total invoice amount"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    
    # Status Information
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('viewed', 'Viewed'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('partially_paid', 'Partially Paid')
        ],
        default='draft',
        db_index=True,
        help_text="Invoice status"
    )
    
    # Payment Information
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Amount paid"
    )
    paid_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Payment date"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Payment method used"
    )
    
    # Late Fees and Interest
    late_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Late fee amount"
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Interest amount"
    )
    late_fee_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0200'),
        help_text="Late fee rate"
    )
    
    # Notes and Description
    description = models.TextField(
        blank=True,
        help_text="Invoice description"
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes"
    )
    customer_notes = models.TextField(
        blank=True,
        help_text="Customer-facing notes"
    )
    
    # Automation Settings
    auto_send = models.BooleanField(
        default=True,
        help_text="Automatically send invoice"
    )
    auto_charge = models.BooleanField(
        default=False,
        help_text="Automatically charge payment method"
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether payment reminder has been sent"
    )
    
    # External References
    external_invoice_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External invoice ID"
    )
    integration_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration data"
    )
    
    class Meta:
        db_table = 'invoices'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['advertiser', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['issue_date']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status', 'due_date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.invoice_number} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate date ranges
        if self.period_start and self.period_end:
            if self.period_start > self.period_end:
                raise ValidationError("Period start date must be before end date")
        
        if self.issue_date and self.due_date:
            if self.issue_date > self.due_date:
                raise ValidationError("Issue date must be before or equal to due date")
        
        # Validate amounts
        if self.subtotal < 0:
            raise ValidationError("Subtotal cannot be negative")
        
        if self.total_amount < 0:
            raise ValidationError("Total amount cannot be negative")
        
        if self.paid_amount < 0:
            raise ValidationError("Paid amount cannot be negative")
        
        # Validate total calculation
        expected_total = self.subtotal + self.tax_amount
        if abs(self.total_amount - expected_total) > Decimal('0.01'):
            raise ValidationError("Total amount must equal subtotal plus tax")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set default issue date if not set
        if not self.issue_date:
            self.issue_date = timezone.now().date()
        
        # Set default due date if not set
        if not self.due_date and self.advertiser.billing_profile:
            payment_terms = self.advertiser.billing_profile.payment_terms
            self.due_date = self.issue_date + timezone.timedelta(days=payment_terms)
        
        # Calculate late fees if overdue
        if self.due_date and timezone.now().date() > self.due_date:
            days_overdue = (timezone.now().date() - self.due_date).days
            if days_overdue > 0:
                self.late_fee_amount = self.subtotal * self.late_fee_rate * days_overdue / 365
        
        super().save(*args, **kwargs)
    
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return (
            self.status in ['sent', 'viewed', 'partially_paid'] and
            self.due_date and
            timezone.now().date() > self.due_date
        )
    
    def get_amount_due(self) -> Decimal:
        """Get amount currently due."""
        return self.total_amount - self.paid_amount
    
    def get_days_overdue(self) -> int:
        """Get days overdue."""
        if not self.due_date:
            return 0
        
        if self.status in ['paid', 'cancelled', 'refunded']:
            return 0
        
        overdue_date = timezone.now().date() - self.due_date
        return max(0, overdue_date.days)
    
    def get_status_display(self) -> str:
        """Get human-readable status display."""
        status_map = {
            'draft': 'Draft',
            'sent': 'Sent',
            'viewed': 'Viewed',
            'paid': 'Paid',
            'overdue': 'Overdue',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded',
            'partially_paid': 'Partially Paid'
        }
        return status_map.get(self.status, self.status)
    
    def add_late_fee(self, days_overdue: int) -> Decimal:
        """Calculate and add late fee."""
        if days_overdue > 0:
            late_fee = self.subtotal * self.late_fee_rate * days_overdue / 365
            self.late_fee_amount += late_fee
            self.total_amount += late_fee
            return late_fee
        return Decimal('0')


class PaymentTransaction(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing payment transactions.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        help_text="Associated advertiser"
    )
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique transaction identifier"
    )
    external_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External transaction ID"
    )
    
    # Amount Information
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Transaction amount"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Transaction fee"
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Net amount after fees"
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        max_length=50,
        choices=[
            ('payment', 'Payment'),
            ('refund', 'Refund'),
            ('chargeback', 'Chargeback'),
            ('adjustment', 'Adjustment'),
            ('deposit', 'Deposit'),
            ('withdrawal', 'Withdrawal')
        ],
        help_text="Transaction type"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text="Payment method used"
    )
    
    # Status Information
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded')
        ],
        default='pending',
        db_index=True,
        help_text="Transaction status"
    )
    
    # Gateway Information
    gateway = models.CharField(
        max_length=50,
        choices=[
            ('stripe', 'Stripe'),
            ('paypal', 'PayPal'),
            ('braintree', 'Braintree'),
            ('square', 'Square'),
            ('adyen', 'Adyen'),
            ('manual', 'Manual')
        ],
        help_text="Payment gateway"
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Gateway response data"
    )
    gateway_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Gateway transaction ID"
    )
    
    # Invoice Reference
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_transactions',
        help_text="Associated invoice"
    )
    
    # Timestamp Information
    initiated_at = models.DateTimeField(
        db_index=True,
        help_text="Transaction initiation timestamp"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Transaction completion timestamp"
    )
    
    # Failure Information
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Transaction failure reason"
    )
    failure_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Transaction failure code"
    )
    retry_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of retry attempts"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Transaction description"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional transaction metadata"
    )
    
    class Meta:
        db_table = 'payment_transactions'
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        indexes = [
            models.Index(fields=['advertiser', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['external_transaction_id']),
            models.Index(fields=['gateway_transaction_id']),
            models.Index(fields=['initiated_at']),
            models.Index(fields=['status', 'initiated_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.transaction_id} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate amounts
        if self.amount < 0:
            raise ValidationError("Amount cannot be negative")
        
        if self.fee_amount < 0:
            raise ValidationError("Fee amount cannot be negative")
        
        # Validate net amount calculation
        expected_net = self.amount - self.fee_amount
        if abs(self.net_amount - expected_net) > Decimal('0.01'):
            raise ValidationError("Net amount must equal amount minus fee")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Set initiated timestamp if not set
        if not self.initiated_at:
            self.initiated_at = timezone.now()
        
        # Calculate net amount if not set
        if self.net_amount == 0 and self.amount > 0:
            self.net_amount = self.amount - self.fee_amount
        
        # Set completed timestamp if status is completed and not set
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == 'completed'
    
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status in ['pending', 'processing']
    
    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.status == 'failed'
    
    def get_duration(self) -> Optional[int]:
        """Get transaction duration in seconds."""
        if self.initiated_at and self.completed_at:
            return int((self.completed_at - self.initiated_at).total_seconds())
        return None
    
    def get_status_display(self) -> str:
        """Get human-readable status display."""
        status_map = {
            'pending': 'Pending',
            'processing': 'Processing',
            'completed': 'Completed',
            'failed': 'Failed',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded'
        }
        return status_map.get(self.status, self.status)
