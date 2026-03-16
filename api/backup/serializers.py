# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Backup, BackupSchedule, BackupLog, BackupStorageLocation,
    BackupRestoration, BackupNotificationConfig, RetentionPolicy,
    DeltaBackupTracker
)
import uuid
from django.utils import timezone

User = get_user_model()


class BackupStorageLocationSerializer(serializers.ModelSerializer):
    """Serializer for BackupStorageLocation"""
    usage_percentage = serializers.ReadOnlyField()
    available_capacity = serializers.ReadOnlyField()
    is_connected_display = serializers.CharField(source='get_is_connected_display', read_only=True)
    storage_type_display = serializers.CharField(source='get_storage_type_display', read_only=True)
    
    class Meta:
        model = BackupStorageLocation
        fields = [
            'id', 'name', 'description', 'storage_type', 'storage_type_display',
            'is_default', 'is_active', 'is_connected', 'is_connected_display',
            'priority', 'config', 'max_capacity', 'used_capacity',
            'available_capacity', 'usage_percentage', 'upload_speed',
            'download_speed', 'last_connected', 'connection_errors',
            'last_error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['usage_percentage', 'available_capacity', 'created_at', 'updated_at']


class BackupLogSerializer(serializers.ModelSerializer):
    """Serializer for BackupLog"""
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    backup_name = serializers.CharField(source='backup.name', read_only=True)
    timestamp_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = BackupLog
        fields = [
            'id', 'backup', 'backup_name', 'timestamp', 'timestamp_formatted',
            'level', 'level_display', 'message', 'details'
        ]
        read_only_fields = ['timestamp']
    
    def get_timestamp_formatted(self, obj):
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')


class BackupScheduleSerializer(serializers.ModelSerializer):
    """Serializer for BackupSchedule"""
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    backup_type_display = serializers.CharField(source='get_backup_type_display', read_only=True)
    storage_type_display = serializers.CharField(source='get_storage_type_display', read_only=True)
    is_active_display = serializers.SerializerMethodField()
    next_run_formatted = serializers.SerializerMethodField()
    last_run_formatted = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = BackupSchedule
        fields = [
            'id', 'name', 'description', 'is_active', 'is_active_display',
            'frequency', 'frequency_display', 'cron_expression',
            'day_of_week', 'day_of_month', 'hour', 'minute',
            'backup_type', 'backup_type_display', 'storage_type', 'storage_type_display',
            'encryption_type', 'compression_type', 'retention_days', 'keep_last_n',
            'notify_on_success', 'notify_on_failure', 'notification_emails',
            'include_tables', 'exclude_tables', 'max_backup_size', 'parallel_backup',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
            'last_run', 'last_run_formatted', 'next_run', 'next_run_formatted'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_run', 'next_run']
    
    def get_is_active_display(self, obj):
        return 'Active' if obj.is_active else 'Inactive'
    
    def get_next_run_formatted(self, obj):
        if obj.next_run:
            return obj.next_run.strftime('%Y-%m-%d %H:%M')
        return None
    
    def get_last_run_formatted(self, obj):
        if obj.last_run:
            return obj.last_run.strftime('%Y-%m-%d %H:%M')
        return None
    
    def validate_notification_emails(self, value):
        """Validate notification emails"""
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        for email in value:
            if not re.match(email_regex, email):
                raise serializers.ValidationError(f"Invalid email address: {email}")
        
        return value


class BackupSerializer(serializers.ModelSerializer):
    """Serializer for Backup model with enhanced features"""
    # Display fields
    backup_type_display = serializers.CharField(source='get_backup_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    storage_type_display = serializers.CharField(source='get_storage_type_display', read_only=True)
    encryption_type_display = serializers.CharField(source='get_encryption_type_display', read_only=True)
    compression_type_display = serializers.CharField(source='get_compression_type_display', read_only=True)
    retention_policy_display = serializers.CharField(source='get_retention_policy_display', read_only=True)
    gfs_category_display = serializers.CharField(source='get_gfs_category_display', read_only=True)
    
    # Related fields
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True, allow_null=True)
    parent_backup_name = serializers.CharField(source='parent_backup.name', read_only=True, allow_null=True)
    delta_base_name = serializers.CharField(source='delta_base.name', read_only=True, allow_null=True)
    schedule_name = serializers.CharField(source='schedule.name', read_only=True, allow_null=True)
    
    # Calculated fields
    file_size_human = serializers.SerializerMethodField()
    duration_human = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    health_status = serializers.SerializerMethodField()
    redundancy_info = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()
    notification_status = serializers.SerializerMethodField()
    
    # Statistics
    log_count = serializers.SerializerMethodField()
    child_backup_count = serializers.SerializerMethodField()
    restoration_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Backup
        fields = [
            # Basic information
            'id', 'backup_id', 'name', 'description',
            
            # Type and Status
            'backup_type', 'backup_type_display', 'status', 'status_display',
            
            # Storage configuration
            'storage_type', 'storage_type_display', 'storage_path', 'file_name',
            'file_size', 'file_size_human', 'file_hash',
            
            # Security
            'encryption_type', 'encryption_type_display', 'encryption_key_id', 'is_encrypted',
            'compression_type', 'compression_type_display', 'compression_ratio',
            'original_size', 'compressed_size',
            
            # Database details
            'database_engine', 'database_name', 'database_version',
            'table_count', 'row_count', 'included_tables', 'excluded_tables',
            
            # Performance metrics
            'start_time', 'end_time', 'duration', 'duration_human',
            'backup_speed', 'compression_speed', 'upload_speed',
            
            # Retry and recovery
            'retry_count', 'max_retries', 'last_error', 'error_traceback',
            
            # User and metadata
            'created_by', 'created_by_username', 'verified_by', 'verified_by_username',
            'verified_at', 'tags', 'category', 'priority', 'metadata',
            
            # Retention policy
            'retention_days', 'retention_policy', 'retention_policy_display',
            'gfs_category', 'gfs_category_display', 'expires_at', 'is_permanent',
            'is_expired',
            
            # Verification
            'is_verified', 'verification_hash', 'verification_status',
            
            # Relations
            'parent_backup', 'parent_backup_name', 'delta_base', 'delta_base_name',
            'schedule', 'schedule_name', 'is_scheduled',
            
            # Health monitoring
            'is_healthy', 'health_score', 'last_health_check', 'health_check_count',
            'health_status',
            
            # Redundancy
            'redundancy_level', 'storage_locations', 'redundancy_info',
            
            # Delta backup
            'changed_tables', 'changed_row_count',
            
            # Notifications
            'notification_channels', 'notification_sent', 'notification_status',
            
            # Advanced features
            'chunk_size', 'parallel_workers', 'auto_cleanup_enabled',
            'last_cleanup_check', 'verification_method',
            
            # Statistics
            'log_count', 'child_backup_count', 'restoration_count',
        ]
        read_only_fields = [
            'backup_id', 'file_size', 'file_hash', 'start_time', 'end_time',
            'duration', 'backup_speed', 'compression_speed', 'upload_speed',
            'compression_ratio', 'is_verified', 'verified_at', 'verification_hash',
            'is_healthy', 'health_score', 'last_health_check', 'health_check_count',
            'is_expired', 'notification_sent', 'log_count', 'child_backup_count',
            'restoration_count'
        ]
    
    def get_file_size_human(self, obj):
        from django.template.defaultfilters import filesizeformat
        return filesizeformat(obj.file_size) if obj.file_size else 'N/A'
    
    def get_duration_human(self, obj):
        if obj.duration:
            seconds = obj.duration
            if seconds < 60:
                return f"{int(seconds)}s"
            elif seconds < 3600:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                return f"{int(minutes)}m {int(remaining_seconds)}s"
            else:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                return f"{int(hours)}h {int(minutes)}m"
        return 'N/A'
    
    def get_health_status(self, obj):
        if not obj.is_healthy:
            return {'status': 'critical', 'message': 'Unhealthy'}
        
        if obj.health_score >= 90:
            return {'status': 'healthy', 'message': 'Excellent'}
        elif obj.health_score >= 70:
            return {'status': 'warning', 'message': 'Good'}
        else:
            return {'status': 'critical', 'message': 'Poor'}
    
    def get_redundancy_info(self, obj):
        from .models import BackupStorageLocation
        
        if obj.storage_type == 'redundant' and obj.storage_locations:
            locations = BackupStorageLocation.objects.filter(id__in=obj.storage_locations)
            return {
                'level': obj.redundancy_level,
                'locations': [
                    {'id': loc.id, 'name': loc.name, 'type': loc.storage_type}
                    for loc in locations
                ]
            }
        return {'level': 1, 'locations': []}
    
    def get_verification_status(self, obj):
        if obj.is_verified:
            return {'status': 'verified', 'message': 'Backup verified'}
        elif obj.verified_at:
            return {'status': 'failed', 'message': 'Verification failed'}
        else:
            return {'status': 'pending', 'message': 'Not verified'}
    
    def get_notification_status(self, obj):
        if obj.notification_sent:
            return {'sent': True, 'channels': obj.notification_channels}
        return {'sent': False, 'channels': []}
    
    def get_log_count(self, obj):
        return obj.logs.count()
    
    def get_child_backup_count(self, obj):
        return obj.child_backups.count()
    
    def get_restoration_count(self, obj):
        return obj.restorations.count()
    
    def validate(self, data):
        """Validate backup data"""
        # Set expires_at if not provided
        if 'expires_at' not in data and 'retention_days' in data:
            data['expires_at'] = timezone.now() + timezone.timedelta(days=data['retention_days'])
        
        # Validate included_tables and excluded_tables
        if 'included_tables' in data and 'excluded_tables' in data:
            if set(data['included_tables']) & set(data['excluded_tables']):
                raise serializers.ValidationError(
                    "Tables cannot be both included and excluded"
                )
        
        # Validate delta backup
        if data.get('backup_type') == 'delta' and not data.get('delta_base'):
            raise serializers.ValidationError(
                "Delta backup requires a base backup"
            )
        
        return data
    
    def create(self, validated_data):
        """Create backup with additional logic"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        # Generate backup ID if not provided
        if 'backup_id' not in validated_data:
            validated_data['backup_id'] = uuid.uuid4()
        
        return super().create(validated_data)


class BackupRestorationSerializer(serializers.ModelSerializer):
    """Serializer for BackupRestoration"""
    restoration_type_display = serializers.CharField(source='get_restoration_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    backup_name = serializers.CharField(source='backup.name', read_only=True)
    initiated_by_username = serializers.CharField(source='initiated_by.username', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, allow_null=True)
    rollback_to_backup_name = serializers.CharField(source='rollback_to_backup.name', read_only=True, allow_null=True)
    duration_human = serializers.SerializerMethodField()
    restoration_successful = serializers.ReadOnlyField()
    
    class Meta:
        model = BackupRestoration
        fields = [
            'id', 'restoration_id', 'backup', 'backup_name',
            'restoration_type', 'restoration_type_display',
            'status', 'status_display', 'tables_to_restore',
            'restore_point', 'started_at', 'completed_at',
            'duration', 'duration_human', 'initiated_by',
            'initiated_by_username', 'reviewed_by', 'reviewed_by_username',
            'success', 'error_message', 'error_traceback',
            'verification_passed', 'verification_details',
            'rollback_enabled', 'rollback_performed',
            'rollback_to_backup', 'rollback_to_backup_name',
            'notes', 'metadata', 'restoration_successful'
        ]
        read_only_fields = [
            'restoration_id', 'started_at', 'completed_at', 'duration',
            'success', 'verification_passed', 'rollback_performed'
        ]
    
    def get_duration_human(self, obj):
        if obj.duration:
            if obj.duration < 60:
                return f"{obj.duration:.1f}s"
            elif obj.duration < 3600:
                return f"{obj.duration/60:.1f}m"
            else:
                return f"{obj.duration/3600:.1f}h"
        return 'N/A'
    
    def validate(self, data):
        """Validate restoration data"""
        # Validate tables to restore
        backup = data.get('backup')
        tables_to_restore = data.get('tables_to_restore', [])
        
        if backup and tables_to_restore:
            # Check if tables exist in backup
            backup_tables = backup.included_tables or []
            if backup_tables and backup_tables != ['*']:
                invalid_tables = set(tables_to_restore) - set(backup_tables)
                if invalid_tables:
                    raise serializers.ValidationError(
                        f"Tables not in backup: {', '.join(invalid_tables)}"
                    )
        
        return data


class BackupNotificationConfigSerializer(serializers.ModelSerializer):
    """Serializer for BackupNotificationConfig"""
    channel_display = serializers.SerializerMethodField()
    notification_type_display = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = BackupNotificationConfig
        fields = [
            'id', 'name', 'is_active', 'channels', 'channel_display',
            'channel_config', 'notification_types', 'notification_type_display',
            'recipients', 'failure_threshold', 'storage_threshold',
            'quiet_hours_start', 'quiet_hours_end', 'created_at', 'updated_at',
            'created_by', 'created_by_username'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_channel_display(self, obj):
        channel_names = {
            'email': 'Email',
            'slack': 'Slack',
            'telegram': 'Telegram',
            'webhook': 'Webhook',
            'sms': 'SMS',
            'push': 'Push Notification'
        }
        return [channel_names.get(channel, channel) for channel in obj.channels]
    
    def get_notification_type_display(self, obj):
        type_names = {
            'success': 'Backup Success',
            'failure': 'Backup Failure',
            'warning': 'Backup Warning',
            'health_alert': 'Health Alert',
            'storage_full': 'Storage Almost Full',
            'retention_alert': 'Retention Policy Alert'
        }
        return [type_names.get(ntype, ntype) for ntype in obj.notification_types]
    
    def validate(self, data):
        """Validate notification config"""
        # Validate channel config
        channels = data.get('channels', [])
        channel_config = data.get('channel_config', {})
        
        for channel in channels:
            if channel not in channel_config:
                raise serializers.ValidationError(
                    f"Configuration missing for channel: {channel}"
                )
        
        # Validate quiet hours
        quiet_start = data.get('quiet_hours_start')
        quiet_end = data.get('quiet_hours_end')
        
        if quiet_start and quiet_end and quiet_start == quiet_end:
            raise serializers.ValidationError(
                "Quiet hours start and end times cannot be the same"
            )
        
        return data


class RetentionPolicySerializer(serializers.ModelSerializer):
    """Serializer for RetentionPolicy"""
    policy_type_display = serializers.CharField(source='get_policy_type_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = RetentionPolicy
        fields = [
            'id', 'name', 'policy_type', 'policy_type_display',
            'is_active', 'daily_keep_days', 'weekly_keep_weeks',
            'monthly_keep_months', 'yearly_keep_years', 'custom_rules',
            'apply_to_all', 'apply_to_databases', 'apply_to_backup_types',
            'auto_cleanup', 'cleanup_schedule', 'dry_run',
            'notify_before_delete', 'notify_on_delete',
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DeltaBackupTrackerSerializer(serializers.ModelSerializer):
    """Serializer for DeltaBackupTracker"""
    base_backup_name = serializers.CharField(source='base_backup.name', read_only=True)
    chain_size_human = serializers.SerializerMethodField()
    
    class Meta:
        model = DeltaBackupTracker
        fields = [
            'id', 'chain_id', 'base_backup', 'base_backup_name',
            'chain_length', 'total_size', 'compressed_size', 'chain_size_human',
            'avg_delta_size', 'max_delta_size', 'needs_consolidation',
            'last_consolidation', 'created_at', 'updated_at'
        ]
        read_only_fields = ['chain_id', 'created_at', 'updated_at']
    
    def get_chain_size_human(self, obj):
        from django.template.defaultfilters import filesizeformat
        return filesizeformat(obj.total_size)
    
    def validate(self, data):
        """Validate delta tracker data"""
        base_backup = data.get('base_backup')
        
        if base_backup and base_backup.backup_type not in ['full', 'incremental']:
            raise serializers.ValidationError(
                "Base backup must be full or incremental type"
            )
        
        return data


class BackupProgressSerializer(serializers.Serializer):
    """Serializer for backup progress updates"""
    backup_id = serializers.UUIDField()
    status = serializers.CharField(max_length=20)
    percentage = serializers.IntegerField(min_value=0, max_value=100)
    current_step = serializers.CharField(max_length=200)
    started_at = serializers.DateTimeField(required=False)
    ended_at = serializers.DateTimeField(required=False)
    details = serializers.JSONField(required=False)


class BackupTaskRequestSerializer(serializers.Serializer):
    """Serializer for backup task requests"""
    backup_type = serializers.CharField(max_length=20, default='full')
    storage_type = serializers.CharField(max_length=20, default='local')
    encryption_type = serializers.CharField(max_length=20, default='none')
    compression_type = serializers.CharField(max_length=20, default='gzip')
    retention_days = serializers.IntegerField(min_value=1, default=30)
    tables = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=['*']
    )
    description = serializers.CharField(required=False, allow_blank=True)
    notification_channels = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=['email']
    )


class RestoreRequestSerializer(serializers.Serializer):
    """Serializer for restore requests"""
    backup_id = serializers.UUIDField()
    restore_type = serializers.CharField(max_length=20, default='full')
    tables = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    enable_maintenance = serializers.BooleanField(default=False)
    verify_before_restore = serializers.BooleanField(default=True)


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check requests"""
    backup_id = serializers.UUIDField()
    full_check = serializers.BooleanField(default=False)


class MaintenanceModeSerializer(serializers.Serializer):
    """Serializer for maintenance mode toggle"""
    enable = serializers.BooleanField()
    duration_hours = serializers.IntegerField(min_value=1, max_value=24, default=1)
    reason = serializers.CharField(required=False, allow_blank=True)