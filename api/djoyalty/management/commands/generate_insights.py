# api/djoyalty/management/commands/generate_insights.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate daily/weekly loyalty insight reports.'

    def add_arguments(self, parser):
        parser.add_argument('--period', default='daily', choices=['daily', 'weekly', 'monthly'], help='Report period.')
        parser.add_argument('--date', type=str, help='Report date YYYY-MM-DD (default: today).')
        parser.add_argument('--all-tenants', action='store_true', help='Generate for all tenants.')

    def handle(self, *args, **options):
        from djoyalty.services.advanced.InsightService import InsightService
        from djoyalty.models.core import Tenant
        import datetime

        period = options['period']
        date_str = options.get('date')
        report_date = None
        if date_str:
            try:
                report_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Invalid date format: {date_str}. Use YYYY-MM-DD.'))
                return

        self.stdout.write(f'Generating {period} insight report...')

        if options['all_tenants']:
            tenants = list(Tenant.objects.filter(is_active=True))
            tenants.append(None)  # global
        else:
            tenants = [None]

        count = 0
        for tenant in tenants:
            try:
                insight = InsightService.generate_daily_insight(tenant=tenant, date=report_date)
                tenant_name = tenant.name if tenant else 'Global'
                self.stdout.write(self.style.SUCCESS(
                    f'  [{tenant_name}] {insight.report_date}: '
                    f'customers={insight.total_customers}, '
                    f'points_issued={insight.total_points_issued}, '
                    f'redeemed={insight.total_points_redeemed}'
                ))
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error for tenant {tenant}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nGenerated {count} insight reports.'))
