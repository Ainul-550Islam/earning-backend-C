# management/commands/update_exchange_rates.py
"""python manage.py update_exchange_rates"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Currency exchange rates update করে'

    def add_arguments(self, parser):
        parser.add_argument('--provider', default='exchangerate-api', choices=['exchangerate-api','ecb','openexchangerates'])
        parser.add_argument('--base', default='USD', help='Base currency')

    def handle(self, *args, **options):
        from localization.services.currency.CurrencyRateProvider import CurrencyRateProvider
        from localization.services.currency.ExchangeRateService import ExchangeRateService
        provider_name = options.get('provider', 'exchangerate-api')
        base = options.get('base', 'USD')
        provider = CurrencyRateProvider()
        result = provider.fetch_rates(base, provider_name)
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(result.get('rates',{}))} rates from {provider_name}"))
        else:
            self.stderr.write(self.style.ERROR(f"Failed: {result.get('error')}"))
