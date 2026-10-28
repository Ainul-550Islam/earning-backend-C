"""
Management command: export_metrics

Exports RealTimeMetric rows to stdout as CSV or JSON.

Business use-cases:
  - BI pipeline ingestion: pipe output to S3, BigQuery, or a data warehouse
  - Ops snapshot: capture current metric values before a deployment
  - Debugging: inspect what the broadcast task would push to subscribers
  - Data migration: seed a new environment with existing metric definitions

Usage:
    # Export all active metrics as CSV (default)
    python manage.py export_metrics

    # Export as JSON
    python manage.py export_metrics --format json

    # Export specific status
    python manage.py export_metrics --status inactive

    # Export specific metric IDs
    python manage.py export_metrics --ids 1 2 3

    # Export all metrics regardless of status
    python manage.py export_metrics --status all

    # Write to a file instead of stdout
    python manage.py export_metrics --format json > /tmp/metrics.json

OWNERSHIP: reads via RealTimeMetricService.get_metric() for cache-aware
access. Writes to stdout only — no DB mutations.
"""
import csv
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


SUPPORTED_FORMATS = ('csv', 'json')
SUPPORTED_STATUSES = ('active', 'inactive', 'all')


class Command(BaseCommand):
    help = 'Export RealTimeMetric rows to stdout as CSV or JSON.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=SUPPORTED_FORMATS,
            default='csv',
            help='Output format (default: csv).',
        )
        parser.add_argument(
            '--status',
            choices=SUPPORTED_STATUSES,
            default='active',
            help=(
                'Which metrics to export: active, inactive, or all '
                '(default: active).'
            ),
        )
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            metavar='ID',
            default=None,
            help='Specific metric IDs to export. Overrides --status.',
        )

    def handle(self, *args, **options):
        from ...models.real_time_metric import RealTimeMetric

        fmt = options['format']
        status_filter = options['status']
        ids = options['ids']

        # ── Build queryset ───────────────────────────────────────────────────
        qs = RealTimeMetric.objects.all().order_by('id')

        if ids:
            qs = qs.filter(id__in=ids)
            missing = set(ids) - set(qs.values_list('id', flat=True))
            if missing:
                raise CommandError(
                    f'Metric IDs not found: {sorted(missing)}'
                )
        elif status_filter != 'all':
            qs = qs.filter(status=status_filter)

        rows = list(qs.values(
            'id', 'name', 'description', 'metric_type', 'status',
            'value', 'previous_value', 'unit',
            'warning_threshold', 'critical_threshold',
            'last_updated', 'created_at', 'updated_at',
        ))

        if not rows:
            self.stderr.write(self.style.WARNING('No metrics matched the filter.'))
            return

        count = len(rows)

        # ── Export ───────────────────────────────────────────────────────────
        if fmt == 'csv':
            self._export_csv(rows)
        else:
            self._export_json(rows)

        self.stderr.write(
            self.style.SUCCESS(
                f'Exported {count} metric(s) [{fmt}] at {timezone.now().isoformat()}'
            )
        )

    # ── Format helpers ────────────────────────────────────────────────────────

    def _export_csv(self, rows: list) -> None:
        """Write rows as CSV to stdout."""
        if not rows:
            return
        writer = csv.DictWriter(
            self.stdout,
            fieldnames=rows[0].keys(),
            lineterminator='\n',
        )
        writer.writeheader()
        for row in rows:
            # Coerce datetime objects to ISO strings for CSV compatibility
            writer.writerow({
                k: v.isoformat() if hasattr(v, 'isoformat') else v
                for k, v in row.items()
            })

    def _export_json(self, rows: list) -> None:
        """Write rows as pretty-printed JSON array to stdout."""
        serialisable = []
        for row in rows:
            serialisable.append({
                k: v.isoformat() if hasattr(v, 'isoformat') else v
                for k, v in row.items()
            })
        json.dump(serialisable, self.stdout, indent=2, ensure_ascii=False)
        self.stdout.write('\n')
