from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    DeltaBackupTracker, RetentionPolicy, BackupNotificationConfig,
    BackupRestoration, BackupVerification, BackupEncryption, BackupAlert
)
from .choices import (
    BackupType, BackupStatus, StorageType, RestoreStatus,
    DatabaseEngine, EncryptionType, CompressionType, ScheduleFrequency,
    LogLevel, VerificationMethod, AlertSeverity, AlertType, RestorationType
)
from .constants import MAX_BACKUP_SIZE_GB, DEFAULT_RETENTION_DAYS

User = get_user_model()

class BackupStorageLocationSerializer(serializers.ModelSerializer):
    """Serializer for BackupStorageLocation model"""
    
    class Meta:
        model = BackupStorageLocation
        fields = [
            'id', 'name', 'description', 'storage_type', 'is_default', 'priority',
            'config', 'connection_errors', 'is_active', 'last_checked', 'created_at', 'updated_at',
            'total_space', 'used_space', 'free_space', 'usage_percentage'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'connection_errors', 'last_checked']
    
    def validate_storage_type(self, value):
        """Validate storage type"""
        valid_types = [choice[0] for choice in StorageType.CHOICES]
        if value not in valid_types:
            raise ValidationError(f"Invalid storage type. Must be one of: {valid_types}")
        return value
    
    def validate_config(self, value):
        """Validate configuration based on storage type"""
        storage_type = self.initial_data.get('storage_type')
        if not storage_type:
            return value
        
        if storage_type == 's3':
            required_fields = ['access_key', 'secret_key', 'bucket_name']
        elif storage_type == 'gcs':
            required_fields = ['project_id', 'bucket_name', 'credentials_file']
        elif storage_type == 'azure':
            required_fields = ['account_name', 'account_key', 'container_name']
        else:
            required_fields = []
        
        for field in required_fields:
            if field not in value:
                raise ValidationError(f"Missing required field for {storage_type}: {field}")
        
        return value

class BackupLogSerializer(serializers.ModelSerializer):
    """Serializer for BackupLog model"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = BackupLog
        fields = [
            'id', 'backup', 'timestamp', 'level', 'category', 'action', 'source',
            'message', 'details', 'duration', 'memory_usage', 'cpu_usage', 'network_speed',
            'bytes_transferred', 'error_code', 'error_message', 'error_traceback',
            'error_context', 'encryption_method', 'compression_method', 'checksum',
            'hostname', 'process_id', 'thread_id', 'created_by'
        ]
        read_only_fields = ['id', 'timestamp', 'created_by']
    
    def validate_level(self, value):
        """Validate log level"""
        valid_levels = [choice[0] for choice in LogLevel.CHOICES]
        if value not in valid_levels:
            raise ValidationError(f"Invalid log level. Must be one of: {valid_levels}")
        return value

class BackupScheduleSerializer(serializers.ModelSerializer):
    """Serializer for BackupSchedule model"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    next_run_display = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupSchedule
        fields = [
            'id', 'name', 'description', 'is_active', 'is_paused', 'frequency',
            'cron_expression', 'scheduled_time', 'day_of_week', 'day_of_month',
            'month_of_year', 'backup_type', 'databases', 'tables_include', 'tables_exclude',
            'storage_type', 'retention_days', 'notify_on_success', 'notify_on_failure',
            'retry_on_failure', 'retry_count', 'retry_delay_minutes', 'created_by',
            'created_at', 'updated_at', 'last_run', 'next_run', 'success_rate',
            'next_run_display', 'total_runs', 'successful_runs', 'failed_runs'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_run', 'next_run', 'success_rate']
    
    def validate_frequency(self, value):
        """Validate frequency"""
        valid_frequencies = [choice[0] for choice in ScheduleFrequency.CHOICES]
        if value not in valid_frequencies:
            raise ValidationError(f"Invalid frequency. Must be one of: {valid_frequencies}")
        return value
    
    def get_next_run_display(self, obj):
        """Get human-readable next run time"""
        if obj.next_run:
            return obj.next_run.strftime('%Y-%m-%d %H:%M:%S')
        return 'Not scheduled'
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_runs == 0:
            return 0.0
        return round((obj.successful_runs / obj.total_runs) * 100, 2)

class BackupSerializer(serializers.ModelSerializer):
    """Serializer for Backup model"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    backup_schedule = serializers.StringRelatedField(read_only=True)
    retention_policy_ref = serializers.StringRelatedField(read_only=True)
    parent_backup = serializers.StringRelatedField(read_only=True)
    file_size_display = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    health_score_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Backup
        fields = [
            'id', 'backup_id', 'name', 'description', 'backup_type', 'status',
            'storage_type', 'file_path', 'file_size', 'file_size_display', 'file_hash',
            'encryption_enabled', 'encryption_type', 'encryption_key', 'compression_enabled',
            'compression_type', 'original_size', 'compressed_size',
            'compression_ratio', 'database_engine', 'database_name', 'row_count',
            'start_time', 'end_time', 'duration', 'duration_display', 'created_at', 'updated_at',
            'created_by', 'backup_schedule', 'retention_policy_ref', 'parent_backup',
            'is_permanent', 'expires_at', 'health_score', 'health_score_display',
            'tags', 'metadata'
        ]
        read_only_fields = ['id', 'backup_id', 'created_at', 'updated_at', 'file_size_display', 'duration_display', 'health_score_display']
    
    def validate_backup_type(self, value):
        """Validate backup type"""
        valid_types = [choice[0] for choice in BackupType.CHOICES]
        if value not in valid_types:
            raise ValidationError(f"Invalid backup type. Must be one of: {valid_types}")
        return value
    
    def validate_status(self, value):
        """Validate backup status"""
        valid_statuses = [choice[0] for choice in BackupStatus.CHOICES]
        if value not in valid_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate_file_size(self, value):
        """Validate file size"""
        max_size = MAX_BACKUP_SIZE_GB * 1024 * 1024 * 1024  # Convert to bytes
        if value > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {MAX_BACKUP_SIZE_GB}GB")
        return value
    
    def get_file_size_display(self, obj):
        """Get human-readable file size"""
        if not obj.file_size:
            return '0 B'
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def get_duration_display(self, obj):
        """Get human-readable duration"""
        if not obj.duration:
            return '0s'
        
        duration = obj.duration
        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            return f"{duration//60}m {duration%60:.0f}s"
        else:
            return f"{duration//3600}h {(duration%3600)//60}m"
    
    def get_health_score_display(self, obj):
        """Get health score with emoji"""
        if not obj.health_score:
            return '⚪ Unknown'
        
        score = obj.health_score
        if score >= 80:
            return f'🟢 {score}%'
        elif score >= 60:
            return f'🟡 {score}%'
        elif score >= 40:
            return f'🟠 {score}%'
        else:
            return f'🔴 {score}%'

class BackupRestorationSerializer(serializers.ModelSerializer):
    """Serializer for BackupRestoration model"""
    
    backup = BackupSerializer(read_only=True)
    initiated_by = serializers.StringRelatedField(read_only=True)
    reviewed_by = serializers.StringRelatedField(read_only=True)
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupRestoration
        fields = [
            'id', 'restoration_id', 'backup', 'backup_id', 'restoration_type',
            'status', 'initiated_by', 'reviewed_by', 'started_at', 'completed_at',
            'duration', 'duration_display', 'tables_to_restore', 'restore_point', 'rollback_enabled', 'rollback_performed',
            'rollback_to_backup', 'verification_passed', 'verification_details',
            'error_message', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'restoration_id', 'created_at', 'updated_at', 'duration_display']
    
    def validate_restoration_type(self, value):
        """Validate restoration type"""
        valid_types = [choice[0] for choice in RestorationType.CHOICES]
        if value not in valid_types:
            raise ValidationError(f"Invalid restoration type. Must be one of: {valid_types}")
        return value
    
    def get_duration_display(self, obj):
        """Get human-readable duration"""
        if not obj.duration:
            return '0s'
        
        duration = obj.duration
        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            return f"{duration//60}m {duration%60:.0f}s"
        else:
            return f"{duration//3600}h {(duration%3600)//60}m"

class RetentionPolicySerializer(serializers.ModelSerializer):
    """Serializer for RetentionPolicy model"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = RetentionPolicy
        fields = [
            'id', 'name', 'description', 'keep_all', 'keep_weekly',
            'keep_monthly', 'keep_yearly', 'is_active', 'priority',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class BackupNotificationConfigSerializer(serializers.ModelSerializer):
    """Serializer for BackupNotificationConfig model"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = BackupNotificationConfig
        fields = [
            'id', 'name', 'description', 'notify_on_success',
            'notify_on_failure', 'notify_on_warning',
            'is_active', 'priority', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_channels(self, value):
        """Validate notification channels"""
        valid_channels = ['email', 'webhook', 'slack', 'teams', 'sms', 'push']
        for channel in value:
            if channel not in valid_channels:
                raise ValidationError(f"Invalid channel: {channel}. Must be one of: {valid_channels}")
        return value

class DeltaBackupTrackerSerializer(serializers.ModelSerializer):
    """Serializer for DeltaBackupTracker model"""
    
    parent_backup = serializers.StringRelatedField(read_only=True)
    child_backup = serializers.StringRelatedField(read_only=True)
    base_backup = serializers.StringRelatedField(read_only=True)
    compression_ratio = serializers.SerializerMethodField()
    
    class Meta:
        model = DeltaBackupTracker
        fields = [
            'id', 'parent_backup', 'child_backup',
            'compressed_size',
            'compression_ratio', 'changed_tables', 'changed_row_count', 'change_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'compression_ratio']
    
    def get_compression_ratio(self, obj):
        """Calculate compression ratio"""
        if obj.total_size == 0:
            return 0.0
        return round((obj.compressed_size / obj.total_size) * 100, 2)

class BackupProgressSerializer(serializers.Serializer):
    """Serializer for real-time backup progress data."""
    backup_id = serializers.UUIDField()
    progress = serializers.FloatField()
    status = serializers.CharField()
    message = serializers.CharField(required=False)

class BackupTaskRequestSerializer(serializers.Serializer):
    """Serializer for initiating backup task requests."""
    backup_type = serializers.CharField(max_length=50, required=False)
    storage_type = serializers.CharField(max_length=50, required=False)
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)

class RestoreRequestSerializer(serializers.Serializer):
    """Serializer for backup restoration requests."""
    backup_id = serializers.UUIDField()
    restore_point = serializers.DateTimeField(required=False)
    tables_to_restore = serializers.ListField(child=serializers.CharField(), required=False)

class HealthCheckSerializer(serializers.Serializer):
    """Serializer for system health check responses."""
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    details = serializers.DictField(required=False)

class MaintenanceModeSerializer(serializers.Serializer):
    """Serializer for enabling/disabling maintenance mode."""
    enabled = serializers.BooleanField()
    message = serializers.CharField(required=False)
    estimated_duration = serializers.IntegerField(required=False)

class BackupVerificationSerializer(serializers.ModelSerializer):
    """Serializer for BackupVerification model"""
    
    backup = BackupSerializer(read_only=True)
    verified_by = serializers.StringRelatedField(read_only=True)
    verification_method_display = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupVerification
        fields = [
            'id', 'backup', 'verified_at', 'is_valid',
            'checksum_match', 'size_match', 'error_message', 'verification_method',
            'verification_method_display', 'verification_details', 'verified_by'
        ]
        read_only_fields = ['id', 'verified_at', 'verification_method_display']
    
    def validate_verification_method(self, value):
        """Validate verification method"""
        valid_methods = [choice[0] for choice in VerificationMethod.CHOICES]
        if value not in valid_methods:
            raise ValidationError(f"Invalid verification method. Must be one of: {valid_methods}")
        return value
    
    def get_verification_method_display(self, obj):
        """Get display name for verification method"""
        return VerificationMethod.get_display_name(obj.verification_method)

class BackupEncryptionSerializer(serializers.ModelSerializer):
    """Serializer for BackupEncryption model"""
    
    backup = BackupSerializer(read_only=True)
    algorithm_display = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupEncryption
        fields = [
            'id', 'backup', 'algorithm', 'algorithm_display', 'key_hash',
            'is_encrypted', 'encryption_key', 'salt', 'iv', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'algorithm_display', 'key_hash', 'created_at', 'updated_at']
    
    def validate_algorithm(self, value):
        """Validate encryption algorithm"""
        valid_algorithms = [choice[0] for choice in EncryptionType.CHOICES]
        if value not in valid_algorithms:
            raise ValidationError(f"Invalid encryption algorithm. Must be one of: {valid_algorithms}")
        return value
    
    def get_algorithm_display(self, obj):
        """Get display name for encryption algorithm"""
        return EncryptionType.get_display_name(obj.algorithm)

class BackupAlertSerializer(serializers.ModelSerializer):
    """Serializer for BackupAlert model"""
    
    backup = BackupSerializer(read_only=True)
    resolved_by = serializers.StringRelatedField(read_only=True)
    alert_type_display = serializers.SerializerMethodField()
    severity_display = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupAlert
        fields = [
            'id', 'alert_type', 'alert_type_display', 'backup', 'message',
            'is_resolved', 'severity', 'severity_display', 'created_at',
            'resolved_at', 'resolved_by', 'metadata', 'notification_sent'
        ]
        read_only_fields = ['id', 'alert_type_display', 'severity_display', 'created_at']
    
    def validate_alert_type(self, value):
        """Validate alert type"""
        valid_types = [choice[0] for choice in AlertType.CHOICES]
        if value not in valid_types:
            raise ValidationError(f"Invalid alert type. Must be one of: {valid_types}")
        return value
    
    def validate_severity(self, value):
        """Validate severity level"""
        valid_severities = [choice[0] for choice in AlertSeverity.CHOICES]
        if value not in valid_severities:
            raise ValidationError(f"Invalid severity. Must be one of: {valid_severities}")
        return value
    
    def get_alert_type_display(self, obj):
        """Get display name for alert type"""
        return AlertType.get_display_name(obj.alert_type)
    
    def get_severity_display(self, obj):
        """Get display name for severity"""
        return AlertSeverity.get_display_name(obj.severity)


# ================================================
# UTILITY AND ACTION SERIALIZERS
# ================================================

class BackupProgressSerializer(serializers.Serializer):
    """Serializer for backup progress tracking"""
    backup_id = serializers.UUIDField()
    progress = serializers.FloatField(min_value=0, max_value=100)
    status = serializers.CharField(max_length=50)
    message = serializers.CharField(required=False, allow_blank=True)
    estimated_remaining = serializers.IntegerField(required=False)
    current_operation = serializers.CharField(max_length=100, required=False)
    bytes_processed = serializers.IntegerField(required=False)
    bytes_total = serializers.IntegerField(required=False)
    error_details = serializers.DictField(required=False)

class BackupTaskRequestSerializer(serializers.Serializer):
    """Serializer for backup task requests"""
    backup_type = serializers.ChoiceField(choices=BackupType.CHOICES, required=False)
    storage_type = serializers.ChoiceField(choices=StorageType.CHOICES, required=False)
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    database_name = serializers.CharField(max_length=100, required=False)
    tables_include = serializers.ListField(child=serializers.CharField(), required=False)
    tables_exclude = serializers.ListField(child=serializers.CharField(), required=False)
    encrypt = serializers.BooleanField(default=False)
    encryption_algorithm = serializers.ChoiceField(choices=EncryptionType.CHOICES, required=False)
    compress = serializers.BooleanField(default=False)
    compression_algorithm = serializers.ChoiceField(choices=CompressionType.CHOICES, required=False)
    compression_level = serializers.IntegerField(min_value=1, max_value=9, required=False)
    retention_days = serializers.IntegerField(min_value=1, max_value=3650, required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    metadata = serializers.DictField(required=False)
    priority = serializers.ChoiceField(choices=['low', 'normal', 'high'], default='normal')
    schedule_id = serializers.UUIDField(required=False)
    
    def validate(self, attrs):
        """Cross-field validation"""
        if attrs.get('encrypt') and not attrs.get('encryption_algorithm'):
            attrs['encryption_algorithm'] = 'AES-256-GCM'  # Default
        
        if attrs.get('compress') and not attrs.get('compression_algorithm'):
            attrs['compression_algorithm'] = 'gzip'  # Default
        
        if attrs.get('backup_type') == 'incremental' and not attrs.get('parent_backup_id'):
            raise ValidationError("Incremental backups require a parent backup ID")
        
        return attrs

class RestoreRequestSerializer(serializers.Serializer):
    """Serializer for restore requests"""
    backup_id = serializers.UUIDField()
    restoration_type = serializers.ChoiceField(choices=RestorationType.CHOICES, required=False)
    restore_point = serializers.DateTimeField(required=False)
    tables_to_restore = serializers.ListField(child=serializers.CharField(), required=False)
    target_database = serializers.CharField(max_length=100, required=False)
    target_host = serializers.CharField(max_length=255, required=False)
    target_port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    target_name = serializers.CharField(max_length=100, required=False)
    create_database = serializers.BooleanField(default=True)
    drop_database = serializers.BooleanField(default=True)
    rollback_enabled = serializers.BooleanField(default=True)
    verify_after_restore = serializers.BooleanField(default=True)
    dry_run = serializers.BooleanField(default=False)
    force_restore = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Cross-field validation"""
        backup_id = attrs.get('backup_id')
        if backup_id:
            try:
                backup = Backup.objects.get(backup_id=backup_id)
                if backup.status != 'completed':
                    raise ValidationError("Can only restore completed backups")
            except Backup.DoesNotExist:
                raise ValidationError("Backup not found")
        
        return attrs

class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check requests"""
    status = serializers.ChoiceField(choices=['healthy', 'warning', 'critical', 'unknown'])
    message = serializers.CharField(required=False, allow_blank=True)
    details = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(read_only=True)
    checks = serializers.DictField(required=False)
    uptime_seconds = serializers.IntegerField(required=False)
    version = serializers.CharField(read_only=True)
    environment = serializers.CharField(read_only=True)

class MaintenanceModeSerializer(serializers.Serializer):
    """Serializer for maintenance mode"""
    enabled = serializers.BooleanField()
    message = serializers.CharField(required=False, allow_blank=True)
    estimated_duration = serializers.IntegerField(min_value=0, required=False)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)
    allowed_users = serializers.ListField(child=serializers.CharField(), required=False)
    emergency_contacts = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate(self, attrs):
        """Cross-field validation"""
        if attrs.get('start_time') and attrs.get('end_time'):
            if attrs['end_time'] <= attrs['start_time']:
                raise ValidationError("End time must be after start time")
        
        if attrs.get('enabled') and not attrs.get('message'):
            attrs['message'] = "System is under maintenance"  # Default message
        
        return attrs

# ================================================
# ANALYTICS AND REPORTING SERIALIZERS
# ================================================

class BackupStatsSerializer(serializers.Serializer):
    """Serializer for backup statistics"""
    total_backups = serializers.IntegerField(read_only=True)
    successful_backups = serializers.IntegerField(read_only=True)
    failed_backups = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    total_size_bytes = serializers.IntegerField(read_only=True)
    total_size_gb = serializers.FloatField(read_only=True)
    average_duration = serializers.FloatField(read_only=True)
    last_24h_count = serializers.IntegerField(read_only=True)
    last_7d_count = serializers.IntegerField(read_only=True)
    last_30d_count = serializers.IntegerField(read_only=True)
    oldest_backup_age = serializers.IntegerField(read_only=True)
    newest_backup_age = serializers.IntegerField(read_only=True)
    storage_utilization = serializers.FloatField(read_only=True)
    health_score = serializers.FloatField(read_only=True)
    alerts_count = serializers.IntegerField(read_only=True)
    critical_alerts_count = serializers.IntegerField(read_only=True)

class StorageUsageSerializer(serializers.Serializer):
    """Serializer for storage usage analytics"""
    storage_type = serializers.CharField(read_only=True)
    total_space = serializers.IntegerField(read_only=True)
    used_space = serializers.IntegerField(read_only=True)
    free_space = serializers.IntegerField(read_only=True)
    usage_percentage = serializers.FloatField(read_only=True)
    backup_count = serializers.IntegerField(read_only=True)
    oldest_backup = serializers.DateTimeField(read_only=True)
    newest_backup = serializers.DateTimeField(read_only=True)
    performance_metrics = serializers.DictField(read_only=True)
    trend_data = serializers.ListField(child=serializers.DictField(), read_only=True)

class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance metrics"""
    metric_name = serializers.CharField(read_only=True)
    current_value = serializers.FloatField(read_only=True)
    average_value = serializers.FloatField(read_only=True)
    min_value = serializers.FloatField(read_only=True)
    max_value = serializers.FloatField(read_only=True)
    trend = serializers.CharField(read_only=True)
    unit = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    historical_data = serializers.ListField(child=serializers.DictField(), read_only=True)

# ================================================
# NOTIFICATION SERIALIZERS
# ================================================

class NotificationRequestSerializer(serializers.Serializer):
    """Serializer for notification requests"""
    channels = serializers.ListField(child=serializers.CharField())
    recipients = serializers.ListField(child=serializers.CharField())
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    priority = serializers.ChoiceField(choices=['low', 'normal', 'high', 'urgent'], default='normal')
    backup_id = serializers.UUIDField(required=False)
    alert_type = serializers.ChoiceField(choices=AlertType.CHOICES, required=False)
    custom_data = serializers.DictField(required=False)
    attachments = serializers.ListField(child=serializers.DictField(), required=False)
    
    def validate_channels(self, value):
        """Validate notification channels"""
        valid_channels = ['email', 'webhook', 'slack', 'teams', 'sms', 'push']
        for channel in value:
            if channel not in valid_channels:
                raise ValidationError(f"Invalid channel: {channel}")
        return value

class NotificationTestSerializer(serializers.Serializer):
    """Serializer for notification testing"""
    channel = serializers.ChoiceField(choices=['email', 'webhook', 'slack', 'teams', 'sms', 'push'])
    recipient = serializers.CharField(max_length=255)
    message = serializers.CharField(default="Test notification from backup system")
    backup_id = serializers.UUIDField(required=False)

# ================================================
# BATCH OPERATION SERIALIZERS
# ================================================

class BatchOperationSerializer(serializers.Serializer):
    """Serializer for batch operations"""
    operation = serializers.ChoiceField(choices=['delete', 'verify', 'compress', 'encrypt', 'move'])
    backup_ids = serializers.ListField(child=serializers.UUIDField())
    parameters = serializers.DictField(required=False)
    dry_run = serializers.BooleanField(default=False)
    confirm = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Validate batch operation"""
        operation = attrs.get('operation')
        backup_ids = attrs.get('backup_ids', [])
        
        if not backup_ids:
            raise ValidationError("At least one backup ID is required")
        
        if operation == 'delete' and not attrs.get('confirm'):
            raise ValidationError("Confirmation required for delete operations")
        
        return attrs

class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions"""
    action = serializers.ChoiceField(choices=['archive', 'restore', 'cleanup', 'verify', 'encrypt'])
    filters = serializers.DictField(required=False)
    target_all = serializers.BooleanField(default=False)
    dry_run = serializers.BooleanField(default=False)
    schedule = serializers.BooleanField(default=False)
    schedule_time = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """Validate bulk action"""
        if attrs.get('schedule') and not attrs.get('schedule_time'):
            raise ValidationError("Schedule time is required when scheduling actions")
        
        if not attrs.get('target_all') and not attrs.get('filters'):
            raise ValidationError("Either target_all=True or filters must be provided")
        
        return attrs


# ─── Serializer Enhancements ────────────────────────────────────────────────

class BackupCreateSerializer(BackupSerializer):
    """
    Specialised write serializer for Backup creation.
    Uses extra_kwargs for field-level control and overrides create().
    """
    class Meta(BackupSerializer.Meta):
        extra_kwargs = {
            'file_path':     {'required': False},
            'file_size':     {'required': False, 'read_only': True},
            'checksum':      {'required': False, 'read_only': True},
            'status':        {'read_only': True},
            'created_by':    {'read_only': True},
            'completed_at':  {'read_only': True},
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        validated_data.setdefault('status', 'pending')
        return super().create(validated_data)


class BackupUpdateSerializer(BackupSerializer):
    """
    Specialised write serializer for Backup partial updates.
    Restricts which fields can be modified after creation.
    """
    class Meta(BackupSerializer.Meta):
        extra_kwargs = {
            'name':          {'required': False},
            'notes':         {'required': False},
            'retention_days':{'required': False},
            'status':        {'read_only': True},
            'created_by':    {'read_only': True},
            'backup_type':   {'read_only': True},  # cannot change type after creation
            'file_path':     {'read_only': True},
        }

    def update(self, instance, validated_data):
        # Prevent status changes via PATCH — use dedicated action endpoints
        validated_data.pop('status', None)
        return super().update(instance, validated_data)


class BackupDetailSerializer(BackupSerializer):
    """
    Read serializer with full nested detail — used on retrieve().
    Adds nested logs, verification, restoration context.
    """
    logs = BackupLogSerializer(many=True, read_only=True)
    verifications = BackupVerificationSerializer(many=True, read_only=True)
    restorations = BackupRestorationSerializer(many=True, read_only=True)
    storage_location_detail = BackupStorageLocationSerializer(
        source='storage_location', read_only=True
    )

    class Meta(BackupSerializer.Meta):
        fields = BackupSerializer.Meta.fields + [
            'logs', 'verifications', 'restorations', 'storage_location_detail'
        ] if isinstance(BackupSerializer.Meta.fields, list) else '__all__'

    def to_representation(self, instance):
        """Enrich output with computed display fields"""
        data = super().to_representation(instance)
        # Add human-readable size
        size = getattr(instance, 'file_size', None) or getattr(instance, 'size', None)
        if size:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024:
                    data['size_human'] = f'{size:.1f} {unit}'
                    break
                size /= 1024
        # Add status display label
        data['status_display'] = instance.get_status_display() if hasattr(instance, 'get_status_display') else data.get('status', '')
        return data


class HealthyBackupManagerSerializer(serializers.Serializer):
    """Serializer for HealthyBackupManager queryset output"""
    id             = serializers.UUIDField(read_only=True)
    name           = serializers.CharField(read_only=True)
    status         = serializers.CharField(read_only=True)
    is_healthy     = serializers.BooleanField(read_only=True)
    health_score   = serializers.IntegerField(read_only=True)
    created_at     = serializers.DateTimeField(read_only=True)


class ExpiredBackupManagerSerializer(serializers.Serializer):
    """Serializer for ExpiredBackupManager queryset output"""
    id             = serializers.UUIDField(read_only=True)
    name           = serializers.CharField(read_only=True)
    expires_at     = serializers.DateTimeField(read_only=True)
    retention_days = serializers.IntegerField(read_only=True)
    created_at     = serializers.DateTimeField(read_only=True)
