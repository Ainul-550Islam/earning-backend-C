# kyc/transaction_monitoring/models.py  ── WORLD #1
"""
Transaction Monitoring — AML requirement.
Monitors financial activity for suspicious patterns:
- Velocity (too many transactions in short time)
- Structuring (splitting large amounts to avoid reporting)
- High-risk country transfers
- Unusual pattern changes
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class TransactionMonitoringRule(models.Model):
    """Configurable AML monitoring rules."""
    RULE_TYPE = [
        ('velocity',       'Velocity — Too many transactions'),
        ('amount_limit',   'Amount Limit Breach'),
        ('structuring',    'Structuring Detection'),
        ('country_risk',   'High-Risk Country'),
        ('pattern_change', 'Unusual Pattern Change'),
        ('dormant_account','Dormant Account Activity'),
        ('round_amounts',  'Suspicious Round Amounts'),
        ('third_party',    'Unusual Third-Party Transfers'),
    ]
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name            = models.CharField(max_length=100, null=True, blank=True)
    rule_type       = models.CharField(max_length=20, choices=RULE_TYPE, db_index=True, null=True, blank=True)
    is_active       = models.BooleanField(default=True, db_index=True)
    threshold_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    threshold_count = models.IntegerField(null=True, blank=True, help_text="Max transactions in window")
    time_window_hours = models.IntegerField(default=24)
    currency        = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    action          = models.CharField(max_length=10, choices=[('alert','Alert'),('block','Block'),('review','Review')], default='alert')
    severity        = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High')], default='medium')
    description     = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_tm_rules'
        verbose_name = 'Transaction Monitoring Rule'

    def __str__(self): return f"Rule[{self.rule_type}] {self.name} - {'ON' if self.is_active else 'OFF'}"


class TransactionMonitoringAlert(models.Model):
    """Alerts triggered by transaction monitoring rules."""
    ALERT_STATUS = [
        ('open','Open'), ('reviewing','Under Review'), ('closed','Closed'), ('escalated','Escalated — SAR'),
    ]
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tm_alerts', null=True, blank=True)
    kyc             = models.ForeignKey('kyc.KYC', on_delete=models.SET_NULL, null=True, blank=True)
    rule            = models.ForeignKey(TransactionMonitoringRule, on_delete=models.SET_NULL, null=True)
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    status          = models.CharField(max_length=15, choices=ALERT_STATUS, default='open', db_index=True, null=True, blank=True)
    alert_details   = models.JSONField(default=dict)
    total_amount    = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    transaction_count = models.IntegerField(default=0)
    time_period     = models.CharField(max_length=50, null=True, blank=True)
    assigned_to     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tm_alerts')
    resolution_note = models.TextField(blank=True)
    sar_filed       = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_tm_alerts'
        verbose_name = 'Transaction Monitoring Alert'
        ordering = ['-created_at']

    def __str__(self): return f"TM_Alert[{self.rule}] {self.user} - {self.status}"


class WatchlistScreeningJob(models.Model):
    """Periodic re-screening jobs against updated watchlists."""
    STATUS = [('pending','Pending'),('running','Running'),('done','Done'),('failed','Failed')]
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    status          = models.CharField(max_length=10, choices=STATUS, default='pending', db_index=True, null=True, blank=True)
    total_screened  = models.IntegerField(default=0)
    hits_found      = models.IntegerField(default=0)
    error           = models.TextField(blank=True)
    started_at      = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_watchlist_jobs'
        verbose_name = 'Watchlist Screening Job'
        ordering = ['-created_at']

    def __str__(self): return f"WatchlistJob[{self.status}] screened={self.total_screened} hits={self.hits_found}"
