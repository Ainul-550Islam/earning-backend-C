# api/promotions/management/commands/sync_currency_rates.py
from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.sync_currency_rates')
class Command(BaseCommand):
    help = 'sync_currency_rates'
    def add_arguments(self, parser): pass
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(f'Running: sync_currency_rates'))
        try:
            self._run()
            self.stdout.write(self.style.SUCCESS(f'Done: sync_currency_rates'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed: {e}'))
            raise
    def _run(self): pass
