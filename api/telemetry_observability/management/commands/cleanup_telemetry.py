"""
Management command: cleanup_telemetry
Deletes old telemetry records beyond the retention window.

Usage:
  python manage.py cleanup_telemetry
  python manage.py cleanup_telemetry --days 30
  python manage.py cleanup_telemetry --dry-run
  python manage.py cleanup_telemetry --domain metrics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Delete telemetry records older than the retention period.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=None,
            help='Retention window in days (overrides TELEMETRY_RETENTION_DAYS setting).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show how many records would be deleted without deleting them.',
        )
        parser.add_argument(
            '--domain', choices=['metrics', 'logs', 'traces', 'alerts', 'all'],
            default='all',
            help='Which domain to clean up (default: all).',
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from api.telemetry_observability.models.metric_event import MetricEvent
        from api.telemetry_observability.models.log_entry    import LogEntry
        from api.telemetry_observability.models.trace_span   import TraceSpan
        from api.telemetry_observability.models.alert        import Alert

        retention_days = options['days'] or getattr(settings, 'TELEMETRY_RETENTION_DAYS', 90)
        dry_run        = options['dry_run']
        domain         = options['domain']
        cutoff         = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(
            self.style.WARNING(
                f"{'[DRY RUN] ' if dry_run else ''}Cleaning up records older than "
                f"{retention_days} days (before {cutoff.date()})."
            )
        )

        targets = {
            'metrics': (MetricEvent, MetricEvent.objects.filter(timestamp__lt=cutoff)),
            'logs':    (LogEntry,    LogEntry.objects.filter(timestamp__lt=cutoff)),
            'traces':  (TraceSpan,   TraceSpan.objects.filter(start_time__lt=cutoff)),
            'alerts':  (Alert,       Alert.objects.filter(
                                         triggered_at__lt=cutoff, status='resolved')),
        }

        domains = list(targets.keys()) if domain == 'all' else [domain]
        total   = 0

        for name in domains:
            _, qs    = targets[name]
            count    = qs.count()
            total   += count

            if dry_run:
                self.stdout.write(f"  {name}: {count} records would be deleted.")
            else:
                deleted, _ = qs.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"  {name}: {deleted} records deleted.")
                )

        action = 'would be deleted' if dry_run else 'deleted'
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal: {total} records {action}.")
        )
