from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.audit_report')

class Command(BaseCommand):
    help = 'Generate and send audit report'

    def add_arguments(self, parser):
        parser.add_argument('--type', default='daily', choices=['daily','weekly','monthly'])

    def handle(self, *args, **options):
        from api.promotions.auditing.report_archiver import ReportArchiver
        from api.promotions.reporting.export_service import ExportService
        from django.utils import timezone
        import datetime

        archiver = ReportArchiver()
        rtype    = options['type']
        today    = timezone.now().date()

        if rtype == 'daily':
            report = archiver.generate_daily_report(today - datetime.timedelta(days=1))
        else:
            report = archiver.generate_monthly_report(today.year, today.month - 1 or 12)

        self.stdout.write(self.style.SUCCESS(f'Audit report ({rtype}) generated: {report}'))
