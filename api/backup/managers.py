"""
Backup Module Managers
Custom Django model managers for backup operations
"""
from django.db.models import Case
from django.db.models import CharField
from django.db.models import Value
from django.db.models import When

from django.db import models
from django.utils import timezone
from django.db.models import Q, F, Count, Avg, Sum, Max, Min
from django.core.cache import cache
from datetime import datetime, timedelta
import logging

from .constants import CACHE_KEY_PREFIX, CACHE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class BackupManager(models.Manager):
    """
    Custom manager for Backup model with advanced query methods
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'created_by',
            'backup_schedule',
            'retention_policy_ref',
            'parent_backup'
        ).prefetch_related(
            'verifications',
            'alerts',
            'encryption_info'
        )
    
    def healthy(self):
        """Get healthy backups (completed with good health score)"""
        return self.get_queryset().filter(
            status='completed',
            health_score__gte=80,
            expires_at__gt=timezone.now()
        )
    
    def unhealthy(self):
        """Get unhealthy backups (failed or poor health)"""
        now = timezone.now()
        return self.get_queryset().filter(
            Q(status='failed') |
            Q(health_score__lt=50) |
            Q(expires_at__lt=now)
        )
    
    def expired(self):
        """Get expired backups"""
        return self.get_queryset().filter(
            expires_at__lt=timezone.now(),
            is_permanent=False
        )
    
    def recent(self, hours=24):
        """Get recent backups within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_storage_type(self, storage_type):
        """Get backups by storage type"""
        return self.get_queryset().filter(storage_type=storage_type)
    
    def by_backup_type(self, backup_type):
        """Get backups by backup type"""
        return self.get_queryset().filter(backup_type=backup_type)
    
    def by_user(self, user):
        """Get backups created by specific user"""
        return self.get_queryset().filter(created_by=user)
    
    def large_backups(self, size_mb=100):
        """Get large backups (greater than specified MB)"""
        size_bytes = size_mb * 1024 * 1024
        return self.get_queryset().filter(file_size__gte=size_bytes)
    
    def long_running(self, minutes=60):
        """Get long-running backups (greater than specified minutes)"""
        duration_seconds = minutes * 60
        return self.get_queryset().filter(duration__gte=duration_seconds)
    
    def with_verifications(self):
        """Get backups that have verification records"""
        return self.get_queryset().filter(verifications__isnull=False).distinct()
    
    def without_verifications(self):
        """Get backups without verification records"""
        return self.get_queryset().filter(verifications__isnull=True)
    
    def with_alerts(self):
        """Get backups that have alerts"""
        return self.get_queryset().filter(alerts__isnull=False).distinct()
    
    def encrypted(self):
        """Get encrypted backups"""
        return self.get_queryset().filter(encryption_enabled=True)
    
    def unencrypted(self):
        """Get unencrypted backups"""
        return self.get_queryset().filter(encryption_enabled=False)
    
    def compressed(self):
        """Get compressed backups"""
        return self.get_queryset().filter(compression_enabled=True)
    
    def uncompressed(self):
        """Get uncompressed backups"""
        return self.get_queryset().filter(compression_enabled=False)
    
    def scheduled(self):
        """Get scheduled backups"""
        return self.get_queryset().filter(
            backup_type__in=['scheduled', 'automated']
        )
    
    def manual(self):
        """Get manual backups"""
        return self.get_queryset().filter(backup_type='manual')
    
    def by_status_group(self, group):
        """Get backups by status group"""
        if group == 'active':
            return self.get_queryset().filter(
                status__in=['pending', 'running', 'verifying', 'restoring']
            )
        elif group == 'completed':
            return self.get_queryset().filter(status='completed')
        elif group == 'failed':
            return self.get_queryset().filter(
                status__in=['failed', 'corrupted', 'cancelled']
            )
        elif group == 'pending':
            return self.get_queryset().filter(status='pending')
        return self.get_queryset()
    
    def performance_stats(self):
        """Get performance statistics for backups"""
        return self.get_queryset().aggregate(
            total_backups=Count('backup_id'),
            avg_duration=Avg('duration'),
            avg_file_size=Avg('file_size'),
            total_file_size=Sum('file_size'),
            avg_health_score=Avg('health_score'),
            success_rate=Count('backup_id', filter=Q(status='completed')) / Count('backup_id') * 100
        )
    
    def by_date_range(self, start_date, end_date):
        """Get backups within date range"""
        return self.get_queryset().filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def by_health_tier(self, tier):
        """Get backups by health tier"""
        if tier == 'excellent':
            return self.get_queryset().filter(health_score__gte=90)
        elif tier == 'good':
            return self.get_queryset().filter(
                health_score__gte=70,
                health_score__lt=90
            )
        elif tier == 'fair':
            return self.get_queryset().filter(
                health_score__gte=50,
                health_score__lt=70
            )
        elif tier == 'poor':
            return self.get_queryset().filter(health_score__lt=50)
        return self.get_queryset()


class BackupStorageLocationManager(models.Manager):
    """
    Custom manager for BackupStorageLocation model
    """
    
    def get_queryset(self):
        """Get base queryset with annotations"""
        return super().get_queryset().annotate(
            used_space_percentage=F('used_space') * 100.0 / F('total_space'),
            free_space_percentage=F('free_space') * 100.0 / F('total_space')
        )
    
    def active(self):
        """Get active storage locations"""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get inactive storage locations"""
        return self.get_queryset().filter(is_active=False)
    
    def by_storage_type(self, storage_type):
        """Get storage locations by type"""
        return self.get_queryset().filter(storage_type=storage_type)
    
    def healthy(self):
        """Get healthy storage locations"""
        return self.get_queryset().filter(health_status='healthy')
    
    def unhealthy(self):
        """Get unhealthy storage locations"""
        return self.get_queryset().filter(health_status__in=['warning', 'critical'])
    
    def nearly_full(self, threshold=80):
        """Get storage locations nearly full (above threshold percentage)"""
        return self.get_queryset().filter(used_space_percentage__gte=threshold)
    
    def with_space(self, required_space_gb):
        """Get storage locations with enough space"""
        required_space_bytes = required_space_gb * 1024 * 1024 * 1024
        return self.get_queryset().filter(free_space__gte=required_space_bytes)
    
    def encrypted_at_rest(self):
        """Get storage locations with encryption at rest"""
        return self.get_queryset().filter(encryption_at_rest=True)
    
    def ssl_required(self):
        """Get storage locations requiring SSL"""
        return self.get_queryset().filter(ssl_required=True)
    
    def by_performance_tier(self, tier):
        """Get storage locations by performance tier"""
        if tier == 'high':
            return self.get_queryset().filter(
                upload_speed_mbps__gte=100,
                download_speed_mbps__gte=100,
                latency_ms__lte=50
            )
        elif tier == 'medium':
            return self.get_queryset().filter(
                upload_speed_mbps__gte=10,
                download_speed_mbps__gte=10,
                latency_ms__lte=200
            )
        elif tier == 'low':
            return self.get_queryset().filter(
                upload_speed_mbps__lt=10,
                download_speed_mbps__lt=10
            )
        return self.get_queryset()
    
    def recently_checked(self, hours=24):
        """Get storage locations checked within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(last_checked__gte=cutoff_time)
    
    def not_checked_recently(self, hours=24):
        """Get storage locations not checked within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(last_checked__lt=cutoff_time)


class BackupRestorationManager(models.Manager):
    """
    Custom manager for BackupRestoration model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'backup',
            'initiated_by',
            'reviewed_by'
        )
    
    def successful(self):
        """Get successful restorations"""
        return self.get_queryset().filter(success=True)
    
    def failed(self):
        """Get failed restorations"""
        return self.get_queryset().filter(success=False)
    
    def by_status(self, status):
        """Get restorations by status"""
        return self.get_queryset().filter(status=status)
    
    def by_restoration_type(self, restoration_type):
        """Get restorations by type"""
        return self.get_queryset().filter(restoration_type=restoration_type)
    
    def by_user(self, user):
        """Get restorations initiated by user"""
        return self.get_queryset().filter(initiated_by=user)
    
    def recent(self, hours=24):
        """Get recent restorations within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def long_running(self, minutes=60):
        """Get long-running restorations"""
        duration_seconds = minutes * 60
        return self.get_queryset().filter(duration__gte=duration_seconds)
    
    def with_rollback(self):
        """Get restorations with rollback enabled"""
        return self.get_queryset().filter(rollback_enabled=True)
    
    def rollback_performed(self):
        """Get restorations where rollback was performed"""
        return self.get_queryset().filter(rollback_performed=True)
    
    def verified(self):
        """Get verified restorations"""
        return self.get_queryset().filter(verification_passed=True)
    
    def unverified(self):
        """Get unverified restorations"""
        return self.get_queryset().filter(verification_passed=False)
    
    def by_backup(self, backup):
        """Get restorations for specific backup"""
        return self.get_queryset().filter(backup=backup)
    
    def by_date_range(self, start_date, end_date):
        """Get restorations within date range"""
        return self.get_queryset().filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def performance_stats(self):
        """Get performance statistics for restorations"""
        return self.get_queryset().aggregate(
            total_restorations=Count('restoration_id'),
            avg_duration=Avg('duration'),
            success_rate=Count('restoration_id', filter=Q(success=True)) / Count('restoration_id') * 100,
            rollback_rate=Count('restoration_id', filter=Q(rollback_performed=True)) / Count('restoration_id') * 100
        )


class BackupVerificationManager(models.Manager):
    """
    Custom manager for BackupVerification model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'backup',
            'verified_by'
        )
    
    def valid(self):
        """Get valid verifications"""
        return self.get_queryset().filter(is_valid=True)
    
    def invalid(self):
        """Get invalid verifications"""
        return self.get_queryset().filter(is_valid=False)
    
    def by_method(self, verification_method):
        """Get verifications by method"""
        return self.get_queryset().filter(verification_method=verification_method)
    
    def by_user(self, user):
        """Get verifications by user"""
        return self.get_queryset().filter(verified_by=user)
    
    def recent(self, hours=24):
        """Get recent verifications within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(verified_at__gte=cutoff_time)
    
    def with_errors(self):
        """Get verifications with errors"""
        return self.get_queryset().filter(
            error_message__isnull=False
        ).exclude(error_message='')
    
    def checksum_failed(self):
        """Get verifications with checksum failures"""
        return self.get_queryset().filter(checksum_match=False)
    
    def size_failed(self):
        """Get verifications with size failures"""
        return self.get_queryset().filter(size_match=False)
    
    def by_backup(self, backup):
        """Get verifications for specific backup"""
        return self.get_queryset().filter(backup=backup)
    
    def by_date_range(self, start_date, end_date):
        """Get verifications within date range"""
        return self.get_queryset().filter(
            verified_at__date__gte=start_date,
            verified_at__date__lte=end_date
        )
    
    def verification_stats(self):
        """Get verification statistics"""
        return self.get_queryset().aggregate(
            total_verifications=Count('id'),
            valid_rate=Count('id', filter=Q(is_valid=True)) / Count('id') * 100,
            checksum_success_rate=Count('id', filter=Q(checksum_match=True)) / Count('id') * 100,
            size_success_rate=Count('id', filter=Q(size_match=True)) / Count('id') * 100
        )


class BackupAlertManager(models.Manager):
    """
    Custom manager for BackupAlert model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'backup',
            'resolved_by'
        )
    
    def unresolved(self):
        """Get unresolved alerts"""
        return self.get_queryset().filter(is_resolved=False)
    
    def resolved(self):
        """Get resolved alerts"""
        return self.get_queryset().filter(is_resolved=True)
    
    def by_alert_type(self, alert_type):
        """Get alerts by type"""
        return self.get_queryset().filter(alert_type=alert_type)
    
    def by_severity(self, severity):
        """Get alerts by severity"""
        return self.get_queryset().filter(severity=severity)
    
    def critical(self):
        """Get critical alerts"""
        return self.get_queryset().filter(severity='critical')
    
    def high(self):
        """Get high severity alerts"""
        return self.get_queryset().filter(severity='high')
    
    def medium(self):
        """Get medium severity alerts"""
        return self.get_queryset().filter(severity='medium')
    
    def low(self):
        """Get low severity alerts"""
        return self.get_queryset().filter(severity='low')
    
    def recent(self, hours=24):
        """Get recent alerts within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_user(self, user):
        """Get alerts resolved by user"""
        return self.get_queryset().filter(resolved_by=user)
    
    def by_backup(self, backup):
        """Get alerts for specific backup"""
        return self.get_queryset().filter(backup=backup)
    
    def by_date_range(self, start_date, end_date):
        """Get alerts within date range"""
        return self.get_queryset().filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def alert_stats(self):
        """Get alert statistics"""
        return self.get_queryset().aggregate(
            total_alerts=Count('id'),
            unresolved_count=Count('id', filter=Q(is_resolved=False)),
            critical_count=Count('id', filter=Q(severity='critical')),
            high_count=Count('id', filter=Q(severity='high')),
            resolution_rate=Count('id', filter=Q(is_resolved=True)) / Count('id') * 100
        )


class RetentionPolicyManager(models.Manager):
    """
    Custom manager for RetentionPolicy model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related('created_by')
    
    def active(self):
        """Get active retention policies"""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get inactive retention policies"""
        return self.get_queryset().filter(is_active=False)
    
    def by_policy_type(self, policy_type):
        """Get policies by type"""
        return self.get_queryset().filter(policy_type=policy_type)
    
    def keep_all_policies(self):
        """Get policies that keep all backups"""
        return self.get_queryset().filter(keep_all=True)
    
    def by_user(self, user):
        """Get policies created by user"""
        return self.get_queryset().filter(created_by=user)
    
    def by_retention_days(self, days):
        """Get policies with specific retention days"""
        return self.get_queryset().filter(retention_days=days)
    
    def gfs_policies(self):
        """Get GFS (Grandfather-Father-Son) policies"""
        return self.get_queryset().filter(
            policy_type='gfs'
        )
    
    def daily_policies(self):
        """Get daily retention policies"""
        return self.get_queryset().filter(
            policy_type='daily'
        )
    
    def weekly_policies(self):
        """Get weekly retention policies"""
        return self.get_queryset().filter(
            policy_type='weekly'
        )
    
    def monthly_policies(self):
        """Get monthly retention policies"""
        return self.get_queryset().filter(
            policy_type='monthly'
        )


class BackupLogManager(models.Manager):
    """
    Custom manager for BackupLog model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'backup',
            'restoration',
            'user'
        )
    
    def by_level(self, level):
        """Get logs by level"""
        return self.get_queryset().filter(level=level)
    
    def by_category(self, category):
        """Get logs by category"""
        return self.get_queryset().filter(category=category)
    
    def by_action(self, action):
        """Get logs by action"""
        return self.get_queryset().filter(action=action)
    
    def by_source(self, source):
        """Get logs by source"""
        return self.get_queryset().filter(source=source)
    
    def error_logs(self):
        """Get error logs"""
        return self.get_queryset().filter(level__in=['error', 'critical'])
    
    def security_logs(self):
        """Get security logs"""
        return self.get_queryset().filter(category='security')
    
    def performance_logs(self):
        """Get performance logs"""
        return self.get_queryset().filter(category='performance')
    
    def recent(self, hours=24):
        """Get recent logs within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(timestamp__gte=cutoff_time)
    
    def by_user(self, user):
        """Get logs by user"""
        return self.get_queryset().filter(user=user)
    
    def by_backup(self, backup):
        """Get logs for specific backup"""
        return self.get_queryset().filter(backup=backup)
    
    def by_date_range(self, start_date, end_date):
        """Get logs within date range"""
        return self.get_queryset().filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
    
    def with_errors(self):
        """Get logs with errors"""
        return self.get_queryset().filter(
            Q(error_code__isnull=False) |
            Q(error_message__isnull=False)
        ).exclude(
            Q(error_code='') &
            Q(error_message='')
        )
    
    def log_stats(self):
        """Get log statistics"""
        return self.get_queryset().aggregate(
            total_logs=Count('id'),
            error_count=Count('id', filter=Q(level__in=['error', 'critical'])),
            avg_duration=Avg('duration'),
            avg_memory_usage=Avg('memory_usage_mb')
        )


class DeltaBackupTrackerManager(models.Manager):
    """
    Custom manager for DeltaBackupTracker model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related(
            'parent_backup',
            'child_backup'
        )
    
    def by_parent_backup(self, backup):
        """Get trackers by parent backup"""
        return self.get_queryset().filter(parent_backup=backup)
    
    def by_child_backup(self, backup):
        """Get trackers by child backup"""
        return self.get_queryset().filter(child_backup=backup)
    
    def significant_changes(self, threshold=10):
        """Get trackers with significant changes (percentage above threshold)"""
        return self.get_queryset().filter(change_percentage__gte=threshold)
    
    def by_change_percentage_range(self, min_percentage, max_percentage):
        """Get trackers within change percentage range"""
        return self.get_queryset().filter(
            change_percentage__gte=min_percentage,
            change_percentage__lte=max_percentage
        )
    
    def by_changed_row_count_range(self, min_count, max_count):
        """Get trackers within row count range"""
        return self.get_queryset().filter(
            changed_row_count__gte=min_count,
            changed_row_count__lte=max_count
        )
    
    def by_table(self, table_name):
        """Get trackers for specific table"""
        return self.get_queryset().filter(
            changed_tables__contains=table_name
        )
    
    def recent(self, hours=24):
        """Get recent trackers within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_date_range(self, start_date, end_date):
        """Get trackers within date range"""
        return self.get_queryset().filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def change_stats(self):
        """Get change statistics"""
        return self.get_queryset().aggregate(
            total_trackers=Count('id'),
            avg_change_percentage=Avg('change_percentage'),
            avg_changed_rows=Avg('changed_row_count'),
            max_change_percentage=Max('change_percentage'),
            max_changed_rows=Max('changed_row_count')
        )


class BackupNotificationConfigManager(models.Manager):
    """
    Custom manager for BackupNotificationConfig model
    """
    
    def get_queryset(self):
        """Get base queryset with related objects"""
        return super().get_queryset().select_related('created_by')
    
    def active(self):
        """Get active notification configurations"""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get inactive notification configurations"""
        return self.get_queryset().filter(is_active=False)
    
    def failure_notifications(self):
        """Get configurations that notify on failure"""
        return self.get_queryset().filter(notify_on_failure=True)
    
    def warning_notifications(self):
        """Get configurations that notify on warning"""
        return self.get_queryset().filter(notify_on_warning=True)
    
    def success_notifications(self):
        """Get configurations that notify on success"""
        return self.get_queryset().filter(notify_on_success=True)
    
    def by_user(self, user):
        """Get configurations created by user"""
        return self.get_queryset().filter(created_by=user)
    
    def by_name(self, name):
        """Get configurations by name"""
        return self.get_queryset().filter(name__icontains=name)


# Specialized managers for specific use cases
class BackupAnalyticsManager(models.Manager):
    """
    Manager for analytics and reporting on backup data
    """
    
    def daily_backup_stats(self, days=30):
        """Get daily backup statistics for specified days"""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.get_queryset().filter(
            created_at__date__gte=cutoff_date
        ).values('created_at__date').annotate(
            total_backups=Count('backup_id'),
            successful_backups=Count('backup_id', filter=Q(status='completed')),
            failed_backups=Count('backup_id', filter=Q(status='failed')),
            total_size=Sum('file_size'),
            avg_duration=Avg('duration'),
            avg_health_score=Avg('health_score')
        ).order_by('created_at__date')
    
    def storage_usage_by_type(self):
        """Get storage usage statistics by storage type"""
        return self.get_queryset().values('storage_type').annotate(
            total_backups=Count('backup_id'),
            total_size=Sum('file_size'),
            avg_size=Avg('file_size'),
            success_rate=Count('backup_id', filter=Q(status='completed')) / Count('backup_id') * 100
        ).order_by('storage_type')
    
    def backup_type_performance(self):
        """Get performance statistics by backup type"""
        return self.get_queryset().values('backup_type').annotate(
            total_backups=Count('backup_id'),
            avg_duration=Avg('duration'),
            avg_file_size=Avg('file_size'),
            success_rate=Count('backup_id', filter=Q(status='completed')) / Count('backup_id') * 100
        ).order_by('backup_type')
    
    def user_activity_stats(self):
        """Get backup activity statistics by user"""
        return self.get_queryset().values('created_by__username').annotate(
            total_backups=Count('backup_id'),
            successful_backups=Count('backup_id', filter=Q(status='completed')),
            total_size=Sum('file_size'),
            avg_duration=Avg('duration')
        ).order_by('-total_backups')
    
    def health_score_distribution(self):
        """Get distribution of health scores"""
        return self.get_queryset().values(
            health_tier=Case(
                When(health_score__gte=90, then=Value('excellent')),
                When(health_score__gte=70, then=Value('good')),
                When(health_score__gte=50, then=Value('fair')),
                default=Value('poor'),
                output_field=CharField(),
            )
        ).annotate(
            count=Count('backup_id'),
            percentage=Count('backup_id') * 100.0 / Count('backup_id', filter=Q(health_score__isnull=False))
        ).order_by('health_tier')


class BackupMaintenanceManager(models.Manager):
    """
    Manager for backup maintenance operations
    """
    
    def cleanup_candidates(self, retention_days=30):
        """Get backup candidates for cleanup"""
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        return self.get_queryset().filter(
            created_at__lt=cutoff_date,
            is_permanent=False,
            status='completed'
        )
    
    def orphaned_backups(self):
        """Get potentially orphaned backups (no verification or alerts)"""
        return self.get_queryset().filter(
            verifications__isnull=True,
            alerts__isnull=True
        ).distinct()
    
    def duplicate_backups(self):
        """Get potentially duplicate backups (same checksum and size)"""
        return self.get_queryset().values('checksum', 'file_size').annotate(
            count=Count('backup_id')
        ).filter(count__gt=1)
    
    def verification_needed(self, hours=24):
        """Get backups that need verification"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(
            status='completed',
            created_at__lt=cutoff_time
        ).exclude(
            verifications__verified_at__gte=cutoff_time
        ).distinct()
    
    def storage_health_check_needed(self, hours=24):
        """Get storage locations that need health check"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        from .models import BackupStorageLocation
        return BackupStorageLocation.objects.filter(
            Q(last_checked__lt=cutoff_time) |
            Q(last_checked__isnull=True)
        )
