# Simple replacement serializers for backup app
from rest_framework import serializers
from .models import Backup, BackupLog, BackupSchedule, BackupStorageLocation, DeltaBackupTracker

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

class DeltaBackupTrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeltaBackupTracker
        fields = ['id', 'base_backup', 'total_size', 'compressed_size', 'avg_delta_size', 'max_delta_size', 'needs_consolidation', 'last_consolidation', 'created_at', 'updated_at']
