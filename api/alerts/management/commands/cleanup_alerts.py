"""
Django Management Command: Cleanup Old Alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from api.alerts.models.core import AlertLog, Notification
from api.alerts.models.channel import ChannelHealthLog
from api.alerts.models.incident import IncidentTimeline
from api.alerts.models.intelligence import AlertCorrelation
from api.alerts.models.threshold import ThresholdHistory

logger = logging.getLogger(__name__)

ALL_DATA_TYPES = ['alerts', 'notifications', 'health_logs', 'timeline', 'correlations', 'thresholds']


class Command(BaseCommand):
    help = 'Clean up old alert data and logs'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Delete data older than N days (default: 90)')
        parser.add_argument('--data-type', type=str,
                             choices=ALL_DATA_TYPES + ['all'], default='all',
                             help='Type of data to cleanup (default: all)')
        parser.add_argument('--exclude', type=str, help='Comma-separated data types to exclude from cleanup')
        parser.add_argument('--dry-run', action='store_true',
                             help='Show what would be deleted without actually deleting')
        parser.add_argument('--batch-size', type=int, default=1000,
                             help='Batch size for deletion operations (default: 1000)')
        parser.add_argument('--keep-resolved', action='store_true',
                             help='Keep resolved alerts, only delete unresolved ones')
        parser.add_argument('--keep-critical', action='store_true',
                             help='Keep critical alerts, only delete non-critical ones')

    def handle(self, *args, **options):
        days = options['days']
        data_type = options['data_type']
        exclude = options.get('exclude')
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        keep_resolved = options['keep_resolved']
        keep_critical = options['keep_critical']

        self.stdout.write(self.style.SUCCESS('Cleaning up old alert data'))
        self.stdout.write(f'Days: {days}')
        self.stdout.write(f'Data type: {data_type}')
        self.stdout.write(f'Batch size: {batch_size}')

        cutoff_date = timezone.now() - timedelta(days=days)

        if data_type == 'all':
            data_types = list(ALL_DATA_TYPES)
        else:
            data_types = [data_type]

        excluded_types = []
        if exclude:
            excluded_types = [t.strip() for t in exclude.split(',')]
            self.stdout.write(f'Excluding: {", ".join(excluded_types)}')
            data_types = [t for t in data_types if t not in excluded_types]

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no data will be deleted'))

        total_deleted = 0
        total_failed = 0
        batches_processed = 0
        any_data_found = False

        for c_type in data_types:
            try:
                count, batches = self._cleanup_type(
                    c_type, cutoff_date, dry_run, batch_size, keep_resolved, keep_critical
                )
                batches_processed += batches
                if count > 0:
                    any_data_found = True
                total_deleted += count
                verb = 'Would delete' if dry_run else 'Deleted'
                self.stdout.write(f'  - {c_type}: {verb} {count} records')
            except Exception as e:
                total_failed += 1
                self.stdout.write(self.style.ERROR(f'  - {c_type}: failed - {str(e)}'))

        if not any_data_found and total_failed == 0:
            self.stdout.write(self.style.WARNING('No data found to cleanup'))
            return

        self.stdout.write(self.style.SUCCESS('Cleanup complete:'))
        self.stdout.write(f'  - Cutoff date: {cutoff_date}')
        self.stdout.write(f'  - Types processed: {", ".join(data_types)}')
        self.stdout.write(f'  - Batches processed: {batches_processed}')
        self.stdout.write(f'  - Failed: {total_failed}')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN - Would delete {total_deleted} records total.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Deleted {total_deleted} old records total'))

    def _cleanup_type(self, cleanup_type, cutoff_date, dry_run, batch_size, keep_resolved, keep_critical):
        """Clean up specific type of data. Returns (count, batches_processed)."""
        if cleanup_type == 'alerts':
            return self._delete_in_batches(self._alerts_queryset(cutoff_date, keep_resolved, keep_critical), dry_run, batch_size)
        elif cleanup_type == 'notifications':
            return self._delete_in_batches(Notification.objects.filter(created_at__lt=cutoff_date), dry_run, batch_size)
        elif cleanup_type == 'health_logs':
            return self._delete_in_batches(ChannelHealthLog.objects.filter(checked_at__lt=cutoff_date), dry_run, batch_size)
        elif cleanup_type == 'timeline':
            return self._delete_in_batches(IncidentTimeline.objects.filter(timestamp__lt=cutoff_date), dry_run, batch_size)
        elif cleanup_type == 'correlations':
            return self._delete_in_batches(AlertCorrelation.objects.filter(created_at__lt=cutoff_date), dry_run, batch_size)
        elif cleanup_type == 'thresholds':
            return self._delete_in_batches(ThresholdHistory.objects.filter(created_at__lt=cutoff_date), dry_run, batch_size)
        return 0, 0

    def _alerts_queryset(self, cutoff_date, keep_resolved, keep_critical):
        queryset = AlertLog.objects.filter(triggered_at__lt=cutoff_date)
        if keep_resolved:
            queryset = queryset.filter(is_resolved=False)
        if keep_critical:
            queryset = queryset.exclude(rule__severity='critical')
        return queryset

    def _delete_in_batches(self, queryset, dry_run, batch_size):
        count = queryset.count()
        if dry_run or count == 0:
            return count, (1 if count else 0)

        deleted = 0
        batches = 0
        pks = list(queryset.values_list('pk', flat=True))
        model = queryset.model
        for i in range(0, len(pks), batch_size):
            batch_pks = pks[i:i + batch_size]
            deleted += model.objects.filter(pk__in=batch_pks).delete()[0]
            batches += 1
        return deleted, batches
