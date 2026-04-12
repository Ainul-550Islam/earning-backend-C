"""TESTS/test_sellers.py — Seller & commission tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import SellerProfile, CommissionConfig, Category
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


class CommissionTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Comm Tenant", slug="comm", domain="comm.localhost")
        self.category = Category.objects.create(tenant=self.tenant, name="Electronics", slug="elec")
        self.config = CommissionConfig.objects.create(
            tenant=self.tenant, category=self.category, rate=Decimal("15.00"), flat_fee=Decimal("10.00")
        )

    def test_commission_calculation(self):
        amount = Decimal("1000.00")
        commission = self.config.calculate(amount)
        expected = Decimal("160.00")  # 15% of 1000 + 10
        self.assertEqual(commission, expected)
