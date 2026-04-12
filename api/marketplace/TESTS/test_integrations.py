"""TESTS/test_integrations.py — Integration Layer Tests"""
from django.test import TestCase
from decimal import Decimal
from api.marketplace.INTEGRATIONS.payment_gateway import BkashGateway, NagadGateway
from api.marketplace.INTEGRATIONS.tax_provider_integration import calculate_bd_vat, tax_breakdown
from api.marketplace.PAYMENT_SETTLEMENT.commission_calculator import CommissionCalculator
from api.marketplace.PROMOTION_MARKETING.promo_code_generator import generate_code, bulk_generate


class IntegrationTest(TestCase):
    def test_bkash_gateway_init(self):
        gw = BkashGateway()
        self.assertEqual(gw.name, "bkash")

    def test_vat_calculation(self):
        vat = calculate_bd_vat(Decimal("1000.00"))
        self.assertEqual(vat, Decimal("150.00"))

    def test_tax_breakdown(self):
        bd  = tax_breakdown(Decimal("1000.00"))
        self.assertEqual(bd["vat_rate"], "15%")
        self.assertEqual(bd["vat"], "150.00")

    def test_promo_code_length(self):
        code = generate_code("PROMO", 8)
        self.assertTrue(code.startswith("PROMO-"))
        self.assertEqual(len(code), 14)  # "PROMO-" + 8 chars

    def test_zero_commission_fallback(self):
        """CommissionCalculator returns fallback when no config exists."""
        from api.tenants.models import Tenant
        tenant = Tenant.objects.create(name="NoCfg", slug="nocfg", domain="nocfg.localhost")
        calc = CommissionCalculator()
        rate, amount = calc.calculate(Decimal("1000"), None, tenant)
        self.assertGreater(amount, 0)
