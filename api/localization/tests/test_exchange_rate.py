# tests/test_exchange_rate.py
from django.test import TestCase
from .factories import make_currency
from decimal import Decimal


class ExchangeRateServiceTest(TestCase):
    def setUp(self):
        self.usd = make_currency(code='USD', name='US Dollar', symbol='$')
        self.bdt = make_currency(code='BDT', name='Taka', symbol='৳', exchange_rate=110.0)
        self.eur = make_currency(code='EUR', name='Euro', symbol='€', exchange_rate=0.92)

    def test_convert_same_currency(self):
        from localization.services.currency.ExchangeRateService import ExchangeRateService
        result = ExchangeRateService().convert(Decimal('100'), 'USD', 'USD')
        self.assertIsNotNone(result)
        self.assertEqual(result['from'], 'USD')
        self.assertEqual(result['to'], 'USD')

    def test_rate_provider_fetch_structure(self):
        from localization.services.currency.CurrencyRateProvider import CurrencyRateProvider
        provider = CurrencyRateProvider()
        self.assertTrue(hasattr(provider, 'fetch_rates'))
        self.assertTrue(hasattr(provider, '_fetch_ecb'))
        self.assertTrue(hasattr(provider, '_fetch_exchangerate_api'))

    def test_conversion_service_structure(self):
        from localization.services.currency.CurrencyConversionService import CurrencyConversionService
        service = CurrencyConversionService()
        self.assertTrue(hasattr(service, 'convert_and_log'))

    def test_format_service_parse(self):
        from localization.services.currency.CurrencyFormatService import CurrencyFormatService
        service = CurrencyFormatService()
        result = service.parse('$1,234.56', 'USD')
        self.assertEqual(result, Decimal('1234.56'))

    def test_format_service_parse_with_currency_symbol(self):
        from localization.services.currency.CurrencyFormatService import CurrencyFormatService
        service = CurrencyFormatService()
        result = service.parse('৳1,10,000', 'BDT')
        self.assertEqual(result, Decimal('110000'))
