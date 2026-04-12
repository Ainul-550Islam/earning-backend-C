# kyc/batch/models.py  ── WORLD #1
"""
Batch Verification API.
Jumio/Sumsub enterprise feature — verify thousands of users at once.
Use case: Bank data migration, corporate onboarding, crypto exchange re-KYC.
"""
from django.db import models
from django.conf import settings


class BatchVerificationJob(models.Model):
    """Batch KYC verification job."""
    STATUS = [
        ('pending','Pending'), ('processing','Processing'),
        ('done','Done'), ('failed','Failed'), ('partial','Partial'),
    ]
    TYPE = [
        ('csv_import',    'CSV Import'),
        ('api_bulk',      'API Bulk'),
        ('rekyc',         'Re-KYC Campaign'),
        ('migration',     'Data Migration'),
    ]
    requested_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tenant             = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    job_type           = models.CharField(max_length=20, choices=TYPE, default='api_bulk', null=True, blank=True)
    status             = models.CharField(max_length=15, choices=STATUS, default='pending', db_index=True, null=True, blank=True)
    total_records      = models.IntegerField(default=0)
    processed_count    = models.IntegerField(default=0)
    success_count      = models.IntegerField(default=0)
    failed_count       = models.IntegerField(default=0)
    skipped_count      = models.IntegerField(default=0)
    input_file         = models.FileField(upload_to='kyc/batch/input/', null=True, blank=True)
    result_file        = models.FileField(upload_to='kyc/batch/output/', null=True, blank=True)
    error_log          = models.TextField(blank=True)
    config             = models.JSONField(default=dict, blank=True, help_text="Screening config for this batch")
    started_at         = models.DateTimeField(null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_batch_jobs'
        verbose_name = 'Batch Verification Job'
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch[{self.job_type}] {self.processed_count}/{self.total_records} - {self.status}"

    @property
    def progress_pct(self):
        if not self.total_records: return 0
        return round(self.processed_count / self.total_records * 100, 1)


class BatchVerificationRecord(models.Model):
    """Individual record within a batch job."""
    STATUS = [('pending','Pending'),('done','Done'),('failed','Failed'),('skipped','Skipped')]
    job            = models.ForeignKey(BatchVerificationJob, on_delete=models.CASCADE, related_name='records', null=True, blank=True)
    row_number     = models.IntegerField()
    external_id    = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    input_data     = models.JSONField(default=dict)
    result         = models.JSONField(default=dict, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS, default='pending', null=True, blank=True)
    kyc_id         = models.IntegerField(null=True, blank=True)
    error          = models.TextField(blank=True)
    processed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_batch_records'
        verbose_name = 'Batch Record'
        ordering = ['row_number']

    def __str__(self):
        return f"Row#{self.row_number} [{self.status}] job={self.job_id}"


# ──────────────────────────────────────────────────────────
# kyc/batch/views.py
# ──────────────────────────────────────────────────────────
