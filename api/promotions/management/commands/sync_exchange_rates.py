from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.sync_rates')

class Command(BaseCommand):
    help = 'Sync currency exchange rates from API providers'

    def handle(self, *args, **options):
        from api.promotions.localization.currency_cache import currency_cache
        results = currency_cache.refresh_all_rates()
        self.stdout.write(self.style.SUCCESS(f'Synced {len(results)} currency pairs'))
        logger.info(f'Exchange rates synced: {len(results)} pairs')
