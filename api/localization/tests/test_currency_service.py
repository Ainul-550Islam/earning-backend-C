# tests/test_currency_service.py
from django.test import TestCase
from .factories import make_currency
from decimal import Decimal


class CurrencyFormatServiceTest(TestCase):
    def setUp(self):
        from .factories import make_language, make_country
        self.lang = make_language(code='te-cf', name='Currency Format Test', is_default=False)
        self.country = make_country(code='TC', name='Test Country CF', phone_code='+999')
        self.currency = make_currency(code='TCF', name='Test Format Currency', symbol='T$')

    def test_format_amount_basic(self):
        from localization.services.currency.CurrencyFormatService import CurrencyFormatService
        service = CurrencyFormatService()
        # Without a CurrencyFormat object, falls back to currency.format_amount
        result = service.format(Decimal('1234.56'), 'TCF', 'te-cf')
        self.assertIsNotNone(result)

    def test_currency_parse(self):
        from localization.services.currency.CurrencyFormatService import CurrencyFormatService
        service = CurrencyFormatService()
        result = service.parse('$1,234.56', 'USD')
        self.assertEqual(result, Decimal('1234.56'))


class ExchangeRateServiceTest(TestCase):
    def test_convert_same_currency(self):
        from localization.services.currency.ExchangeRateService import ExchangeRateService
        service = ExchangeRateService()
        result = service.convert(Decimal('100'), 'USD', 'USD')
        self.assertIsNotNone(result)
        self.assertEqual(result['amount'], Decimal('100'))
