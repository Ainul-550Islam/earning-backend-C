# api/djoyalty/management/commands/generate_insights.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate daily loyalty insight report for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Report date in YYYY-MM-DD format (default: today)',
            default=None,
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Generate insight for specific tenant only',
            default=None,
        )

    def handle(self, *args, **options):
        from djoyalty.services.advanced.InsightService import InsightService
        from django.utils import timezone
        import datetime

        report_date = None
        if options.get('date'):
            try:
                report_date = datetime.date.fromisoformat(options['date'])
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {options['date']}. Use YYYY-MM-DD."))
                return

        tenant = None
        if options.get('tenant_id'):
            try:
                from tenants.models import Tenant
                tenant = Tenant.objects.get(id=options['tenant_id'])
                self.stdout.write(f'Generating insight for tenant: {tenant}')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Tenant not found: {e}'))
                return

        self.stdout.write('Generating daily loyalty insight...')
        try:
            insight = InsightService.generate_daily_insight(tenant=tenant, date=report_date)
            self.stdout.write(self.style.SUCCESS(
                f'Insight generated: {insight.report_date} | '
                f'Customers: {insight.total_customers} | '
                f'Points issued: {insight.total_points_issued} | '
                f'Transactions: {insight.total_transactions}'
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error generating insight: {e}'))
            raise
