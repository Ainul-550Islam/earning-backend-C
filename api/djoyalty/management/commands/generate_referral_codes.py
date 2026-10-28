# api/djoyalty/management/commands/generate_referral_codes.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate referral codes for customers who don\'t have one।'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', dest='all_customers', help='Generate for ALL customers')
        parser.add_argument('--tenant-id', type=int)

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        from djoyalty.models.referral import ReferralLink
        import secrets
        import string

        qs = Customer.objects.filter(is_active=True)
        if options.get('tenant_id'):
            qs = qs.filter(tenant_id=options['tenant_id'])

        if not options.get('all_customers'):
            # Only customers missing referral code
            qs = qs.filter(referral_code__isnull=True)

        total = qs.count()
        self.stdout.write(f'Generating referral codes for {total} customers...')

        alphabet = string.ascii_uppercase + string.digits
        generated = 0

        for customer in qs.iterator(chunk_size=100):
            try:
                if not customer.referral_code or options.get('all_customers'):
                    # Generate unique code
                    while True:
                        code = ''.join(secrets.choice(alphabet) for _ in range(8))
                        if not Customer.objects.filter(referral_code=code).exists():
                            break
                    customer.referral_code = code
                    customer.save(update_fields=['referral_code'])

                # Create ReferralLink if not exists
                ReferralLink.objects.get_or_create(
                    customer=customer,
                    code=customer.referral_code,
                    defaults={
                        'tenant': customer.tenant,
                        'destination_url': '',
                    },
                )
                generated += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error for {customer.code}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Generated {generated} referral codes'))
