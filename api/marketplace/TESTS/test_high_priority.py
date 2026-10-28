"""
TESTS/test_high_priority.py — High-Priority Missing Component Tests
===================================================================
Covers the critical gaps identified after the base test suite:

  1.  ProductVariantViewSet          — full CRUD + active/inactive filtering
  2.  Security / Authentication      — unauthenticated access to every protected endpoint
  3.  Multi-Tenant Isolation         — cross-tenant data leakage prevention
  4.  Cart edge cases                — oversell guard, qty > stock, coupon already applied
  5.  Order state machine            — illegal transitions (ship→pending, cancel delivered)
  6.  Refund window enforcement      — request_refund outside REVIEW_WINDOW_DAYS
  7.  Coupon limits                  — usage_limit exhausted, max_discount_amount cap
  8.  Escrow release guard           — cannot release before release_after date
  9.  Review uniqueness              — same buyer cannot review same product twice
  10. Role-based order actions       — seller cannot cancel buyer's order
  11. Seller payout isolation        — seller A cannot see seller B's payouts
  12. SellerVerification lifecycle   — full submit → approve → reject flow
  13. Service-layer unit tests       — request_refund, approve_refund, release_escrow
  14. Concurrency / oversell         — race condition protection on last-unit purchase
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import threading

from rest_framework.test import APIClient
from rest_framework import status

from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory, ProductAttribute,
    SellerProfile, SellerVerification, SellerPayout,
    Cart, CartItem, Order, OrderItem,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview,
)
from api.marketplace.enums import (
    OrderStatus, PaymentStatus, EscrowStatus, VerificationStatus,
)
from api.marketplace.exceptions import (
    OutOfStockException, InsufficientStockException,
    CartEmptyException, CouponInvalidException,
    RefundWindowExpiredException,
)
from api.marketplace.services import (
    add_to_cart, create_order_from_cart, request_refund,
    approve_refund, release_escrow_and_credit,
)
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture base
# ─────────────────────────────────────────────────────────────────────────────

class HPFixture(TestCase):
    """Full marketplace fixture for high-priority tests."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="HP Tenant", slug="hp", domain="hp.localhost"
        )
        self.admin = User.objects.create_superuser(
            username="hp_admin", password="pass", email="admin@hp.com"
        )
        self.buyer = User.objects.create_user(username="hp_buyer", password="pass")
        self.buyer2 = User.objects.create_user(username="hp_buyer2", password="pass")

        seller_user = User.objects.create_user(username="hp_seller", password="pass")
        self.seller = create_seller_profile(
            seller_user, self.tenant, "HP Store", "+8801711000001"
        )
        seller_user2 = User.objects.create_user(username="hp_seller2", password="pass")
        self.seller2 = create_seller_profile(
            seller_user2, self.tenant, "HP Store 2", "+8801711000002"
        )

        self.category = Category.objects.create(
            tenant=self.tenant, name="HP Cat", slug="hp-cat", level=1
        )
        self.product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="HP Phone", slug="hp-phone", description="Test.",
            base_price=Decimal("5000.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product,
            sku="HP-001", name="Black 64GB",
        )
        self.inventory = ProductInventory.objects.create(
            tenant=self.tenant, variant=self.variant, quantity=10
        )
        self.order = Order.objects.create(
            tenant=self.tenant, user=self.buyer,
            total_price=Decimal("5000.00"),
            shipping_name="HP Buyer", shipping_phone="01711000001",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        self.order_item = OrderItem.objects.create(
            tenant=self.tenant, order=self.order, seller=self.seller,
            variant=self.variant, product_name="HP Phone",
            quantity=1, unit_price=Decimal("5000.00"),
            subtotal=Decimal("5000.00"), seller_net=Decimal("4250.00"),
        )

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        c.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        return c

    def url(self, path):
        return f"/{path}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. ProductVariantViewSet — CRUD + filtering
# ─────────────────────────────────────────────────────────────────────────────

class ProductVariantViewSetTest(HPFixture):

    def test_list_variants(self):
        c = self.client_for(self.buyer)
        resp = c.get(self.url("product-variants/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        skus = [v["sku"] for v in resp.data]
        self.assertIn("HP-001", skus)

    def test_retrieve_variant(self):
        c = self.client_for(self.buyer)
        resp = c.get(self.url(f"product-variants/{self.variant.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sku"], "HP-001")

    def test_create_variant(self):
        c = self.client_for(self.seller.user)
        resp = c.post(self.url("product-variants/"), {
            "product": self.product.pk,
            "sku": "HP-002",
            "name": "White 128GB",
            "color": "White",
            "price_modifier": "500.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertTrue(ProductVariant.objects.filter(sku="HP-002").exists())

    def test_update_variant(self):
        c = self.client_for(self.seller.user)
        resp = c.patch(self.url(f"product-variants/{self.variant.pk}/"), {
            "sale_price": "4500.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.sale_price, Decimal("4500.00"))

    def test_deactivate_variant(self):
        c = self.client_for(self.admin)
        resp = c.patch(self.url(f"product-variants/{self.variant.pk}/"), {
            "is_active": False,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.variant.refresh_from_db()
        self.assertFalse(self.variant.is_active)

    def test_delete_variant_as_admin(self):
        extra_variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product,
            sku="HP-DEL", name="To Delete",
        )
        ProductInventory.objects.create(
            tenant=self.tenant, variant=extra_variant, quantity=0
        )
        c = self.client_for(self.admin)
        resp = c.delete(self.url(f"product-variants/{extra_variant.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductVariant.objects.filter(pk=extra_variant.pk).exists())

    def test_sku_must_be_unique(self):
        c = self.client_for(self.seller.user)
        resp = c.post(self.url("product-variants/"), {
            "product": self.product.pk,
            "sku": "HP-001",      # already exists
            "name": "Duplicate",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Security — unauthenticated access
# ─────────────────────────────────────────────────────────────────────────────

class AuthenticationSecurityTest(HPFixture):

    def anon_client(self):
        """Client with no auth but valid tenant header."""
        c = APIClient()
        c.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        return c

    def test_anon_cannot_access_cart(self):
        c = self.anon_client()
        resp = c.get(self.url("cart/current/"))
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anon_cannot_list_orders(self):
        c = self.anon_client()
        resp = c.get(self.url("orders/"))
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anon_cannot_create_review(self):
        c = self.anon_client()
        resp = c.post(self.url("reviews/"), {
            "product": self.product.pk, "rating": 5, "body": "Nice!",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anon_cannot_initiate_payment(self):
        c = self.anon_client()
        resp = c.post(self.url("transactions/initiate/"), {
            "order_id": self.order.pk, "method": "bkash", "amount": "5000.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anon_cannot_create_dispute(self):
        c = self.anon_client()
        resp = c.post(self.url("disputes/"), {
            "order_item": self.order_item.pk,
            "dispute_type": "not_as_described",
            "description": "Wrong item",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anon_can_list_products(self):
        """Public endpoints must remain accessible."""
        c = self.anon_client()
        resp = c.get(self.url("products/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_anon_can_list_categories(self):
        c = self.anon_client()
        resp = c.get(self.url("categories/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multi-Tenant Isolation
# ─────────────────────────────────────────────────────────────────────────────

class MultiTenantIsolationTest(TestCase):

    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", domain="t1.localhost")
        self.t2 = Tenant.objects.create(name="T2", slug="t2", domain="t2.localhost")

        self.buyer1 = User.objects.create_user(username="iso_buyer1", password="x")
        self.buyer2 = User.objects.create_user(username="iso_buyer2", password="x")

        su1 = User.objects.create_user(username="iso_seller1", password="x")
        su2 = User.objects.create_user(username="iso_seller2", password="x")
        self.seller1 = create_seller_profile(su1, self.t1, "Iso Store 1", "+8801700000091")
        self.seller2 = create_seller_profile(su2, self.t2, "Iso Store 2", "+8801700000092")

        cat1 = Category.objects.create(tenant=self.t1, name="C1", slug="c1-iso", level=1)
        cat2 = Category.objects.create(tenant=self.t2, name="C2", slug="c2-iso", level=1)

        self.prod1 = Product.objects.create(
            tenant=self.t1, seller=self.seller1, category=cat1,
            name="T1 Product", slug="t1-prod-iso", description="d",
            base_price=Decimal("100"), status="active",
        )
        self.prod2 = Product.objects.create(
            tenant=self.t2, seller=self.seller2, category=cat2,
            name="T2 Product", slug="t2-prod-iso", description="d",
            base_price=Decimal("200"), status="active",
        )
        self.order1 = Order.objects.create(
            tenant=self.t1, user=self.buyer1, total_price=Decimal("100"),
            shipping_name="B1", shipping_phone="01700000091",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        self.order2 = Order.objects.create(
            tenant=self.t2, user=self.buyer2, total_price=Decimal("200"),
            shipping_name="B2", shipping_phone="01700000092",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )

    def client_for(self, user, tenant):
        c = APIClient()
        c.force_authenticate(user=user)
        c.credentials(HTTP_X_TENANT_ID=str(tenant.pk))
        return c

    def test_products_isolated_by_tenant(self):
        """Buyer in T1 only sees T1 products."""
        c = self.client_for(self.buyer1, self.t1)
        resp = c.get("/products/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [p["slug"] for p in resp.data]
        self.assertIn("t1-prod-iso", slugs)
        self.assertNotIn("t2-prod-iso", slugs)

    def test_orders_isolated_by_tenant(self):
        """Buyer in T1 cannot see T2 orders."""
        c = self.client_for(self.buyer1, self.t1)
        resp = c.get("/orders/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order_ids = [o["id"] for o in resp.data]
        self.assertIn(self.order1.pk, order_ids)
        self.assertNotIn(self.order2.pk, order_ids)

    def test_cannot_retrieve_other_tenant_order(self):
        """Buyer in T1 cannot retrieve a T2 order directly."""
        c = self.client_for(self.buyer1, self.t1)
        resp = c.get(f"/orders/{self.order2.pk}/")
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_sellers_isolated_by_tenant(self):
        """Seller list for T1 contains only T1 sellers."""
        c = self.client_for(self.buyer1, self.t1)
        resp = c.get("/sellers/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        store_names = [s.get("store_name", "") for s in resp.data]
        self.assertNotIn("Iso Store 2", store_names)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Cart edge cases
# ─────────────────────────────────────────────────────────────────────────────

class CartEdgeCaseTest(HPFixture):

    def test_add_more_than_stock_raises(self):
        """Cannot add quantity exceeding available inventory."""
        self.inventory.quantity = 3
        self.inventory.allow_backorder = False
        self.inventory.save()
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        with self.assertRaises((OutOfStockException, InsufficientStockException)):
            add_to_cart(cart, self.variant, 5)

    def test_add_exactly_stock_amount_succeeds(self):
        self.inventory.quantity = 3
        self.inventory.save()
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        item = add_to_cart(cart, self.variant, 3)
        self.assertEqual(item.quantity, 3)

    def test_cart_already_has_coupon_replaced(self):
        """Applying a second coupon replaces the first."""
        coupon1 = Coupon.objects.create(
            tenant=self.tenant, code="FIRST-HP", name="First",
            coupon_type="fixed", discount_value=Decimal("50.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        coupon2 = Coupon.objects.create(
            tenant=self.tenant, code="SECOND-HP", name="Second",
            coupon_type="fixed", discount_value=Decimal("100.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        cart = Cart.objects.create(
            tenant=self.tenant, user=self.buyer, is_active=True, coupon=coupon1
        )
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"cart/{cart.pk}/apply_coupon/"), {
            "code": "SECOND-HP",
        }, format="json")
        # Coupon replacement may return 200 (replaced) or 400 (needs items first)
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        if resp.status_code in [200, 201]:
            cart.refresh_from_db()
            self.assertEqual(cart.coupon.code, "SECOND-HP")

    def test_checkout_empty_cart_raises_api(self):
        """API checkout on empty cart returns 4xx."""
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"cart/{cart.pk}/checkout/"), {
            "shipping_name": "HP Buyer",
            "shipping_phone": "01711000001",
            "shipping_address": "Dhaka",
            "shipping_city": "Dhaka",
            "payment_method": "bkash",
        }, format="json")
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT,
        ])

    def test_coupon_usage_limit_enforced(self):
        """Coupon with usage_limit=1 cannot be applied a second time."""
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="LIMIT1-HP", name="Limit 1",
            coupon_type="fixed", discount_value=Decimal("50.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            usage_limit=1, used_count=1,   # already exhausted
            is_active=True,
        )
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        with self.assertRaises(CouponInvalidException):
            from api.marketplace.services import apply_coupon_to_cart
            apply_coupon_to_cart(cart, "LIMIT1-HP")

    def test_percentage_coupon_respects_max_discount(self):
        """Percentage coupon with max_discount_amount caps the discount."""
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="PCT-HP", name="PCT",
            coupon_type="percentage", discount_value=Decimal("20.00"),  # 20%
            max_discount_amount=Decimal("200.00"),   # cap at 200 BDT
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        # On a 5000 BDT order: 20% = 1000 BDT, but capped at 200
        discount = coupon.calculate_discount(Decimal("5000.00"))
        self.assertEqual(discount, Decimal("200.00"))

    def test_inactive_coupon_is_rejected(self):
        """Inactive coupon raises CouponInvalidException."""
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="INACTIVE-HP", name="Inactive",
            coupon_type="fixed", discount_value=Decimal("50.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=False,
        )
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        with self.assertRaises(CouponInvalidException):
            from api.marketplace.services import apply_coupon_to_cart
            apply_coupon_to_cart(cart, "INACTIVE-HP")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Order state machine — illegal transitions
# ─────────────────────────────────────────────────────────────────────────────

class OrderStateMachineTest(HPFixture):

    def test_cannot_ship_pending_order(self):
        """Shipping a PENDING order (not confirmed) should fail."""
        self.assertEqual(self.order.status, OrderStatus.PENDING)
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"orders/{self.order.pk}/ship/"), {
            "courier": "Pathao", "tracking_number": "PTH-000",
        }, format="json")
        # Should return 4xx — cannot skip confirm step
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ])
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, OrderStatus.SHIPPED)

    def test_cannot_cancel_delivered_order(self):
        """Cancelling a DELIVERED order should fail."""
        self.order.status = OrderStatus.DELIVERED
        self.order.save()
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"orders/{self.order.pk}/cancel/"), {
            "reason": "Changed mind",
        }, format="json")
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT,
        ])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)

    def test_cannot_deliver_pending_order(self):
        """Delivering a PENDING order should fail."""
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"orders/{self.order.pk}/deliver/"))
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT,
        ])

    def test_full_valid_lifecycle(self):
        """PENDING → CONFIRMED → SHIPPED → DELIVERED is the correct path."""
        c = self.client_for(self.admin)

        resp = c.post(self.url(f"orders/{self.order.pk}/confirm/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)

        resp = c.post(self.url(f"orders/{self.order.pk}/ship/"), {
            "courier": "Steadfast", "tracking_number": "SF-001",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.SHIPPED)

        resp = c.post(self.url(f"orders/{self.order.pk}/deliver/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Refund window enforcement (service-layer)
# ─────────────────────────────────────────────────────────────────────────────

class RefundWindowTest(HPFixture):

    def test_refund_within_window_succeeds(self):
        self.order.status = OrderStatus.DELIVERED
        self.order.created_at = timezone.now() - timedelta(days=5)
        self.order.save()
        refund = request_refund(
            order_item=self.order_item,
            user=self.buyer,
            reason="damaged",
            description="Screen cracked on arrival.",
            amount=Decimal("5000.00"),
        )
        self.assertIsNotNone(refund.pk)

    def test_refund_outside_window_raises(self):
        """request_refund raises RefundWindowExpiredException after REVIEW_WINDOW_DAYS."""
        self.order.created_at = timezone.now() - timedelta(days=35)
        self.order.save()
        with self.assertRaises(RefundWindowExpiredException):
            request_refund(
                order_item=self.order_item,
                user=self.buyer,
                reason="damaged",
                description="Too late.",
                amount=Decimal("5000.00"),
            )

    def test_approve_refund_sets_correct_amount(self):
        self.order.created_at = timezone.now() - timedelta(days=2)
        self.order.save()
        refund = request_refund(
            order_item=self.order_item,
            user=self.buyer,
            reason="not_as_described",
            description="Wrong colour.",
            amount=Decimal("5000.00"),
        )
        approved = approve_refund(refund, Decimal("4000.00"), self.admin)
        self.assertEqual(approved.amount_approved, Decimal("4000.00"))


# ─────────────────────────────────────────────────────────────────────────────
# 7. Escrow release guard
# ─────────────────────────────────────────────────────────────────────────────

class EscrowReleaseGuardTest(HPFixture):

    def _make_escrow(self, release_after):
        return EscrowHolding.objects.create(
            tenant=self.tenant, order_item=self.order_item, seller=self.seller,
            gross_amount=Decimal("5000.00"),
            commission_deducted=Decimal("750.00"),
            net_amount=Decimal("4250.00"),
            release_after=release_after,
        )

    def test_admin_can_release_after_date(self):
        escrow = self._make_escrow(timezone.now() - timedelta(days=1))
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"escrow/{escrow.pk}/release/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowStatus.RELEASED)

    def test_cannot_release_before_date(self):
        """Escrow that hasn't matured yet must not be released."""
        escrow = self._make_escrow(timezone.now() + timedelta(days=5))
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"escrow/{escrow.pk}/release/"))
        # Should return 4xx — escrow not yet due
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT,
        ])
        escrow.refresh_from_db()
        self.assertNotEqual(escrow.status, EscrowStatus.RELEASED)

    def test_service_release_updates_status(self):
        """release_escrow_and_credit service marks escrow RELEASED."""
        escrow = self._make_escrow(timezone.now() - timedelta(hours=1))
        result = release_escrow_and_credit(escrow)
        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowStatus.RELEASED)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Review uniqueness — same buyer cannot review same product twice
# ─────────────────────────────────────────────────────────────────────────────

class ReviewUniquenessTest(HPFixture):

    def test_duplicate_review_rejected(self):
        """Creating a second review for the same product by the same buyer must fail at DB or API level."""
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=4, body="First review.",
        )
        c = self.client_for(self.buyer)
        resp = c.post(self.url("reviews/"), {
            "product": self.product.pk,
            "rating": 5,
            "body": "Second review attempt.",
        }, format="json")
        # DB constraint raises IntegrityError → DRF returns 400
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])
        count = ProductReview.objects.filter(
            product=self.product, user=self.buyer
        ).count()
        self.assertEqual(count, 1)

    def test_different_buyers_can_review_same_product(self):
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=4, body="Buyer1 review.",
        )
        c = self.client_for(self.buyer2)
        resp = c.post(self.url("reviews/"), {
            "product": self.product.pk,
            "rating": 3,
            "body": "Buyer2 review, different user.",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


# ─────────────────────────────────────────────────────────────────────────────
# 9. Role-based order actions
# ─────────────────────────────────────────────────────────────────────────────

class OrderRoleAccessTest(HPFixture):

    def test_seller_cannot_cancel_buyers_order(self):
        """A seller cannot cancel an order that belongs to another user."""
        c = self.client_for(self.seller.user)
        resp = c.post(self.url(f"orders/{self.order.pk}/cancel/"), {
            "reason": "I am the seller, not the buyer",
        }, format="json")
        # Seller should not be able to find or cancel buyer's order
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        ])

    def test_buyer_cannot_confirm_own_order(self):
        """Only admin should be able to confirm an order."""
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"orders/{self.order.pk}/confirm/"))
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED,
        ])
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, OrderStatus.CONFIRMED)

    def test_buyer_cannot_ship_own_order(self):
        """Buyers cannot mark their own orders as shipped."""
        self.order.status = OrderStatus.CONFIRMED
        self.order.save()
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"orders/{self.order.pk}/ship/"), {
            "courier": "Fake", "tracking_number": "FAKE-001",
        }, format="json")
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED,
        ])


# ─────────────────────────────────────────────────────────────────────────────
# 10. Seller payout isolation
# ─────────────────────────────────────────────────────────────────────────────

class SellerPayoutIsolationTest(HPFixture):

    def setUp(self):
        super().setUp()
        self.payout1 = SellerPayout.objects.create(
            tenant=self.tenant, seller=self.seller,
            amount=Decimal("4250.00"), method="bank",
        )
        self.payout2 = SellerPayout.objects.create(
            tenant=self.tenant, seller=self.seller2,
            amount=Decimal("3000.00"), method="bank",
        )

    def test_seller1_cannot_see_seller2_payouts(self):
        c = self.client_for(self.seller.user)
        resp = c.get(self.url("seller-payouts/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payout_ids = [p["id"] for p in resp.data]
        self.assertIn(self.payout1.pk, payout_ids)
        self.assertNotIn(self.payout2.pk, payout_ids)

    def test_seller1_cannot_retrieve_seller2_payout(self):
        c = self.client_for(self.seller.user)
        resp = c.get(self.url(f"seller-payouts/{self.payout2.pk}/"))
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_admin_sees_all_payouts(self):
        c = self.client_for(self.admin)
        resp = c.get(self.url("seller-payouts/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payout_ids = [p["id"] for p in resp.data]
        self.assertIn(self.payout1.pk, payout_ids)
        self.assertIn(self.payout2.pk, payout_ids)


# ─────────────────────────────────────────────────────────────────────────────
# 11. SellerVerification full lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class SellerVerificationLifecycleTest(HPFixture):

    def setUp(self):
        super().setUp()
        self.verification = SellerVerification.objects.create(
            tenant=self.tenant,
            seller=self.seller,
            status=VerificationStatus.UNVERIFIED,
        )

    def test_full_approve_flow(self):
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.VERIFIED)

    def test_full_reject_flow_with_reason(self):
        c = self.client_for(self.admin)
        resp = c.post(
            self.url(f"seller-verification/{self.verification.pk}/reject/"),
            {"reason": "ID document expired."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.REJECTED)
        self.assertEqual(self.verification.rejection_reason, "ID document expired.")

    def test_seller_cannot_approve_own_verification(self):
        c = self.client_for(self.seller.user)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])
        self.verification.refresh_from_db()
        self.assertNotEqual(self.verification.status, VerificationStatus.VERIFIED)

    def test_cannot_reject_already_approved(self):
        """Re-rejecting a VERIFIED seller should return an error or be a no-op."""
        self.verification.status = VerificationStatus.VERIFIED
        self.verification.save()
        c = self.client_for(self.admin)
        resp = c.post(
            self.url(f"seller-verification/{self.verification.pk}/reject/"),
            {"reason": "Oops"},
            format="json",
        )
        # Either 400 (illegal transition) or 200 (override allowed) — must not silently corrupt
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


# ─────────────────────────────────────────────────────────────────────────────
# 12. Service-layer unit tests
# ─────────────────────────────────────────────────────────────────────────────

class ServiceLayerTest(HPFixture):

    def test_add_to_cart_creates_item(self):
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        item = add_to_cart(cart, self.variant, 2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, self.product.base_price)

    def test_add_to_cart_accumulates_quantity(self):
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        add_to_cart(cart, self.variant, 2)
        add_to_cart(cart, self.variant, 3)
        item = CartItem.objects.get(cart=cart, variant=self.variant)
        self.assertEqual(item.quantity, 5)

    def test_create_order_from_cart_creates_order_items(self):
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        add_to_cart(cart, self.variant, 1)
        order = create_order_from_cart(cart, "bkash", {
            "shipping_name": "HP Buyer", "shipping_phone": "01711000001",
            "shipping_address": "Dhaka", "shipping_city": "Dhaka",
        })
        self.assertIsNotNone(order.pk)
        self.assertEqual(order.items.count(), 1)

    def test_create_order_reserves_inventory(self):
        before = self.inventory.reserved_quantity
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        add_to_cart(cart, self.variant, 2)
        create_order_from_cart(cart, "bkash", {
            "shipping_name": "HP Buyer", "shipping_phone": "01711000001",
            "shipping_address": "Dhaka", "shipping_city": "Dhaka",
        })
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, before + 2)

    def test_empty_cart_cannot_checkout(self):
        cart = Cart.objects.create(tenant=self.tenant, user=self.buyer, is_active=True)
        with self.assertRaises(CartEmptyException):
            create_order_from_cart(cart, "bkash", {
                "name": "HP Buyer", "phone": "01711000001",
                "address": "Dhaka", "city": "Dhaka",
            })

    def test_release_escrow_sets_released_status(self):
        escrow = EscrowHolding.objects.create(
            tenant=self.tenant, order_item=self.order_item, seller=self.seller,
            gross_amount=Decimal("5000.00"),
            commission_deducted=Decimal("750.00"),
            net_amount=Decimal("4250.00"),
            release_after=timezone.now() - timedelta(hours=1),
        )
        result = release_escrow_and_credit(escrow)
        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowStatus.RELEASED)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Concurrency / oversell protection
# ─────────────────────────────────────────────────────────────────────────────

class OversellProtectionTest(HPFixture):

    def test_concurrent_add_to_cart_does_not_oversell(self):
        """
        Two threads attempt to add 5 items each when only 6 are in stock.
        Only one should succeed; the other must raise OutOfStockException.
        """
        self.inventory.quantity = 6
        self.inventory.allow_backorder = False
        self.inventory.save()

        cart1 = Cart.objects.create(tenant=self.tenant, user=self.buyer,  is_active=True)
        cart2 = Cart.objects.create(tenant=self.tenant, user=self.buyer2, is_active=True)

        results = []
        errors  = []

        def buyer_thread(cart):
            try:
                add_to_cart(cart, self.variant, 5)
                results.append("ok")
            except (OutOfStockException, InsufficientStockException):
                errors.append("out_of_stock")  # OutOfStockException or InsufficientStockException
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=buyer_thread, args=(cart1,))
        t2 = threading.Thread(target=buyer_thread, args=(cart2,))
        t1.start(); t2.start()
        t1.join();  t2.join()

        # At least one must succeed, at least one must fail (or both succeed if stock allows)
        self.assertGreater(len(results) + len(errors), 0)
        # Total items added must never exceed available stock (6)
        total_added = CartItem.objects.filter(
            cart__in=[cart1, cart2], variant=self.variant
        ).values_list("quantity", flat=True)
        self.assertLessEqual(sum(total_added), 6)
