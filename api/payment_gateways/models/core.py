# api/payment_gateways/models/core.py
# Core payment gateway models — fixed & expanded

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from core.models import TimeStampedModel


GATEWAY_CHOICES = (
    ('bkash',      'bKash'),
    ('nagad',      'Nagad'),
    ('sslcommerz', 'SSLCommerz'),
    ('amarpay',    'AmarPay'),
    ('upay',       'Upay'),
    ('shurjopay',  'ShurjoPay'),
    ('stripe',     'Stripe'),
    ('paypal',     'PayPal'),
    ('payoneer',   'Payoneer'),
    ('wire',       'Wire Transfer'),
    ('ach',        'ACH (US Bank)'),
    ('crypto',     'Cryptocurrency'),
)

GATEWAY_STATUS = (
    ('active',       'Active'),
    ('inactive',     'Inactive'),
    ('maintenance',  'Maintenance'),
    ('degraded',     'Degraded'),
)

TRANSACTION_TYPES = (
    ('deposit',    'Deposit'),
    ('withdrawal', 'Withdrawal'),
    ('refund',     'Refund'),
    ('bonus',      'Bonus'),
    ('commission', 'Commission'),
    ('adjustment', 'Adjustment'),
)

TRANSACTION_STATUS = (
    ('pending',    'Pending'),
    ('processing', 'Processing'),
    ('completed',  'Completed'),
    ('failed',     'Failed'),
    ('cancelled',  'Cancelled'),
    ('reversed',   'Reversed'),
    ('on_hold',    'On Hold'),
)


class PaymentGateway(TimeStampedModel):
    """Payment Gateway configuration — 12 gateways supported."""

    name             = models.CharField(max_length=50, choices=GATEWAY_CHOICES, unique=True)
    display_name     = models.CharField(max_length=100)
    description      = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=GATEWAY_STATUS, default='active')

    # API Credentials (use GatewayCredential for per-tenant)
    merchant_id      = models.CharField(max_length=200, blank=True)
    merchant_key     = models.CharField(max_length=500, blank=True)
    merchant_secret  = models.CharField(max_length=500, blank=True)
    api_url          = models.URLField(max_length=500, blank=True)
    callback_url     = models.URLField(max_length=500, blank=True)

    is_test_mode     = models.BooleanField(default=True)
    transaction_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.50')
    )
    minimum_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10'))
    maximum_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50000'))
    daily_limit      = models.DecimalField(max_digits=12, decimal_places=2,
                        null=True, blank=True, help_text='Max total per day (null=unlimited)')

    supports_deposit     = models.BooleanField(default=True)
    supports_withdrawal  = models.BooleanField(default=True)
    supports_refund      = models.BooleanField(default=True)
    supported_currencies = models.CharField(max_length=200, default='BDT')

    logo             = models.ImageField(upload_to='gateway_logos/', blank=True, null=True)
    color_code       = models.CharField(max_length=7, default='#0066CC')
    sort_order       = models.IntegerField(default=0)
    region           = models.CharField(max_length=10, default='BD',
                        choices=(('BD','Bangladesh'),('GLOBAL','Global'),('US','United States')))

    # Health
    last_health_check    = models.DateTimeField(null=True, blank=True)
    health_status        = models.CharField(max_length=10, default='unknown',
                            choices=(('healthy','Healthy'),('degraded','Degraded'),
                                     ('down','Down'),('unknown','Unknown')))
    avg_response_time_ms = models.IntegerField(default=0)

    config_data      = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Payment Gateway'
        verbose_name_plural = 'Payment Gateways'
        ordering            = ['sort_order', 'name']

    def __str__(self):
        return f'{self.get_name_display()} ({self.get_status_display()})'

    @property
    def is_available(self):
        return self.status == 'active'


class PaymentGatewayMethod(TimeStampedModel):
    """User's saved payment method / account for a gateway."""

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='pg_payment_methods')
    gateway          = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    account_number   = models.CharField(max_length=100)
    account_name     = models.CharField(max_length=100, blank=True)
    is_verified      = models.BooleanField(default=False)
    is_default       = models.BooleanField(default=False)
    metadata         = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Payment Method'
        unique_together     = ['user', 'gateway', 'account_number']

    def __str__(self):
        return f'{self.user.username} — {self.gateway} ({self.account_number})'


class GatewayTransaction(TimeStampedModel):
    """Core transaction record for all gateway operations."""

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='gateway_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    gateway          = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    amount           = models.DecimalField(max_digits=12, decimal_places=2)
    fee              = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    net_amount       = models.DecimalField(max_digits=12, decimal_places=2)
    currency         = models.CharField(max_length=5, default='BDT')
    status           = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    reference_id     = models.CharField(max_length=100, unique=True)
    gateway_reference= models.CharField(max_length=200, blank=True)
    payment_method   = models.ForeignKey(PaymentGatewayMethod, on_delete=models.SET_NULL,
                        null=True, blank=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    metadata         = models.JSONField(default=dict, blank=True)
    notes            = models.TextField(blank=True)
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    device_type      = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name        = 'Gateway Transaction'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['reference_id']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
        ]

    def __str__(self):
        return f'{self.user.username} | {self.transaction_type} | {self.amount} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)


class PayoutRequest(TimeStampedModel):
    """Withdrawal / payout request."""

    PAYOUT_METHODS = GATEWAY_CHOICES  # Reuse gateway choices

    STATUS_CHOICES = (
        ('pending',    'Pending'),
        ('approved',   'Approved'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('rejected',   'Rejected'),
        ('cancelled',  'Cancelled'),
        ('failed',     'Failed'),
    )

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='payout_requests')
    amount           = models.DecimalField(max_digits=12, decimal_places=2)
    fee              = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    net_amount       = models.DecimalField(max_digits=12, decimal_places=2)
    currency         = models.CharField(max_length=5, default='BDT')
    payout_method    = models.CharField(max_length=20, choices=PAYOUT_METHODS)
    account_number   = models.CharField(max_length=200)
    account_name     = models.CharField(max_length=200, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference_id     = models.CharField(max_length=100, unique=True)
    gateway_reference= models.CharField(max_length=200, blank=True)
    admin_notes      = models.TextField(blank=True)
    processed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                        null=True, blank=True, related_name='pg_processed_payouts')
    processed_at     = models.DateTimeField(null=True, blank=True)
    metadata         = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name  = 'Payout Request'
        ordering      = ['-created_at']
        indexes       = [models.Index(fields=['status']), models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'{self.user.username} — {self.amount} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)


class GatewayConfig(TimeStampedModel):
    """Key-value config per gateway."""
    gateway    = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE, related_name='configs')
    key        = models.CharField(max_length=100)
    value      = models.TextField()
    is_secret  = models.BooleanField(default=False)
    description= models.TextField(blank=True)

    class Meta:
        unique_together = ['gateway', 'key']
        verbose_name    = 'Gateway Config'

    def __str__(self):
        return f'{self.gateway.name} — {self.key}'


class Currency(TimeStampedModel):
    """Supported currencies with live exchange rates."""
    code          = models.CharField(max_length=3, unique=True)
    name          = models.CharField(max_length=50)
    symbol        = models.CharField(max_length=10)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1'))
    is_default    = models.BooleanField(default=False)
    is_active     = models.BooleanField(default=True)
    last_updated  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name  = 'Currency'
        ordering      = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class PaymentGatewayWebhookLog(TimeStampedModel):
    """Raw webhook log from any gateway."""
    gateway    = models.CharField(max_length=20)
    payload    = models.JSONField()
    headers    = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    processed  = models.BooleanField(default=False)
    is_valid   = models.BooleanField(default=True)
    response   = models.TextField(blank=True)
    event_type = models.CharField(max_length=100, blank=True)
    transaction= models.ForeignKey(GatewayTransaction, on_delete=models.SET_NULL,
                  null=True, blank=True, related_name='webhook_logs')

    class Meta:
        verbose_name = 'Webhook Log'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['gateway', 'processed'])]

    def __str__(self):
        return f'{self.gateway} webhook [{self.created_at}]'
