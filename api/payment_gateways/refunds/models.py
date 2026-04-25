# api/payment_gateways/refunds/models.py
# FILE 59 of 257 — Refund Models

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.models import TimeStampedModel


# ── Shared choices ─────────────────────────────────────────────────────────────
ALL_GATEWAY_CHOICES = (
    ('bkash',      'bKash'),
    ('nagad',      'Nagad'),
    ('sslcommerz', 'SSLCommerz'),
    ('amarpay',    'AmarPay'),
    ('upay',       'Upay'),
    ('shurjopay',  'ShurjoPay'),
    ('stripe',     'Stripe'),
    ('paypal',     'PayPal'),
)

REFUND_STATUS_CHOICES = (
    ('pending',    'Pending'),
    ('processing', 'Processing'),
    ('completed',  'Completed'),
    ('failed',     'Failed'),
    ('cancelled',  'Cancelled'),
)

REFUND_REASON_CHOICES = (
    ('duplicate',              'Duplicate payment'),
    ('fraudulent',             'Fraudulent transaction'),
    ('customer_request',       'Customer requested refund'),
    ('order_cancelled',        'Order cancelled'),
    ('service_not_provided',   'Service not provided'),
    ('partial_refund',         'Partial refund'),
    ('other',                  'Other'),
)


class RefundRequest(TimeStampedModel):
    """
    Represents a single refund request for a completed payment transaction.
    Supports both full and partial refunds. Multiple partial refunds can
    exist for the same original_transaction as long as total does not
    exceed original net_amount.
    """

    gateway              = models.CharField(max_length=20, choices=ALL_GATEWAY_CHOICES)
    original_transaction = models.ForeignKey(
        'payment_gateways.GatewayTransaction',
        on_delete=models.PROTECT,
        related_name='refund_requests',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='refund_requests',
    )

    # ── Financials ──────────────────────────────────────────────────────────
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text='Amount to refund in the transaction currency.',
    )

    # ── Tracking ────────────────────────────────────────────────────────────
    status             = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')
    reason             = models.CharField(max_length=50, choices=REFUND_REASON_CHOICES, default='customer_request')
    reference_id       = models.CharField(max_length=100, unique=True, help_text='Our internal refund reference.')
    gateway_refund_id  = models.CharField(max_length=200, blank=True, null=True, help_text='Gateway-side refund ID.')

    # ── Who initiated ───────────────────────────────────────────────────────
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='initiated_refunds',
        help_text='Admin or system user who initiated the refund.',
    )

    # ── Timestamps ──────────────────────────────────────────────────────────
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at    = models.DateTimeField(null=True, blank=True)

    # ── Metadata ────────────────────────────────────────────────────────────
    metadata = models.JSONField(default=dict, blank=True)
    notes    = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = 'Refund Request'
        verbose_name_plural = 'Refund Requests'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['gateway']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference_id']),
            models.Index(fields=['original_transaction']),
        ]

    def __str__(self):
        return f'Refund {self.reference_id} — {self.gateway} — {self.amount} [{self.status}]'

    @property
    def is_partial(self) -> bool:
        """True if this refund is less than the original transaction amount."""
        return self.amount < self.original_transaction.net_amount

    @property
    def is_final(self) -> bool:
        """True if refund is in a terminal state."""
        return self.status in ('completed', 'failed', 'cancelled')


class RefundPolicy(TimeStampedModel):
    """
    Per-gateway refund policy configuration.
    Admins can configure how refunds are handled for each gateway.
    """

    gateway              = models.CharField(max_length=20, choices=ALL_GATEWAY_CHOICES, unique=True)
    auto_approve         = models.BooleanField(default=False, help_text='Auto-process refunds without admin approval.')
    max_refund_days      = models.IntegerField(default=30, help_text='Max days after payment to allow refund.')
    max_refund_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50000.00'))
    allow_partial_refund = models.BooleanField(default=True)
    fee_refundable       = models.BooleanField(default=False, help_text='Whether gateway fee is included in refund.')
    is_active            = models.BooleanField(default=True)
    notes                = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = 'Refund Policy'
        verbose_name_plural = 'Refund Policies'

    def __str__(self):
        return f'{self.get_gateway_display()} — Refund Policy (auto={self.auto_approve})'


class RefundAuditLog(TimeStampedModel):
    """
    Immutable audit trail for every refund state change.
    Never deleted — append-only.
    """

    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    previous_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, blank=True)
    new_status      = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='refund_audit_actions',
    )
    note     = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Refund Audit Log'
        verbose_name_plural = 'Refund Audit Logs'
        ordering            = ['created_at']

    def __str__(self):
        return (
            f'Refund {self.refund_request.reference_id}: '
            f'{self.previous_status} → {self.new_status}'
        )
