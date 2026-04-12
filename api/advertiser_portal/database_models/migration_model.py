"""Application-level migration tracking models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel
from django.contrib.auth import get_user_model
User = get_user_model()


class Migration(AdvertiserPortalBaseModel):
    name = models.CharField(max_length=200, unique=True)
    migration_type = models.CharField(max_length=20, db_index=True)
    version = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Migration {self.name} [{self.status}]"


class SchemaMigration(AdvertiserPortalBaseModel):
    migration = models.OneToOneField(Migration, on_delete=models.CASCADE, related_name='schema')
    up_sql = models.TextField()
    down_sql = models.TextField(blank=True)
    def __str__(self):
        return f"SchemaMigration {self.migration_id}"


class DataMigration(AdvertiserPortalBaseModel):
    migration = models.OneToOneField(Migration, on_delete=models.CASCADE, related_name='data')
    source_table = models.CharField(max_length=200)
    rows_affected = models.BigIntegerField(default=0)
    def __str__(self):
        return f"DataMigration {self.migration_id}"


class Rollback(AdvertiserPortalBaseModel):
    migration = models.ForeignKey(Migration, on_delete=models.CASCADE, related_name='rollbacks')
    rolled_back_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField()
    success = models.BooleanField(default=False)
    class Meta:
        ordering = ['-rolled_back_at']
    def __str__(self):
        return f"Rollback {self.migration_id}"


class MigrationTracking(AdvertiserPortalBaseModel):
    migration = models.OneToOneField(Migration, on_delete=models.CASCADE, related_name='tracking')
    total_rows = models.BigIntegerField(default=0)
    processed_rows = models.BigIntegerField(default=0)
    progress_percent = models.FloatField(default=0.0)
    def __str__(self):
        return f"Tracking {self.migration_id} {self.progress_percent:.1f}%"


class MigrationValidation(AdvertiserPortalBaseModel):
    migration = models.ForeignKey(Migration, on_delete=models.CASCADE, related_name='validations')
    check_name = models.CharField(max_length=200)
    check_type = models.CharField(max_length=20)
    passed = models.BooleanField(default=False)
    details = models.JSONField(default=dict)
    def __str__(self):
        return f"Validation {self.check_name}"


class MigrationBackup(AdvertiserPortalBaseModel):
    migration = models.ForeignKey(Migration, on_delete=models.CASCADE, related_name='backups')
    backup_path = models.TextField()
    size_bytes = models.BigIntegerField(default=0)
    taken_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"MigrationBackup {self.migration_id}"

class MigrationExecution(AdvertiserPortalBaseModel):
    """Migration execution tracking model."""
    
    migration = models.ForeignKey(
        Migration, on_delete=models.CASCADE, related_name='executions'
    )
    status = models.CharField(max_length=50, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)
    executed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='migration_executions'
    )

    class Meta:
        app_label = 'advertiser_portal'

    def __str__(self):
        return f"{self.migration} - {self.status}"


class MigrationValidation(AdvertiserPortalBaseModel):
    """Migration validation model."""
    
    migration = models.ForeignKey(
        Migration, on_delete=models.CASCADE, related_name='validations'
    )
    validation_type = models.CharField(max_length=100)
    is_valid = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    validated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'advertiser_portal'

    def __str__(self):
        return f"{self.migration} - {self.validation_type}"
