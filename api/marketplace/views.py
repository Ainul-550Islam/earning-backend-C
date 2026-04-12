"""
marketplace/views.py — API ViewSets
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db import transaction
from django.utils import timezone
import logging

from .models import (
    Category, Product, ProductVariant, ProductInventory,
    SellerProfile, SellerVerification, SellerPayout, CommissionConfig,
    Cart, CartItem, Order, OrderItem, OrderTracking,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview, PromotionCampaign,
)
from .schemas import (
    CategorySerializer, CategoryTreeSerializer,
    ProductListSerializer, ProductDetailSerializer,
    ProductVariantSerializer, ProductInventorySerializer,
    SellerProfileSerializer, SellerVerificationSerializer,
    SellerPayoutSerializer, CommissionConfigSerializer,
    CartSerializer, CartItemSerializer,
    OrderListSerializer, OrderDetailSerializer, OrderTrackingSerializer,
    PaymentTransactionSerializer, EscrowHoldingSerializer, RefundRequestSerializer,
    CouponSerializer, ProductReviewSerializer, PromotionCampaignSerializer,
)
from .services import (
    add_to_cart, remove_from_cart, apply_coupon_to_cart,
    create_order_from_cart, confirm_order, mark_order_shipped,
    mark_order_delivered, create_payment_transaction,
    process_payment_success, request_refund, approve_refund,
    release_escrow_and_credit,
)
from .enums import OrderStatus

logger = logging.getLogger(__name__)


class TenantFilterMixin:
    """Filters queryset by request.tenant for multi-tenant isolation."""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return qs.none()
        return qs.filter(tenant=tenant)


# ──────────────────────────────────────────────
# CATEGORY
# ──────────────────────────────────────────────
class CategoryViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by("sort_order")
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "slug"]

    def get_serializer_class(self):
        if self.action == "tree":
            return CategoryTreeSerializer
        return CategorySerializer

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Returns root categories with nested children."""
        roots = self.get_queryset().filter(parent__isnull=True)
        data = CategoryTreeSerializer(roots, many=True, context={"request": request}).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        category = self.get_object()
        qs = category.products.filter(status="active")
        serializer = ProductListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


# ──────────────────────────────────────────────
# PRODUCT
# ──────────────────────────────────────────────
class ProductViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related("seller", "category").all()
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "tags"]
    ordering_fields = ["base_price", "average_rating", "total_sales", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ("list",):
            return ProductListSerializer
        return ProductDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        seller = SellerProfile.objects.get(user=self.request.user, tenant=self.request.tenant)
        serializer.save(tenant=self.request.tenant, seller=seller)

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        product = self.get_object()
        reviews = product.reviews.filter(is_approved=True).order_by("-created_at")
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def featured(self, request):
        qs = self.get_queryset().filter(is_featured=True, status="active")
        serializer = ProductListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class ProductVariantViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = ProductVariant.objects.select_related("product", "inventory").all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]


class ProductInventoryViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = ProductInventory.objects.select_related("variant__product").all()
    serializer_class = ProductInventorySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def restock(self, request, pk=None):
        inventory = self.get_object()
        qty = int(request.data.get("quantity", 0))
        if qty <= 0:
            return Response({"error": "Quantity must be positive."}, status=400)
        inventory.quantity += qty
        inventory.last_restocked_at = timezone.now()
        inventory.save(update_fields=["quantity", "last_restocked_at"])
        return Response(ProductInventorySerializer(inventory).data)


# ──────────────────────────────────────────────
# SELLER
# ──────────────────────────────────────────────
class SellerProfileViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = SellerProfile.objects.all()
    serializer_class = SellerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            return qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, user=self.request.user)

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        seller = self.get_object()
        data = {
            "store_name": seller.store_name,
            "status": seller.status,
            "total_sales": seller.total_sales,
            "total_revenue": str(seller.total_revenue),
            "average_rating": str(seller.average_rating),
            "pending_orders": Order.objects.filter(
                items__seller=seller, status=OrderStatus.PENDING
            ).count(),
            "total_products": seller.products.count(),
        }
        return Response(data)


class SellerVerificationViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = SellerVerification.objects.all()
    serializer_class = SellerVerificationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        verification = self.get_object()
        verification.approve(reviewed_by=request.user)
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        reason = request.data.get("reason", "")
        verification = self.get_object()
        verification.reject(reviewed_by=request.user, reason=reason)
        return Response({"status": "rejected"})


class SellerPayoutViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = SellerPayout.objects.all()
    serializer_class = SellerPayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            return qs.filter(seller__user=self.request.user)
        return qs


class CommissionConfigViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = CommissionConfig.objects.filter(is_active=True)
    serializer_class = CommissionConfigSerializer
    permission_classes = [IsAdminUser]


# ──────────────────────────────────────────────
# CART
# ──────────────────────────────────────────────
class CartViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = Cart.objects.filter(is_active=True)
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        cart = self.get_object()
        variant_id = request.data.get("variant_id")
        qty = int(request.data.get("quantity", 1))
        try:
            variant = ProductVariant.objects.get(pk=variant_id, tenant=request.tenant)
            item = add_to_cart(cart, variant, qty)
            return Response(CartItemSerializer(item).data, status=201)
        except ProductVariant.DoesNotExist:
            return Response({"error": "Variant not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=True, methods=["delete"])
    def remove_item(self, request, pk=None):
        cart = self.get_object()
        variant_id = request.data.get("variant_id")
        remove_from_cart(cart, variant_id)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def apply_coupon(self, request, pk=None):
        cart = self.get_object()
        code = request.data.get("code", "")
        try:
            coupon = apply_coupon_to_cart(cart, code)
            return Response({"discount": coupon.calculate_discount(cart.total)})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        cart = self.get_object()
        shipping_data = {
            "shipping_name": request.data.get("name", ""),
            "shipping_phone": request.data.get("phone", ""),
            "shipping_address": request.data.get("address", ""),
            "shipping_city": request.data.get("city", ""),
        }
        try:
            order = create_order_from_cart(cart, request.data.get("payment_method", "cod"), shipping_data)
            return Response(OrderDetailSerializer(order).data, status=201)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# ORDER
# ──────────────────────────────────────────────
class OrderViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related("items", "tracking_events").all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            return qs.filter(user=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        order = confirm_order(order, confirmed_by=request.user)
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        order = self.get_object()
        order = mark_order_shipped(
            order,
            courier=request.data.get("courier", ""),
            tracking_number=request.data.get("tracking_number", ""),
            created_by=request.user,
        )
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        order = self.get_object()
        order = mark_order_delivered(order, created_by=request.user)
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        reason = request.data.get("reason", "")
        order.cancel(reason)
        return Response({"status": "cancelled"})

    @action(detail=True, methods=["get"])
    def tracking(self, request, pk=None):
        order = self.get_object()
        events = order.tracking_events.all()
        return Response(OrderTrackingSerializer(events, many=True).data)


# ──────────────────────────────────────────────
# PAYMENT
# ──────────────────────────────────────────────
class PaymentTransactionViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            return qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=["post"])
    def initiate(self, request):
        order_id = request.data.get("order_id")
        method = request.data.get("method", "cod")
        try:
            order = Order.objects.get(pk=order_id, tenant=request.tenant)
            tx = create_payment_transaction(order, method, ip=request.META.get("REMOTE_ADDR"))
            return Response(PaymentTransactionSerializer(tx).data, status=201)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def mark_success(self, request, pk=None):
        tx = self.get_object()
        gateway_id = request.data.get("gateway_id", "")
        order = process_payment_success(tx, gateway_id, request.data)
        return Response({"order_status": order.status})


class EscrowHoldingViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = EscrowHolding.objects.all()
    serializer_class = EscrowHoldingSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def release(self, request, pk=None):
        escrow = self.get_object()
        payout = release_escrow_and_credit(escrow)
        return Response(SellerPayoutSerializer(payout).data)


class RefundRequestViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = RefundRequest.objects.all()
    serializer_class = RefundRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            return qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, user=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        refund = self.get_object()
        from decimal import Decimal
        amount = Decimal(str(request.data.get("amount", refund.amount_requested)))
        refund = approve_refund(refund, amount, reviewed_by=request.user)
        return Response(RefundRequestSerializer(refund).data)


# ──────────────────────────────────────────────
# MARKETING
# ──────────────────────────────────────────────
class CouponViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminUser()]
        return [AllowAny()]

    @action(detail=False, methods=["post"])
    def validate(self, request):
        code = request.data.get("code", "")
        amount = request.data.get("amount", 0)
        try:
            coupon = Coupon.objects.get(code=code, tenant=request.tenant)
            if not coupon.is_valid:
                return Response({"valid": False, "reason": "Coupon expired or limit reached."})
            from decimal import Decimal
            discount = coupon.calculate_discount(Decimal(str(amount)))
            return Response({"valid": True, "discount": str(discount), "coupon": CouponSerializer(coupon).data})
        except Coupon.DoesNotExist:
            return Response({"valid": False, "reason": "Invalid coupon code."})


class ProductReviewViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = ProductReview.objects.filter(is_approved=True)
    serializer_class = ProductReviewSerializer

    def get_permissions(self):
        if self.action in ("create",):
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, user=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reply(self, request, pk=None):
        review = self.get_object()
        reply_text = request.data.get("reply", "")
        review.seller_reply = reply_text
        review.seller_replied_at = timezone.now()
        review.save(update_fields=["seller_reply", "seller_replied_at"])
        return Response(ProductReviewSerializer(review).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def helpful(self, request, pk=None):
        review = self.get_object()
        helpful = request.data.get("helpful", True)
        if helpful:
            review.helpful_count += 1
        else:
            review.not_helpful_count += 1
        review.save(update_fields=["helpful_count", "not_helpful_count"])
        return Response({"helpful": review.helpful_count, "not_helpful": review.not_helpful_count})


class PromotionCampaignViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = PromotionCampaign.objects.filter(is_active=True)
    serializer_class = PromotionCampaignSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminUser()]
        return [AllowAny()]

    @action(detail=False, methods=["get"])
    def live(self, request):
        now = timezone.now()
        qs = self.get_queryset().filter(starts_at__lte=now, ends_at__gte=now)
        return Response(PromotionCampaignSerializer(qs, many=True).data)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)
