from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from core.models import TimeStampedModel


class PaymentGateway(TimeStampedModel):
    """Payment Gateway Configuration"""
    GATEWAY_CHOICES = (
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('sslcommerz', 'SSLCommerz'),
        ('amarpay', 'AmarPay'),
        ('upay', 'Upay'),
        ('shurjopay', 'ShurjoPay'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    )
    
    name = models.CharField(max_length=50, choices=GATEWAY_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # API Credentials
    merchant_id = models.CharField(max_length=200, blank=True, null=True)
    merchant_key = models.CharField(max_length=500, blank=True, null=True)
    merchant_secret = models.CharField(max_length=500, blank=True, null=True)
    api_url = models.URLField(max_length=500, blank=True, null=True)
    callback_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Configuration
    is_test_mode = models.BooleanField(default=True)
    transaction_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    maximum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50000.00)
    
    # Settings
    supports_deposit = models.BooleanField(default=True)
    supports_withdrawal = models.BooleanField(default=True)
    supported_currencies = models.CharField(max_length=100, default='BDT,USD')
    
    # Visual
    logo = models.ImageField(upload_to='gateway_logos/', blank=True, null=True)
    color_code = models.CharField(max_length=7, default='#0066CC')
    sort_order = models.IntegerField(default=0)
    
    # Metadata
    config_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Payment Gateway'
        verbose_name_plural = 'Payment Gateways'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.get_name_display()} ({self.get_status_display()})"
    
    @property
    def is_available(self):
        return self.status == 'active'


class PaymentGatewayMethod(TimeStampedModel):  # [ERROR] PaymentMethod থেকে PaymentGatewayMethod নাম পরিবর্তন করুন
    GATEWAY_CHOICES = (
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_gateways_paymentgatewaymethod_user'  # [ERROR] unique related_name দিন
    )
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    account_number = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Payment Gateway Method'  # [ERROR] নাম পরিবর্তন করুন
        verbose_name_plural = 'Payment Gateway Methods'  # [ERROR] নাম পরিবর্তন করুন
        unique_together = ['user', 'gateway', 'account_number']
    
    def __str__(self):
        return f"{self.user.username} - {self.gateway}"


class GatewayTransaction(TimeStampedModel):  # [ERROR] Transaction থেকে GatewayTransaction নাম পরিবর্তন করুন
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_gateways_gatewaytransaction_user'  # [ERROR] unique related_name দিন
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    gateway = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference_id = models.CharField(max_length=100, unique=True)
    gateway_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.ForeignKey(
        PaymentGatewayMethod,  # [ERROR] PaymentGatewayMethod এর সাথে সম্পর্ক
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Gateway Transaction'  # [ERROR] নাম পরিবর্তন করুন
        verbose_name_plural = 'Gateway Transactions'  # [ERROR] নাম পরিবর্তন করুন
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference_id']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"


class PayoutRequest(TimeStampedModel):
    """Withdrawal/Payout Request Model"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYOUT_METHODS = (
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('bank', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_gateways_payoutrequest_user'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHODS)
    account_number = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference_id = models.CharField(max_length=100, unique=True)
    admin_notes = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='payment_gateways_payoutrequest_processed_by'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Payout Request'
        verbose_name_plural = 'Payout Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)


class GatewayConfig(TimeStampedModel):
    """Gateway Specific Configuration"""
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE, related_name='configs')
    key = models.CharField(max_length=100)
    value = models.TextField()
    is_secret = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Gateway Configuration'
        verbose_name_plural = 'Gateway Configurations'
        unique_together = ['gateway', 'key']
    
    def __str__(self):
        return f"{self.gateway.name} - {self.key}"


class Currency(TimeStampedModel):
    """Currency Model"""
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Currency'
        verbose_name_plural = 'Currencies'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default currency
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class PaymentGatewayWebhookLog(TimeStampedModel):  # [ERROR] PaymentWebhookLog থেকে PaymentGatewayWebhookLog নাম পরিবর্তন করুন
    gateway = models.CharField(max_length=20)
    payload = models.JSONField()
    headers = models.TextField(default='{}')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    response = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Payment Gateway Webhook Log'  # [ERROR] নাম পরিবর্তন করুন
        verbose_name_plural = 'Payment Gateway Webhook Logs'  # [ERROR] নাম পরিবর্তন করুন
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.gateway} - {self.created_at}"