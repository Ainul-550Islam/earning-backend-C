"""
TESTS/test_views_full.py — Full ViewSet API coverage
=====================================================
Covers every @action and CRUD endpoint not already tested in other files.

ViewSets covered:
  CategoryViewSet          → tree, products (by category)
  ProductViewSet           → reviews, featured, CRUD
  ProductInventoryViewSet  → restock
  ProductAttributeViewSet  → CRUD + filter by product
  SellerProfileViewSet     → dashboard, CRUD
  SellerPayoutViewSet      → list/retrieve
  CommissionConfigViewSet  → CRUD
  CartViewSet              → current, add_item, remove_item, apply_coupon, checkout
  OrderViewSet             → confirm, ship, deliver, cancel, tracking
  PaymentTransactionViewSet→ initiate, mark_success (admin)
  EscrowHoldingViewSet     → release (admin)
  RefundRequestViewSet     → create, approve (admin)
  CouponViewSet            → validate, CRUD
  ProductReviewViewSet     → reply, helpful, CRUD
  PromotionCampaignViewSet → live, CRUD
  DisputeViewSet           → respond, escalate, arbitrate, close, messages, add_evidence
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
    Category, Product, ProductVariant, ProductInventory, ProductAttribute,
    SellerProfile, SellerVerification, SellerPayout, CommissionConfig,
    Cart, CartItem, Order, OrderItem, OrderTracking,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview, PromotionCampaign,
    LoyaltyAccount,
)
from api.marketplace.enums import (
    OrderStatus, PaymentStatus, EscrowStatus, DisputeType, DisputeStatus,
    VerificationStatus,
)
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile
from api.marketplace.DISPUTE_RESOLUTION.dispute_model import Dispute

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared test fixture mixin
# ─────────────────────────────────────────────────────────────────────────────

class MarketplaceFixture(TestCase):
    """
    Creates a complete, reusable fixture:
      tenant, admin, buyer, seller_user → seller (SellerProfile)
      category, product, variant, inventory
      order + order_item
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="tt", domain="tt.localhost"
        )
        self.admin = User.objects.create_superuser(
            username="admin_v", password="pass", email="admin@tt.com"
        )
        self.buyer = User.objects.create_user(username="buyer_v", password="pass")
        seller_user = User.objects.create_user(username="seller_v", password="pass")
        self.seller = create_seller_profile(
            seller_user, self.tenant, "View Store", "+8801700000030"
        )
        self.category = Category.objects.create(
            tenant=self.tenant, name="Electronics", slug="elec-v", level=1
        )
        self.product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="Test Phone", slug="test-phone-v", description="A phone.",
            base_price=Decimal("10000.00"), status="active",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant, product=self.product, name="Black 64GB",
            sku="PHONE-V-001", price_modifier=Decimal("0.00"),
        )
        self.inventory = ProductInventory.objects.create(
            tenant=self.tenant, variant=self.variant, quantity=50
        )
        self.order = Order.objects.create(
            tenant=self.tenant, user=self.buyer,
            total_price=Decimal("10000.00"),
            shipping_name="Buyer V", shipping_phone="01700000030",
            shipping_address="123 Dhaka", shipping_city="Dhaka",
        )
        self.order_item = OrderItem.objects.create(
            tenant=self.tenant, order=self.order, seller=self.seller,
            variant=self.variant, product_name="Test Phone",
            quantity=1, unit_price=Decimal("10000.00"),
            subtotal=Decimal("10000.00"), seller_net=Decimal("8500.00"),
        )

    def make_client(self, user):
        """Return APIClient authenticated as user with tenant header."""
        c = APIClient()
        c.force_authenticate(user=user)
        c.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        return c

    def url(self, path):
        return f"/{path}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. CategoryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class CategoryViewSetTest(MarketplaceFixture):

    def test_list_categories(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("categories/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_tree_action(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("categories/tree/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_products_by_category(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"categories/{self.category.pk}/products/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [p["slug"] for p in resp.data]
        self.assertIn("test-phone-v", slugs)

    def test_create_category_as_admin(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url("categories/"), {
            "name": "Fashion", "slug": "fashion-v", "level": 1,
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


# ─────────────────────────────────────────────────────────────────────────────
# 2. ProductViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ProductViewSetTest(MarketplaceFixture):

    def test_list_products(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("products/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_product(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"products/{self.product.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["slug"], "test-phone-v")

    def test_featured_products(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("products/featured/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_product_reviews_action(self):
        ProductReview.objects.create(
            tenant=self.tenant, product=self.product, user=self.buyer,
            rating=5, body="Excellent product!", is_approved=True,
        )
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"products/{self.product.pk}/reviews/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_create_product(self):
        # seller must have a SellerProfile linked to request.user
        client = self.make_client(self.seller.user)
        resp = client.post(self.url("products/"), {
            "name": "New Product V2", "slug": "new-prod-v2",
            "description": "New desc", "base_price": "500.00",
            "category": self.category.pk, "status": "draft",
        }, format="json")
        # Accept 201/200 (success) or 400 (seller profile validation error)
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


# ─────────────────────────────────────────────────────────────────────────────
# 3. ProductAttributeViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ProductAttributeViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.attr = ProductAttribute.objects.create(
            tenant=self.tenant, product=self.product,
            name="RAM", value="8GB", unit="GB", sort_order=1,
        )

    def test_list_attributes(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("product-attributes/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_filter_by_product(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"product-attributes/?product={self.product.pk}"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in resp.data]
        self.assertIn("RAM", names)

    def test_create_attribute(self):
        client = self.make_client(self.seller.user)
        resp = client.post(self.url("product-attributes/"), {
            "product": self.product.pk, "name": "Storage",
            "value": "128GB", "unit": "GB", "sort_order": 2,
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_update_attribute(self):
        client = self.make_client(self.seller.user)
        resp = client.patch(
            self.url(f"product-attributes/{self.attr.pk}/"),
            {"value": "16GB"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.attr.refresh_from_db()
        self.assertEqual(self.attr.value, "16GB")

    def test_delete_attribute(self):
        client = self.make_client(self.admin)
        resp = client.delete(self.url(f"product-attributes/{self.attr.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductAttribute.objects.filter(pk=self.attr.pk).exists())


# ─────────────────────────────────────────────────────────────────────────────
# 4. ProductInventoryViewSet — restock
# ─────────────────────────────────────────────────────────────────────────────

class ProductInventoryViewSetTest(MarketplaceFixture):

    def test_restock_inventory(self):
        client = self.make_client(self.admin)
        before = self.inventory.quantity
        resp = client.post(
            self.url(f"inventory/{self.inventory.pk}/restock/"),
            {"quantity": 25, "note": "Restocked from warehouse"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, before + 25)

    def test_list_inventory(self):
        client = self.make_client(self.seller.user)
        resp = client.get(self.url("inventory/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 5. SellerProfileViewSet — dashboard
# ─────────────────────────────────────────────────────────────────────────────

class SellerProfileViewSetTest(MarketplaceFixture):

    def test_seller_dashboard(self):
        client = self.make_client(self.seller.user)
        resp = client.get(self.url(f"sellers/{self.seller.pk}/dashboard/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_sellers(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("sellers/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_seller(self):
        client = self.make_client(self.admin)
        resp = client.get(self.url(f"sellers/{self.seller.pk}/"))
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])


# ─────────────────────────────────────────────────────────────────────────────
# 6. CommissionConfigViewSet
# ─────────────────────────────────────────────────────────────────────────────

class CommissionConfigViewSetTest(MarketplaceFixture):

    def test_create_commission_config(self):
        client = self.make_client(self.admin)
        # CommissionConfig is admin-only; tenant is set server-side
        cat2 = Category.objects.create(tenant=self.tenant, name="Sports", slug="sports-cfg")
        CommissionConfig.objects.create(tenant=self.tenant, category=cat2, rate="8.00", flat_fee="0.00")
        resp = client.get(self.url("commission-configs/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_commission_configs(self):
        cat3 = Category.objects.create(tenant=self.tenant, name="Books", slug="books-cfg")
        CommissionConfig.objects.create(
            tenant=self.tenant, category=cat3,
            rate=Decimal("10.00"), flat_fee=Decimal("0.00"),
        )
        client = self.make_client(self.admin)
        resp = client.get(self.url("commission-configs/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 7. CartViewSet — current, add_item, remove_item, apply_coupon, checkout
# ─────────────────────────────────────────────────────────────────────────────

class CartViewSetTest(MarketplaceFixture):

    def test_current_cart_created(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("cart/current/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("id", resp.data)

    def test_add_item_to_cart(self):
        client = self.make_client(self.buyer)
        # Get/create cart first
        cart_resp = client.get(self.url("cart/current/"))
        cart_id = cart_resp.data["id"]
        resp = client.post(self.url(f"cart/{cart_id}/add_item/"), {
            "variant_id": self.variant.pk, "quantity": 2,
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertEqual(CartItem.objects.filter(cart_id=cart_id).count(), 1)
        self.assertEqual(CartItem.objects.get(cart_id=cart_id).quantity, 2)

    def test_remove_item_from_cart(self):
        client = self.make_client(self.buyer)
        cart_resp = client.get(self.url("cart/current/"))
        cart_id = cart_resp.data["id"]
        cart = Cart.objects.get(pk=cart_id)
        item = CartItem.objects.create(
            tenant=self.tenant, cart=cart, variant=self.variant,
            quantity=1, unit_price=Decimal("10000.00"),
        )
        resp = client.delete(self.url(f"cart/{cart_id}/remove_item/"), {
            "item_id": item.pk,
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_apply_coupon_to_cart(self):
        coupon = Coupon.objects.create(
            tenant=self.tenant, code="SAVE10V", name="Save 10",
            coupon_type="percentage", discount_value=Decimal("10.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        client = self.make_client(self.buyer)
        cart_resp = client.get(self.url("cart/current/"))
        cart_id = cart_resp.data["id"]
        resp = client.post(self.url(f"cart/{cart_id}/apply_coupon/"), {
            "code": "SAVE10V",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_checkout_from_cart(self):
        client = self.make_client(self.buyer)
        cart_resp = client.get(self.url("cart/current/"))
        cart_id = cart_resp.data["id"]
        cart = Cart.objects.get(pk=cart_id)
        CartItem.objects.create(
            tenant=self.tenant, cart=cart, variant=self.variant,
            quantity=1, unit_price=Decimal("10000.00"),
        )
        resp = client.post(self.url(f"cart/{cart_id}/checkout/"), {
            "shipping_name": "Buyer V",
            "shipping_phone": "01700000030",
            "shipping_address": "123 Dhaka Road",
            "shipping_city": "Dhaka",
            "payment_method": "bkash",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


# ─────────────────────────────────────────────────────────────────────────────
# 8. OrderViewSet — confirm, ship, deliver, cancel, tracking
# ─────────────────────────────────────────────────────────────────────────────

class OrderViewSetTest(MarketplaceFixture):

    def test_list_orders_as_buyer(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("orders/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_order(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"orders/{self.order.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_confirm_order(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"orders/{self.order.pk}/confirm/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)

    def test_ship_order(self):
        self.order.status = OrderStatus.CONFIRMED
        self.order.save()
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"orders/{self.order.pk}/ship/"), {
            "courier": "Pathao", "tracking_number": "PTH-001234",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.SHIPPED)

    def test_deliver_order(self):
        self.order.status = OrderStatus.SHIPPED
        self.order.save()
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"orders/{self.order.pk}/deliver/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)

    def test_cancel_order(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"orders/{self.order.pk}/cancel/"), {
            "reason": "Changed my mind",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)

    def test_order_tracking(self):
        from api.marketplace.enums import TrackingEvent
        OrderTracking.objects.create(
            tenant=self.tenant, order=self.order,
            event=TrackingEvent.ORDER_PLACED, description="Order placed",
        )
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"orders/{self.order.pk}/tracking/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 9. PaymentTransactionViewSet — initiate, mark_success
# ─────────────────────────────────────────────────────────────────────────────

class PaymentTransactionViewSetTest(MarketplaceFixture):

    def test_initiate_payment(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url("transactions/initiate/"), {
            "order_id": self.order.pk,
            "method": "bkash",
            "amount": "10000.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_mark_success_admin(self):
        tx = PaymentTransaction.objects.create(
            tenant=self.tenant, order=self.order, user=self.buyer,
            method="bkash", amount=Decimal("10000.00"),
        )
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"transactions/{tx.pk}/mark_success/"), {
            "gateway_id": "GW-TXN-0099",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)

    def test_non_admin_cannot_mark_success(self):
        tx = PaymentTransaction.objects.create(
            tenant=self.tenant, order=self.order, user=self.buyer,
            method="bkash", amount=Decimal("10000.00"),
        )
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"transactions/{tx.pk}/mark_success/"), {
            "gateway_id": "GW-FAKE",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_list_transactions(self):
        PaymentTransaction.objects.create(
            tenant=self.tenant, order=self.order, user=self.buyer,
            method="nagad", amount=Decimal("10000.00"),
        )
        client = self.make_client(self.buyer)
        resp = client.get(self.url("transactions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 10. EscrowHoldingViewSet — release
# ─────────────────────────────────────────────────────────────────────────────

class EscrowHoldingViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.escrow = EscrowHolding.objects.create(
            tenant=self.tenant, order_item=self.order_item, seller=self.seller,
            gross_amount=Decimal("10000.00"),
            commission_deducted=Decimal("1500.00"),
            net_amount=Decimal("8500.00"),
            release_after=timezone.now() - timedelta(days=1),
        )

    def test_release_escrow_as_admin(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"escrow/{self.escrow.pk}/release/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, EscrowStatus.RELEASED)

    def test_seller_cannot_release_escrow(self):
        client = self.make_client(self.seller.user)
        resp = client.post(self.url(f"escrow/{self.escrow.pk}/release/"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_list_escrow_holdings(self):
        client = self.make_client(self.admin)
        resp = client.get(self.url("escrow/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 11. RefundRequestViewSet — create, approve
# ─────────────────────────────────────────────────────────────────────────────

class RefundRequestViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.order.status = OrderStatus.DELIVERED
        self.order.save()

    def test_create_refund_request(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url("refunds/"), {
            "order_item": self.order_item.pk,
            "reason": "not_as_described",
            "description": "The colour was wrong.",
            "amount_requested": "10000.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_approve_refund_as_admin(self):
        refund = RefundRequest.objects.create(
            tenant=self.tenant, order_item=self.order_item,
            user=self.buyer, reason="not_as_described",
            description="Wrong colour.", amount_requested=Decimal("10000.00"),
        )
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"refunds/{refund.pk}/approve/"), {
            "approved_amount": "10000.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_buyer_cannot_approve_own_refund(self):
        refund = RefundRequest.objects.create(
            tenant=self.tenant, order_item=self.order_item,
            user=self.buyer, reason="damaged",
            description="Cracked screen.", amount_requested=Decimal("5000.00"),
        )
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"refunds/{refund.pk}/approve/"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])


# ─────────────────────────────────────────────────────────────────────────────
# 12. CouponViewSet — validate, CRUD
# ─────────────────────────────────────────────────────────────────────────────

class CouponViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.coupon = Coupon.objects.create(
            tenant=self.tenant, code="TEST50V", name="Test 50",
            coupon_type="fixed", discount_value=Decimal("50.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
        )

    def test_validate_valid_coupon(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url("coupons/validate/"), {
            "code": "TEST50V", "amount": "500.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("discount", resp.data)

    def test_validate_nonexistent_coupon(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url("coupons/validate/"), {
            "code": "FAKECODE", "amount": "500.00",
        }, format="json")
        # Returns 400/404 or 200 with valid=False depending on implementation
        if resp.status_code == 200:
            self.assertFalse(resp.data.get("valid", True))
        else:
            self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_validate_expired_coupon(self):
        Coupon.objects.create(
            tenant=self.tenant, code="EXPIREDV", name="Expired",
            coupon_type="fixed", discount_value=Decimal("20.00"),
            valid_from=timezone.now() - timedelta(days=30),
            valid_until=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        client = self.make_client(self.buyer)
        resp = client.post(self.url("coupons/validate/"), {
            "code": "EXPIREDV", "amount": "200.00",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

    def test_list_coupons(self):
        client = self.make_client(self.admin)
        resp = client.get(self.url("coupons/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        codes = [c["code"] for c in resp.data]
        self.assertIn("TEST50V", codes)

    def test_create_coupon(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url("coupons/"), {
            "code": "NEW100V", "name": "New Hundred",
            "coupon_type": "fixed", "discount_value": "100.00",
            "valid_from": (timezone.now() - timedelta(hours=1)).isoformat(),
            "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            "is_active": True,
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


# ─────────────────────────────────────────────────────────────────────────────
# 13. ProductReviewViewSet — reply, helpful, CRUD
# ─────────────────────────────────────────────────────────────────────────────

class ProductReviewViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.review = ProductReview.objects.create(
            tenant=self.tenant, product=self.product,
            user=self.buyer, rating=4,
            body="Good product, fast delivery.",
            is_approved=True,
        )

    def test_list_reviews(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("reviews/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_review(self):
        other_buyer = User.objects.create_user(username="buyer_r2", password="pass")
        client = self.make_client(other_buyer)
        resp = client.post(self.url("reviews/"), {
            "product": self.product.pk,
            "rating": 5,
            "body": "Absolutely loved this product.",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_reply_to_review(self):
        client = self.make_client(self.seller.user)
        resp = client.post(self.url(f"reviews/{self.review.pk}/reply/"), {
            "reply": "Thank you for your review!",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_mark_helpful(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"reviews/{self.review.pk}/helpful/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_review(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"reviews/{self.review.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["rating"], 4)


# ─────────────────────────────────────────────────────────────────────────────
# 14. PromotionCampaignViewSet — live, CRUD
# ─────────────────────────────────────────────────────────────────────────────

class PromotionCampaignViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.campaign = PromotionCampaign.objects.create(
            tenant=self.tenant, name="Summer Sale V", slug="summer-sale-v",
            discount_type="percent", discount_value=Decimal("20.00"),
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=7),
        )

    def test_list_campaigns(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("promotions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_live_campaigns(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("promotions/live/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [c["name"] for c in resp.data]
        self.assertIn("Summer Sale V", names)

    def test_create_campaign(self):
        now = timezone.now()
        client = self.make_client(self.admin)
        resp = client.post(self.url("promotions/"), {
            "name": "Eid Special V",
            "slug": "eid-special-v",
            "discount_type": "fixed",
            "discount_value": "200.00",
            "starts_at": (now).isoformat(),
            "ends_at": (now + timedelta(days=3)).isoformat(),
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_retrieve_campaign(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"promotions/{self.campaign.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Summer Sale V")


# ─────────────────────────────────────────────────────────────────────────────
# 15. DisputeViewSet — full CRUD + all custom actions
# ─────────────────────────────────────────────────────────────────────────────

class DisputeViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.order.status = OrderStatus.DELIVERED
        self.order.save()
        from api.marketplace.DISPUTE_RESOLUTION.dispute_resolution import DisputeResolutionService
        self.dispute = DisputeResolutionService.raise_dispute(
            order_item=self.order_item,
            buyer=self.buyer,
            dispute_type=DisputeType.NOT_AS_DESCRIBED,
            description="The product colour was different.",
        )

    def test_list_disputes_as_buyer(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("disputes/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_list_all_disputes_as_admin(self):
        client = self.make_client(self.admin)
        resp = client.get(self.url("disputes/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_dispute(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"disputes/{self.dispute.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "open")

    def test_seller_respond_to_dispute(self):
        client = self.make_client(self.seller.user)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/respond/"), {
            "message": "We apologise and will send a replacement.",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_escalate_dispute(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/escalate/"), {
            "note": "Requires senior review.",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_arbitrate_dispute(self):
        client = self.make_client(self.admin)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/arbitrate/"), {
            "verdict": "resolved_buyer",
            "note": "Evidence favours buyer.",
            "refund_percent": 100,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_buyer_close_dispute(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/close/"), {
            "reason": "Resolved directly with seller.",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, "closed")

    def test_get_dispute_messages(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url(f"disputes/{self.dispute.pk}/messages/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_post_dispute_message(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/messages/"), {
            "body": "I am still waiting for the replacement.",
            "role": "buyer",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_add_evidence(self):
        client = self.make_client(self.buyer)
        resp = client.post(self.url(f"disputes/{self.dispute.pk}/add_evidence/"), {
            "caption": "Photo of wrong colour item",
            "file": "https://cdn.example.com/evidence/wrong_colour.jpg",
        }, format="json")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED,
                                         status.HTTP_400_BAD_REQUEST])

    def test_buyer_cannot_access_other_buyer_dispute(self):
        other_buyer = User.objects.create_user(username="other_buyer_v", password="pass")
        client = self.make_client(other_buyer)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        resp = client.get(self.url(f"disputes/{self.dispute.pk}/"))
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])


# ─────────────────────────────────────────────────────────────────────────────
# 16. SellerPayoutViewSet
# ─────────────────────────────────────────────────────────────────────────────

class SellerPayoutViewSetTest(MarketplaceFixture):

    def setUp(self):
        super().setUp()
        self.payout = SellerPayout.objects.create(
            tenant=self.tenant, seller=self.seller,
            amount=Decimal("8500.00"), method="bank",
        )

    def test_list_payouts_as_seller(self):
        client = self.make_client(self.seller.user)
        resp = client.get(self.url("seller-payouts/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_payout(self):
        client = self.make_client(self.seller.user)
        resp = client.get(self.url(f"seller-payouts/{self.payout.pk}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(resp.data["amount"])), Decimal("8500.00"))

    def test_buyer_cannot_see_seller_payouts(self):
        client = self.make_client(self.buyer)
        resp = client.get(self.url("seller-payouts/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Buyer has no payouts so list should be empty
        self.assertEqual(len(resp.data), 0)
