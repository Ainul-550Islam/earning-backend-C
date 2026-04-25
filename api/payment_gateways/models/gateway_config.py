# api/payment_gateways/models/gateway_config.py
# Advanced gateway configuration models

from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel
from .core import PaymentGateway, GATEWAY_CHOICES


class GatewayCredential(TimeStampedModel):
    """
    Per-tenant encrypted gateway credentials.
    Supports multi-tenant setups where each tenant has own gateway account.
    """

    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='credentials')
    tenant          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       null=True, blank=True, related_name='gateway_credentials',
                       help_text='null = platform-wide credentials')
    label           = models.CharField(max_length=100, default='default')

    # Encrypted credential fields
    merchant_id     = models.CharField(max_length=500, blank=True)
    api_key         = models.TextField(blank=True, help_text='Encrypted API key')
    api_secret      = models.TextField(blank=True, help_text='Encrypted secret')
    webhook_secret  = models.TextField(blank=True)
    extra_fields    = models.JSONField(default=dict, blank=True,
                       help_text='Gateway-specific extra fields (e.g. store_id, client_id)')

    is_test_mode    = models.BooleanField(default=True)
    is_active       = models.BooleanField(default=True)
    expires_at      = models.DateTimeField(null=True, blank=True,
                       help_text='API key expiry — triggers rotation reminder')
    last_verified   = models.DateTimeField(null=True, blank=True)
    is_verified     = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Gateway Credential'
        unique_together     = ['gateway', 'tenant', 'label']

    def __str__(self):
        tenant_str = self.tenant.username if self.tenant else 'platform'
        return f'{self.gateway.name} | {tenant_str} | {"test" if self.is_test_mode else "live"}'


class GatewayWebhookConfig(TimeStampedModel):
    """Webhook configuration per gateway."""

    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='webhook_configs')
    webhook_url     = models.URLField(max_length=500, help_text='URL registered with gateway')
    secret          = models.CharField(max_length=500, blank=True,
                       help_text='HMAC signing secret from gateway')
    events          = models.JSONField(default=list, blank=True,
                       help_text='Events to receive e.g. ["payment.completed","refund.processed"]')
    is_active       = models.BooleanField(default=True)
    last_tested     = models.DateTimeField(null=True, blank=True)
    test_passed     = models.BooleanField(default=False)
    signature_header= models.CharField(max_length=100, blank=True,
                       help_text='Header name containing signature e.g. X-bKash-Signature')
    signature_algo  = models.CharField(max_length=20, default='sha256',
                       choices=(('sha256','HMAC-SHA256'),('sha512','HMAC-SHA512'),('md5','MD5')))

    class Meta:
        verbose_name = 'Gateway Webhook Config'

    def __str__(self):
        return f'{self.gateway.name} webhook config'


class GatewayLimit(TimeStampedModel):
    """Per-gateway, per-tenant transaction limits."""

    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='limits')
    tenant          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       null=True, blank=True, related_name='gateway_limits')
    transaction_type= models.CharField(max_length=20, default='deposit',
                       choices=(('deposit','Deposit'),('withdrawal','Withdrawal'),('all','All')))

    min_amount      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))
    max_amount      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50000'))
    daily_limit     = models.DecimalField(max_digits=12, decimal_places=2,
                       null=True, blank=True, help_text='Max cumulative per day')
    monthly_limit   = models.DecimalField(max_digits=12, decimal_places=2,
                       null=True, blank=True)
    per_txn_count_daily = models.IntegerField(null=True, blank=True,
                       help_text='Max number of transactions per day')
    currency        = models.CharField(max_length=5, default='BDT')
    is_active       = models.BooleanField(default=True)

    class Meta:
        verbose_name    = 'Gateway Limit'
        unique_together = ['gateway', 'tenant', 'transaction_type']

    def __str__(self):
        return f'{self.gateway.name} limit: {self.min_amount}–{self.max_amount}'


class GatewayFeeRule(TimeStampedModel):
    """Dynamic fee rules per gateway."""

    FEE_TYPES = (
        ('percentage', 'Percentage of amount'),
        ('fixed',      'Fixed amount'),
        ('tiered',     'Tiered (amount-based)'),
        ('mixed',      'Percentage + fixed'),
    )

    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='fee_rules')
    tenant          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       null=True, blank=True)
    transaction_type= models.CharField(max_length=20, default='deposit')
    fee_type        = models.CharField(max_length=15, choices=FEE_TYPES, default='percentage')

    fee_value       = models.DecimalField(max_digits=7, decimal_places=4,
                       help_text='Percentage (e.g. 1.5 = 1.5%) or fixed amount')
    fixed_component = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'),
                       help_text='Fixed component for mixed fee type')
    min_fee         = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    max_fee         = models.DecimalField(max_digits=10, decimal_places=2,
                       null=True, blank=True)
    currency        = models.CharField(max_length=5, default='BDT')

    # Tiered rules stored as JSON
    tiers           = models.JSONField(default=list, blank=True,
                       help_text='[{"min":0,"max":1000,"rate":2.0},{"min":1001,"rate":1.5}]')
    is_active       = models.BooleanField(default=True)
    valid_from      = models.DateField(null=True, blank=True)
    valid_until     = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Gateway Fee Rule'

    def __str__(self):
        return f'{self.gateway.name} fee: {self.fee_type} {self.fee_value}'

    def calculate(self, amount: Decimal) -> Decimal:
        """Calculate fee for a given amount."""
        if self.fee_type == 'percentage':
            fee = (amount * self.fee_value) / 100
        elif self.fee_type == 'fixed':
            fee = self.fee_value
        elif self.fee_type == 'mixed':
            fee = (amount * self.fee_value) / 100 + self.fixed_component
        else:
            fee = Decimal('0')

        if self.min_fee:
            fee = max(fee, self.min_fee)
        if self.max_fee:
            fee = min(fee, self.max_fee)
        return fee


class GatewayHealthLog(TimeStampedModel):
    """Health check log for each gateway — pinged every 5 minutes."""

    STATUS = (
        ('healthy',  'Healthy'),
        ('degraded', 'Degraded (slow)'),
        ('down',     'Down'),
        ('timeout',  'Timeout'),
        ('error',    'Error'),
    )

    gateway             = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                           related_name='health_logs')
    status              = models.CharField(max_length=10, choices=STATUS)
    response_time_ms    = models.IntegerField(default=0)
    http_status_code    = models.IntegerField(null=True, blank=True)
    error               = models.TextField(blank=True)
    checked_at          = models.DateTimeField(auto_now_add=True)
    is_test_mode        = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Gateway Health Log'
        ordering     = ['-checked_at']
        indexes      = [models.Index(fields=['gateway', 'checked_at'])]

    def __str__(self):
        return f'{self.gateway.name} health [{self.status}] {self.response_time_ms}ms'
