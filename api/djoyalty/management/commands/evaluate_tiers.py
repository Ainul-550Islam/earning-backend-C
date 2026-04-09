# api/djoyalty/management/commands/evaluate_tiers.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Evaluate and update all customer tiers'

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService
        customers = Customer.objects.filter(is_active=True)
        self.stdout.write(f'Evaluating {customers.count()} customers...')
        count = 0
        for customer in customers:
            try:
                TierEvaluationService.evaluate(customer, tenant=customer.tenant)
                count += 1
            except Exception as e:
                self.stderr.write(f'Error for {customer}: {e}')
        self.stdout.write(self.style.SUCCESS(f'Tier evaluation done for {count} customers.'))
