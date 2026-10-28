# api/djoyalty/management/commands/evaluate_tiers.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Re-evaluate loyalty tiers for all active customers.'

    def add_arguments(self, parser):
        parser.add_argument('--customer-id', type=int, help='Evaluate a single customer by ID.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without saving.')
        parser.add_argument('--batch-size', type=int, default=100, help='Process N customers per batch.')

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        from djoyalty.services.tiers.TierEvaluationService import TierEvaluationService

        customer_id = options.get('customer_id')
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN -- no changes will be made.'))

        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
                if not dry_run:
                    result = TierEvaluationService.evaluate(customer, tenant=customer.tenant)
                    tier_name = result.tier.name if result and result.tier else 'no_change'
                    self.stdout.write(self.style.SUCCESS(f'Customer {customer.code}: tier = {tier_name}'))
                else:
                    self.stdout.write(f'Would evaluate customer: {customer.code}')
            except Customer.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Customer {customer_id} not found.'))
            return

        customers = Customer.objects.filter(is_active=True).only('id', 'code', 'tenant')
        total = customers.count()
        self.stdout.write(f'Evaluating {total} active customers (batch_size={batch_size})...')

        processed, upgraded, errors = 0, 0, 0
        batch = []
        for customer in customers.iterator(chunk_size=batch_size):
            try:
                if not dry_run:
                    old_tier = customer.user_tiers.filter(is_current=True).first()
                    result = TierEvaluationService.evaluate(customer, tenant=customer.tenant)
                    if result and old_tier and old_tier.tier != result.tier:
                        upgraded += 1
                processed += 1
                if processed % batch_size == 0:
                    self.stdout.write(f'  Processed {processed}/{total}...')
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'Error on {customer.code}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Done. Processed={processed}, Changed={upgraded}, Errors={errors}'
        ))
