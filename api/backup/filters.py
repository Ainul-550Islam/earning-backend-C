"""
Backup Module Filters
Django REST Framework filters for backup and restoration queries
"""
from django.contrib.auth import get_user_model

import django_filters
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Backup, BackupRestoration, BackupVerification
from api.backup.models import BackupSchedule


class BackupFilter(django_filters.FilterSet):
    """
    Filter for Backup model with comprehensive filtering options
    """
    
    # Status filtering
    status = django_filters.ChoiceFilter(
        choices=Backup.STATUS_CHOICES,
        field_name='status',
        lookup_expr='exact',
        label='Backup Status'
    )
    
    # Backup type filtering
    backup_type = django_filters.ChoiceFilter(
        choices=Backup.BACKUP_TYPE_CHOICES,
        field_name='backup_type',
        lookup_expr='exact',
        label='Backup Type'
    )
    
    # Storage type filtering
    storage_type = django_filters.ChoiceFilter(
        choices=Backup.STORAGE_TYPE_CHOICES,
        field_name='storage_type',
        lookup_expr='exact',
        label='Storage Type'
    )
    
    # Date range filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    start_time = django_filters.DateTimeFromToRangeFilter(
        field_name='start_time',
        lookup_expr='range',
        label='Start Time Range'
    )
    
    end_time = django_filters.DateTimeFromToRangeFilter(
        field_name='end_time',
        lookup_expr='range',
        label='End Time Range'
    )
    
    # Size range filtering
    file_size_min = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='gte',
        label='Minimum File Size (bytes)'
    )
    
    file_size_max = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='lte',
        label='Maximum File Size (bytes)'
    )
    
    # Database filtering
    database_name = django_filters.CharFilter(
        field_name='database_name',
        lookup_expr='icontains',
        label='Database Name'
    )
    
    database_engine = django_filters.ChoiceFilter(
        choices=Backup.DATABASE_ENGINE_CHOICES,
        field_name='database_engine',
        lookup_expr='exact',
        label='Database Engine'
    )
    
    # User filtering
    created_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='created_by',
        label='Created By'
    )
    
    # Encryption filtering
    encryption_enabled = django_filters.BooleanFilter(
        field_name='encryption_enabled',
        label='Encryption Enabled'
    )
    
    encryption_type = django_filters.ChoiceFilter(
        choices=Backup.ENCRYPTION_TYPE_CHOICES,
        field_name='encryption_type',
        lookup_expr='exact',
        label='Encryption Type'
    )
    
    # Compression filtering
    compression_enabled = django_filters.BooleanFilter(
        field_name='compression_enabled',
        label='Compression Enabled'
    )
    
    compression_type = django_filters.ChoiceFilter(
        choices=Backup.COMPRESSION_TYPE_CHOICES,
        field_name='compression_type',
        lookup_expr='exact',
        label='Compression Type'
    )
    
    # Text search
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Backup Name'
    )
    
    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )
    
    # Health score filtering
    health_score_min = django_filters.NumberFilter(
        field_name='health_score',
        lookup_expr='gte',
        label='Minimum Health Score'
    )
    
    health_score_max = django_filters.NumberFilter(
        field_name='health_score',
        lookup_expr='lte',
        label='Maximum Health Score'
    )
    
    # Schedule filtering
    backup_schedule = django_filters.ModelChoiceFilter(
        queryset=BackupSchedule.objects.all(),
        field_name='backup_schedule',
        label='Backup Schedule'
    )
    
    # Retention filtering
    retention_days = django_filters.NumberFilter(
        field_name='retention_days',
        lookup_expr='exact',
        label='Retention Days'
    )
    
    # Parent backup filtering (for incremental/differential)
    parent_backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='parent_backup',
        label='Parent Backup'
    )
    
    # Tags filtering (if tags are implemented as JSONField)
    tags = django_filters.CharFilter(
        method='filter_tags',
        label='Tags'
    )
    
    # Duration filtering
    duration_min = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='gte',
        label='Minimum Duration (seconds)'
    )
    
    duration_max = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='lte',
        label='Maximum Duration (seconds)'
    )
    
    # Custom filter for tags
    def filter_tags(self, queryset, name, value):
        if value:
            # Assuming tags are stored as JSONField
            return queryset.filter(
                Q(tags__contains=value) |
                Q(tags__icontains=value)
            )
        return queryset
    
    class Meta:
        model = Backup
        fields = [
            'status', 'backup_type', 'storage_type', 'created_at',
            'start_time', 'end_time', 'file_size_min', 'file_size_max',
            'database_name', 'database_engine', 'created_by',
            'encryption_enabled', 'encryption_type', 'compression_enabled',
            'compression_type', 'name', 'description',
            'health_score_min', 'health_score_max', 'backup_schedule',
            'retention_days', 'parent_backup', 'tags',
            'duration_min', 'duration_max'
        ]


class RestoreFilter(django_filters.FilterSet):
    """
    Filter for BackupRestoration model with comprehensive filtering options
    """
    
    # Status filtering
    status = django_filters.ChoiceFilter(
        choices=BackupRestoration.STATUS_CHOICES,
        field_name='status',
        lookup_expr='exact',
        label='Restoration Status'
    )
    
    # Restoration type filtering
    restoration_type = django_filters.ChoiceFilter(
        choices=BackupRestoration.RESTORATION_TYPE_CHOICES,
        field_name='restoration_type',
        lookup_expr='exact',
        label='Restoration Type'
    )
    
    # Date range filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    started_at = django_filters.DateTimeFromToRangeFilter(
        field_name='started_at',
        lookup_expr='range',
        label='Started Date Range'
    )
    
    completed_at = django_filters.DateTimeFromToRangeFilter(
        field_name='completed_at',
        lookup_expr='range',
        label='Completed Date Range'
    )
    
    # Duration filtering
    duration_min = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='gte',
        label='Minimum Duration (seconds)'
    )
    
    duration_max = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='lte',
        label='Maximum Duration (seconds)'
    )
    
    # Backup filtering
    backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='backup',
        label='Backup'
    )
    
    backup_id = django_filters.UUIDFilter(
        field_name='backup__backup_id',
        lookup_expr='exact',
        label='Backup ID'
    )
    
    # User filtering
    initiated_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='initiated_by',
        label='Initiated By'
    )
    
    reviewed_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='reviewed_by',
        label='Reviewed By'
    )
    
    # Success filtering
    success = django_filters.BooleanFilter(
        field_name='success',
        label='Successful Restoration'
    )
    
    # Rollback filtering
    rollback_enabled = django_filters.BooleanFilter(
        field_name='rollback_enabled',
        label='Rollback Enabled'
    )
    
    rollback_performed = django_filters.BooleanFilter(
        field_name='rollback_performed',
        label='Rollback Performed'
    )
    
    # Verification filtering
    verification_passed = django_filters.BooleanFilter(
        field_name='verification_passed',
        label='Verification Passed'
    )
    
    # Tables to restore filtering
    tables_to_restore = django_filters.CharFilter(
        method='filter_tables_to_restore',
        label='Tables to Restore'
    )
    
    # Custom filter for tables_to_restore (assuming JSONField)
    def filter_tables_to_restore(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(tables_to_restore__contains=value) |
                Q(tables_to_restore__icontains=value)
            )
        return queryset
    
    class Meta:
        model = BackupRestoration
        fields = [
            'status', 'restoration_type', 'created_at',
            'started_at', 'completed_at', 'duration_min', 'duration_max',
            'backup', 'backup_id', 'initiated_by', 'reviewed_by',
            'success', 'rollback_enabled', 'rollback_performed',
            'verification_passed', 'tables_to_restore'
        ]


class VerificationFilter(django_filters.FilterSet):
    """
    Filter for BackupVerification model with comprehensive filtering options
    """
    
    # Verification method filtering
    verification_method = django_filters.ChoiceFilter(
        choices=BackupVerification.VERIFICATION_METHOD_CHOICES,
        field_name='verification_method',
        lookup_expr='exact',
        label='Verification Method'
    )
    
    # Validity filtering
    is_valid = django_filters.BooleanFilter(
        field_name='is_valid',
        label='Is Valid'
    )
    
    # Checksum match filtering
    checksum_match = django_filters.BooleanFilter(
        field_name='checksum_match',
        label='Checksum Match'
    )
    
    # Size match filtering
    size_match = django_filters.BooleanFilter(
        field_name='size_match',
        label='Size Match'
    )
    
    # Date range filtering
    verified_at = django_filters.DateTimeFromToRangeFilter(
        field_name='verified_at',
        lookup_expr='range',
        label='Verified Date Range'
    )
    
    # Backup filtering
    backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='backup',
        label='Backup'
    )
    
    backup_id = django_filters.UUIDFilter(
        field_name='backup__backup_id',
        lookup_expr='exact',
        label='Backup ID'
    )
    
    # User filtering
    verified_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='verified_by',
        label='Verified By'
    )
    
    # Error message filtering
    error_message = django_filters.CharFilter(
        field_name='error_message',
        lookup_expr='icontains',
        label='Error Message'
    )
    
    # Has error filtering
    has_error = django_filters.BooleanFilter(
        method='filter_has_error',
        label='Has Error'
    )
    
    def filter_has_error(self, queryset, name, value):
        if value:
            return queryset.filter(error_message__isnull=False).exclude(error_message='')
        return queryset
    
    class Meta:
        model = BackupVerification
        fields = [
            'verification_method', 'is_valid', 'checksum_match',
            'size_match', 'verified_at', 'backup', 'backup_id',
            'verified_by', 'error_message', 'has_error'
        ]


class BackupHealthFilter(django_filters.FilterSet):
    """
    Filter for backup health monitoring and analytics
    """
    
    # Health status filtering
    health_status = django_filters.ChoiceFilter(
        method='filter_health_status',
        choices=[
            ('healthy', 'Healthy'),
            ('unhealthy', 'Unhealthy'),
            ('warning', 'Warning'),
            ('failed', 'Failed'),
            ('expired', 'Expired')
        ],
        label='Health Status'
    )
    
    def filter_health_status(self, queryset, name, value):
        now = timezone.now()
        
        if value == 'healthy':
            return queryset.filter(
                status='completed',
                health_score__gte=80,
                expires_at__gt=now
            )
        elif value == 'unhealthy':
            return queryset.filter(
                Q(status='failed') |
                Q(health_score__lt=50) |
                Q(expires_at__lt=now)
            )
        elif value == 'warning':
            return queryset.filter(
                status='completed',
                health_score__gte=50,
                health_score__lt=80
            )
        elif value == 'failed':
            return queryset.filter(status='failed')
        elif value == 'expired':
            return queryset.filter(expires_at__lt=now)
        
        return queryset
    
    # Recent backups filtering
    recent_hours = django_filters.NumberFilter(
        method='filter_recent_hours',
        label='Recent Hours'
    )
    
    def filter_recent_hours(self, queryset, name, value):
        if value:
            cutoff_time = timezone.now() - timedelta(hours=value)
            return queryset.filter(created_at__gte=cutoff_time)
        return queryset
    
    # Large backups filtering
    large_size_mb = django_filters.NumberFilter(
        method='filter_large_size_mb',
        label='Large Size (MB)'
    )
    
    def filter_large_size_mb(self, queryset, name, value):
        if value:
            size_bytes = value * 1024 * 1024  # Convert MB to bytes
            return queryset.filter(file_size__gte=size_bytes)
        return queryset
    
    # Long running backups filtering
    long_duration_minutes = django_filters.NumberFilter(
        method='filter_long_duration_minutes',
        label='Long Duration (minutes)'
    )
    
    def filter_long_duration_minutes(self, queryset, name, value):
        if value:
            duration_seconds = value * 60  # Convert minutes to seconds
            return queryset.filter(duration__gte=duration_seconds)
        return queryset
    
    # Failed verifications filtering
    failed_verifications = django_filters.BooleanFilter(
        method='filter_failed_verifications',
        label='Failed Verifications'
    )
    
    def filter_failed_verifications(self, queryset, name, value):
        if value:
            backup_ids = BackupVerification.objects.filter(
                is_valid=False
            ).values_list('backup_id', flat=True)
            return queryset.filter(backup_id__in=backup_ids)
        return queryset
    
    class Meta:
        model = Backup
        fields = [
            'health_status', 'recent_hours', 'large_size_mb',
            'long_duration_minutes', 'failed_verifications'
        ]


# Import for ModelChoiceFilter
from django.contrib.auth import get_user_model
from .models import BackupSchedule, BackupStorageLocation, BackupAlert, RetentionPolicy, BackupNotificationConfig, BackupLog, DeltaBackupTracker


class BackupStorageLocationFilter(django_filters.FilterSet):
    """
    Filter for BackupStorageLocation model with comprehensive filtering options
    """
    
    # Storage type filtering
    storage_type = django_filters.ChoiceFilter(
        choices=BackupStorageLocation.STORAGE_TYPE_CHOICES,
        field_name='storage_type',
        lookup_expr='exact',
        label='Storage Type'
    )
    
    # Active status filtering
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label='Is Active'
    )
    
    # Health status filtering
    health_status = django_filters.ChoiceFilter(
        choices=BackupStorageLocation.HEALTH_STATUS_CHOICES,
        field_name='health_status',
        lookup_expr='exact',
        label='Health Status'
    )
    
    # Capacity filtering
    used_space_percentage_min = django_filters.NumberFilter(
        method='filter_used_space_percentage_min',
        label='Minimum Used Space Percentage'
    )
    
    def filter_used_space_percentage_min(self, queryset, name, value):
        if value:
            return queryset.filter(
                used_space__gte=django_models.F('total_space') * value / 100
            )
        return queryset
    
    used_space_percentage_max = django_filters.NumberFilter(
        method='filter_used_space_percentage_max',
        label='Maximum Used Space Percentage'
    )
    
    def filter_used_space_percentage_max(self, queryset, name, value):
        if value:
            return queryset.filter(
                used_space__lte=django_models.F('total_space') * value / 100
            )
        return queryset
    
    # Performance filtering
    upload_speed_min = django_filters.NumberFilter(
        field_name='upload_speed_mbps',
        lookup_expr='gte',
        label='Minimum Upload Speed (Mbps)'
    )
    
    download_speed_min = django_filters.NumberFilter(
        field_name='download_speed_mbps',
        lookup_expr='gte',
        label='Minimum Download Speed (Mbps)'
    )
    
    latency_max = django_filters.NumberFilter(
        field_name='latency_ms',
        lookup_expr='lte',
        label='Maximum Latency (ms)'
    )
    
    # Security filtering
    encryption_at_rest = django_filters.BooleanFilter(
        field_name='encryption_at_rest',
        label='Encryption at Rest'
    )
    
    encryption_in_transit = django_filters.BooleanFilter(
        field_name='encryption_in_transit',
        label='Encryption in Transit'
    )
    
    ssl_required = django_filters.BooleanFilter(
        field_name='ssl_required',
        label='SSL Required'
    )
    
    # Text search
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Storage Location Name'
    )
    
    endpoint = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        label='Endpoint'
    )
    
    # Date filtering
    last_checked = django_filters.DateTimeFromToRangeFilter(
        field_name='last_checked',
        lookup_expr='range',
        label='Last Checked Date Range'
    )
    
    class Meta:
        model = BackupStorageLocation
        fields = [
            'storage_type', 'is_active', 'health_status',
            'used_space_percentage_min', 'used_space_percentage_max',
            'upload_speed_min', 'download_speed_min', 'latency_max',
            'encryption_at_rest', 'encryption_in_transit', 'ssl_required',
            'name', 'endpoint', 'last_checked'
        ]


class BackupAlertFilter(django_filters.FilterSet):
    """
    Filter for BackupAlert model with comprehensive filtering options
    """
    
    # Alert type filtering
    alert_type = django_filters.ChoiceFilter(
        choices=BackupAlert.ALERT_TYPE_CHOICES,
        field_name='alert_type',
        lookup_expr='exact',
        label='Alert Type'
    )
    
    # Severity filtering
    severity = django_filters.ChoiceFilter(
        choices=BackupAlert.SEVERITY_CHOICES,
        field_name='severity',
        lookup_expr='exact',
        label='Severity'
    )
    
    # Resolution status filtering
    is_resolved = django_filters.BooleanFilter(
        field_name='is_resolved',
        label='Is Resolved'
    )
    
    # Date range filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    resolved_at = django_filters.DateTimeFromToRangeFilter(
        field_name='resolved_at',
        lookup_expr='range',
        label='Resolved Date Range'
    )
    
    # Backup filtering
    backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='backup',
        label='Backup'
    )
    
    backup_id = django_filters.UUIDFilter(
        field_name='backup__backup_id',
        lookup_expr='exact',
        label='Backup ID'
    )
    
    # User filtering
    resolved_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='resolved_by',
        label='Resolved By'
    )
    
    # Text search
    message = django_filters.CharFilter(
        field_name='message',
        lookup_expr='icontains',
        label='Message'
    )
    
    # Recent alerts filtering
    recent_hours = django_filters.NumberFilter(
        method='filter_recent_hours',
        label='Recent Hours'
    )
    
    def filter_recent_hours(self, queryset, name, value):
        if value:
            cutoff_time = timezone.now() - timedelta(hours=value)
            return queryset.filter(created_at__gte=cutoff_time)
        return queryset
    
    class Meta:
        model = BackupAlert
        fields = [
            'alert_type', 'severity', 'is_resolved', 'created_at',
            'resolved_at', 'backup', 'backup_id', 'resolved_by',
            'message', 'recent_hours'
        ]


class RetentionPolicyFilter(django_filters.FilterSet):
    """
    Filter for RetentionPolicy model with comprehensive filtering options
    """
    
    # Policy type filtering
    policy_type = django_filters.ChoiceFilter(
        choices=RetentionPolicy.POLICY_TYPE_CHOICES,
        field_name='policy_type',
        lookup_expr='exact',
        label='Policy Type'
    )
    
    # Boolean filtering
    keep_all = django_filters.BooleanFilter(
        field_name='keep_all',
        label='Keep All'
    )
    
    is_active = django_filters.BooleanFilter(
        method='filter_is_active',
        label='Is Active'
    )
    
    def filter_is_active(self, queryset, name, value):
        if value is True:
            return queryset.filter(is_active=True)
        elif value is False:
            return queryset.filter(is_active=False)
        return queryset
    
    # Retention periods filtering
    keep_daily_min = django_filters.NumberFilter(
        field_name='keep_daily',
        lookup_expr='gte',
        label='Minimum Keep Daily'
    )
    
    keep_weekly_min = django_filters.NumberFilter(
        field_name='keep_weekly',
        lookup_expr='gte',
        label='Minimum Keep Weekly'
    )
    
    keep_monthly_min = django_filters.NumberFilter(
        field_name='keep_monthly',
        lookup_expr='gte',
        label='Minimum Keep Monthly'
    )
    
    keep_yearly_min = django_filters.NumberFilter(
        field_name='keep_yearly',
        lookup_expr='gte',
        label='Minimum Keep Yearly'
    )
    
    # Text search
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Policy Name'
    )
    
    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )
    
    # User filtering
    created_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='created_by',
        label='Created By'
    )
    
    # Date filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    class Meta:
        model = RetentionPolicy
        fields = [
            'policy_type', 'keep_all', 'is_active',
            'keep_daily_min', 'keep_weekly_min', 'keep_monthly_min', 'keep_yearly_min',
            'name', 'description', 'created_by', 'created_at'
        ]


class BackupLogFilter(django_filters.FilterSet):
    """
    Filter for BackupLog model with comprehensive filtering options
    """
    
    # Log level filtering
    level = django_filters.ChoiceFilter(
        choices=BackupLog.LEVEL_CHOICES,
        field_name='level',
        lookup_expr='exact',
        label='Log Level'
    )
    
    # Category filtering
    category = django_filters.ChoiceFilter(
        choices=BackupLog.CATEGORY_CHOICES,
        field_name='category',
        lookup_expr='exact',
        label='Category'
    )
    
    # Action filtering
    action = django_filters.ChoiceFilter(
        choices=BackupLog.ACTION_CHOICES,
        field_name='action',
        lookup_expr='exact',
        label='Action'
    )
    
    # Source filtering
    source = django_filters.ChoiceFilter(
        choices=BackupLog.SOURCE_CHOICES,
        field_name='source',
        lookup_expr='exact',
        label='Source'
    )
    
    # Date range filtering
    timestamp = django_filters.DateTimeFromToRangeFilter(
        field_name='timestamp',
        lookup_expr='range',
        label='Timestamp Range'
    )
    
    # Backup filtering
    backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='backup',
        label='Backup'
    )
    
    backup_id = django_filters.UUIDFilter(
        field_name='backup__backup_id',
        lookup_expr='exact',
        label='Backup ID'
    )
    
    # Restoration filtering
    restoration = django_filters.ModelChoiceFilter(
        queryset=BackupRestoration.objects.all(),
        field_name='restoration',
        label='Restoration'
    )
    
    # User filtering
    user = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='user',
        label='User'
    )
    
    # Performance filtering
    duration_min = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='gte',
        label='Minimum Duration (seconds)'
    )
    
    duration_max = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='lte',
        label='Maximum Duration (seconds)'
    )
    
    memory_usage_min = django_filters.NumberFilter(
        field_name='memory_usage_mb',
        lookup_expr='gte',
        label='Minimum Memory Usage (MB)'
    )
    
    memory_usage_max = django_filters.NumberFilter(
        field_name='memory_usage_mb',
        lookup_expr='lte',
        label='Maximum Memory Usage (MB)'
    )
    
    # Error filtering
    has_error = django_filters.BooleanFilter(
        method='filter_has_error',
        label='Has Error'
    )
    
    def filter_has_error(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(error_code__isnull=False) |
                Q(error_message__isnull=False)
            ).exclude(
                Q(error_code='') &
                Q(error_message='')
            )
        return queryset
    
    error_code = django_filters.CharFilter(
        field_name='error_code',
        lookup_expr='icontains',
        label='Error Code'
    )
    
    error_message = django_filters.CharFilter(
        field_name='error_message',
        lookup_expr='icontains',
        label='Error Message'
    )
    
    # Text search
    message = django_filters.CharFilter(
        field_name='message',
        lookup_expr='icontains',
        label='Message'
    )
    
    # Recent logs filtering
    recent_hours = django_filters.NumberFilter(
        method='filter_recent_hours',
        label='Recent Hours'
    )
    
    def filter_recent_hours(self, queryset, name, value):
        if value:
            cutoff_time = timezone.now() - timedelta(hours=value)
            return queryset.filter(timestamp__gte=cutoff_time)
        return queryset
    
    class Meta:
        model = BackupLog
        fields = [
            'level', 'category', 'action', 'source', 'timestamp',
            'backup', 'backup_id', 'restoration', 'user',
            'duration_min', 'duration_max', 'memory_usage_min', 'memory_usage_max',
            'has_error', 'error_code', 'error_message', 'message', 'recent_hours'
        ]


class DeltaBackupTrackerFilter(django_filters.FilterSet):
    """
    Filter for DeltaBackupTracker model with comprehensive filtering options
    """
    
    # Parent backup filtering
    parent_backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='parent_backup',
        label='Parent Backup'
    )
    
    parent_backup_id = django_filters.UUIDFilter(
        field_name='parent_backup__backup_id',
        lookup_expr='exact',
        label='Parent Backup ID'
    )
    
    # Child backup filtering
    child_backup = django_filters.ModelChoiceFilter(
        queryset=Backup.objects.all(),
        field_name='child_backup',
        label='Child Backup'
    )
    
    child_backup_id = django_filters.UUIDFilter(
        field_name='child_backup__backup_id',
        lookup_expr='exact',
        label='Child Backup ID'
    )
    
    # Change metrics filtering
    changed_row_count_min = django_filters.NumberFilter(
        field_name='changed_row_count',
        lookup_expr='gte',
        label='Minimum Changed Row Count'
    )
    
    changed_row_count_max = django_filters.NumberFilter(
        field_name='changed_row_count',
        lookup_expr='lte',
        label='Maximum Changed Row Count'
    )
    
    change_percentage_min = django_filters.NumberFilter(
        field_name='change_percentage',
        lookup_expr='gte',
        label='Minimum Change Percentage'
    )
    
    change_percentage_max = django_filters.NumberFilter(
        field_name='change_percentage',
        lookup_expr='lte',
        label='Maximum Change Percentage'
    )
    
    # Tables filtering
    changed_tables = django_filters.CharFilter(
        method='filter_changed_tables',
        label='Changed Tables'
    )
    
    def filter_changed_tables(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(changed_tables__contains=value) |
                Q(changed_tables__icontains=value)
            )
        return queryset
    
    # Date filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    class Meta:
        model = DeltaBackupTracker
        fields = [
            'parent_backup', 'parent_backup_id', 'child_backup', 'child_backup_id',
            'changed_row_count_min', 'changed_row_count_max',
            'change_percentage_min', 'change_percentage_max',
            'changed_tables', 'created_at'
        ]


class BackupNotificationConfigFilter(django_filters.FilterSet):
    """
    Filter for BackupNotificationConfig model with comprehensive filtering options
    """
    
    # Boolean filtering
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label='Is Active'
    )
    
    notify_on_failure = django_filters.BooleanFilter(
        field_name='notify_on_failure',
        label='Notify on Failure'
    )
    
    notify_on_warning = django_filters.BooleanFilter(
        field_name='notify_on_warning',
        label='Notify on Warning'
    )
    
    notify_on_success = django_filters.BooleanFilter(
        field_name='notify_on_success',
        label='Notify on Success'
    )
    
    # Text search
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Configuration Name'
    )
    
    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )
    
    # User filtering
    created_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        field_name='created_by',
        label='Created By'
    )
    
    # Date filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    class Meta:
        model = BackupNotificationConfig
        fields = [
            'is_active', 'notify_on_failure', 'notify_on_warning',
            'notify_on_success', 'name', 'description',
            'created_by', 'created_at'
        ]


# Advanced combined filters
class BackupAdvancedFilter(django_filters.FilterSet):
    """
    Advanced filter for Backup model with complex filtering capabilities
    """
    
    # Inherit all basic filters
    status = django_filters.ChoiceFilter(
        choices=Backup.STATUS_CHOICES,
        field_name='status',
        lookup_expr='exact',
        label='Backup Status'
    )
    
    backup_type = django_filters.ChoiceFilter(
        choices=Backup.BACKUP_TYPE_CHOICES,
        field_name='backup_type',
        lookup_expr='exact',
        label='Backup Type'
    )
    
    storage_type = django_filters.ChoiceFilter(
        choices=Backup.STORAGE_TYPE_CHOICES,
        field_name='storage_type',
        lookup_expr='exact',
        label='Storage Type'
    )
    
    # Advanced date filtering
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        lookup_expr='range',
        label='Created Date Range'
    )
    
    # Advanced search
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search (name, description, database)'
    )
    
    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(description__icontains=value) |
                Q(database_name__icontains=value) |
                Q(tags__icontains=value)
            )
        return queryset
    
    # Complex status filtering
    status_group = django_filters.ChoiceFilter(
        method='filter_status_group',
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('pending', 'Pending')
        ],
        label='Status Group'
    )
    
    def filter_status_group(self, queryset, name, value):
        if value == 'active':
            return queryset.filter(status__in=['pending', 'running', 'verifying', 'restoring'])
        elif value == 'completed':
            return queryset.filter(status='completed')
        elif value == 'failed':
            return queryset.filter(status__in=['failed', 'corrupted', 'cancelled'])
        elif value == 'pending':
            return queryset.filter(status='pending')
        return queryset
    
    # Performance filtering
    performance_tier = django_filters.ChoiceFilter(
        method='filter_performance_tier',
        choices=[
            ('fast', 'Fast (< 1 min)'),
            ('normal', 'Normal (1-10 min)'),
            ('slow', 'Slow (> 10 min)')
        ],
        label='Performance Tier'
    )
    
    def filter_performance_tier(self, queryset, name, value):
        if value == 'fast':
            return queryset.filter(duration__lt=60)
        elif value == 'normal':
            return queryset.filter(duration__gte=60, duration__lte=600)
        elif value == 'slow':
            return queryset.filter(duration__gt=600)
        return queryset
    
    # Size tier filtering
    size_tier = django_filters.ChoiceFilter(
        method='filter_size_tier',
        choices=[
            ('small', 'Small (< 100 MB)'),
            ('medium', 'Medium (100 MB - 1 GB)'),
            ('large', 'Large (> 1 GB)')
        ],
        label='Size Tier'
    )
    
    def filter_size_tier(self, queryset, name, value):
        if value == 'small':
            return queryset.filter(file_size__lt=100 * 1024 * 1024)
        elif value == 'medium':
            return queryset.filter(
                file_size__gte=100 * 1024 * 1024,
                file_size__lte=1024 * 1024 * 1024
            )
        elif value == 'large':
            return queryset.filter(file_size__gt=1024 * 1024 * 1024)
        return queryset
    
    # Health filtering
    health_tier = django_filters.ChoiceFilter(
        method='filter_health_tier',
        choices=[
            ('excellent', 'Excellent (90-100)'),
            ('good', 'Good (70-89)'),
            ('fair', 'Fair (50-69)'),
            ('poor', 'Poor (< 50)')
        ],
        label='Health Tier'
    )
    
    def filter_health_tier(self, queryset, name, value):
        if value == 'excellent':
            return queryset.filter(health_score__gte=90)
        elif value == 'good':
            return queryset.filter(health_score__gte=70, health_score__lt=90)
        elif value == 'fair':
            return queryset.filter(health_score__gte=50, health_score__lt=70)
        elif value == 'poor':
            return queryset.filter(health_score__lt=50)
        return queryset
    
    # Recent activity filtering
    last_hours = django_filters.NumberFilter(
        method='filter_last_hours',
        label='Last Hours'
    )
    
    def filter_last_hours(self, queryset, name, value):
        if value:
            cutoff_time = timezone.now() - timedelta(hours=value)
            return queryset.filter(created_at__gte=cutoff_time)
        return queryset
    
    # Has verification filtering
    has_verification = django_filters.BooleanFilter(
        method='filter_has_verification',
        label='Has Verification'
    )
    
    def filter_has_verification(self, queryset, name, value):
        if value:
            backup_ids = BackupVerification.objects.values_list('backup_id', flat=True)
            return queryset.filter(backup_id__in=backup_ids)
        else:
            backup_ids = BackupVerification.objects.values_list('backup_id', flat=True)
            return queryset.exclude(backup_id__in=backup_ids)
    
    # Has alerts filtering
    has_alerts = django_filters.BooleanFilter(
        method='filter_has_alerts',
        label='Has Alerts'
    )
    
    def filter_has_alerts(self, queryset, name, value):
        if value:
            backup_ids = BackupAlert.objects.values_list('backup_id', flat=True)
            return queryset.filter(backup_id__in=backup_ids)
        else:
            backup_ids = BackupAlert.objects.values_list('backup_id', flat=True)
            return queryset.exclude(backup_id__in=backup_ids)
    
    class Meta:
        model = Backup
        fields = [
            'status', 'backup_type', 'storage_type', 'created_at',
            'search', 'status_group', 'performance_tier', 'size_tier',
            'health_tier', 'last_hours', 'has_verification', 'has_alerts'
        ]


# Import missing django models
from django.db import models as django_models
