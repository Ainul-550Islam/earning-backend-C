# api/djoyalty/management/commands/export_loyalty_data.py
"""
GDPR-compliant loyalty data export।
python manage.py export_loyalty_data --customer-code CUST001
python manage.py export_loyalty_data --all --output /tmp/loyalty_export.csv
"""
import os
import json
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Export loyalty data for GDPR compliance or bulk analysis.'

    def add_arguments(self, parser):
        parser.add_argument('--customer-code', type=str, help='Export single customer GDPR data.')
        parser.add_argument('--all', action='store_true', dest='all_customers', help='Export all customers CSV.')
        parser.add_argument('--type', default='customers', choices=['customers', 'ledger', 'insights'],
                            help='Export type (used with --all).')
        parser.add_argument('--output', type=str, default='', help='Output file path (default: stdout).')
        parser.add_argument('--days', type=int, default=90, help='Data range in days (for ledger export).')

    def handle(self, *args, **options):
        from djoyalty.services.LoyaltyExportService import LoyaltyExportService

        customer_code = options.get('customer_code')
        all_customers = options['all_customers']
        export_type = options['type']
        output_path = options.get('output', '')
        days = options['days']

        if customer_code:
            self._export_single_customer(customer_code, output_path, LoyaltyExportService)
        elif all_customers:
            self._export_bulk(export_type, output_path, days, LoyaltyExportService)
        else:
            self.stdout.write(self.style.ERROR('Provide --customer-code or --all.'))
            return

    def _export_single_customer(self, code, output_path, service):
        from djoyalty.models.core import Customer
        try:
            customer = Customer.objects.get(code=code.strip().upper())
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer not found: {code}'))
            return

        data = service.export_customer_gdpr(customer)
        content = json.dumps(data, indent=2, ensure_ascii=False)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f'GDPR export saved to: {output_path}'))
        else:
            self.stdout.write(content)

    def _export_bulk(self, export_type, output_path, days, service):
        self.stdout.write(f'Exporting {export_type}...')

        if export_type == 'customers':
            content = service.export_customers_csv()
        elif export_type == 'ledger':
            content = service.export_ledger_csv(days=days)
        elif export_type == 'insights':
            content = service.export_insights_csv()
        else:
            content = ''

        if not content:
            self.stdout.write(self.style.WARNING('No data to export.'))
            return

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            lines = content.count('\n')
            self.stdout.write(self.style.SUCCESS(f'Export saved to: {output_path} ({lines} rows)'))
        else:
            self.stdout.write(content)
