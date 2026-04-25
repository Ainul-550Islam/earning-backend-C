# kyc/aml/models.py  ── WORLD #1 — AML/PEP/Sanctions Screening
"""
AML = Anti-Money Laundering
PEP = Politically Exposed Person
Sanctions = UN/OFAC/EU blacklists

Jumio/Sumsub এর মতো World-level KYC এ এটা CORE feature.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class PEPSanctionsScreening(models.Model):
    """
    PEP + Sanctions screening result per KYC.
    Checks against: UN Sanctions, OFAC (US), EU, UK HMT lists + PEP databases.
    """
    SCREEN_STATUS = [
        ('pending',    'Pending'),
        ('clear',      'Clear — No Match'),
        ('hit',        'Hit — Manual Review Required'),
        ('false_positive', 'False Positive — Cleared'),
        ('confirmed_hit',  'Confirmed Hit — Blocked'),
    ]
    PROVIDER_CHOICES = [
        ('complyadvantage', 'ComplyAdvantage'),
        ('refinitiv',       'Refinitiv World-Check'),
        ('dow_jones',       'Dow Jones Risk & Compliance'),
        ('acuris',          'Acuris Risk Intelligence'),
        ('manual',          'Manual Screening'),
        ('mock',            'Mock (Dev)'),
    ]

    kyc             = models.ForeignKey('kyc.KYC', on_delete=models.CASCADE, related_name='aml_screenings', null=True, blank=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aml_screenings', null=True, blank=True)
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)

    # Screening details
    provider        = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default='mock', null=True, blank=True)
    status          = models.CharField(max_length=20, choices=SCREEN_STATUS, default='pending', db_index=True, null=True, blank=True)
    reference_id    = models.CharField(max_length=100, blank=True, help_text="Provider reference ID", null=True)

    # What was screened
    screened_name   = models.CharField(max_length=200, null=True, blank=True)
    screened_dob    = models.DateField(null=True, blank=True)
    screened_country = models.CharField(max_length=100, null=True, blank=True)
    screened_nid    = models.CharField(max_length=50, null=True, blank=True)

    # Results
    is_pep          = models.BooleanField(default=False, db_index=True)
    is_sanctioned   = models.BooleanField(default=False, db_index=True)
    is_adverse_media = models.BooleanField(default=False, db_index=True)
    match_count     = models.IntegerField(default=0)
    match_score     = models.FloatField(default=0.0, help_text="0-100 match confidence")

    # Detailed matches (JSON list)
    matches         = models.JSONField(default=list, blank=True)

    # Reviewed by compliance officer
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='aml_reviews')
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    review_note     = models.TextField(blank=True)

    # Raw provider response
    raw_response    = models.JSONField(default=dict, blank=True)
    error           = models.TextField(blank=True)

    # Timestamps
    screened_at     = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at      = models.DateTimeField(auto_now=True)
    next_review_at  = models.DateTimeField(null=True, blank=True, help_text="Periodic re-screening date")

    class Meta:
        db_table = 'kyc_aml_screenings'
        verbose_name = 'AML/PEP Screening'
        ordering = ['-screened_at']
        indexes = [
            models.Index(fields=['kyc', 'status'], name='idx_kyc_status_1030'),
            models.Index(fields=['is_pep', 'is_sanctioned'], name='idx_is_pep_is_sanctioned_1031'),
        ]

    def __str__(self):
        flags = []
        if self.is_pep:       flags.append('PEP')
        if self.is_sanctioned: flags.append('SANCTIONED')
        flag_str = '+'.join(flags) if flags else 'CLEAR'
        return f"AML[{flag_str}] {self.screened_name} via {self.provider}"

    @property
    def is_high_risk(self):
        return self.is_pep or self.is_sanctioned or self.is_adverse_media

    @property
    def requires_edd(self):
        """Enhanced Due Diligence required?"""
        return self.is_pep or self.match_score > 70

    def mark_false_positive(self, reviewer, note=''):
        self.status      = 'false_positive'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save()

    def mark_confirmed_hit(self, reviewer, note=''):
        self.status      = 'confirmed_hit'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save()


class SanctionsList(models.Model):
    """
    Cached sanctions list entries for fast local lookups.
    Updated daily via management command / Celery task.
    """
    LIST_SOURCES = [
        ('un',   'United Nations'),
        ('ofac', 'OFAC (US Treasury)'),
        ('eu',   'European Union'),
        ('uk',   'UK HMT'),
        ('bd',   'Bangladesh BB Sanctions'),
    ]
    source          = models.CharField(max_length=10, choices=LIST_SOURCES, db_index=True, null=True, blank=True)
    list_name       = models.CharField(max_length=200, null=True, blank=True)
    entry_name      = models.CharField(max_length=500, db_index=True, null=True, blank=True)
    aliases         = models.JSONField(default=list, blank=True)
    dob             = models.CharField(max_length=50, null=True, blank=True)
    nationality     = models.CharField(max_length=100, null=True, blank=True)
    entity_type     = models.CharField(max_length=50, blank=True, help_text="individual/entity/vessel", null=True)
    is_active       = models.BooleanField(default=True, db_index=True)
    listed_date     = models.DateField(null=True, blank=True)
    delisted_date   = models.DateField(null=True, blank=True)
    external_id     = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    additional_info = models.JSONField(default=dict, blank=True)
    last_updated    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_sanctions_list'
        verbose_name = 'Sanctions List Entry'
        indexes = [
            models.Index(fields=['source', 'is_active'], name='idx_source_is_active_1032'),
            models.Index(fields=['entry_name', 'is_active'], name='idx_entry_name_is_active_1033'),
        ]

    def __str__(self):
        return f"[{self.source.upper()}] {self.entry_name}"


class PEPDatabase(models.Model):
    """
    PEP (Politically Exposed Persons) database cache.
    Includes politicians, judges, military officers, and their close associates.
    """
    CATEGORY_CHOICES = [
        ('head_of_state',   'Head of State / Government'),
        ('minister',        'Cabinet Minister'),
        ('parliament',      'Parliament Member'),
        ('judge',           'Senior Judge'),
        ('military',        'Senior Military Officer'),
        ('state_enterprise','State Enterprise Executive'),
        ('party_official',  'Political Party Official'),
        ('close_associate', 'Close Associate of PEP'),
        ('family_member',   'PEP Family Member'),
    ]
    full_name       = models.CharField(max_length=300, db_index=True, null=True, blank=True)
    aliases         = models.JSONField(default=list, blank=True)
    category        = models.CharField(max_length=30, choices=CATEGORY_CHOICES, null=True, blank=True)
    country         = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    position        = models.CharField(max_length=300, null=True, blank=True)
    party           = models.CharField(max_length=200, null=True, blank=True)
    dob             = models.CharField(max_length=20, null=True, blank=True)
    is_current      = models.BooleanField(default=True, db_index=True)
    start_date      = models.DateField(null=True, blank=True)
    end_date        = models.DateField(null=True, blank=True)
    related_to      = models.ManyToManyField('self', blank=True, symmetrical=False)
    source          = models.CharField(max_length=100, null=True, blank=True)
    external_id     = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    last_updated    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_pep_database'
        verbose_name = 'PEP Entry'
        indexes = [models.Index(fields=['full_name', 'country', 'is_current'], name='idx_full_name_country_is_c_b78')]

    def __str__(self):
        return f"PEP[{self.category}] {self.full_name} ({self.country})"


class AMLAlert(models.Model):
    """
    AML alerts triggered by suspicious patterns.
    Links to transaction monitoring or KYC screening.
    """
    ALERT_TYPE = [
        ('sanctions_hit',       'Sanctions List Hit'),
        ('pep_detected',        'PEP Detected'),
        ('adverse_media',       'Adverse Media Found'),
        ('suspicious_pattern',  'Suspicious Transaction Pattern'),
        ('high_risk_country',   'High-Risk Country'),
        ('velocity_breach',     'Velocity Limit Breach'),
        ('structuring',         'Potential Structuring'),
    ]
    ALERT_STATUS = [
        ('open',      'Open'),
        ('reviewing', 'Under Review'),
        ('closed',    'Closed — No Action'),
        ('escalated', 'Escalated — SAR Filed'),
    ]
    kyc             = models.ForeignKey('kyc.KYC', on_delete=models.SET_NULL, null=True, blank=True, related_name='aml_alerts')
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aml_alerts', null=True, blank=True)
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    alert_type      = models.CharField(max_length=30, choices=ALERT_TYPE, db_index=True, null=True, blank=True)
    status          = models.CharField(max_length=15, choices=ALERT_STATUS, default='open', db_index=True, null=True, blank=True)
    severity        = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='medium')
    description     = models.TextField()
    evidence        = models.JSONField(default=dict, blank=True)
    assigned_to     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_aml_alerts')
    resolved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_aml_alerts')
    resolution_note = models.TextField(blank=True)
    sar_filed       = models.BooleanField(default=False, help_text="Suspicious Activity Report filed?")
    sar_reference   = models.CharField(max_length=100, null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_aml_alerts'
        verbose_name = 'AML Alert'
        ordering = ['-created_at']

    def __str__(self):
        return f"Alert[{self.alert_type}:{self.severity}] {self.user} - {self.status}"
