# api/wallet/tests/test_integration_cpalead.py
"""Integration tests for CPAlead offer conversion flow."""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch

User = get_user_model()


class CPALeadServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cpatest", email="cpa@test.com", password="pass")

    def test_get_geo_rate_tier1(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        rate = CPALeadService.get_geo_rate("US")
        self.assertEqual(rate, Decimal("2.50"))

    def test_get_geo_rate_tier2(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        rate = CPALeadService.get_geo_rate("DE")
        self.assertEqual(rate, Decimal("1.50"))

    def test_get_geo_rate_bangladesh(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        rate = CPALeadService.get_geo_rate("BD")
        self.assertEqual(rate, Decimal("1.00"))

    def test_get_tier_multiplier_free(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        self.user.tier = "FREE"
        rate = CPALeadService.get_tier_multiplier(self.user)
        self.assertEqual(rate, Decimal("1.00"))

    def test_get_tier_multiplier_diamond(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        self.user.tier = "DIAMOND"
        rate = CPALeadService.get_tier_multiplier(self.user)
        self.assertEqual(rate, Decimal("1.30"))

    def test_referral_commission_level1(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        from ..services.core.WalletService import WalletService
        wallet = WalletService.get_or_create(self.user)
        referrer = User.objects.create_user(username="ref1", email="r1@test.com", password="p")
        ref_wallet = WalletService.get_or_create(referrer)
        result = CPALeadService.add_referral(ref_wallet, Decimal("1000"), 1, self.user.id)
        self.assertIn("commission", result)
        self.assertAlmostEqual(result["commission"], 100.0, places=2)

    def test_referral_commission_level2(self):
        from ..services.cpalead.CPALeadService import CPALeadService
        from ..services.core.WalletService import WalletService
        referrer = User.objects.create_user(username="ref2", email="r2@test.com", password="p")
        ref_wallet = WalletService.get_or_create(referrer)
        result = CPALeadService.add_referral(ref_wallet, Decimal("1000"), 2, self.user.id)
        self.assertAlmostEqual(result["commission"], 50.0, places=2)
