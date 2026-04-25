# api/payment_gateways/models/reconciliation.py
# Reconciliation, statement import, and analytics models

from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel
from .core import PaymentGateway, GATEWAY_CHOICES


class ReconciliationBatch(TimeStampedModel):
    """
    A reconciliation run — matches our transaction records against gateway statement.
    Run nightly via Celery.
    """

    STATUS = (
        ('pending',    'Pending'),
        ('running',    'Running'),
        ('completed',  'Completed'),
        ('failed',     'Failed'),
        ('partial',    'Partially completed'),
    )

    date            = models.DateField(help_text='Date being reconciled')
    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='reconciliation_batches')
    status          = models.CharField(max_length=10, choices=STATUS, default='pending')
    started_at      = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    run_by          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='reconciliation_runs')

    # Summary counts
    total_our_records   = models.IntegerField(default=0)
    total_gateway_records= models.IntegerField(default=0)
    total_matched       = models.IntegerField(default=0)
    total_mismatched    = models.IntegerField(default=0)
    total_missing_ours  = models.IntegerField(default=0,
                           help_text='In gateway but not in our DB')
    total_missing_gateway= models.IntegerField(default=0,
                           help_text='In our DB but not in gateway statement')

    # Financial summary
    our_total_amount    = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    gateway_total_amount= models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    discrepancy_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    notes           = models.TextField(blank=True)
    error_log       = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Reconciliation Batch'
        unique_together     = ['date', 'gateway']
        ordering            = ['-date']

    def __str__(self):
        return f'Reconcile {self.gateway.name} | {self.date} [{self.status}]'

    @property
    def match_rate(self) -> float:
        total = self.total_our_records
        return round(self.total_matched / total * 100, 2) if total else 0.0

    @property
    def has_discrepancy(self) -> bool:
        return self.total_mismatched > 0 or abs(self.discrepancy_amount) > Decimal('0.01')


class ReconciliationMismatch(TimeStampedModel):
    """
    Individual mismatch found during reconciliation.
    Each mismatch must be investigated and resolved.
    """

    MISMATCH_TYPES = (
        ('amount_diff',     'Amount difference'),
        ('status_diff',     'Status difference'),
        ('missing_ours',    'In gateway but not our DB'),
        ('missing_gateway', 'In our DB but not gateway'),
        ('duplicate',       'Duplicate transaction'),
        ('timing_diff',     'Timing/date difference'),
    )

    RESOLUTION_STATUS = (
        ('open',     'Open — under investigation'),
        ('resolved', 'Resolved'),
        ('ignored',  'Ignored / Acceptable'),
        ('escalated','Escalated'),
    )

    batch               = models.ForeignKey(ReconciliationBatch, on_delete=models.CASCADE,
                           related_name='mismatches')
    mismatch_type       = models.CharField(max_length=20, choices=MISMATCH_TYPES)

    # Our record
    our_reference_id    = models.CharField(max_length=100, blank=True)
    our_amount          = models.DecimalField(max_digits=12, decimal_places=2,
                           null=True, blank=True)
    our_status          = models.CharField(max_length=20, blank=True)
    our_date            = models.DateField(null=True, blank=True)

    # Gateway record
    gateway_txn_id      = models.CharField(max_length=200, blank=True)
    gateway_amount      = models.DecimalField(max_digits=12, decimal_places=2,
                           null=True, blank=True)
    gateway_status      = models.CharField(max_length=50, blank=True)
    gateway_date        = models.DateField(null=True, blank=True)

    # Discrepancy
    amount_difference   = models.DecimalField(max_digits=12, decimal_places=2,
                           null=True, blank=True)

    # Resolution
    resolution_status   = models.CharField(max_length=15, choices=RESOLUTION_STATUS, default='open')
    resolved            = models.BooleanField(default=False)
    resolved_at         = models.DateTimeField(null=True, blank=True)
    resolved_by         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                           null=True, blank=True)
    resolution_note     = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Reconciliation Mismatch'
        ordering     = ['-created_at']

    def __str__(self):
        return f'Mismatch [{self.mismatch_type}] ref={self.our_reference_id} diff={self.amount_difference}'


class GatewayStatement(TimeStampedModel):
    """
    Imported gateway statement (monthly or daily).
    Used as source of truth for reconciliation.
    """

    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='statements')
    period_start    = models.DateField()
    period_end      = models.DateField()
    statement_file  = models.FileField(upload_to='gateway_statements/', null=True, blank=True)
    raw_data        = models.JSONField(default=list, blank=True,
                       help_text='Parsed statement transactions')
    total_amount    = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_count     = models.IntegerField(default=0)
    currency        = models.CharField(max_length=5, default='BDT')
    imported_at     = models.DateTimeField(auto_now_add=True)
    imported_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True)
    is_reconciled   = models.BooleanField(default=False)
    format          = models.CharField(max_length=10, default='csv',
                       choices=(('csv','CSV'),('xlsx','Excel'),('json','JSON'),('xml','XML')))

    class Meta:
        verbose_name    = 'Gateway Statement'
        unique_together = ['gateway', 'period_start', 'period_end']
        ordering        = ['-period_start']

    def __str__(self):
        return f'{self.gateway.name} statement {self.period_start} to {self.period_end}'


class PaymentAnalytics(models.Model):
    """
    Daily pre-aggregated payment analytics per gateway.
    Updated by background task; used for fast dashboard queries.
    """

    date            = models.DateField()
    gateway         = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                       related_name='analytics')
    transaction_type= models.CharField(max_length=20, default='deposit')
    currency        = models.CharField(max_length=5, default='BDT')

    # Volume
    success_count   = models.IntegerField(default=0)
    failed_count    = models.IntegerField(default=0)
    pending_count   = models.IntegerField(default=0)
    total_count     = models.IntegerField(default=0)

    # Amounts
    total_amount    = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_fees      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    avg_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    max_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    min_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    # Rates
    success_rate    = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))
    failure_rate    = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))
    avg_response_ms = models.IntegerField(default=0)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Payment Analytics'
        unique_together     = ['date', 'gateway', 'transaction_type', 'currency']
        ordering            = ['-date']
        indexes             = [models.Index(fields=['date', 'gateway'])]

    def __str__(self):
        return f'{self.gateway.name} analytics {self.date} — {self.success_count} success'

    def recalculate(self):
        total = self.success_count + self.failed_count + self.pending_count
        self.total_count  = total
        self.success_rate = Decimal(str(self.success_count / max(total, 1)))
        self.failure_rate = Decimal(str(self.failed_count  / max(total, 1)))
        if self.success_count > 0:
            self.avg_amount = self.total_amount / self.success_count
        self.save()
