# api/payment_gateways/schedules/models.py
# Payment schedule models: Daily, Weekly, Net-15, Net-30, Early Payment

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from core.models import TimeStampedModel

SCHEDULE_TYPES = (
    ('daily',   'Daily (paid every day)'),
    ('weekly',  'Weekly (paid every Monday)'),
    ('net15',   'Net-15 (paid 15 days after period)'),
    ('net30',   'Net-30 (paid 30 days after period)'),
    ('manual',  'Manual (admin initiates payout)'),
)

SCHEDULE_STATUS = (
    ('active',   'Active'),
    ('paused',   'Paused'),
    ('cancelled','Cancelled'),
)

PAYOUT_STATUS = (
    ('pending',    'Pending'),
    ('processing', 'Processing'),
    ('completed',  'Completed'),
    ('failed',     'Failed'),
    ('skipped',    'Skipped (below minimum)'),
)

PAYMENT_METHODS = (
    ('bkash',     'bKash'),
    ('nagad',     'Nagad'),
    ('paypal',    'PayPal'),
    ('payoneer',  'Payoneer'),
    ('stripe',    'Stripe'),
    ('wire',      'Wire Transfer'),
    ('ach',       'ACH (US Bank)'),
    ('crypto',    'Cryptocurrency'),
)


class PaymentSchedule(TimeStampedModel):
    """
    Publisher/user payment schedule configuration.
    Each user can have one active schedule determining when they get paid.
    """
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_schedule',
    )
    schedule_type   = models.CharField(max_length=10, choices=SCHEDULE_TYPES, default='net30')
    status          = models.CharField(max_length=10, choices=SCHEDULE_STATUS, default='active')
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='paypal')
    payment_account = models.CharField(max_length=200, help_text='Account number / wallet / email for payouts')
    payment_currency= models.CharField(max_length=5, default='USD')
    minimum_payout  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    next_payout_date= models.DateField(null=True, blank=True)
    last_payout_date= models.DateField(null=True, blank=True)
    last_payout_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    notes           = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Payment Schedule'
        verbose_name_plural = 'Payment Schedules'

    def __str__(self):
        return f'{self.user.username} — {self.get_schedule_type_display()}'

    def calculate_next_payout(self):
        """Calculate and set next_payout_date based on schedule_type."""
        from datetime import date, timedelta
        today = date.today()
        if self.schedule_type == 'daily':
            self.next_payout_date = today + timedelta(days=1)
        elif self.schedule_type == 'weekly':
            # Next Monday
            days_ahead = 7 - today.weekday()
            self.next_payout_date = today + timedelta(days=days_ahead)
        elif self.schedule_type == 'net15':
            self.next_payout_date = today + timedelta(days=15)
        elif self.schedule_type == 'net30':
            self.next_payout_date = today + timedelta(days=30)
        self.save(update_fields=['next_payout_date'])
        return self.next_payout_date


class ScheduledPayout(TimeStampedModel):
    """
    Individual scheduled payout execution record.
    One per payment cycle per user.
    """
    schedule        = models.ForeignKey(PaymentSchedule, on_delete=models.CASCADE, related_name='payouts')
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scheduled_payouts')
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    fee             = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    net_amount      = models.DecimalField(max_digits=10, decimal_places=2)
    currency        = models.CharField(max_length=5, default='USD')
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_account = models.CharField(max_length=200)
    status          = models.CharField(max_length=15, choices=PAYOUT_STATUS, default='pending')
    period_start    = models.DateField(help_text='Earnings period start')
    period_end      = models.DateField(help_text='Earnings period end')
    scheduled_date  = models.DateField(help_text='Date payout was scheduled for')
    processed_at    = models.DateTimeField(null=True, blank=True)
    gateway_reference = models.CharField(max_length=200, blank=True)
    error_message   = models.TextField(blank=True)
    metadata        = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name        = 'Scheduled Payout'
        verbose_name_plural = 'Scheduled Payouts'
        ordering            = ['-scheduled_date']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['scheduled_date', 'status']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.amount} {self.currency} ({self.status})'


class EarlyPaymentRequest(TimeStampedModel):
    """
    Early payment request (like CPAlead's "early payment on request").
    User can request immediate payout before their scheduled date.
    Incurs an early payment fee.
    """
    STATUS_CHOICES = (
        ('pending',  'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processed','Processed'),
    )

    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='early_payment_requests')
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    early_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), help_text='Fee for early payment (e.g. 15% of amount)')
    net_amount      = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_account = models.CharField(max_length=200)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    reason          = models.TextField(blank=True)
    approved_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='approved_early_payments'
    )
    processed_at    = models.DateTimeField(null=True, blank=True)
    admin_notes     = models.TextField(blank=True)

    EARLY_FEE_PERCENT = Decimal('15')  # 15% fee for early payment

    class Meta:
        verbose_name        = 'Early Payment Request'
        verbose_name_plural = 'Early Payment Requests'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.user.username} early payment — {self.amount} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.early_fee:
            self.early_fee = (self.amount * self.EARLY_FEE_PERCENT) / 100
        if not self.net_amount:
            self.net_amount = self.amount - self.early_fee
        super().save(*args, **kwargs)
