"""TESTS/test_coupons.py — Coupon validation tests"""
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from api.tenants.models import Tenant
from api.marketplace.models import Coupon
from api.marketplace.enums import CouponType

class CouponTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Coup Tenant", slug="coup", domain="coup.localhost")

    def test_percentage_coupon(self):
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="SAVE10", name="10% Off",
            coupon_type=CouponType.PERCENTAGE, discount_value=Decimal("10"),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
        )
        discount = coupon.calculate_discount(Decimal("1000.00"))
        self.assertEqual(discount, Decimal("100.00"))

    def test_fixed_coupon(self):
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="FLAT50", name="Flat 50 Off",
            coupon_type=CouponType.FIXED, discount_value=Decimal("50"),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
        )
        discount = coupon.calculate_discount(Decimal("500.00"))
        self.assertEqual(discount, Decimal("50.00"))

    def test_expired_coupon_is_invalid(self):
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="EXPIRED", name="Expired",
            coupon_type=CouponType.FIXED, discount_value=Decimal("50"),
            valid_from=timezone.now() - timedelta(days=10),
            valid_until=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(coupon.is_valid)
