"""
Django Management Command: Cleanup Old Alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from alerts.models.core import AlertLog, Notification
from alerts.models.channel import ChannelHealthLog, ChannelRateLimit
from alerts.models.incident import IncidentTimeline
from alerts.models.intelligence import AlertCorrelation, ThresholdHistory
from alerts.tasks.core import cleanup_old_alerts, cleanup_old_notifications

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old alert data and logs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete data older than N days (default: 90)'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['alerts', 'notifications', 'health_logs', 'timeline', 'correlations', 'thresholds', 'all'],
            default='all',
            help='Type of data to cleanup (default: all)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for deletion operations (default: 1000)'
        )
        parser.add_argument(
            '--keep-resolved',
            action='store_true',
            help='Keep resolved alerts, only delete unresolved ones'
        )
        parser.add_argument(
            '--keep-critical',
            action='store_true',
            help='Keep critical alerts, only delete non-critical ones'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        cleanup_type = options['type']
        dry_run = options['dry_run']
        force = options['force']
        batch_size = options['batch_size']
        keep_resolved = options['keep_resolved']
        keep_critical = options['keep_critical']
        
        self.stdout.write(self.style.SUCCESS(f'Cleaning up data older than {days} days'))
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        if cleanup_type == 'all':
            cleanup_types = ['alerts', 'notifications', 'health_logs', 'timeline', 'correlations', 'thresholds']
        else:
            cleanup_types = [cleanup_type]
        
        if not force and not dry_run:
            self.stdout.write(self.style.WARNING('This will permanently delete old data. Use --force to confirm or --dry-run to preview.'))
            return
        
        total_deleted = 0
        total_failed = 0
        
        for c_type in cleanup_types:
            try:
                deleted_count = self._cleanup_type(c_type, cutoff_date, dry_run, batch_size, keep_resolved, keep_critical)
                total_deleted += deleted_count
                self.stdout.write(f'  - {c_type}: {"would delete" if dry_run else "deleted"} {deleted_count} records')
            except Exception as e:
                total_failed += 1
                self.stdout.write(self.style.ERROR(f'  - {c_type}: failed - {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Cleanup complete:'))
        self.stdout.write(f'  - Cutoff date: {cutoff_date}')
        self.stdout.write(f'  - Types processed: {", ".join(cleanup_types)}')
        self.stdout.write(f'  - Total {"would be deleted" if dry_run else "deleted"}: {total_deleted}')
        self.stdout.write(f'  - Failed: {total_failed}')
        
        if not dry_run and total_deleted > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {total_deleted} old records'))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN - Would delete {total_deleted} records. Use --force to execute.'))
    
    def _cleanup_type(self, cleanup_type, cutoff_date, dry_run, batch_size, keep_resolved, keep_critical):
        """Clean up specific type of data"""
        
        if cleanup_type == 'alerts':
            return self._cleanup_alerts(cutoff_date, dry_run, batch_size, keep_resolved, keep_critical)
        elif cleanup_type == 'notifications':
            return self._cleanup_notifications(cutoff_date, dry_run, batch_size)
        elif cleanup_type == 'health_logs':
            return self._cleanup_health_logs(cutoff_date, dry_run, batch_size)
        elif cleanup_type == 'timeline':
            return self._cleanup_timeline(cutoff_date, dry_run, batch_size)
        elif cleanup_type == 'correlations':
            return self._cleanup_correlations(cutoff_date, dry_run, batch_size)
        elif cleanup_type == 'thresholds':
            return self._cleanup_thresholds(cutoff_date, dry_run, batch_size)
        
        return 0
    
    def _cleanup_alerts(self, cutoff_date, dry_run, batch_size, keep_resolved, keep_critical):
        """Clean up old alerts"""
        queryset = AlertLog.objects.filter(triggered_at__lt=cutoff_date)
        
        if keep_resolved:
            queryset = queryset.filter(is_resolved=False)
        
        if keep_critical:
            queryset = queryset.exclude(rule__severity='critical')
        
        count = queryset.count()
        
        if not dry_run and count > 0:
            # Delete in batches to avoid memory issues
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
    
    def _cleanup_notifications(self, cutoff_date, dry_run, batch_size):
        """Clean up old notifications"""
        queryset = Notification.objects.filter(created_at__lt=cutoff_date)
        count = queryset.count()
        
        if not dry_run and count > 0:
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
    
    def _cleanup_health_logs(self, cutoff_date, dry_run, batch_size):
        """Clean up old channel health logs"""
        queryset = ChannelHealthLog.objects.filter(checked_at__lt=cutoff_date)
        count = queryset.count()
        
        if not dry_run and count > 0:
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
    
    def _cleanup_timeline(self, cutoff_date, dry_run, batch_size):
        """Clean up old incident timeline events"""
        queryset = IncidentTimeline.objects.filter(timestamp__lt=cutoff_date)
        count = queryset.count()
        
        if not dry_run and count > 0:
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
    
    def _cleanup_correlations(self, cutoff_date, dry_run, batch_size):
        """Clean up old alert correlations"""
        queryset = AlertCorrelation.objects.filter(created_at__lt=cutoff_date)
        count = queryset.count()
        
        if not dry_run and count > 0:
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
    
    def _cleanup_thresholds(self, cutoff_date, dry_run, batch_size):
        """Clean up old threshold history"""
        queryset = ThresholdHistory.objects.filter(created_at__lt=cutoff_date)
        count = queryset.count()
        
        if not dry_run and count > 0:
            deleted = 0
            while queryset.exists():
                batch = queryset[:batch_size]
                deleted += batch.delete()[0]
            return deleted
        
        return count
