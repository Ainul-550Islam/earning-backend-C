# kyc/perpetual_kyc/models.py  ── WORLD #1
"""
Perpetual KYC (pKYC) — 2025 industry standard.
Instead of one-time verification, continuously monitor customer risk.
Triggers re-verification on: risk events, sanctions updates, behavior changes.

Used by: Revolut, Binance, Crypto.com, all Tier-1 fintech.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class KYCMonitoringProfile(models.Model):
    """
    Continuous monitoring profile per user.
    Tracks risk over time, triggers re-verification when needed.
    """
    MONITORING_LEVEL = [
        ('standard',  'Standard — Annual review'),
        ('enhanced',  'Enhanced — Quarterly review'),
        ('intensive', 'Intensive — Monthly review'),
        ('realtime',  'Real-time — Event-triggered only'),
    ]
    user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_monitoring', null=True, blank=True)
    tenant            = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    monitoring_level  = models.CharField(max_length=15, choices=MONITORING_LEVEL, default='standard', db_index=True, null=True, blank=True)
    is_active         = models.BooleanField(default=True, db_index=True)

    # Current risk state
    current_risk_score = models.IntegerField(default=0)
    current_risk_level = models.CharField(max_length=10, default='low', db_index=True, null=True, blank=True)
    risk_trend         = models.CharField(max_length=10, choices=[
        ('stable','Stable'), ('increasing','Increasing'), ('decreasing','Decreasing')
    ], default='stable')

    # Review schedule
    last_review_at     = models.DateTimeField(null=True, blank=True)
    next_review_at     = models.DateTimeField(null=True, blank=True, db_index=True)
    rekyc_required     = models.BooleanField(default=False, db_index=True)
    rekyc_reason       = models.TextField(blank=True)

    # Trigger history
    total_triggers     = models.IntegerField(default=0)
    last_triggered_at  = models.DateTimeField(null=True, blank=True)
    last_trigger_type  = models.CharField(max_length=50, null=True, blank=True)

    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_monitoring_profiles'
        verbose_name = 'KYC Monitoring Profile'

    def __str__(self):
        return f"Monitor[{self.monitoring_level}] {self.user} risk={self.current_risk_score}"

    def trigger_rekyc(self, reason: str, trigger_type: str = 'manual'):
        self.rekyc_required    = True
        self.rekyc_reason      = reason
        self.total_triggers   += 1
        self.last_triggered_at = timezone.now()
        self.last_trigger_type = trigger_type
        self.save()

        # Notify user
        try:
            from kyc.services import KYCNotificationService
            KYCNotificationService.send(
                user=self.user, event_type='rekyc_required',
                extra={'reason': reason}
            )
        except Exception:
            pass


class KYCRiskEvent(models.Model):
    """
    Individual risk events that trigger monitoring updates.
    Examples: PEP status change, sanctions list update, unusual transaction, address change.
    """
    EVENT_TYPES = [
        ('sanctions_update',    'Sanctions List Updated'),
        ('pep_status_change',   'PEP Status Changed'),
        ('unusual_transaction', 'Unusual Transaction Pattern'),
        ('address_change',      'Address Changed'),
        ('high_value_tx',       'High-Value Transaction'),
        ('country_risk_change', 'Country Risk Level Changed'),
        ('document_expired',    'Identity Document Expired'),
        ('kyc_expired',         'KYC Validity Expired'),
        ('adverse_media',       'Adverse Media Detected'),
        ('suspicious_login',    'Suspicious Login Activity'),
        ('manual_trigger',      'Manually Triggered'),
    ]
    SEVERITY = [('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')]

    user              = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_risk_events', null=True, blank=True)
    monitoring_profile = models.ForeignKey(KYCMonitoringProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='risk_events')
    tenant            = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    event_type        = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True, null=True, blank=True)
    severity          = models.CharField(max_length=10, choices=SEVERITY, default='medium', db_index=True, null=True, blank=True)
    description       = models.TextField()
    evidence          = models.JSONField(default=dict, blank=True)
    risk_delta        = models.IntegerField(default=0, help_text="Change in risk score (+/-)")
    triggered_rekyc   = models.BooleanField(default=False)
    is_resolved       = models.BooleanField(default=False, db_index=True)
    resolved_at       = models.DateTimeField(null=True, blank=True)
    resolved_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_risk_events')
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'kyc_risk_events'
        verbose_name = 'KYC Risk Event'
        ordering = ['-created_at']

    def __str__(self):
        return f"RiskEvent[{self.event_type}:{self.severity}] {self.user}"


class PeriodicReviewTask(models.Model):
    """Scheduled periodic review tasks."""
    STATUS = [('scheduled','Scheduled'),('running','Running'),('done','Done'),('failed','Failed'),('skipped','Skipped')]
    monitoring_profile = models.ForeignKey(KYCMonitoringProfile, on_delete=models.CASCADE, related_name='review_tasks', null=True, blank=True)
    scheduled_for      = models.DateTimeField(db_index=True)
    status             = models.CharField(max_length=15, choices=STATUS, default='scheduled', null=True, blank=True)
    review_type        = models.CharField(max_length=30, default='periodic', null=True, blank=True)
    started_at         = models.DateTimeField(null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    result             = models.JSONField(default=dict, blank=True)
    error              = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_periodic_reviews'
        verbose_name = 'Periodic Review Task'
        ordering = ['scheduled_for']

    def __str__(self):
        return f"Review[{self.review_type}] {self.monitoring_profile.user} scheduled={self.scheduled_for.date()}"
