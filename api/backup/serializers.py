from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    DeltaBackupTracker, RetentionPolicy, BackupNotificationConfig
)

User = get_user_model()

class BackupStorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupStorageLocation
        fields = ['id', 'name', 'description', 'storage_type', 'is_default', 'priority', 'config', 'connection_errors', 'created_at', 'updated_at']

class BackupLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupLog
        fields = ['id', 'backup', 'timestamp', 'level', 'message', 'details']

class BackupScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupSchedule
        fields = ['id', 'name', 'description', 'is_active', 'frequency', 'cron_expression', 'day_of_week', 'day_of_month', 'backup_type', 'storage_type', 'retention_days', 'notify_on_success', 'notify_on_failure', 'created_by', 'created_at', 'updated_at', 'last_run', 'next_run']

class BackupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Backup
        fields = ['id', 'backup_id', 'name', 'description', 'backup_type', 'status', 'storage_type', 'file_path', 'file_size', 'file_hash', 'encryption_type', 'encryption_key', 'compression_type', 'original_size', 'compressed_size', 'database_engine', 'database_name', 'row_count', 'start_time', 'end_time', 'duration', 'created_at', 'updated_at']

class BackupRestorationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Backup
        fields = ['id', 'backup_id', 'name', 'backup_type', 'status', 'start_time', 'end_time', 'created_at']

class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionPolicy
        fields = ['id', 'name', 'keep_all', 'keep_weekly', 'keep_monthly', 'keep_yearly', 'created_by', 'created_at', 'updated_at']

class BackupNotificationConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupNotificationConfig
        fields = ['id', 'name', 'notify_on_failure', 'notify_on_warning', 'created_by', 'created_at', 'updated_at']

class DeltaBackupTrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeltaBackupTracker
        fields = ['id', 'parent_backup', 'child_backup']

class BackupProgressSerializer(serializers.Serializer):
    backup_id = serializers.UUIDField()
    progress = serializers.FloatField()
    status = serializers.CharField()
    message = serializers.CharField(required=False)

class BackupTaskRequestSerializer(serializers.Serializer):
    backup_type = serializers.CharField(max_length=50, required=False)
    storage_type = serializers.CharField(max_length=50, required=False)
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)

class RestoreRequestSerializer(serializers.Serializer):
    backup_id = serializers.UUIDField()
    restore_point = serializers.DateTimeField(required=False)
    tables_to_restore = serializers.ListField(child=serializers.CharField(), required=False)

class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    details = serializers.DictField(required=False)

class MaintenanceModeSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    message = serializers.CharField(required=False)
    estimated_duration = serializers.IntegerField(required=False)
