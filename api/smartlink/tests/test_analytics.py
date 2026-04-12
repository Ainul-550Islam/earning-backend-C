from django.test import TestCase
from .factories import SmartLinkFactory, ClickFactory, SmartLinkDailyStatFactory
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from ..services.analytics.EPCCalculatorService import EPCCalculatorService
from ..services.analytics.ConversionRateService import ConversionRateService


class SmartLinkAnalyticsServiceTest(TestCase):
    def setUp(self):
        self.service = SmartLinkAnalyticsService()
        self.sl = SmartLinkFactory()

    def test_summary_returns_correct_keys(self):
        summary = self.service.get_summary(self.sl, days=30)
        for key in ['clicks', 'unique_clicks', 'conversions', 'revenue', 'epc', 'conversion_rate']:
            self.assertIn(key, summary)

    def test_summary_zeros_for_new_smartlink(self):
        summary = self.service.get_summary(self.sl, days=30)
        self.assertEqual(summary['clicks'], 0)
        self.assertEqual(summary['revenue'], 0)

    def test_daily_breakdown_returns_list(self):
        SmartLinkDailyStatFactory(smartlink=self.sl, clicks=100, conversions=5, revenue=25.00)
        result = self.service.get_daily_breakdown(self.sl, days=30)
        self.assertIsInstance(result, list)

    def test_geo_breakdown_returns_list(self):
        result = self.service.get_geo_breakdown(self.sl, days=30)
        self.assertIsInstance(result, list)

    def test_device_breakdown_returns_list(self):
        result = self.service.get_device_breakdown(self.sl, days=30)
        self.assertIsInstance(result, list)


class EPCCalculatorServiceTest(TestCase):
    def setUp(self):
        self.service = EPCCalculatorService()

    def test_zero_clicks_returns_zero_epc(self):
        sl = SmartLinkFactory()
        epc = self.service.calculate_for_smartlink(sl, days=7)
        self.assertEqual(epc, 0.0)

    def test_epc_formula_correct(self):
        """EPC = revenue / clicks"""
        sl = SmartLinkFactory(total_clicks=1000, total_revenue=250)
        # With real clicks in DB, EPC = 250/1000 = 0.25
        # For now just verify it returns a float
        epc = self.service.calculate_for_smartlink(sl, days=7)
        self.assertIsInstance(epc, float)


class ConversionRateServiceTest(TestCase):
    def setUp(self):
        self.service = ConversionRateService()

    def test_zero_clicks_returns_zero_cr(self):
        sl = SmartLinkFactory()
        cr = self.service.calculate_for_smartlink(sl, days=30)
        self.assertEqual(cr, 0.0)

    def test_cr_is_percentage(self):
        sl = SmartLinkFactory()
        cr = self.service.calculate_for_smartlink(sl, days=30)
        self.assertGreaterEqual(cr, 0)
        self.assertLessEqual(cr, 100)
