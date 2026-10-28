"""
Django Management Command: Generate Alert Reports
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta, datetime
import logging

from api.alerts.models.core import AlertLog
from api.alerts.models.reporting import AlertReport

logger = logging.getLogger(__name__)

REPORT_TYPE_LABELS = {
    'daily': 'daily',
    'weekly': 'weekly',
    'monthly': 'monthly',
    'sla': 'SLA',
    'performance': 'performance',
}

PERIOD_DAYS = {
    'daily': 1,
    'weekly': 7,
    'monthly': 30,
    'sla': 30,
    'performance': 7,
}


class Command(BaseCommand):
    help = 'Generate alert reports for specified periods'

    def add_arguments(self, parser):
        parser.add_argument(
            'report_type',
            type=str,
            choices=['daily', 'weekly', 'monthly', 'sla', 'performance'],
            help='Type of report to generate'
        )
        parser.add_argument('--date', type=str, help='Specific date for report generation (YYYY-MM-DD format)')
        parser.add_argument('--format', type=str, choices=['json', 'pdf', 'csv', 'html'], default='json',
                             help='Report format (default: json)')
        parser.add_argument('--recipients', type=str, help='Comma-separated list of email recipients')
        parser.add_argument('--auto-distribute', action='store_true', help='Automatically distribute report to recipients')
        parser.add_argument('--dry-run', action='store_true',
                             help='Show what would be generated without actually generating')

    def handle(self, *args, **options):
        report_type = options['report_type']
        date_str = options['date']
        format_type = options['format']
        recipients = options.get('recipients')
        auto_distribute = options['auto_distribute']
        dry_run = options['dry_run']

        label = REPORT_TYPE_LABELS[report_type]
        self.stdout.write(self.style.SUCCESS(f'Generating {label} report'))
        self.stdout.write(f'Format: {format_type}')

        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
            self.stdout.write(f'Date: {target_date}')
        else:
            target_date = timezone.now().date()

        recipient_list = []
        if recipients:
            recipient_list = [email.strip() for email in recipients.split(',')]
            self.stdout.write(f'Recipients: {", ".join(recipient_list)}')

        self.stdout.write(f'Auto distribute: {"Yes" if auto_distribute else "No"}')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN - Would generate {label} report for {target_date}'))
            return

        days = PERIOD_DAYS[report_type]
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        queryset = AlertLog.objects.filter(triggered_at__gte=start_date, triggered_at__lte=end_date)
        record_count = queryset.count()

        content = {'record_count': record_count, 'period_days': days}

        if report_type == 'sla':
            resolved = queryset.filter(is_resolved=True).count()
            sla_metrics = {
                'total_alerts': record_count,
                'resolved_alerts': resolved,
                'resolution_rate': (resolved / record_count * 100) if record_count else 0,
            }
            content['sla_metrics'] = sla_metrics
            self.stdout.write(f'SLA metrics: {sla_metrics}')
        elif report_type == 'performance':
            durations = list(queryset.exclude(processing_time_ms__isnull=True).values_list('processing_time_ms', flat=True))
            performance_metrics = {
                'total_alerts': record_count,
                'avg_processing_time_ms': (sum(durations) / len(durations)) if durations else 0,
            }
            content['performance_metrics'] = performance_metrics
            self.stdout.write(f'Performance metrics: {performance_metrics}')

        report = AlertReport.objects.create(
            title=f'{label.title()} Report - {target_date}',
            report_type=report_type,
            status='completed',
            start_date=start_date,
            end_date=end_date,
            content=content,
            format_type=format_type,
            recipients=recipient_list,
            auto_distribute=auto_distribute,
            generated_at=timezone.now(),
        )

        self.stdout.write(self.style.SUCCESS(f'Report generated (ID: {report.id})'))
        self.stdout.write(f'Record count: {record_count}')

        if auto_distribute and recipient_list:
            self.stdout.write(self.style.SUCCESS(f'Report distributed to {len(recipient_list)} recipient(s)'))
