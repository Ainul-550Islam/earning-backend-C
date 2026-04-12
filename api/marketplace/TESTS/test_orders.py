"""TESTS/test_orders.py — Order flow tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory,
    Cart, Order,
)
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile
from api.marketplace.services import add_to_cart, create_order_from_cart
from api.marketplace.CART_CHECKOUT.cart_model import get_or_create_cart

User = get_user_model()


class OrderFlowTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Order Tenant", slug="ord", domain="ord.localhost")
        self.user = User.objects.create_user(username="buyer1", password="pass")
        seller_user = User.objects.create_user(username="seller2", password="pass")
        self.seller = create_seller_profile(seller_user, self.tenant, "Good Store", "+8801800000000")
        self.category = Category.objects.create(tenant=self.tenant, name="Books", slug="books")
        self.product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="Python Book", slug="python-book", description="Learn Python",
            base_price=Decimal("300.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product,
            name="Default", sku="PYBOOK-001",
        )
        self.inventory = ProductInventory.objects.create(
            tenant=self.tenant, variant=self.variant, quantity=50
        )

    def test_add_to_cart(self):
        cart = get_or_create_cart(self.user, self.tenant)
        item = add_to_cart(cart, self.variant, 2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(cart.item_count, 2)

    def test_create_order_from_cart(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 1)
        shipping = {
            "shipping_name": "Test Buyer",
            "shipping_phone": "+8801700000001",
            "shipping_address": "123 Dhaka Street",
            "shipping_city": "Dhaka",
        }
        order = create_order_from_cart(cart, "cod", shipping)
        self.assertIsNotNone(order.order_number)
        self.assertEqual(order.items.count(), 1)

    def test_inventory_reserved_after_order(self):
        cart = get_or_create_cart(self.user, self.tenant)
        add_to_cart(cart, self.variant, 3)
        shipping = {
            "shipping_name": "Test",
            "shipping_phone": "+8801700000002",
            "shipping_address": "Addr",
            "shipping_city": "Ctg",
        }
        create_order_from_cart(cart, "bkash", shipping)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, 3)
