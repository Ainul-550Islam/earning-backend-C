# kyc/compliance/models.py  ── WORLD #1
"""
Compliance module:
- GDPR: Data deletion requests, consent logs, data export
- CDD: Customer Due Diligence tiers
- EDD: Enhanced Due Diligence for high-risk
- SAR: Suspicious Activity Report tracking
- Periodic Review scheduling
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class GDPRDataRequest(models.Model):
    """
    GDPR Article 17 (Right to Erasure) + Article 15 (Right of Access) requests.
    World-level legal requirement — EU GDPR, UK GDPR, Bangladesh PDPA 2023.
    """
    REQUEST_TYPES = [
        ('erasure',  'Right to Erasure (Article 17)'),
        ('access',   'Right of Access (Article 15)'),
        ('portability', 'Data Portability (Article 20)'),
        ('rectification', 'Rectification (Article 16)'),
        ('restriction', 'Restriction of Processing (Article 18)'),
    ]
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('processing','Processing'),
        ('completed', 'Completed'),
        ('rejected',  'Rejected — Legal Obligation'),
        ('partial',   'Partially Completed'),
    ]
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gdpr_requests', null=True, blank=True)
    request_type    = models.CharField(max_length=20, choices=REQUEST_TYPES, db_index=True, null=True, blank=True)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True, null=True, blank=True)
    reason          = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True, help_text="e.g. Legal obligation to retain data")
    data_export_file = models.FileField(upload_to='compliance/gdpr_exports/', null=True, blank=True)
    handled_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_gdpr_requests')
    deadline        = models.DateTimeField(help_text="GDPR requires response within 30 days")
    completed_at    = models.DateTimeField(null=True, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_gdpr_requests'
        verbose_name = 'GDPR Data Request'
        ordering = ['-created_at']

    def __str__(self):
        return f"GDPR[{self.request_type}] {self.user} - {self.status}"

    @property
    def is_overdue(self):
        return timezone.now() > self.deadline and self.status == 'pending'

    @classmethod
    def create_erasure_request(cls, user, reason='', ip=None):
        import datetime
        return cls.objects.create(
            user=user, request_type='erasure', reason=reason,
            deadline=timezone.now() + datetime.timedelta(days=30),
            ip_address=ip,
        )


class ConsentLog(models.Model):
    """
    GDPR consent records — what data processing was consented to.
    """
    CONSENT_TYPES = [
        ('kyc_processing',   'KYC Data Processing'),
        ('biometric_data',   'Biometric Data Processing'),
        ('third_party_share','Third-Party Data Sharing'),
        ('marketing',        'Marketing Communications'),
        ('analytics',        'Analytics & Profiling'),
    ]
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consent_logs', null=True, blank=True)
    consent_type    = models.CharField(max_length=25, choices=CONSENT_TYPES, db_index=True, null=True, blank=True)
    is_given        = models.BooleanField(default=True)
    version         = models.CharField(max_length=20, default='1.0', null=True, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    text_shown      = models.TextField(blank=True, help_text="Exact consent text shown to user")
    withdrawn_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_consent_logs'
        verbose_name = 'Consent Log'
        ordering = ['-created_at']

    def __str__(self):
        status = 'given' if self.is_given else 'withdrawn'
        return f"Consent[{self.consent_type}:{status}] {self.user}"


class CustomerDueDiligence(models.Model):
    """
    CDD (Customer Due Diligence) tiers per FATF Recommendations.
    SDD = Simplified, CDD = Standard, EDD = Enhanced.
    """
    CDD_TIER = [
        ('sdd', 'Simplified Due Diligence (Low Risk)'),
        ('cdd', 'Standard Due Diligence (Normal)'),
        ('edd', 'Enhanced Due Diligence (High Risk)'),
    ]
    REVIEW_FREQUENCY = [
        ('annual',     'Annual'),
        ('biannual',   'Every 6 Months'),
        ('quarterly',  'Quarterly'),
        ('monthly',    'Monthly'),
        ('triggered',  'Event-Triggered'),
    ]
    kyc             = models.OneToOneField('kyc.KYC', on_delete=models.CASCADE, related_name='due_diligence', null=True, blank=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cdd_records', null=True, blank=True)
    tier            = models.CharField(max_length=5, choices=CDD_TIER, default='cdd', db_index=True, null=True, blank=True)
    risk_category   = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High')], default='medium')
    review_frequency = models.CharField(max_length=15, choices=REVIEW_FREQUENCY, default='annual', null=True, blank=True)
    last_review_at  = models.DateTimeField(null=True, blank=True)
    next_review_at  = models.DateTimeField(null=True, blank=True, db_index=True)
    is_edd_required = models.BooleanField(default=False, db_index=True)
    edd_reason      = models.TextField(blank=True)
    edd_completed   = models.BooleanField(default=False)
    edd_completed_at = models.DateTimeField(null=True, blank=True)
    source_of_funds = models.TextField(blank=True)
    source_of_wealth = models.TextField(blank=True)
    business_purpose = models.TextField(blank=True)
    beneficial_owner = models.TextField(blank=True)
    assigned_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cdd')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_due_diligence'
        verbose_name = 'Customer Due Diligence'

    def __str__(self):
        return f"CDD[{self.tier.upper()}] {self.user} next_review={self.next_review_at}"

    def is_overdue_for_review(self) -> bool:
        if not self.next_review_at: return False
        return timezone.now() > self.next_review_at

    def schedule_next_review(self):
        import datetime
        freq_days = {
            'annual': 365, 'biannual': 182, 'quarterly': 90,
            'monthly': 30, 'triggered': 365,
        }
        days = freq_days.get(self.review_frequency, 365)
        self.last_review_at = timezone.now()
        self.next_review_at = timezone.now() + datetime.timedelta(days=days)
        self.save(update_fields=['last_review_at', 'next_review_at', 'updated_at'])


class SARReport(models.Model):
    """
    SAR = Suspicious Activity Report.
    Filed with Bangladesh Financial Intelligence Unit (BFIU) or relevant authority.
    """
    SAR_STATUS = [
        ('draft',     'Draft'),
        ('submitted', 'Submitted to Authority'),
        ('acknowledged', 'Acknowledged by Authority'),
        ('closed',    'Closed'),
    ]
    REPORT_TO = [
        ('bfiu',     'BFIU Bangladesh'),
        ('fincen',   'FinCEN USA'),
        ('fca',      'FCA UK'),
        ('other',    'Other Authority'),
    ]
    reference_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    filed_by        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='filed_sars')
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    kyc             = models.ForeignKey('kyc.KYC', on_delete=models.SET_NULL, null=True, blank=True, related_name='sar_reports')
    user_reported   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_in_sars')
    report_to       = models.CharField(max_length=10, choices=REPORT_TO, default='bfiu', null=True, blank=True)
    status          = models.CharField(max_length=15, choices=SAR_STATUS, default='draft', db_index=True, null=True, blank=True)
    suspicious_activity_description = models.TextField()
    amount_involved = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency        = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    supporting_documents = models.JSONField(default=list, blank=True)
    authority_reference = models.CharField(max_length=100, null=True, blank=True)
    submitted_at    = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_sar_reports'
        verbose_name = 'SAR Report'
        ordering = ['-created_at']

    def __str__(self):
        return f"SAR[{self.reference_number}] {self.status} → {self.report_to}"
