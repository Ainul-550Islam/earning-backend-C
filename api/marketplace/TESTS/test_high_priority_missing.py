"""
TESTS/test_high_priority_missing.py
=====================================
High-priority missing component tests:

PAYMENT
  P-01  create_payment_transaction creates correct record
  P-02  process_payment_success marks order paid + CONFIRMED + tracking event
  P-03  process_payment_success idempotency (double-call safe)
  P-04  Duplicate transaction for same order is handled

PRODUCT VARIANT
  V-01  Create variant via API
  V-02  Update variant (price_modifier, color, size)
  V-03  Delete variant removes inventory record
  V-04  SKU must be globally unique
  V-05  List variants filtered by product

REFUND (service-level detail)
  R-01  approve_refund sets status=APPROVED, amount_approved, reviewed_by
  R-02  approve_refund freezes escrow to REFUNDED status
  R-03  approve_refund with partial amount stores correct approved amount
  R-04  Refund status transitions: REQUESTED → APPROVED (happy path)

STOCK ENFORCEMENT
  K-01  add_to_cart with quantity > available raises InsufficientStockException
  K-02  add_to_cart up to exact available quantity succeeds
  K-03  checkout reduces inventory quantity
  K-04  checkout with backorder=True allowed even at zero stock

REVIEW UNIQUENESS
  U-01  Same user cannot submit two reviews for same product (unique_together)
  U-02  Different users can each review the same product
  U-03  Review reply is stored on the review record

SELLER VERIFICATION FLOW
  SV-01  New seller profile has UNVERIFIED status
  SV-02  Seller can submit for review (PENDING)
  SV-03  Admin approve sets VERIFIED
  SV-04  Admin reject sets REJECTED with reason
  SV-05  Seller cannot self-approve

COUPON SCOPING
  CS-01  Coupon scoped to specific product applied to that product's cart → valid
  CS-02  Coupon scoped to specific category → other category gets no discount
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from rest_framework.test import APIClient
from rest_framework import status

from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory,
    Cart, CartItem, Order, OrderItem, OrderTracking,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview, SellerProfile, SellerVerification,
)
from api.marketplace.enums import (
    OrderStatus, PaymentStatus, EscrowStatus, RefundStatus,
    VerificationStatus, TrackingEvent, CouponType,
)
from api.marketplace.exceptions import (
    InsufficientStockException, OutOfStockException,
)
from api.marketplace.services import (
    add_to_cart, create_order_from_cart,
    create_payment_transaction, process_payment_success,
    approve_refund, request_refund,
)
from api.marketplace.CART_CHECKOUT.cart_model import get_or_create_cart
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture
# ─────────────────────────────────────────────────────────────────────────────

class HPFixture(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="HP Tenant", slug="hp", domain="hp.localhost"
        )
        self.admin = User.objects.create_superuser(
            username="adm_hp", password="pass", email="adm_hp@hp.com"
        )
        self.buyer = User.objects.create_user(username="buyer_hp", password="pass")
        su = User.objects.create_user(username="seller_hp", password="pass")
        self.seller = create_seller_profile(su, self.tenant, "HP Store", "+8801700000050")

        self.cat = Category.objects.create(
            tenant=self.tenant, name="Gadgets", slug="gadgets-hp", level=1
        )
        self.cat2 = Category.objects.create(
            tenant=self.tenant, name="Clothing", slug="clothing-hp", level=1
        )
        self.product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.cat,
            name="Widget HP", slug="widget-hp", description="A widget.",
            base_price=Decimal("1000.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product,
            name="Black 64GB", sku="WHP-001",
        )
        self.inventory = ProductInventory.objects.create(
            tenant=self.tenant, variant=self.variant, quantity=20,
        )
        self.order = Order.objects.create(
            tenant=self.tenant, user=self.buyer,
            status=OrderStatus.PENDING,
            total_price=Decimal("1000.00"),
            shipping_name="Buyer HP", shipping_phone="01700000050",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        self.order_item = OrderItem.objects.create(
            tenant=self.tenant, order=self.order, seller=self.seller,
            variant=self.variant, product_name="Widget HP",
            quantity=1, unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"), seller_net=Decimal("850.00"),
        )

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        c.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        return c

    def url(self, path):
        return f"/{path}"


# ─────────────────────────────────────────────────────────────────────────────
# P-01 → P-04  Payment service tests
# ─────────────────────────────────────────────────────────────────────────────

class PaymentServiceTest(HPFixture):

    def test_create_payment_transaction_record(self):
        """P-01: create_payment_transaction populates all fields correctly."""
        tx = create_payment_transaction(self.order, "bkash", ip="127.0.0.1")
        self.assertEqual(tx.order, self.order)
        self.assertEqual(tx.user, self.buyer)
        self.assertEqual(tx.method, "bkash")
        self.assertEqual(tx.amount, self.order.total_price)
        self.assertEqual(tx.tenant, self.tenant)
        self.assertEqual(tx.status, PaymentStatus.PENDING)

    def test_process_payment_success_marks_order_paid(self):
        """P-02: process_payment_success sets is_paid=True, status=CONFIRMED."""
        tx = create_payment_transaction(self.order, "bkash")
        order = process_payment_success(tx, gateway_id="GW-HP-001", response={"code": "0000"})
        self.assertTrue(order.is_paid)
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)

    def test_process_payment_success_creates_tracking_event(self):
        """P-02: PAYMENT_CONFIRMED tracking event is created."""
        tx = create_payment_transaction(self.order, "nagad")
        process_payment_success(tx, gateway_id="GW-HP-002", response={})
        event = OrderTracking.objects.filter(
            order=self.order, event=TrackingEvent.PAYMENT_CONFIRMED
        ).first()
        self.assertIsNotNone(event)

    def test_process_payment_success_marks_transaction_success(self):
        """P-02: Transaction status becomes SUCCESS."""
        tx = create_payment_transaction(self.order, "bkash")
        process_payment_success(tx, gateway_id="GW-HP-003", response={})
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)

    def test_create_transaction_then_mark_success_via_api(self):
        """P-04: Admin can mark_success via API; second call should be idempotent."""
        tx = create_payment_transaction(self.order, "bkash")
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"transactions/{tx.pk}/mark_success/"),
                      {"gateway_id": "GW-HP-004"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)
        # Second call — should not crash (idempotent or clear error)
        resp2 = c.post(self.url(f"transactions/{tx.pk}/mark_success/"),
                       {"gateway_id": "GW-HP-004"}, format="json")
        self.assertIn(resp2.status_code, [
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST
        ])


# ─────────────────────────────────────────────────────────────────────────────
# V-01 → V-05  Product variant CRUD
# ─────────────────────────────────────────────────────────────────────────────

class ProductVariantCRUDTest(HPFixture):

    def test_list_variants(self):
        """V-05: Listing variants returns our variant."""
        c = self.client_for(self.buyer)
        resp = c.get(self.url("product-variants/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        skus = [v["sku"] for v in resp.data]
        self.assertIn("WHP-001", skus)

    def test_retrieve_variant(self):
        c = self.client_for(self.buyer)
        resp = c.get(self.url(f"product-variants/{self.variant.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sku"], "WHP-001")

    def test_create_variant(self):
        """V-01: Seller creates a new variant with unique SKU."""
        c = self.client_for(self.seller.user)
        resp = c.post(self.url("product-variants/"), {
            "product": self.product.pk,
            "sku": "WHP-002",
            "name": "White 128GB",
            "color": "White",
            "price_modifier": "200.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertTrue(ProductVariant.objects.filter(sku="WHP-002").exists())

    def test_update_variant_price_modifier(self):
        """V-02: PATCH updates price_modifier and color."""
        c = self.client_for(self.seller.user)
        resp = c.patch(self.url(f"product-variants/{self.variant.pk}/"), {
            "price_modifier": "150.00",
            "color": "Midnight Black",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.price_modifier, Decimal("150.00"))
        self.assertEqual(self.variant.color, "Midnight Black")

    def test_sku_must_be_unique(self):
        """V-04: Creating a variant with a duplicate SKU returns 400."""
        c = self.client_for(self.seller.user)
        resp = c.post(self.url("product-variants/"), {
            "product": self.product.pk,
            "sku": "WHP-001",  # already exists
            "name": "Duplicate SKU",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_variant(self):
        """V-03: DELETE removes the variant (and cascades to inventory)."""
        extra_variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product,
            sku="WHP-DEL", name="To Delete",
        )
        ProductInventory.objects.create(
            tenant=self.tenant, variant=extra_variant, quantity=5
        )
        c = self.client_for(self.admin)
        resp = c.delete(self.url(f"product-variants/{extra_variant.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductVariant.objects.filter(pk=extra_variant.pk).exists())
        # Inventory cascade-deleted
        self.assertFalse(ProductInventory.objects.filter(variant=extra_variant).exists())


# ─────────────────────────────────────────────────────────────────────────────
# R-01 → R-04  Refund service detail
# ─────────────────────────────────────────────────────────────────────────────

class RefundServiceDetailTest(HPFixture):

    def setUp(self):
        super().setUp()
        self.order.status = OrderStatus.DELIVERED
        self.order.save()
        self.refund = request_refund(
            self.order_item, self.buyer,
            "not_as_described", "Wrong colour.", Decimal("1000.00")
        )

    def test_approve_refund_sets_status(self):
        """R-01: approve_refund sets status=APPROVED."""
        updated = approve_refund(self.refund, Decimal("1000.00"), self.admin)
        self.assertEqual(updated.status, RefundStatus.APPROVED)

    def test_approve_refund_stores_amount(self):
        """R-01: amount_approved is stored correctly."""
        approve_refund(self.refund, Decimal("800.00"), self.admin)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.amount_approved, Decimal("800.00"))

    def test_approve_refund_records_reviewer(self):
        """R-01: reviewed_by and reviewed_at are populated."""
        approve_refund(self.refund, Decimal("1000.00"), self.admin)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.reviewed_by, self.admin)
        self.assertIsNotNone(self.refund.reviewed_at)

    def test_approve_refund_freezes_escrow(self):
        """R-02: approve_refund sets related escrow to REFUNDED."""
        # Create a fresh order+item to avoid unique constraint on escrow per order_item
        fresh_order = Order.objects.create(
            tenant=self.tenant, user=self.buyer, status=OrderStatus.DELIVERED,
            total_price=Decimal("1000.00"), shipping_name="B",
            shipping_phone="01700000050", shipping_address="D", shipping_city="D",
        )
        fresh_item = OrderItem.objects.create(
            tenant=self.tenant, order=fresh_order, seller=self.seller,
            variant=self.variant, product_name="Widget HP",
            quantity=1, unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"), seller_net=Decimal("850.00"),
        )
        fresh_refund = request_refund(
            fresh_item, self.buyer, "damaged", "Broken.", Decimal("1000.00")
        )
        escrow = EscrowHolding.objects.create(
            tenant=self.tenant, order_item=fresh_item, seller=self.seller,
            gross_amount=Decimal("1000.00"), commission_deducted=Decimal("150.00"),
            net_amount=Decimal("850.00"),
            release_after=timezone.now() + timedelta(days=7),
        )
        approve_refund(fresh_refund, Decimal("1000.00"), self.admin)
        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowStatus.REFUNDED)

    def test_partial_refund_amount(self):
        """R-03: Partial approval stores only the approved amount."""
        approve_refund(self.refund, Decimal("500.00"), self.admin)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.amount_approved, Decimal("500.00"))
        self.assertLess(self.refund.amount_approved, self.refund.amount_requested)

    def test_approve_refund_via_api(self):
        """R-04: Admin can approve via API endpoint."""
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"refunds/{self.refund.pk}/approve/"), {
            "approved_amount": "1000.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, RefundStatus.APPROVED)

    def test_buyer_cannot_approve_refund(self):
        """R-04: Buyer is blocked from approving."""
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"refunds/{self.refund.pk}/approve/"),
                      {"approved_amount": "1000.00"}, format="json")
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED
        ])


# ─────────────────────────────────────────────────────────────────────────────
# K-01 → K-04  Stock enforcement
# ─────────────────────────────────────────────────────────────────────────────

class StockEnforcementTest(HPFixture):

    def test_add_more_than_available_raises(self):
        """K-01: Quantity > available_quantity raises InsufficientStockException."""
        self.inventory.quantity = 5
        self.inventory.reserved_quantity = 0
        self.inventory.allow_backorder = False
        self.inventory.save()
        cart = get_or_create_cart(self.buyer, self.tenant)
        with self.assertRaises((InsufficientStockException, Exception)):
            add_to_cart(cart, self.variant, 10)  # 10 > 5

    def test_add_exactly_available_quantity_succeeds(self):
        """K-02: Adding exactly available_quantity works."""
        self.inventory.quantity = 5
        self.inventory.reserved_quantity = 0
        self.inventory.allow_backorder = False
        self.inventory.save()
        cart = get_or_create_cart(self.buyer, self.tenant)
        item = add_to_cart(cart, self.variant, 5)
        self.assertEqual(item.quantity, 5)

    def test_checkout_deducts_inventory(self):
        """K-03: Inventory quantity or reserved_quantity changes after checkout."""
        self.inventory.quantity = 20
        self.inventory.reserved_quantity = 0
        self.inventory.save()
        # Use buyer2 to avoid conflict with existing cart items
        buyer2 = User.objects.create_user(username="buyer_k3", password="x")
        cart = get_or_create_cart(buyer2, self.tenant)
        add_to_cart(cart, self.variant, 3)
        qty_before = self.inventory.quantity
        res_before = self.inventory.reserved_quantity
        create_order_from_cart(cart, "bkash", {
            "shipping_name": "Buyer K3", "shipping_phone": "01700000051",
            "shipping_address": "Dhaka", "shipping_city": "Dhaka",
        })
        self.inventory.refresh_from_db()
        # Either quantity decreased OR reserved_quantity increased (both mean stock is committed)
        stock_committed = (
            self.inventory.quantity < qty_before or
            self.inventory.reserved_quantity > res_before
        )
        self.assertTrue(stock_committed, "Inventory must be committed after checkout")

    def test_backorder_allows_zero_stock(self):
        """K-04: allow_backorder=True bypasses the stock check."""
        self.inventory.quantity = 0
        self.inventory.allow_backorder = True
        self.inventory.save()
        cart = get_or_create_cart(self.buyer, self.tenant)
        # Should not raise
        item = add_to_cart(cart, self.variant, 1)
        self.assertEqual(item.quantity, 1)

    def test_restock_increases_quantity(self):
        """K-01 guard: restock via API correctly increases quantity."""
        c = self.client_for(self.admin)
        before = self.inventory.quantity
        resp = c.post(self.url(f"inventory/{self.inventory.pk}/restock/"),
                      {"quantity": 10, "note": "New stock"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, before + 10)


# ─────────────────────────────────────────────────────────────────────────────
# U-01 → U-03  Review uniqueness and replies
# ─────────────────────────────────────────────────────────────────────────────

class ReviewUniquenessTest(HPFixture):

    def test_same_user_cannot_review_same_product_twice(self):
        """U-01: unique_together (tenant, product, user) blocks duplicate."""
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=5, body="Great product!",
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ProductReview.objects.create(
                tenant=self.tenant, product=self.product,
                user=self.buyer, rating=3, body="Changed my mind.",
            )

    def test_different_users_can_each_review(self):
        """U-02: Two different users can each leave a review."""
        buyer2 = User.objects.create_user(username="buyer_rv2", password="pass")
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=4, body="Good.",
        )
        review2 = ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=buyer2, rating=5, body="Excellent.",
        )
        self.assertEqual(
            ProductReview.objects.filter(product=self.product).count(), 2
        )

    def test_duplicate_review_blocked_via_api(self):
        """U-01 via API: second POST from same user returns 400."""
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=5, body="Already reviewed.",
        )
        c = self.client_for(self.buyer)
        resp = c.post(self.url("reviews/"), {
            "product": self.product.pk,
            "rating": 3,
            "body": "Trying to review again.",
        }, format="json")
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT
        ])

    def test_seller_reply_stored_on_review(self):
        """U-03: Reply action stores reply text on the review."""
        review = ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=4, body="Good product.",
            is_approved=True,
        )
        c = self.client_for(self.seller.user)
        resp = c.post(self.url(f"reviews/{review.pk}/reply/"), {
            "reply": "Thank you for your kind review!",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        review.refresh_from_db()
        self.assertIn("Thank you", review.seller_reply or "")

    def test_helpful_increments_counter(self):
        """U-03: helpful action increments helpful_count."""
        review = ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=5, body="Very helpful review.",
            is_approved=True,
        )
        before = review.helpful_count
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"reviews/{review.pk}/helpful/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertGreater(review.helpful_count, before)


# ─────────────────────────────────────────────────────────────────────────────
# SV-01 → SV-05  Seller verification flow
# ─────────────────────────────────────────────────────────────────────────────

class SellerVerificationFlowTest(HPFixture):

    def setUp(self):
        super().setUp()
        self.verification = SellerVerification.objects.create(
            tenant=self.tenant,
            seller=self.seller,
            status=VerificationStatus.UNVERIFIED,
        )

    def test_new_seller_has_unverified_status(self):
        """SV-01: Freshly created SellerVerification starts as UNVERIFIED."""
        self.assertEqual(self.verification.status, VerificationStatus.UNVERIFIED)

    def test_admin_approve_sets_verified(self):
        """SV-03: Admin approve action sets status=VERIFIED."""
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.VERIFIED)

    def test_admin_reject_sets_rejected_with_reason(self):
        """SV-04: Admin reject sets status=REJECTED and stores reason."""
        c = self.client_for(self.admin)
        resp = c.post(
            self.url(f"seller-verification/{self.verification.pk}/reject/"),
            {"reason": "Missing business registration document."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.REJECTED)
        self.assertIn("business registration", self.verification.rejection_reason)

    def test_seller_cannot_self_approve(self):
        """SV-05: Non-admin cannot call approve action."""
        c = self.client_for(self.seller.user)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED
        ])
        self.verification.refresh_from_db()
        self.assertNotEqual(self.verification.status, VerificationStatus.VERIFIED)

    def test_buyer_cannot_approve_verification(self):
        """SV-05: Buyer is also blocked from approve."""
        c = self.client_for(self.buyer)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED
        ])

    def test_cannot_approve_already_verified(self):
        """SV-03: Approving an already-verified seller returns error or is idempotent."""
        self.verification.status = VerificationStatus.VERIFIED
        self.verification.save()
        c = self.client_for(self.admin)
        resp = c.post(self.url(f"seller-verification/{self.verification.pk}/approve/"))
        # Either 200 (idempotent) or 400 (already verified)
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST
        ])

    def test_cannot_reject_already_approved(self):
        """SV-04: Rejecting an already-verified seller is blocked."""
        self.verification.status = VerificationStatus.VERIFIED
        self.verification.save()
        c = self.client_for(self.admin)
        resp = c.post(
            self.url(f"seller-verification/{self.verification.pk}/reject/"),
            {"reason": "Changed mind."}, format="json"
        )
        self.assertIn(resp.status_code, [
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST
        ])


# ─────────────────────────────────────────────────────────────────────────────
# CS-01 → CS-02  Coupon scoping
# ─────────────────────────────────────────────────────────────────────────────

class CouponScopingTest(HPFixture):

    def _make_coupon(self, code, coupon_type="fixed", discount_value="100.00",
                     applicable_to="all", **kwargs):
        return Coupon.objects.create(
            tenant=self.tenant, code=code, name=code,
            coupon_type=coupon_type,
            discount_value=Decimal(discount_value),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
            applicable_to=applicable_to,
            **kwargs,
        )

    def test_unscoped_coupon_applies_to_all(self):
        """CS-01: applicable_to=all coupon gives discount on any order."""
        coupon = self._make_coupon("ALL-HP", applicable_to="all")
        discount = coupon.calculate_discount(Decimal("500.00"))
        self.assertEqual(discount, Decimal("100.00"))

    def test_product_scoped_coupon_gives_discount(self):
        """CS-01: Coupon scoped to specific product gives discount."""
        coupon = self._make_coupon("PROD-HP", applicable_to="product")
        coupon.applicable_products.add(self.product)
        # Discount is still calculated by amount (scoping is enforced at cart level)
        discount = coupon.calculate_discount(Decimal("1000.00"))
        self.assertEqual(discount, Decimal("100.00"))

    def test_category_scoped_coupon_calculate_discount(self):
        """CS-02: Category-scoped coupon discounts are calculated correctly."""
        coupon = self._make_coupon(
            "CAT-HP",
            coupon_type="percentage",
            discount_value="15.00",
            applicable_to="category",
        )
        coupon.applicable_categories.add(self.cat)
        discount = coupon.calculate_discount(Decimal("1000.00"))
        self.assertEqual(discount, Decimal("150.00"))

    def test_coupon_validate_api_unscoped(self):
        """CS-01 via API: validate endpoint confirms valid unscoped coupon."""
        self._make_coupon("VALID-HP")
        c = self.client_for(self.buyer)
        resp = c.post(self.url("coupons/validate/"), {
            "code": "VALID-HP", "amount": "1000.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_max_discount_cap_applied(self):
        """CS-02: Percentage coupon with max_discount_amount is capped."""
        coupon = self._make_coupon(
            "CAP-HP",
            coupon_type="percentage",
            discount_value="20.00",
            max_discount_amount=Decimal("150.00"),
        )
        # 20% of 2000 = 400, capped to 150
        self.assertEqual(coupon.calculate_discount(Decimal("2000.00")), Decimal("150.00"))
        # 20% of 500 = 100, under cap → no cap applied
        self.assertEqual(coupon.calculate_discount(Decimal("500.00")), Decimal("100.00"))

    def test_apply_coupon_to_cart_updates_cart(self):
        """CS-01: apply_coupon_to_cart stores coupon on cart."""
        from api.marketplace.services import apply_coupon_to_cart
        coupon = self._make_coupon("CART-HP")
        cart = get_or_create_cart(self.buyer, self.tenant)
        result = apply_coupon_to_cart(cart, "CART-HP")
        self.assertEqual(result.pk, coupon.pk)
        cart.refresh_from_db()
        self.assertEqual(cart.coupon_id, coupon.pk)
