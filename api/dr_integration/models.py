"""
DR Integration Models — Django models that mirror/extend DR system state.
These models allow Django admin and DRF to interact with DR system data.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class DRSystemStatus(models.Model):
    """Cached status of the DR system — synced from DR API periodically."""
    overall_health = models.CharField(max_length=20, default='unknown', null=True, blank=True)
    last_backup_at = models.DateTimeField(null=True, blank=True)
    last_failover_at = models.DateTimeField(null=True, blank=True)
    replication_lag_seconds = models.FloatField(null=True, blank=True)
    active_incidents = models.IntegerField(default=0)
    active_alerts = models.IntegerField(default=0)
    rto_achieved_seconds = models.FloatField(null=True, blank=True)
    rpo_achieved_seconds = models.FloatField(null=True, blank=True)
    raw_status = models.JSONField(default=dict)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'DR System Status'
        verbose_name_plural = 'DR System Status'

    def __str__(self):
        return f"DR Status [{self.overall_health}] synced {self.synced_at:%Y-%m-%d %H:%M}"


class DRBackupRecord(models.Model):
    """Django-side record of DR-managed backups."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('verified', 'Verified'),
    ]
    TYPE_CHOICES = [
        ('full', 'Full'),
        ('incremental', 'Incremental'),
        ('differential', 'Differential'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dr_job_id = models.CharField(max_length=100, unique=True, help_text="ID from DR system", null=True, blank=True)
    backup_type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    source_size_bytes = models.BigIntegerField(null=True, blank=True)
    compressed_size_bytes = models.BigIntegerField(null=True, blank=True)
    storage_path = models.TextField(blank=True)
    checksum = models.CharField(max_length=64, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    encryption_enabled = models.BooleanField(default=True)
    compression_enabled = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_993'),
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_994'),
        ]

    def __str__(self):
        return f"DR Backup [{self.backup_type}] {self.status} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def size_mb(self):
        if self.source_size_bytes:
            return round(self.source_size_bytes / 1e6, 2)
        return None


class DRRestoreRecord(models.Model):
    """Django-side record of DR-managed restore operations."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    TYPE_CHOICES = [
        ('full', 'Full'),
        ('partial', 'Partial'),
        ('table', 'Table'),
        ('point_in_time', 'Point In Time'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dr_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    restore_type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    source_backup = models.ForeignKey(DRBackupRecord, on_delete=models.SET_NULL, null=True, blank=True)
    target_database = models.CharField(max_length=100, null=True, blank=True)
    point_in_time = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dr_restore_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dr_restore_approvals')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    approval_status = models.CharField(max_length=20, default='pending', null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"DR Restore [{self.restore_type}] -> {self.target_database} [{self.status}]"


class DRFailoverEvent(models.Model):
    """Records of DR failover events triggered by/from the system."""
    TYPE_CHOICES = [
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),
        ('drill', 'Drill'),
    ]
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dr_failover_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    failover_type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    primary_node = models.CharField(max_length=200, null=True, blank=True)
    secondary_node = models.CharField(max_length=200, null=True, blank=True)
    trigger_reason = models.TextField()
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    rto_achieved_seconds = models.FloatField(null=True, blank=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    initiated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_drill = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-initiated_at']

    def __str__(self):
        return f"DR Failover [{self.failover_type}] {self.primary_node}->{self.secondary_node} [{self.status}]"


class DRAlert(models.Model):
    """DR system alerts synced into Django for visibility."""
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dr_alert_id = models.CharField(max_length=100, null=True, blank=True)
    rule_name = models.CharField(max_length=200, null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True)
    message = models.TextField()
    metric = models.CharField(max_length=100, null=True, blank=True)
    metric_value = models.FloatField(null=True, blank=True)
    threshold = models.FloatField(null=True, blank=True)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    fired_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fired_at']

    def __str__(self):
        return f"DR Alert [{self.severity}] {self.rule_name}"


class DRDrillRecord(models.Model):
    """Records of DR drills (game days, chaos tests) run via the DR system."""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dr_drill_id = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    scenario_type = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', null=True, blank=True)
    passed = models.BooleanField(null=True)
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    achieved_rto_seconds = models.FloatField(null=True, blank=True)
    target_rto_seconds = models.IntegerField(null=True, blank=True)
    achieved_rpo_seconds = models.FloatField(null=True, blank=True)
    target_rpo_seconds = models.IntegerField(null=True, blank=True)
    planned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    participants = models.JSONField(default=list)
    lessons_learned = models.TextField(blank=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"DR Drill: {self.name} [{self.status}]"
