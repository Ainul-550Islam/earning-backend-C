# api/wallet/tests/test_currency.py
from decimal import Decimal
from django.test import TestCase
from unittest.mock import patch


class CurrencyConverterTest(TestCase):
    def test_bdt_to_bdt(self):
        from ..currency_converter import CurrencyConverter
        result = CurrencyConverter.to_bdt(Decimal("1000"), "BDT")
        self.assertEqual(result, Decimal("1000"))

    def test_from_bdt_to_bdt(self):
        from ..currency_converter import CurrencyConverter
        result = CurrencyConverter.from_bdt(Decimal("1000"), "BDT")
        self.assertEqual(result, Decimal("1000"))

    def test_fallback_usd_rate(self):
        from ..currency_converter import CurrencyConverter
        with patch.object(CurrencyConverter, "_fetch_live_rate", return_value=Decimal("0")):
            rate = CurrencyConverter.get_rate_to_bdt("USD")
            self.assertGreater(rate, Decimal("1"))  # Fallback should be > 1

    def test_convert_usd_to_bdt(self):
        from ..currency_converter import CurrencyConverter
        with patch.object(CurrencyConverter, "_fetch_live_rate", return_value=Decimal("110")):
            result = CurrencyConverter.to_bdt(Decimal("10"), "USD")
            self.assertEqual(result, Decimal("1100.00"))

    def test_convert_bdt_to_usd(self):
        from ..currency_converter import CurrencyConverter
        with patch.object(CurrencyConverter, "_fetch_live_rate", return_value=Decimal("110")):
            result = CurrencyConverter.from_bdt(Decimal("1100"), "USD")
            self.assertAlmostEqual(float(result), 10.0, places=4)

    def test_get_all_rates_returns_dict(self):
        from ..currency_converter import CurrencyConverter
        rates = CurrencyConverter.get_all_rates()
        self.assertIn("USD", rates)
        self.assertIn("BDT", rates)
        self.assertIsInstance(rates["USD"], float)
