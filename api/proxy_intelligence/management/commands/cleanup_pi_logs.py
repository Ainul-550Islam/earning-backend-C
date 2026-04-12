"""
Management Command: cleanup_pi_logs
Usage: python manage.py cleanup_pi_logs [--days <n>] [--dry-run] [--stats]

Removes old API request logs, performance metrics, and velocity metrics
to keep the database lean and fast.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old proxy intelligence logs and performance metrics'

    # Default retention days per model
    DEFAULT_RETENTION = {
        'APIRequestLog':    30,
        'PerformanceMetric': 90,
        'VelocityMetric':   7,
        'AnomalyDetectionLog': 90,
        'VPNDetectionLog':  90,
        'ProxyDetectionLog': 90,
        'SystemAuditTrail': 365,   # Keep audit trail longer
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=None,
            help='Delete records older than N days (overrides per-model defaults)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Count records to delete without actually deleting them'
        )
        parser.add_argument(
            '--stats', action='store_true',
            help='Show current database size statistics before and after'
        )
        parser.add_argument(
            '--model',
            choices=list(self.DEFAULT_RETENTION.keys()) + ['all'],
            default='all',
            help='Specific model to clean up (default: all)'
        )
        parser.add_argument(
            '--batch-size', type=int, default=5000,
            help='Number of records to delete per batch (default: 5000)'
        )

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        days_override = options['days']
        model_filter  = options['model']
        batch_size    = options['batch_size']

        self.stdout.write(self.style.NOTICE(
            f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
            f'Starting log cleanup...'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No records will be deleted.\n'))

        # ── Show pre-cleanup stats ───────────────────────────────────────
        if options['stats']:
            self._show_stats('Before cleanup')

        # ── Determine which models to clean ─────────────────────────────
        if model_filter == 'all':
            models_to_clean = self.DEFAULT_RETENTION.items()
        else:
            models_to_clean = [(model_filter, self.DEFAULT_RETENTION[model_filter])]

        total_deleted = 0
        total_would_delete = 0

        for model_name, default_days in models_to_clean:
            days = days_override if days_override is not None else default_days
            cutoff = timezone.now() - timedelta(days=days)

            self.stdout.write(f'\n  {model_name} (>{days}d old):')

            try:
                deleted, would_delete = self._cleanup_model(
                    model_name, cutoff, dry_run, batch_size
                )
                total_deleted      += deleted
                total_would_delete += would_delete

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f'    ~ Would delete: {would_delete:,} records')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ Deleted: {deleted:,} records')
                    )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error: {e}'))
                logger.error(f'Cleanup failed for {model_name}: {e}')

        # ── Summary ──────────────────────────────────────────────────────
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would delete {total_would_delete:,} total records.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Cleanup complete. Deleted {total_deleted:,} records.'
            ))

        # ── Post-cleanup stats ───────────────────────────────────────────
        if options['stats'] and not dry_run:
            self._show_stats('After cleanup')

    def _cleanup_model(self, model_name: str, cutoff,
                        dry_run: bool, batch_size: int) -> tuple:
        """
        Delete records older than cutoff for a given model.
        Uses batch deletion to avoid locking the table for too long.

        Returns: (deleted_count, would_delete_count)
        """
        from api.proxy_intelligence import models as pi_models

        Model = getattr(pi_models, model_name, None)
        if Model is None:
            self.stdout.write(f'    ⚠ Model {model_name} not found')
            return 0, 0

        # Determine the date field
        date_field = 'created_at'
        if model_name == 'PerformanceMetric':
            date_field = 'recorded_at'

        qs = Model.objects.filter(**{f'{date_field}__lt': cutoff})
        count = qs.count()

        if dry_run:
            return 0, count

        # Batch delete to avoid long table locks
        total_deleted = 0
        while True:
            # Get PKs for this batch
            batch_pks = list(
                Model.objects.filter(**{f'{date_field}__lt': cutoff})
                .values_list('pk', flat=True)[:batch_size]
            )
            if not batch_pks:
                break

            deleted, _ = Model.objects.filter(pk__in=batch_pks).delete()
            total_deleted += deleted

            self.stdout.write(
                f'    Deleted {total_deleted:,}/{count:,}...',
                ending='\r'
            )

        self.stdout.write('')  # Newline after progress
        return total_deleted, count

    def _show_stats(self, label: str):
        """Show current record counts for all models."""
        from api.proxy_intelligence import models as pi_models

        self.stdout.write(f'\n  {label}:')
        self.stdout.write(f'  {"Model":<30} {"Count":>12}')
        self.stdout.write(f'  {"-"*44}')

        total = 0
        for model_name in self.DEFAULT_RETENTION:
            Model = getattr(pi_models, model_name, None)
            if Model:
                try:
                    count = Model.objects.count()
                    total += count
                    self.stdout.write(f'  {model_name:<30} {count:>12,}')
                except Exception:
                    self.stdout.write(f'  {model_name:<30} {"ERROR":>12}')

        self.stdout.write(f'  {"-"*44}')
        self.stdout.write(f'  {"TOTAL":<30} {total:>12,}')
