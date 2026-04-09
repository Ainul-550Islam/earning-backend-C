# api/djoyalty/management/commands/sync_partners.py
"""Management command: Sync partner merchant data।"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync partner merchant data and update last_sync_at timestamps'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner-id',
            type=int,
            help='Sync specific partner by ID',
            default=None,
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all active partners and their sync status',
        )

    def handle(self, *args, **options):
        from djoyalty.models.campaigns import PartnerMerchant
        from django.utils import timezone

        if options.get('list'):
            partners = PartnerMerchant.objects.all().order_by('name')
            self.stdout.write(f'\n{"Name":<30} {"Active":<8} {"Last Sync":<25}')
            self.stdout.write('-' * 65)
            for p in partners:
                last_sync = str(p.last_sync_at)[:19] if p.last_sync_at else 'Never'
                active = '✅ Yes' if p.is_active else '❌ No'
                self.stdout.write(f'{p.name:<30} {active:<8} {last_sync:<25}')
            self.stdout.write(f'\nTotal: {partners.count()} partners\n')
            return

        qs = PartnerMerchant.objects.filter(is_active=True)
        if options.get('partner_id'):
            qs = qs.filter(id=options['partner_id'])
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f'Partner ID {options["partner_id"]} not found or inactive.'))
                return

        self.stdout.write(f'Syncing {qs.count()} partner(s)...')
        synced = 0
        errors = 0
        for partner in qs:
            try:
                partner.last_sync_at = timezone.now()
                partner.save(update_fields=['last_sync_at'])
                self.stdout.write(f'  ✅ Synced: {partner.name}')
                synced += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  ❌ Error syncing {partner.name}: {e}'))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nSync complete: {synced} synced, {errors} errors.'
        ))
