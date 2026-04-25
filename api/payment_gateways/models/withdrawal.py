# api/payment_gateways/models/withdrawal.py
# All withdrawal/payout related models

from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel
from .core import GATEWAY_CHOICES


class WithdrawalGatewayRequest(TimeStampedModel):
    """
    Gateway-level payout API call record.
    Created when admin/system initiates actual payout to user's bank/wallet.
    """

    STATUS = (
        ('queued',     'Queued — waiting to be sent'),
        ('sent',       'Sent to gateway'),
        ('accepted',   'Accepted by gateway'),
        ('processing', 'Gateway processing'),
        ('completed',  'Completed'),
        ('failed',     'Failed'),
        ('reversed',   'Reversed'),
    )

    payout_request  = models.ForeignKey('payment_gateways.PayoutRequest', on_delete=models.CASCADE,
                       related_name='gateway_requests',
                       # Use string ref to avoid circular import
                       )
    gateway         = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    status          = models.CharField(max_length=15, choices=STATUS, default='queued')

    # What we sent to gateway
    request_payload = models.JSONField(default=dict, help_text='Payload sent to gateway API')
    request_url     = models.URLField(max_length=500, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)

    # What gateway responded
    response_code   = models.IntegerField(null=True, blank=True)
    response_payload= models.JSONField(default=dict, blank=True)
    gateway_ref     = models.CharField(max_length=200, blank=True,
                       help_text='Gateway transaction/transfer ID')
    gateway_fee     = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))

    # Timing
    sent_at         = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    retry_count     = models.IntegerField(default=0)
    last_retry_at   = models.DateTimeField(null=True, blank=True)

    error_code      = models.CharField(max_length=50, blank=True)
    error_message   = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Withdrawal Gateway Request'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['gateway', 'status'])]

    def __str__(self):
        return f'{self.gateway} payout [{self.status}] ref={self.gateway_ref}'


class WithdrawalGatewayCallback(TimeStampedModel):
    """
    Confirmation/receipt callback from gateway after payout.
    Some gateways send async callbacks; others need polling.
    """

    gateway_request = models.ForeignKey(WithdrawalGatewayRequest, on_delete=models.CASCADE,
                       related_name='callbacks')
    gateway         = models.CharField(max_length=20)
    raw_payload     = models.JSONField()
    is_success      = models.BooleanField(default=False)
    gateway_status  = models.CharField(max_length=50, blank=True)
    confirmed_amount= models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    received_at     = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Withdrawal Gateway Callback'

    def __str__(self):
        return f'{self.gateway} callback — success={self.is_success}'


class WithdrawalReceipt(TimeStampedModel):
    """
    User-facing receipt for a completed withdrawal.
    Can be generated as PDF for download.
    """

    payout_request  = models.OneToOneField('payment_gateways.PayoutRequest', on_delete=models.CASCADE,
                       related_name='receipt')
    receipt_number  = models.CharField(max_length=50, unique=True)
    issued_at       = models.DateTimeField(auto_now_add=True)

    # Summary
    user_name       = models.CharField(max_length=200)
    user_email      = models.EmailField()
    gateway_display = models.CharField(max_length=100)
    account_display = models.CharField(max_length=200, help_text='Masked account number')
    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    fee             = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount      = models.DecimalField(max_digits=12, decimal_places=2)
    currency        = models.CharField(max_length=5)
    reference       = models.CharField(max_length=100)
    gateway_ref     = models.CharField(max_length=200, blank=True)

    # PDF
    pdf_file        = models.FileField(upload_to='receipts/withdrawals/', null=True, blank=True)

    class Meta:
        verbose_name = 'Withdrawal Receipt'
        ordering     = ['-issued_at']

    def __str__(self):
        return f'Receipt {self.receipt_number}'

    def mask_account(self) -> str:
        acc = self.account_display
        if len(acc) > 4:
            return '*' * (len(acc) - 4) + acc[-4:]
        return acc


class WithdrawalFailure(TimeStampedModel):
    """Failure log for a withdrawal attempt."""

    FAILURE_TYPES = (
        ('gateway_error',     'Gateway API error'),
        ('insufficient_balance', 'Insufficient balance'),
        ('invalid_account',   'Invalid account number'),
        ('account_blocked',   'Account blocked by gateway'),
        ('limit_exceeded',    'Gateway limit exceeded'),
        ('network_timeout',   'Network timeout'),
        ('auth_failed',       'Authentication failed'),
        ('other',             'Other'),
    )

    payout_request  = models.ForeignKey('payment_gateways.PayoutRequest', on_delete=models.CASCADE,
                       related_name='failures')
    gateway         = models.CharField(max_length=20)
    failure_type    = models.CharField(max_length=30, choices=FAILURE_TYPES)
    error_code      = models.CharField(max_length=50, blank=True)
    error_message   = models.TextField()
    raw_response    = models.JSONField(default=dict, blank=True)
    retry_count     = models.IntegerField(default=0)
    is_final        = models.BooleanField(default=False,
                       help_text='True = no more retries; payout permanently failed')
    resolved        = models.BooleanField(default=False)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='resolved_failures')
    resolution_note = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Withdrawal Failure'
        ordering     = ['-created_at']

    def __str__(self):
        return f'{self.gateway} failure: {self.failure_type} (retry={self.retry_count})'
