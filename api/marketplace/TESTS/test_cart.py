"""TESTS/test_cart.py — Cart & Coupon Tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from api.tenants.models import Tenant
from api.marketplace.models import Cart, CartItem, Coupon, Category, ProductVariant, ProductInventory
from api.marketplace.enums import CouponType
from api.marketplace.services import add_to_cart, remove_from_cart, apply_coupon_to_cart
from api.marketplace.CART_CHECKOUT.cart_model import get_or_create_cart
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile
from api.marketplace.PRODUCT_MANAGEMENT.product_variant import create_variant

User = get_user_model()

class CartTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Cart Tenant", slug="ct", domain="ct.localhost")
        self.user   = User.objects.create_user(username="cartuser", password="pass")
        seller_user = User.objects.create_user(username="seller_ct", password="pass")
        self.seller = create_seller_profile(seller_user, self.tenant, "Cart Store", "+8801700000009")
        self.cat    = Category.objects.create(tenant=self.tenant, name="T", slug="t")
        from api.marketplace.models import Product
        self.product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.cat,
            name="Test Product", slug="test-prod", description="Desc",
            base_price=Decimal("500.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product, name="Default", sku="TEST-001"
        )
        ProductInventory.objects.create(tenant=self.tenant, variant=self.variant, quantity=20)

    def test_get_or_create_cart(self):
        cart = get_or_create_cart(self.user, self.tenant)
        self.assertIsNotNone(cart)
        self.assertTrue(cart.is_active)

    def test_add_item_to_cart(self):
        cart = get_or_create_cart(self.user, self.tenant)
        item = add_to_cart(cart, self.variant, 3)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(cart.item_count, 3)

    def test_add_same_item_twice_accumulates(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 2)
        add_to_cart(cart, self.variant, 3)
        self.assertEqual(cart.item_count, 5)

    def test_remove_item(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 2)
        remove_from_cart(cart, self.variant.pk)
        self.assertEqual(cart.item_count, 0)

    def test_cart_total(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 2)
        self.assertEqual(cart.total, Decimal("1000.00"))

    def test_apply_coupon(self):
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="SAVE10", name="10% Off",
            coupon_type=CouponType.PERCENTAGE, discount_value=Decimal("10"),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
        )
        cart = get_or_create_cart(self.user, self.tenant)
        applied = apply_coupon_to_cart(cart, "SAVE10")
        self.assertEqual(applied.code, "SAVE10")

    def test_out_of_stock_raises(self):
        from api.marketplace.exceptions import OutOfStockException
        inv = ProductInventory.objects.get(variant=self.variant)
        inv.quantity = 0
        inv.allow_backorder = False
        inv.save()
        cart = get_or_create_cart(self.user, self.tenant)
        with self.assertRaises(OutOfStockException):
            add_to_cart(cart, self.variant, 1)
