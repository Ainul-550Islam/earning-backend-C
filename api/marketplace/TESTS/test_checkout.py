"""TESTS/test_checkout.py — Checkout Flow Tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory, Order
)
from api.marketplace.services import add_to_cart, create_order_from_cart
from api.marketplace.CART_CHECKOUT.cart_model import get_or_create_cart
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()

class CheckoutTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Checkout T", slug="cht", domain="cht.localhost")
        self.user   = User.objects.create_user(username="buyer_co", password="pass")
        su          = User.objects.create_user(username="seller_co", password="pass")
        self.seller = create_seller_profile(su, self.tenant, "Checkout Store", "+8801700000010")
        self.cat    = Category.objects.create(tenant=self.tenant, name="Elec", slug="elec")
        self.product= Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.cat,
            name="Phone", slug="phone", description="A phone",
            base_price=Decimal("25000.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product, name="Default", sku="PHONE-001",
        )
        ProductInventory.objects.create(tenant=self.tenant, variant=self.variant, quantity=10)

    def _shipping(self):
        return {"shipping_name":"Test","shipping_phone":"01700000001",
                "shipping_address":"Dhaka","shipping_city":"Dhaka"}

    def test_checkout_creates_order(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 1)
        order = create_order_from_cart(cart, "cod", self._shipping())
        self.assertIsInstance(order, Order)
        self.assertEqual(order.items.count(), 1)

    def test_checkout_clears_cart(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 2)
        create_order_from_cart(cart, "bkash", self._shipping())
        self.assertEqual(cart.items.count(), 0)

    def test_inventory_reserved_on_checkout(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 3)
        create_order_from_cart(cart, "cod", self._shipping())
        self.variant.inventory.refresh_from_db()
        self.assertEqual(self.variant.inventory.reserved_quantity, 3)

    def test_empty_cart_raises(self):
        from api.marketplace.exceptions import CartEmptyException
        cart = get_or_create_cart(self.user, self.tenant)
        with self.assertRaises(CartEmptyException):
            create_order_from_cart(cart, "cod", self._shipping())
