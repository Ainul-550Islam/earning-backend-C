# api/payment_gateways/models/deposit.py
# All deposit-related models

from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel
from .core import PaymentGateway, PaymentGatewayMethod, GATEWAY_CHOICES


class DepositRequest(TimeStampedModel):
    """
    A user's deposit request — created before gateway redirect.
    Tracks the full deposit lifecycle.
    """

    STATUS_CHOICES = (
        ('initiated',  'Initiated — awaiting gateway redirect'),
        ('pending',    'Pending — user on gateway payment page'),
        ('processing', 'Processing — gateway callback received'),
        ('completed',  'Completed — funds credited'),
        ('failed',     'Failed'),
        ('cancelled',  'Cancelled'),
        ('expired',    'Expired — session timed out'),
        ('refunded',   'Refunded'),
    )

    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='deposit_requests')
    gateway         = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    gateway_obj     = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL,
                       null=True, blank=True)
    payment_method  = models.ForeignKey(PaymentGatewayMethod, on_delete=models.SET_NULL,
                       null=True, blank=True)

    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    fee             = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    net_amount      = models.DecimalField(max_digits=12, decimal_places=2)
    currency        = models.CharField(max_length=5, default='BDT')
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='initiated')

    # References
    reference_id    = models.CharField(max_length=100, unique=True,
                       help_text='Our internal reference')
    gateway_ref     = models.CharField(max_length=200, blank=True,
                       help_text='Gateway transaction ID (from callback)')
    payment_url     = models.URLField(max_length=2000, blank=True,
                       help_text='URL to redirect user to for payment')
    session_key     = models.CharField(max_length=200, blank=True,
                       help_text='Gateway session (bKash paymentID, SSL session key, etc.)')

    # Tracking
    initiated_at    = models.DateTimeField(auto_now_add=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    device_type     = models.CharField(max_length=20, blank=True)

    # Response data
    gateway_response = models.JSONField(default=dict, blank=True,
                        help_text='Full gateway API response')
    callback_data    = models.JSONField(default=dict, blank=True,
                        help_text='Parsed callback payload')

    metadata         = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Deposit Request'
        verbose_name_plural = 'Deposit Requests'
        ordering            = ['-initiated_at']
        indexes = [
            models.Index(fields=['reference_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway', 'status']),
            models.Index(fields=['gateway_ref']),
        ]

    def __str__(self):
        return f'Deposit {self.reference_id} | {self.gateway} | {self.amount} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def is_successful(self):
        return self.status == 'completed'


class DepositCallback(TimeStampedModel):
    """
    Raw callback / webhook data from gateway after payment attempt.
    Stored even if invalid — critical for debugging and auditing.
    """

    deposit         = models.ForeignKey(DepositRequest, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='callbacks')
    gateway         = models.CharField(max_length=20)
    raw_payload     = models.JSONField(help_text='Exact payload received from gateway')
    raw_body        = models.TextField(blank=True, help_text='Raw request body string')
    headers         = models.JSONField(default=dict, blank=True)
    signature       = models.CharField(max_length=500, blank=True,
                       help_text='Signature from gateway header')
    is_valid        = models.BooleanField(default=False,
                       help_text='Signature verification result')
    processed       = models.BooleanField(default=False)
    processed_at    = models.DateTimeField(null=True, blank=True)
    event_type      = models.CharField(max_length=100, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    processing_error= models.TextField(blank=True)
    response_sent   = models.CharField(max_length=10, blank=True,
                       help_text='HTTP status we responded with')

    class Meta:
        verbose_name  = 'Deposit Callback'
        ordering      = ['-created_at']
        indexes = [
            models.Index(fields=['gateway', 'is_valid']),
            models.Index(fields=['deposit', 'processed']),
        ]

    def __str__(self):
        return f'{self.gateway} callback [{self.created_at}] valid={self.is_valid}'


class DepositVerification(TimeStampedModel):
    """
    Manual or automated verification of a deposit.
    Used when auto-verification fails or for compliance.
    """

    METHODS = (
        ('auto_webhook',  'Auto — gateway webhook'),
        ('auto_api_poll', 'Auto — API polling'),
        ('manual_admin',  'Manual — admin review'),
        ('manual_bank',   'Manual — bank statement match'),
        ('manual_sms',    'Manual — SMS confirmation'),
    )

    deposit             = models.OneToOneField(DepositRequest, on_delete=models.CASCADE,
                           related_name='verification')
    verified_by         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='verified_deposits')
    verification_method = models.CharField(max_length=20, choices=METHODS, default='auto_webhook')
    verified_at         = models.DateTimeField(null=True, blank=True)
    is_verified         = models.BooleanField(default=False)
    gateway_txn_id      = models.CharField(max_length=200, blank=True,
                           help_text='Transaction ID confirmed by gateway')
    verified_amount     = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes               = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Deposit Verification'

    def __str__(self):
        return f'Verification for {self.deposit.reference_id} — {self.is_verified}'


class DepositRefund(TimeStampedModel):
    """Refund for a completed deposit."""

    STATUS = (
        ('requested',  'Requested'),
        ('approved',   'Approved'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('rejected',   'Rejected'),
        ('failed',     'Failed'),
    )

    REASONS = (
        ('duplicate',          'Duplicate payment'),
        ('customer_request',   'Customer request'),
        ('failed_delivery',    'Service not delivered'),
        ('fraud',              'Fraud / Unauthorized'),
        ('amount_mismatch',    'Amount mismatch'),
        ('other',              'Other'),
    )

    deposit         = models.ForeignKey(DepositRequest, on_delete=models.CASCADE,
                       related_name='refunds')
    requested_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='deposit_refund_requests')
    approved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='approved_deposit_refunds')
    refund_amount   = models.DecimalField(max_digits=12, decimal_places=2)
    reason          = models.CharField(max_length=30, choices=REASONS, default='customer_request')
    reason_detail   = models.TextField(blank=True)
    status          = models.CharField(max_length=15, choices=STATUS, default='requested')
    gateway_refund_id = models.CharField(max_length=200, blank=True)
    refunded_at     = models.DateTimeField(null=True, blank=True)
    rejection_reason= models.TextField(blank=True)
    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Deposit Refund'
        ordering     = ['-created_at']

    def __str__(self):
        return f'Refund {self.refund_amount} for {self.deposit.reference_id} [{self.status}]'
