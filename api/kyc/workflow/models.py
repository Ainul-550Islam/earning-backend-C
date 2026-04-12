# kyc/workflow/models.py  ── WORLD #1
"""
No-Code KYC Workflow Builder.
Like Onfido Studio / Sumsub Flows — drag-drop KYC process configuration.
Tenants define their own KYC flow without writing code.
"""
from django.db import models
from django.conf import settings


class KYCWorkflow(models.Model):
    """
    A configured KYC verification workflow.
    Each tenant can have multiple workflows for different use cases.
    e.g. 'Basic Onboarding', 'High-Value Account', 'Crypto Tier 2'
    """
    STATUS = [('draft','Draft'), ('active','Active'), ('archived','Archived')]

    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_workflows', null=True, blank=True)
    name        = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=10, choices=STATUS, default='draft', db_index=True, null=True, blank=True)
    is_default  = models.BooleanField(default=False, help_text="Default workflow for this tenant")
    version     = models.IntegerField(default=1)

    # Workflow configuration (JSON)
    config      = models.JSONField(default=dict, help_text="Workflow step configuration")

    # Stats
    total_runs     = models.IntegerField(default=0)
    pass_count     = models.IntegerField(default=0)
    fail_count     = models.IntegerField(default=0)
    avg_duration_s = models.FloatField(default=0.0)

    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_workflows'
        verbose_name = 'KYC Workflow'
        unique_together = [('tenant', 'name', 'version')]
        ordering = ['-created_at']

    def __str__(self):
        return f"Workflow[{self.name} v{self.version}] {self.tenant} - {self.status}"

    def activate(self):
        self.status = 'active'
        # Only one active default per tenant
        if self.is_default:
            KYCWorkflow.objects.filter(tenant=self.tenant, is_default=True).exclude(id=self.id).update(is_default=False)
        self.save()

    def get_steps(self) -> list:
        return self.steps.filter(is_enabled=True).order_by('order')


class KYCWorkflowStep(models.Model):
    """
    Individual step in a KYC workflow.
    Steps can be: document_upload, face_match, liveness, aml_check, manual_review, etc.
    """
    STEP_TYPES = [
        ('consent',          'User Consent Collection'),
        ('personal_info',    'Personal Information'),
        ('document_upload',  'Document Upload'),
        ('selfie',           'Selfie Capture'),
        ('face_match',       'Face Matching'),
        ('liveness',         'Liveness Check'),
        ('ocr_extraction',   'OCR Data Extraction'),
        ('aml_screening',    'AML/PEP Screening'),
        ('address_verify',   'Address Verification'),
        ('phone_verify',     'Phone Verification'),
        ('fraud_check',      'Fraud Risk Check'),
        ('manual_review',    'Manual Admin Review'),
        ('auto_decision',    'Automated Decision'),
        ('webhook_notify',   'Webhook Notification'),
        ('email_notify',     'Email Notification'),
    ]
    CONDITION_OP = [
        ('always',  'Always execute'),
        ('if_pass', 'Only if previous passed'),
        ('if_fail', 'Only if previous failed'),
        ('if_risk', 'If risk score > threshold'),
    ]

    workflow    = models.ForeignKey(KYCWorkflow, on_delete=models.CASCADE, related_name='steps', null=True, blank=True)
    step_type   = models.CharField(max_length=25, choices=STEP_TYPES, null=True, blank=True)
    name        = models.CharField(max_length=100, null=True, blank=True)
    order       = models.IntegerField(default=0)
    is_enabled  = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    condition   = models.CharField(max_length=10, choices=CONDITION_OP, default='always', null=True, blank=True)
    condition_value = models.IntegerField(default=0, help_text="Risk threshold if condition=if_risk")

    # Step-specific config
    config      = models.JSONField(default=dict, blank=True, help_text="Step-specific parameters")

    # e.g. {'allowed_doc_types': ['nid','passport'], 'min_confidence': 0.8}
    # e.g. {'provider': 'aws_rekognition', 'threshold': 0.85}
    # e.g. {'provider': 'complyadvantage', 'types': ['sanctions','pep']}

    class Meta:
        db_table = 'kyc_workflow_steps'
        verbose_name = 'Workflow Step'
        ordering = ['order']
        unique_together = [('workflow', 'order')]

    def __str__(self):
        return f"Step[{self.order}:{self.step_type}] {self.workflow.name}"


class KYCWorkflowRun(models.Model):
    """Runtime execution of a workflow for a specific user/KYC."""
    STATUS = [
        ('running',   'Running'),
        ('completed', 'Completed — Passed'),
        ('failed',    'Failed'),
        ('abandoned', 'Abandoned'),
        ('paused',    'Paused — Manual Review'),
    ]
    workflow        = models.ForeignKey(KYCWorkflow, on_delete=models.SET_NULL, null=True)
    kyc             = models.ForeignKey('kyc.KYC', on_delete=models.CASCADE, related_name='workflow_runs', null=True, blank=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    status          = models.CharField(max_length=15, choices=STATUS, default='running', db_index=True, null=True, blank=True)
    current_step    = models.IntegerField(default=0)
    total_steps     = models.IntegerField(default=0)
    step_results    = models.JSONField(default=list, blank=True)
    final_decision  = models.CharField(max_length=20, null=True, blank=True)
    started_at      = models.DateTimeField(auto_now_add=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)

    class Meta:
        db_table = 'kyc_workflow_runs'
        verbose_name = 'Workflow Run'
        ordering = ['-started_at']

    def __str__(self):
        return f"Run[{self.workflow}] {self.user} - {self.status}"


# ── Default workflow templates ─────────────────────────────

DEFAULT_WORKFLOWS = {
    'basic': {
        'name': 'Basic KYC (Bangladesh Standard)',
        'steps': [
            {'step_type': 'consent',         'name': 'User consent',     'order': 1},
            {'step_type': 'personal_info',   'name': 'Personal info',    'order': 2},
            {'step_type': 'document_upload', 'name': 'NID upload',       'order': 3,
             'config': {'allowed_doc_types': ['nid'], 'require_back': True}},
            {'step_type': 'selfie',          'name': 'Selfie capture',   'order': 4},
            {'step_type': 'face_match',      'name': 'Face matching',    'order': 5,
             'config': {'provider': 'aws_rekognition', 'threshold': 0.80}},
            {'step_type': 'ocr_extraction',  'name': 'OCR extraction',   'order': 6,
             'config': {'provider': 'google_vision'}},
            {'step_type': 'fraud_check',     'name': 'Fraud check',      'order': 7},
            {'step_type': 'auto_decision',   'name': 'Auto decision',    'order': 8,
             'config': {'auto_approve_threshold': 30, 'auto_reject_threshold': 80}},
        ]
    },
    'enhanced': {
        'name': 'Enhanced KYC (High-Value)',
        'steps': [
            {'step_type': 'consent',         'name': 'GDPR consent',    'order': 1},
            {'step_type': 'personal_info',   'name': 'Personal info',   'order': 2},
            {'step_type': 'document_upload', 'name': 'Document upload', 'order': 3,
             'config': {'allowed_doc_types': ['nid','passport'], 'require_back': True}},
            {'step_type': 'selfie',          'name': 'Selfie capture',  'order': 4},
            {'step_type': 'liveness',        'name': 'Liveness check',  'order': 5,
             'config': {'provider': 'facetec', 'type': 'active'}},
            {'step_type': 'face_match',      'name': 'Face matching',   'order': 6,
             'config': {'provider': 'aws_rekognition', 'threshold': 0.85}},
            {'step_type': 'ocr_extraction',  'name': 'OCR extraction',  'order': 7},
            {'step_type': 'aml_screening',   'name': 'AML/PEP check',   'order': 8,
             'config': {'provider': 'complyadvantage', 'types': ['sanctions','pep','adverse-media']}},
            {'step_type': 'phone_verify',    'name': 'Phone OTP',       'order': 9},
            {'step_type': 'fraud_check',     'name': 'Fraud check',     'order': 10},
            {'step_type': 'manual_review',   'name': 'Admin review',    'order': 11,
             'condition': 'if_risk', 'condition_value': 50},
            {'step_type': 'auto_decision',   'name': 'Auto decision',   'order': 12},
        ]
    }
}
