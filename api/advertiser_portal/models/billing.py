"""
Billing Models for Advertiser Portal

This module contains models for managing advertiser billing,
including wallets, deposits, invoices, and spend tracking.
"""

import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserWallet(models.Model):
    """
    Model for managing advertiser wallets.
    
    Stores account balance, credit limits, and
    automatic refill configuration.
    """
    
    # Core relationship
    advertiser = models.OneToOneField(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='wallet',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this wallet belongs to')
    )
    
    # Balance information
    balance = models.DecimalField(
        _('Balance'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Current account balance')
    )
    
    credit_limit = models.DecimalField(
        _('Credit Limit'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Maximum credit limit')
    )
    
    available_credit = models.DecimalField(
        _('Available Credit'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Available credit balance')
    )
    
    # Auto-refill configuration
    auto_refill_enabled = models.BooleanField(
        _('Auto Refill Enabled'),
        default=False,
        help_text=_('Whether automatic refill is enabled')
    )
    
    auto_refill_threshold = models.DecimalField(
        _('Auto Refill Threshold'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Balance threshold for auto-refill')
    )
    
    auto_refill_amount = models.DecimalField(
        _('Auto Refill Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Amount to auto-refill')
    )
    
    auto_refill_max = models.DecimalField(
        _('Auto Refill Maximum'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum auto-refill amount per period')
    )
    
    # Payment method
    default_payment_method = models.CharField(
        _('Default Payment Method'),
        max_length=50,
        choices=[
            ('credit_card', _('Credit Card')),
            ('bank_transfer', _('Bank Transfer')),
            ('paypal', _('PayPal')),
            ('wire', _('Wire Transfer')),
            ('crypto', _('Cryptocurrency')),
        ],
        default='credit_card',
        help_text=_('Default payment method for refills')
    )
    
    # Status
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this wallet is active')
    )
    
    is_suspended = models.BooleanField(
        _('Is Suspended'),
        default=False,
        help_text=_('Whether this wallet is suspended')
    )
    
    suspension_reason = models.TextField(
        _('Suspension Reason'),
        null=True,
        blank=True,
        help_text=_('Reason for wallet suspension')
    )
    
    # Limits and restrictions
    daily_spend_limit = models.DecimalField(
        _('Daily Spend Limit'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum daily spending limit')
    )
    
    weekly_spend_limit = models.DecimalField(
        _('Weekly Spend Limit'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum weekly spending limit')
    )
    
    monthly_spend_limit = models.DecimalField(
        _('Monthly Spend Limit'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum monthly spending limit')
    )
    
    # Currency
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this wallet was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this wallet was last updated')
    )
    
    last_refill_at = models.DateTimeField(
        _('Last Refill At'),
        null=True,
        blank=True,
        help_text=_('When last auto-refill occurred')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_wallet'
        verbose_name = _('Advertiser Wallet')
        verbose_name_plural = _('Advertiser Wallets')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser'], name='idx_advertiser_395'),
            models.Index(fields=['is_active', 'is_suspended'], name='idx_is_active_is_suspended_396'),
            models.Index(fields=['created_at'], name='idx_created_at_397'),
        ]
    
    def __str__(self):
        return f"Wallet: {self.advertiser.company_name} (${self.balance})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate credit limit
        if self.credit_limit < 0:
            raise ValidationError(_('Credit limit cannot be negative'))
        
        # Validate auto-refill amounts
        if self.auto_refill_enabled:
            if self.auto_refill_threshold < 0:
                raise ValidationError(_('Auto-refill threshold cannot be negative'))
            
            if self.auto_refill_amount <= 0:
                raise ValidationError(_('Auto-refill amount must be positive'))
            
            if self.auto_refill_max and self.auto_refill_max <= 0:
                raise ValidationError(_('Auto-refill maximum must be positive'))
        
        # Validate spend limits
        for limit_field in ['daily_spend_limit', 'weekly_spend_limit', 'monthly_spend_limit']:
            limit_value = getattr(self, limit_field)
            if limit_value and limit_value <= 0:
                raise ValidationError(_(f'{limit_field.replace("_", " ").title()} must be positive'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate available credit
        self.available_credit = self.credit_limit - self.balance
        
        super().save(*args, **kwargs)
    
    @property
    def is_over_limit(self) -> bool:
        """Check if wallet is over credit limit."""
        return self.balance > self.credit_limit
    
    @property
    def needs_refill(self) -> bool:
        """Check if wallet needs auto-refill."""
        return (
            self.auto_refill_enabled and
            self.balance <= self.auto_refill_threshold
        )
    
    @property
    def available_balance(self) -> Decimal:
        """Get available balance including credit."""
        return self.balance + self.available_credit
    
    @property
    def utilization_percentage(self) -> float:
        """Get credit utilization percentage."""
        if self.credit_limit > 0:
            return float((self.balance / self.credit_limit) * 100)
        return 0.0
    
    def add_funds(self, amount: Decimal, description: str = None):
        """Add funds to wallet."""
        if amount <= 0:
            raise ValueError(_('Amount must be positive'))
        
        self.balance += amount
        self.save()
        
        # Create transaction record
        AdvertiserTransaction.objects.create(
            wallet=self,
            transaction_type='deposit',
            amount=amount,
            description=description or _('Funds added'),
            balance_after=self.balance
        )
        
        logger.info(f"Funds added to wallet: {self.advertiser.company_name} +${amount}")
    
    def spend_funds(self, amount: Decimal, description: str = None) -> bool:
        """Spend funds from wallet."""
        if amount <= 0:
            raise ValueError(_('Amount must be positive'))
        
        if amount > self.available_balance:
            return False  # Insufficient funds
        
        self.balance -= amount
        self.save()
        
        # Create transaction record
        AdvertiserTransaction.objects.create(
            wallet=self,
            transaction_type='spend',
            amount=amount,
            description=description or _('Funds spent'),
            balance_after=self.balance
        )
        
        logger.info(f"Funds spent from wallet: {self.advertiser.company_name} -${amount}")
        return True
    
    def check_spend_limit(self, amount: Decimal, period: str = 'daily') -> bool:
        """Check if spend amount exceeds limit for period."""
        limit_field = f'{period}_spend_limit'
        limit_value = getattr(self, limit_field, None)
        
        if not limit_value:
            return True  # No limit set
        
        # Get current spend for period
        current_spend = self.get_current_spend(period)
        
        return (current_spend + amount) <= limit_value
    
    def get_current_spend(self, period: str = 'daily') -> Decimal:
        """Get current spend for period."""
        from django.utils import timezone as tz_utils
        
        now = timezone.now()
        
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now - timezone.timedelta(days=7)
        elif period == 'monthly':
            start_date = now - timezone.timedelta(days=30)
        else:
            return Decimal('0')
        
        # This would calculate actual spend from transactions
        # For now, return 0
        return Decimal('0')
    
    def get_wallet_summary(self) -> dict:
        """Get wallet summary."""
        return {
            'balance': float(self.balance),
            'credit_limit': float(self.credit_limit),
            'available_credit': float(self.available_credit),
            'available_balance': float(self.available_balance),
            'utilization_percentage': self.utilization_percentage,
            'is_over_limit': self.is_over_limit,
            'needs_refill': self.needs_refill,
            'auto_refill_enabled': self.auto_refill_enabled,
            'auto_refill_threshold': float(self.auto_refill_threshold),
            'auto_refill_amount': float(self.auto_refill_amount),
            'is_active': self.is_active,
            'is_suspended': self.is_suspended,
            'currency': self.currency,
        }


class AdvertiserTransaction(models.Model):
    """
    Model for tracking wallet transactions.
    
    Stores all financial transactions including
    deposits, spends, and adjustments.
    """
    
    # Core relationships
    wallet = models.ForeignKey(
        AdvertiserWallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_('Wallet'),
        help_text=_('Wallet this transaction belongs to')
    )
    
    # Transaction details
    transaction_type = models.CharField(
        _('Transaction Type'),
        max_length=20,
        choices=[
            ('deposit', _('Deposit')),
            ('spend', _('Spend')),
            ('refund', _('Refund')),
            ('adjustment', _('Adjustment')),
            ('fee', _('Fee')),
            ('bonus', _('Bonus')),
            ('penalty', _('Penalty')),
            ('chargeback', _('Chargeback')),
        ],
        db_index=True,
        help_text=_('Type of transaction')
    )
    
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Transaction amount')
    )
    
    description = models.TextField(
        _('Description'),
        help_text=_('Transaction description')
    )
    
    # Status and reference
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
            ('cancelled', _('Cancelled')),
            ('refunded', _('Refunded')),
        ],
        default='pending',
        db_index=True,
        help_text=_('Transaction status')
    )
    
    reference_id = models.CharField(
        _('Reference ID'),
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('External reference ID')
    )
    
    # Payment information
    payment_method = models.CharField(
        _('Payment Method'),
        max_length=50,
        choices=[
            ('credit_card', _('Credit Card')),
            ('bank_transfer', _('Bank Transfer')),
            ('paypal', _('PayPal')),
            ('wire', _('Wire Transfer')),
            ('crypto', _('Cryptocurrency')),
            ('wallet', _('Wallet')),
        ],
        null=True,
        blank=True,
        help_text=_('Payment method used')
    )
    
    gateway = models.CharField(
        _('Gateway'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Payment gateway used')
    )
    
    gateway_transaction_id = models.CharField(
        _('Gateway Transaction ID'),
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Transaction ID from payment gateway')
    )
    
    # Balance tracking
    balance_before = models.DecimalField(
        _('Balance Before'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Balance before transaction')
    )
    
    balance_after = models.DecimalField(
        _('Balance After'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Balance after transaction')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional transaction metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this transaction was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this transaction was last updated')
    )
    
    completed_at = models.DateTimeField(
        _('Completed At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this transaction was completed')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_transaction'
        verbose_name = _('Advertiser Transaction')
        verbose_name_plural = _('Advertiser Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'transaction_type'], name='idx_wallet_transaction_typ_7f4'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_399'),
            models.Index(fields=['reference_id'], name='idx_reference_id_400'),
            models.Index(fields=['gateway_transaction_id'], name='idx_gateway_transaction_id_401'),
            models.Index(fields=['created_at'], name='idx_created_at_402'),
        ]
    
    def __str__(self):
        return f"{self.transaction_type}: ${self.amount} ({self.wallet.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate amount
        if self.amount == 0:
            raise ValidationError(_('Transaction amount cannot be zero'))
    
    @property
    def is_positive(self) -> bool:
        """Check if transaction is positive (adds to balance)."""
        return self.transaction_type in ['deposit', 'refund', 'bonus']
    
    @property
    def is_negative(self) -> bool:
        """Check if transaction is negative (subtracts from balance)."""
        return self.transaction_type in ['spend', 'fee', 'penalty', 'chargeback']
    
    @property
    def is_completed(self) -> bool:
        """Check if transaction is completed."""
        return self.status == 'completed'
    
    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status == 'pending'
    
    @property
    def transaction_type_display(self) -> str:
        """Get human-readable transaction type."""
        type_names = {
            'deposit': _('Deposit'),
            'spend': _('Spend'),
            'refund': _('Refund'),
            'adjustment': _('Adjustment'),
            'fee': _('Fee'),
            'bonus': _('Bonus'),
            'penalty': _('Penalty'),
            'chargeback': _('Chargeback'),
        }
        return type_names.get(self.transaction_type, self.transaction_type)
    
    def complete_transaction(self):
        """Mark transaction as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        logger.info(f"Transaction completed: {self.id} - {self.transaction_type}")
    
    def fail_transaction(self, reason: str = None):
        """Mark transaction as failed."""
        self.status = 'failed'
        if reason:
            self.metadata = self.metadata or {}
            self.metadata['failure_reason'] = reason
        self.save()
        
        logger.info(f"Transaction failed: {self.id} - {reason or 'Unknown reason'}")
    
    def get_transaction_summary(self) -> dict:
        """Get transaction summary."""
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'transaction_type_display': self.transaction_type_display,
            'amount': float(self.amount),
            'description': self.description,
            'status': self.status,
            'is_positive': self.is_positive,
            'is_negative': self.is_negative,
            'balance_before': float(self.balance_before),
            'balance_after': float(self.balance_after),
            'payment_method': self.payment_method,
            'gateway': self.gateway,
            'reference_id': self.reference_id,
            'gateway_transaction_id': self.gateway_transaction_id,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class AdvertiserDeposit(models.Model):
    """
    Model for managing advertiser deposits.
    
    Stores deposit information including payment
    gateway details and status tracking.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='deposits',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this deposit belongs to')
    )
    
    # Deposit details
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Deposit amount')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Payment information
    gateway = models.CharField(
        _('Gateway'),
        max_length=50,
        choices=[
            ('stripe', _('Stripe')),
            ('paypal', _('PayPal')),
            ('authorize_net', _('Authorize.Net')),
            ('braintree', _('Braintree')),
            ('square', _('Square')),
            ('bank_transfer', _('Bank Transfer')),
            ('wire', _('Wire Transfer')),
            ('crypto', _('Cryptocurrency')),
        ],
        help_text=_('Payment gateway used')
    )
    
    gateway_transaction_id = models.CharField(
        _('Gateway Transaction ID'),
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Transaction ID from payment gateway')
    )
    
    payment_method = models.CharField(
        _('Payment Method'),
        max_length=50,
        choices=[
            ('credit_card', _('Credit Card')),
            ('bank_account', _('Bank Account')),
            ('paypal_account', _('PayPal Account')),
            ('crypto_wallet', _('Crypto Wallet')),
            ('wire_transfer', _('Wire Transfer')),
        ],
        help_text=_('Payment method used')
    )
    
    # Status and processing
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('processing', _('Processing')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
            ('cancelled', _('Cancelled')),
            ('refunded', _('Refunded')),
        ],
        default='pending',
        db_index=True,
        help_text=_('Deposit status')
    )
    
    receipt_url = models.URLField(
        _('Receipt URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL to receipt or invoice')
    )
    
    # Fees and charges
    processing_fee = models.DecimalField(
        _('Processing Fee'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Processing fee charged')
    )
    
    net_amount = models.DecimalField(
        _('Net Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Net amount after fees')
    )
    
    # Additional information
    notes = models.TextField(
        _('Notes'),
        null=True,
        blank=True,
        help_text=_('Additional notes about deposit')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional deposit metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this deposit was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this deposit was last updated')
    )
    
    completed_at = models.DateTimeField(
        _('Completed At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this deposit was completed')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_deposit'
        verbose_name = _('Advertiser Deposit')
        verbose_name_plural = _('Advertiser Deposits')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_403'),
            models.Index(fields=['gateway', 'status'], name='idx_gateway_status_404'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_405'),
            models.Index(fields=['gateway_transaction_id'], name='idx_gateway_transaction_id_406'),
            models.Index(fields=['created_at'], name='idx_created_at_407'),
        ]
    
    def __str__(self):
        return f"Deposit: ${self.amount} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate amount
        if self.amount <= 0:
            raise ValidationError(_('Deposit amount must be positive'))
        
        # Validate fees
        if self.processing_fee < 0:
            raise ValidationError(_('Processing fee cannot be negative'))
        
        # Validate net amount
        if self.net_amount and self.net_amount < 0:
            raise ValidationError(_('Net amount cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate net amount if not provided
        if not self.net_amount:
            self.net_amount = self.amount - self.processing_fee
        
        super().save(*args, **kwargs)
    
    @property
    def is_completed(self) -> bool:
        """Check if deposit is completed."""
        return self.status == 'completed'
    
    @property
    def is_pending(self) -> bool:
        """Check if deposit is pending."""
        return self.status == 'pending'
    
    @property
    def is_failed(self) -> bool:
        """Check if deposit failed."""
        return self.status == 'failed'
    
    @property
    def total_fees(self) -> Decimal:
        """Get total fees for this deposit."""
        return self.processing_fee
    
    @property
    def effective_amount(self) -> Decimal:
        """Get effective amount (net of fees)."""
        return self.net_amount
    
    def complete_deposit(self, gateway_transaction_id: str = None):
        """Mark deposit as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        if gateway_transaction_id:
            self.gateway_transaction_id = gateway_transaction_id
        
        self.save()
        
        # Add funds to wallet
        wallet, created = AdvertiserWallet.objects.get_or_create(
            advertiser=self.advertiser
        )
        wallet.add_funds(self.net_amount, f"Deposit: {self.gateway}")
        
        logger.info(f"Deposit completed: {self.id} - ${self.net_amount}")
    
    def fail_deposit(self, reason: str = None):
        """Mark deposit as failed."""
        self.status = 'failed'
        
        if reason:
            self.notes = reason
        
        self.save()
        
        logger.info(f"Deposit failed: {self.id} - {reason or 'Unknown reason'}")
    
    def get_deposit_summary(self) -> dict:
        """Get deposit summary."""
        return {
            'id': self.id,
            'amount': float(self.amount),
            'currency': self.currency,
            'gateway': self.gateway,
            'payment_method': self.payment_method,
            'status': self.status,
            'processing_fee': float(self.processing_fee),
            'net_amount': float(self.net_amount),
            'effective_amount': float(self.effective_amount),
            'gateway_transaction_id': self.gateway_transaction_id,
            'receipt_url': self.receipt_url,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class AdvertiserInvoice(models.Model):
    """
    Model for managing advertiser invoices.
    
    Stores billing information including period,
    amounts, and payment status.
    """
    
    # Core relationship
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this invoice belongs to')
    )
    
    # Invoice details
    invoice_number = models.CharField(
        _('Invoice Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Unique invoice number')
    )
    
    period = models.CharField(
        _('Period'),
        max_length=20,
        help_text=_('Billing period (e.g., "2023-12")')
    )
    
    period_start = models.DateField(
        _('Period Start'),
        help_text=_('Start date of billing period')
    )
    
    period_end = models.DateField(
        _('Period End'),
        help_text=_('End date of billing period')
    )
    
    # Amounts
    subtotal = models.DecimalField(
        _('Subtotal'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Subtotal before taxes and fees')
    )
    
    tax_amount = models.DecimalField(
        _('Tax Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Tax amount charged')
    )
    
    fee_amount = models.DecimalField(
        _('Fee Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Additional fees charged')
    )
    
    total_amount = models.DecimalField(
        _('Total Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Total amount due')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Status and due dates
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('sent', _('Sent')),
            ('viewed', _('Viewed')),
            ('paid', _('Paid')),
            ('overdue', _('Overdue')),
            ('cancelled', _('Cancelled')),
            ('refunded', _('Refunded')),
        ],
        default='draft',
        db_index=True,
        help_text=_('Invoice status')
    )
    
    due_date = models.DateField(
        _('Due Date'),
        help_text=_('Payment due date')
    )
    
    paid_at = models.DateField(
        _('Paid At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When invoice was paid')
    )
    
    # Files and documents
    pdf_url = models.URLField(
        _('PDF URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL to PDF invoice')
    )
    
    # Additional information
    notes = models.TextField(
        _('Notes'),
        null=True,
        blank=True,
        help_text=_('Additional notes about invoice')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional invoice metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this invoice was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this invoice was last updated')
    )
    
    sent_at = models.DateTimeField(
        _('Sent At'),
        null=True,
        blank=True,
        help_text=_('When invoice was sent to advertiser')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_invoice'
        verbose_name = _('Advertiser Invoice')
        verbose_name_plural = _('Advertiser Invoices')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_408'),
            models.Index(fields=['invoice_number'], name='idx_invoice_number_409'),
            models.Index(fields=['status', 'due_date'], name='idx_status_due_date_410'),
            models.Index(fields=['period_start', 'period_end'], name='idx_period_start_period_en_930'),
            models.Index(fields=['paid_at'], name='idx_paid_at_412'),
            models.Index(fields=['created_at'], name='idx_created_at_413'),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate period dates
        if self.period_start and self.period_end and self.period_start >= self.period_end:
            raise ValidationError(_('Period start must be before period end'))
        
        # Validate amounts
        if self.subtotal < 0:
            raise ValidationError(_('Subtotal cannot be negative'))
        
        if self.tax_amount < 0:
            raise ValidationError(_('Tax amount cannot be negative'))
        
        if self.fee_amount < 0:
            raise ValidationError(_('Fee amount cannot be negative'))
        
        if self.total_amount < 0:
            raise ValidationError(_('Total amount cannot be negative'))
        
        # Validate due date
        if self.due_date and self.period_end and self.due_date < self.period_end:
            raise ValidationError(_('Due date cannot be before period end'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate total amount if not provided
        if not self.total_amount:
            self.total_amount = self.subtotal + self.tax_amount + self.fee_amount
        
        # Generate invoice number if not provided
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number."""
        timestamp = timezone.now().strftime('%Y%m%d')
        advertiser_id = str(self.advertiser.id).zfill(4)
        
        # Get last invoice number for this advertiser
        last_invoice = AdvertiserInvoice.objects.filter(
            advertiser=self.advertiser
        ).order_by('-created_at').first()
        
        if last_invoice and last_invoice.invoice_number:
            # Extract sequence number
            parts = last_invoice.invoice_number.split('-')
            if len(parts) >= 3:
                try:
                    sequence = int(parts[2]) + 1
                    return f"INV-{timestamp}-{advertiser_id}-{sequence:04d}"
                except ValueError:
                    pass
        
        return f"INV-{timestamp}-{advertiser_id}-0001"
    
    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.status == 'paid'
    
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return (
            self.status in ['sent', 'viewed'] and
            self.due_date and
            timezone.now().date() > self.due_date
        )
    
    @property
    def days_overdue(self) -> int:
        """Get days invoice is overdue."""
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0
    
    @property
    def amount_due(self) -> Decimal:
        """Get amount due (total minus any payments)."""
        if self.is_paid:
            return Decimal('0')
        return self.total_amount
    
    def mark_as_sent(self):
        """Mark invoice as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
        
        logger.info(f"Invoice sent: {self.invoice_number}")
    
    def mark_as_paid(self, payment_date=None):
        """Mark invoice as paid."""
        self.status = 'paid'
        self.paid_at = payment_date or timezone.now().date()
        self.save()
        
        logger.info(f"Invoice paid: {self.invoice_number}")
    
    def get_invoice_summary(self) -> dict:
        """Get invoice summary."""
        return {
            'invoice_number': self.invoice_number,
            'period': self.period,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'fee_amount': float(self.fee_amount),
            'total_amount': float(self.total_amount),
            'amount_due': float(self.amount_due),
            'currency': self.currency,
            'status': self.status,
            'due_date': self.due_date.isoformat(),
            'is_paid': self.is_paid,
            'is_overdue': self.is_overdue,
            'days_overdue': self.days_overdue,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'pdf_url': self.pdf_url,
            'created_at': self.created_at.isoformat(),
        }


class CampaignSpend(models.Model):
    """
    Model for tracking campaign spend.
    
    Stores daily spend data for campaigns
    including impressions, clicks, and conversions.
    """
    
    # Core relationships
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='spend_data',
        verbose_name=_('Campaign'),
        help_text=_('Campaign this spend data belongs to')
    )
    
    # Date and period
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this spend data')
    )
    
    hour = models.IntegerField(
        _('Hour'),
        null=True,
        blank=True,
        help_text=_('Hour of day (0-23)')
    )
    
    # Performance metrics
    impressions = models.IntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions delivered')
    )
    
    clicks = models.IntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks received')
    )
    
    conversions = models.IntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions generated')
    )
    
    # Financial metrics
    spend_amount = models.DecimalField(
        _('Spend Amount'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Amount spent')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Action'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per action')
    )
    
    cpc = models.DecimalField(
        _('Cost Per Click'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per click')
    )
    
    cpm = models.DecimalField(
        _('Cost Per Mille'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Cost per thousand impressions')
    )
    
    # Calculated metrics
    ctr = models.DecimalField(
        _('Click Through Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Click through rate percentage')
    )
    
    conversion_rate = models.DecimalField(
        _('Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Conversion rate percentage')
    )
    
    # Currency
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional spend metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this spend data was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this spend data was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_campaign_spend'
        verbose_name = _('Campaign Spend')
        verbose_name_plural = _('Campaign Spend')
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['campaign', 'date'], name='idx_campaign_date_414'),
            models.Index(fields=['date', 'hour'], name='idx_date_hour_415'),
            models.Index(fields=['date'], name='idx_date_416'),
            models.Index(fields=['created_at'], name='idx_created_at_417'),
        ]
        unique_together = [
            ['campaign', 'date', 'hour'],
        ]
    
    def __str__(self):
        return f"Spend: {self.campaign.name} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate hour
        if self.hour and (self.hour < 0 or self.hour > 23):
            raise ValidationError(_('Hour must be between 0 and 23'))
        
        # Validate metrics
        for field_name in ['impressions', 'clicks', 'conversions']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate amounts
        for field_name in ['spend_amount', 'cpa', 'cpc', 'cpm']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_metrics()
        
        super().save(*args, **kwargs)
    
    def _calculate_metrics(self):
        """Calculate derived performance metrics."""
        # Calculate CTR
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        # Calculate conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        # Calculate CPA
        if self.conversions > 0:
            self.cpa = self.spend_amount / self.conversions
        
        # Calculate CPC
        if self.clicks > 0:
            self.cpc = self.spend_amount / self.clicks
        
        # Calculate CPM
        if self.impressions > 0:
            self.cpm = (self.spend_amount / self.impressions) * 1000
    
    def get_spend_summary(self) -> dict:
        """Get spend summary."""
        return {
            'campaign_id': self.campaign.id,
            'campaign_name': self.campaign.name,
            'date': self.date.isoformat(),
            'hour': self.hour,
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'spend_amount': float(self.spend_amount),
            'currency': self.currency,
            'ctr': float(self.ctr),
            'conversion_rate': float(self.conversion_rate),
            'cpa': float(self.cpa),
            'cpc': float(self.cpc),
            'cpm': float(self.cpm),
            'created_at': self.created_at.isoformat(),
        }


class BillingAlert(models.Model):
    """
    Model for managing billing alerts.
    
    Stores alert configurations for low balance,
    daily budget limits, and other billing events.
    """
    
    # Core relationship
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='billing_alerts',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this alert belongs to')
    )
    
    # Alert configuration
    alert_type = models.CharField(
        _('Alert Type'),
        max_length=50,
        choices=[
            ('low_balance', _('Low Balance')),
            ('daily_budget_reached', _('Daily Budget Reached')),
            ('weekly_budget_reached', _('Weekly Budget Reached')),
            ('monthly_budget_reached', _('Monthly Budget Reached')),
            ('credit_limit_reached', _('Credit Limit Reached')),
            ('payment_failed', _('Payment Failed')),
            ('invoice_due', _('Invoice Due')),
            ('invoice_overdue', _('Invoice Overdue')),
            ('unusual_spend', _('Unusual Spend')),
        ],
        help_text=_('Type of billing alert')
    )
    
    # Threshold configuration
    threshold = models.DecimalField(
        _('Threshold'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Alert threshold value')
    )
    
    threshold_type = models.CharField(
        _('Threshold Type'),
        max_length=20,
        choices=[
            ('percentage', _('Percentage')),
            ('amount', _('Amount')),
            ('count', _('Count')),
            ('boolean', _('Boolean')),
        ],
        default='amount',
        help_text=_('Type of threshold')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this alert is active')
    )
    
    # Notification settings
    email_enabled = models.BooleanField(
        _('Email Enabled'),
        default=True,
        help_text=_('Whether to send email notifications')
    )
    
    sms_enabled = models.BooleanField(
        _('SMS Enabled'),
        default=False,
        help_text=_('Whether to send SMS notifications')
    )
    
    webhook_url = models.URLField(
        _('Webhook URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('URL to send webhook notifications')
    )
    
    # Frequency settings
    cooldown_minutes = models.IntegerField(
        _('Cooldown Minutes'),
        default=60,
        help_text=_('Minutes between same alert notifications')
    )
    
    max_alerts_per_day = models.IntegerField(
        _('Max Alerts Per Day'),
        default=10,
        help_text=_('Maximum alerts per day')
    )
    
    # Additional settings
    custom_message = models.TextField(
        _('Custom Message'),
        null=True,
        blank=True,
        help_text=_('Custom alert message template')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional alert metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this alert was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this alert was last updated')
    )
    
    last_triggered_at = models.DateTimeField(
        _('Last Triggered At'),
        null=True,
        blank=True,
        help_text=_('When this alert was last triggered')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_billing_alert'
        verbose_name = _('Billing Alert')
        verbose_name_plural = _('Billing Alerts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'alert_type'], name='idx_advertiser_alert_type_418'),
            models.Index(fields=['is_active', 'alert_type'], name='idx_is_active_alert_type_419'),
            models.Index(fields=['created_at'], name='idx_created_at_420'),
        ]
        unique_together = [
            ['advertiser', 'alert_type'],
        ]
    
    def __str__(self):
        return f"{self.alert_type} Alert ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate threshold
        if self.threshold_type == 'amount' and self.threshold < 0:
            raise ValidationError(_('Threshold amount cannot be negative'))
        
        if self.threshold_type == 'percentage' and (self.threshold < 0 or self.threshold > 100):
            raise ValidationError(_('Threshold percentage must be between 0 and 100'))
        
        if self.threshold_type == 'count' and self.threshold < 0:
            raise ValidationError(_('Threshold count cannot be negative'))
        
        # Validate cooldown
        if self.cooldown_minutes < 0:
            raise ValidationError(_('Cooldown minutes cannot be negative'))
        
        # Validate max alerts per day
        if self.max_alerts_per_day < 1:
            raise ValidationError(_('Max alerts per day must be at least 1'))
    
    @property
    def alert_type_display(self) -> str:
        """Get human-readable alert type."""
        type_names = {
            'low_balance': _('Low Balance'),
            'daily_budget_reached': _('Daily Budget Reached'),
            'weekly_budget_reached': _('Weekly Budget Reached'),
            'monthly_budget_reached': _('Monthly Budget Reached'),
            'credit_limit_reached': _('Credit Limit Reached'),
            'payment_failed': _('Payment Failed'),
            'invoice_due': _('Invoice Due'),
            'invoice_overdue': _('Invoice Overdue'),
            'unusual_spend': _('Unusual Spend'),
        }
        return type_names.get(self.alert_type, self.alert_type)
    
    def should_trigger(self, current_value: Decimal, context: dict = None) -> bool:
        """Check if alert should trigger based on current value."""
        if not self.is_active:
            return False
        
        # Check cooldown period
        if self.last_triggered_at:
            cooldown_end = self.last_triggered_at + timezone.timedelta(minutes=self.cooldown_minutes)
            if timezone.now() < cooldown_end:
                return False
        
        # Check threshold based on type
        if self.threshold_type == 'amount':
            return current_value <= self.threshold
        elif self.threshold_type == 'percentage':
            # This would need a base value to calculate percentage
            return False  # Placeholder
        elif self.threshold_type == 'count':
            return current_value >= self.threshold
        elif self.threshold_type == 'boolean':
            return bool(current_value)
        
        return False
    
    def trigger_alert(self, context: dict = None):
        """Trigger the alert."""
        self.last_triggered_at = timezone.now()
        self.save()
        
        # Send notifications
        self._send_notifications(context)
        
        logger.info(f"Billing alert triggered: {self.alert_type} for {self.advertiser.company_name}")
    
    def _send_notifications(self, context: dict = None):
        """Send alert notifications."""
        # This would implement email, SMS, and webhook notifications
        # For now, just log
        pass
    
    def get_alert_summary(self) -> dict:
        """Get alert configuration summary."""
        return {
            'alert_type': self.alert_type,
            'alert_type_display': self.alert_type_display,
            'threshold': float(self.threshold),
            'threshold_type': self.threshold_type,
            'is_active': self.is_active,
            'email_enabled': self.email_enabled,
            'sms_enabled': self.sms_enabled,
            'webhook_url': self.webhook_url,
            'cooldown_minutes': self.cooldown_minutes,
            'max_alerts_per_day': self.max_alerts_per_day,
            'last_triggered_at': self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            'created_at': self.created_at.isoformat(),
        }


# Signal handlers for billing models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdvertiserWallet)
def wallet_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for wallets."""
    if created:
        logger.info(f"New wallet created: {instance.advertiser.company_name}")

@receiver(post_save, sender=AdvertiserTransaction)
def transaction_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for transactions."""
    if created:
        logger.info(f"New transaction created: {instance.transaction_type} - ${instance.amount}")

@receiver(post_save, sender=AdvertiserDeposit)
def deposit_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for deposits."""
    if created:
        logger.info(f"New deposit created: ${instance.amount} ({instance.advertiser.company_name})")

@receiver(post_save, sender=AdvertiserInvoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for invoices."""
    if created:
        logger.info(f"New invoice created: {instance.invoice_number}")

@receiver(post_save, sender=CampaignSpend)
def spend_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for spend data."""
    if created:
        logger.info(f"New spend data: {instance.campaign.name} - ${instance.spend_amount}")

@receiver(post_save, sender=BillingAlert)
def alert_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for billing alerts."""
    if created:
        logger.info(f"New billing alert created: {instance.alert_type} ({instance.advertiser.company_name})")

@receiver(post_delete, sender=AdvertiserWallet)
def wallet_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for wallets."""
    logger.info(f"Wallet deleted: {instance.advertiser.company_name}")

@receiver(post_delete, sender=AdvertiserTransaction)
def transaction_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for transactions."""
    logger.info(f"Transaction deleted: {instance.transaction_type} - ${instance.amount}")

@receiver(post_delete, sender=AdvertiserDeposit)
def deposit_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for deposits."""
    logger.info(f"Deposit deleted: ${instance.amount} ({instance.advertiser.company_name})")

@receiver(post_delete, sender=AdvertiserInvoice)
def invoice_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for invoices."""
    logger.info(f"Invoice deleted: {instance.invoice_number}")

@receiver(post_delete, sender=CampaignSpend)
def spend_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for spend data."""
    logger.info(f"Spend data deleted: {instance.campaign.name} - ${instance.spend_amount}")

@receiver(post_delete, sender=BillingAlert)
def alert_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for billing alerts."""
    logger.info(f"Billing alert deleted: {instance.alert_type} ({instance.advertiser.company_name})")
