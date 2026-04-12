"""TESTS/test_disputes.py — Dispute Resolution Tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory, Order, OrderItem
)
from api.marketplace.enums import OrderStatus, DisputeType, DisputeStatus
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile
from api.marketplace.DISPUTE_RESOLUTION.dispute_model import Dispute
from api.marketplace.DISPUTE_RESOLUTION.dispute_resolution import DisputeResolutionService, DisputeAlreadyExists

User = get_user_model()

class DisputeTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Dispute T", slug="dt", domain="dt.localhost")
        self.buyer  = User.objects.create_user(username="buyer_d", password="pass")
        su          = User.objects.create_user(username="seller_d", password="pass")
        self.seller = create_seller_profile(su, self.tenant, "Dispute Store", "+8801700000011")
        self.cat    = Category.objects.create(tenant=self.tenant, name="Cat", slug="cat-d")
        self.product= Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.cat,
            name="Prod", slug="prod-d", description="P",
            base_price=Decimal("500.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product, name="D", sku="DISP-001",
        )
        ProductInventory.objects.create(tenant=self.tenant, variant=self.variant, quantity=5)
        self.order = Order.objects.create(
            tenant=self.tenant, user=self.buyer,
            total_price=Decimal("500.00"), status=OrderStatus.DELIVERED,
            shipping_name="Test", shipping_phone="01700000001",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        self.order_item = OrderItem.objects.create(
            tenant=self.tenant, order=self.order, seller=self.seller,
            variant=self.variant, product_name="Prod", quantity=1,
            unit_price=Decimal("500.00"), subtotal=Decimal("500.00"),
        )

    def test_raise_dispute(self):
        dispute = DisputeResolutionService.raise_dispute(
            self.order_item, self.buyer,
            DisputeType.NOT_AS_DESCRIBED, "Item not as described",
        )
        self.assertEqual(dispute.status, DisputeStatus.OPEN)
        self.assertEqual(dispute.raised_by, self.buyer)

    def test_cannot_dispute_twice(self):
        DisputeResolutionService.raise_dispute(
            self.order_item, self.buyer, DisputeType.DAMAGED, "Damaged",
        )
        with self.assertRaises(DisputeAlreadyExists):
            DisputeResolutionService.raise_dispute(
                self.order_item, self.buyer, DisputeType.DAMAGED, "Again",
            )
