# api/djoyalty/management/commands/compute_rfm_scores.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Compute RFM scores for all customers।'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-id', type=int, help='Specific tenant only')
        parser.add_argument('--customer-code', type=str, help='Single customer')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        from djoyalty.services.AIPersonalizationService import AIPersonalizationService

        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY RUN -- no changes'))

        qs = Customer.objects.filter(is_active=True)
        if options.get('tenant_id'):
            qs = qs.filter(tenant_id=options['tenant_id'])
        if options.get('customer_code'):
            qs = qs.filter(code=options['customer_code'].upper())

        total = qs.count()
        self.stdout.write(f'Computing RFM for {total} customers...')

        updated = 0
        for customer in qs.iterator(chunk_size=50):
            if not options.get('dry_run'):
                profile = AIPersonalizationService.update_ai_profile(customer)
                if profile:
                    updated += 1
            else:
                rfm = AIPersonalizationService.compute_rfm_score(customer)
                self.stdout.write(f'  {customer.code}: RFM={rfm["rfm_segment"]} churn={AIPersonalizationService.predict_churn_probability(customer)["risk_level"]}')

        if not options.get('dry_run'):
            self.stdout.write(self.style.SUCCESS(f'Updated {updated}/{total} AI profiles'))
