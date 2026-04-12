"""TESTS/test_promotions.py — Promotions & Campaign Tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta, date
from api.tenants.models import Tenant
from api.marketplace.models import Coupon
from api.marketplace.enums import CouponType
from api.marketplace.PROMOTION_MARKETING.deal_of_day import DealOfTheDayManager
from api.marketplace.PROMOTION_MARKETING.coupon_manager import create_coupon, deactivate_expired_coupons
from api.marketplace.PROMOTION_MARKETING.loyalty_reward import LoyaltyEngine

User = get_user_model()

class PromotionTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Promo T", slug="pt", domain="pt.localhost")
        self.user   = User.objects.create_user(username="promo_user", password="pass")

    def test_create_coupon(self):
        coupon = create_coupon(
            self.tenant, self.user, "Flash Sale", Decimal("20"), CouponType.PERCENTAGE,
            valid_until=timezone.now() + timedelta(days=7),
        )
        self.assertTrue(coupon.is_valid)
        self.assertEqual(coupon.coupon_type, CouponType.PERCENTAGE)

    def test_deactivate_expired_coupons(self):
        expired = Coupon.objects.create(
            tenant=self.tenant, code="EXP100", name="Expired",
            coupon_type=CouponType.FIXED, discount_value=Decimal("50"),
            valid_from=timezone.now() - timedelta(days=10),
            valid_until=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        deactivated = deactivate_expired_coupons(self.tenant)
        expired.refresh_from_db()
        self.assertFalse(expired.is_active)

    def test_loyalty_earn_and_redeem(self):
        acc = LoyaltyEngine.earn(self.user, self.tenant, Decimal("1000"), "ORD12345678")
        self.assertEqual(acc.points, Decimal("1000"))
        discount = LoyaltyEngine.redeem(self.user, self.tenant, Decimal("200"), "ORD99999999")
        self.assertEqual(discount, Decimal("100.00"))  # 200 pts × 0.5 = 100 BDT
