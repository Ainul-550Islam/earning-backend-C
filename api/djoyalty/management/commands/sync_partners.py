# api/djoyalty/management/commands/sync_partners.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync all active partner merchants (update last_sync_at, check webhooks).'

    def add_arguments(self, parser):
        parser.add_argument('--partner-id', type=int, help='Sync a single partner by ID.')
        parser.add_argument('--check-webhooks', action='store_true', help='Also ping webhook URLs.')

    def handle(self, *args, **options):
        from djoyalty.models.campaigns import PartnerMerchant
        from djoyalty.services.PartnerMerchantService import PartnerMerchantService
        from django.utils import timezone

        partner_id = options.get('partner_id')

        if partner_id:
            try:
                partner = PartnerMerchant.objects.get(id=partner_id)
                ok = PartnerMerchantService.sync_partner(partner)
                if ok:
                    self.stdout.write(self.style.SUCCESS(f'Synced partner: {partner.name}'))
                else:
                    self.stdout.write(self.style.ERROR(f'Failed to sync: {partner.name}'))
            except PartnerMerchant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Partner {partner_id} not found.'))
            return

        count = PartnerMerchantService.sync_all_active()
        self.stdout.write(self.style.SUCCESS(f'Synced {count} active partners at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}.'))

        if options['check_webhooks']:
            self.stdout.write('Checking partner webhook URLs...')
            partners_with_webhooks = PartnerMerchant.objects.filter(
                is_active=True,
                webhook_url__isnull=False,
            ).exclude(webhook_url='')

            active, failed = 0, 0
            import urllib.request
            for partner in partners_with_webhooks:
                try:
                    req = urllib.request.Request(
                        partner.webhook_url, method='HEAD',
                        headers={'User-Agent': 'DjoyaltySync/1.0'},
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        if resp.status < 400:
                            active += 1
                            self.stdout.write(f'  ✓ {partner.name}: {partner.webhook_url}')
                        else:
                            failed += 1
                            self.stdout.write(self.style.WARNING(f'  ✗ {partner.name}: HTTP {resp.status}'))
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ {partner.name}: {e}'))

            self.stdout.write(f'Webhook check: {active} ok, {failed} failed.')
