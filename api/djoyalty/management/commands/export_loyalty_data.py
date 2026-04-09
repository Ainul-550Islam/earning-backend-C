# api/djoyalty/management/commands/export_loyalty_data.py
import json
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'GDPR: Export loyalty data for a customer'

    def add_arguments(self, parser):
        parser.add_argument('customer_code', type=str)

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        code = options['customer_code']
        try:
            customer = Customer.objects.get(code=code.upper())
        except Customer.DoesNotExist:
            self.stderr.write(f'Customer {code} not found.')
            return
        data = {
            'code': customer.code,
            'name': customer.full_name,
            'email': customer.email,
            'phone': customer.phone,
            'city': customer.city,
            'newsletter': customer.newsletter,
            'created_at': str(customer.created_at),
            'points_balance': str(customer.points_balance),
            'transaction_count': customer.transactions.count(),
            'event_count': customer.events.count(),
        }
        self.stdout.write(json.dumps(data, indent=2))
        self.stdout.write(self.style.SUCCESS(f'Data exported for {code}.'))
