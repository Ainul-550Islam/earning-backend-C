# api/publisher_tools/publisher_management/publisher_payout.py
"""Publisher Payout — Payout request, processing, history।"""
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel


class PayoutRequest(TimeStampedModel):
    """Publisher-এর payout request।"""

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_payoutreq_tenant', db_index=True)

    STATUS_CHOICES = [
        ('pending',    _('Pending Review')),
        ('approved',   _('Approved')),
        ('processing', _('Processing Payment')),
        ('completed',  _('Payment Completed')),
        ('rejected',   _('Rejected')),
        ('cancelled',  _('Cancelled by Publisher')),
        ('failed',     _('Payment Failed')),
    ]

    publisher       = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='payout_requests', db_index=True)
    invoice         = models.ForeignKey('publisher_tools.PublisherInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='payout_requests')
    bank_account    = models.ForeignKey('publisher_management.PublisherBankAccount', on_delete=models.SET_NULL, null=True, related_name='payout_requests')
    request_id      = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    requested_amount= models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal('1.00'))])
    approved_amount = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    processing_fee  = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    withholding_tax = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    net_amount      = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    currency        = models.CharField(max_length=5, default='USD')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    priority        = models.CharField(max_length=10, choices=[('normal','Normal'),('urgent','Urgent')], default='normal')
    publisher_notes = models.TextField(blank=True)
    admin_notes     = models.TextField(blank=True)
    rejection_reason= models.TextField(blank=True)
    approved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_payout_approved')
    approved_at     = models.DateTimeField(null=True, blank=True)
    processed_at    = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    payment_reference  = models.CharField(max_length=200, blank=True)
    payment_gateway_ref= models.CharField(max_length=200, blank=True)
    gateway_response   = models.JSONField(default=dict, blank=True)
    metadata           = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_payout_requests'
        verbose_name = _('Payout Request')
        verbose_name_plural = _('Payout Requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status'], name='idx_publisher_status_1624'),
            models.Index(fields=['request_id'], name='idx_request_id_1625'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_1626'),
        ]

    def __str__(self):
        return f"{self.request_id} | {self.publisher.publisher_id} | ${self.requested_amount} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.request_id:
            import uuid
            self.request_id = f"PAY{uuid.uuid4().hex[:10].upper()}"
        if not self.net_amount:
            self.net_amount = max(Decimal('0'), self.requested_amount - self.processing_fee - self.withholding_tax)
        super().save(*args, **kwargs)

    @transaction.atomic
    def approve(self, approved_by=None, approved_amount: Decimal = None):
        if self.status != 'pending':
            raise ValueError(f"Cannot approve payout in {self.status} status.")
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.approved_amount = approved_amount or self.requested_amount
        self.net_amount = max(Decimal('0'), self.approved_amount - self.processing_fee - self.withholding_tax)
        self.save()

    @transaction.atomic
    def mark_completed(self, payment_reference: str):
        self.status = 'completed'
        self.payment_reference = payment_reference
        self.completed_at = timezone.now()
        self.save()
        # Update publisher paid_out total
        pub = self.publisher
        from django.db.models import F
        pub.total_paid_out = F('total_paid_out') + (self.net_amount or self.approved_amount or self.requested_amount)
        pub.save(update_fields=['total_paid_out', 'updated_at'])

    @transaction.atomic
    def reject(self, reason: str, rejected_by=None):
        self.status = 'rejected'
        self.rejection_reason = reason
        self.approved_by = rejected_by
        self.save()

    @transaction.atomic
    def cancel(self):
        if self.status not in ('pending',):
            raise ValueError("Only pending payouts can be cancelled.")
        self.status = 'cancelled'
        self.save()


class PayoutSchedule(TimeStampedModel):
    """Publisher payout schedule configuration।"""

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_payoutsched_tenant', db_index=True)

    publisher       = models.OneToOneField('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='payout_schedule')
    is_automatic    = models.BooleanField(default=False, verbose_name=_("Automatic Payout Enabled"))
    frequency       = models.CharField(max_length=20, choices=[('monthly','Monthly'),('bimonthly','Bi-Monthly'),('weekly','Weekly'),('on_demand','On Demand')], default='monthly')
    payout_day      = models.IntegerField(default=15, help_text=_("Day of month for monthly payouts (1-28)"))
    min_threshold   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))
    hold_days       = models.IntegerField(default=30, help_text=_("Days to hold earnings before paying"))
    next_payout_date= models.DateField(null=True, blank=True)
    last_payout_date= models.DateField(null=True, blank=True)
    is_paused       = models.BooleanField(default=False)
    pause_reason    = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_payout_schedules'
        verbose_name = _('Payout Schedule')
        verbose_name_plural = _('Payout Schedules')

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.frequency} {'(auto)' if self.is_automatic else '(manual)'}"

    def calculate_next_payout_date(self):
        from datetime import date, timedelta
        from calendar import monthrange
        today = date.today()
        if self.frequency == 'monthly':
            if today.day < self.payout_day:
                year, month = today.year, today.month
            else:
                if today.month == 12:
                    year, month = today.year + 1, 1
                else:
                    year, month = today.year, today.month + 1
            last_day = monthrange(year, month)[1]
            self.next_payout_date = date(year, month, min(self.payout_day, last_day))
        elif self.frequency == 'weekly':
            self.next_payout_date = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        self.save(update_fields=['next_payout_date', 'updated_at'])
        return self.next_payout_date
