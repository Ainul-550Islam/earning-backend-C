"""
marketplace/schemas.py — DRF Serializers (Schemas)
"""

from rest_framework import serializers
from .models import (
    Category, Product, ProductVariant, ProductInventory, ProductAttribute,
    SellerProfile, SellerVerification, SellerPayout, CommissionConfig,
    Cart, CartItem, Order, OrderItem, OrderTracking,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview, PromotionCampaign,
)


# ──────────────────────────────────────────────
# Category
# ──────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    full_path = serializers.ReadOnlyField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "description", "image", "icon",
            "parent", "level", "is_active", "sort_order",
            "meta_title", "meta_description", "full_path", "children_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["level", "created_at", "updated_at"]

    def get_children_count(self, obj):
        return obj.children.filter(is_active=True).count()


class CategoryTreeSerializer(CategorySerializer):
    children = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ["children"]

    def get_children(self, obj):
        qs = obj.children.filter(is_active=True).order_by("sort_order")
        return CategoryTreeSerializer(qs, many=True, context=self.context).data


# ──────────────────────────────────────────────
# Product
# ──────────────────────────────────────────────
class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ["id", "name", "value", "unit", "sort_order"]


class ProductInventorySerializer(serializers.ModelSerializer):
    available_quantity = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()

    class Meta:
        model = ProductInventory
        fields = [
            "id", "quantity", "reserved_quantity", "available_quantity",
            "warehouse_location", "reorder_point", "is_low_stock",
            "is_out_of_stock", "allow_backorder", "last_restocked_at",
        ]


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    inventory = ProductInventorySerializer(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id", "sku", "name", "color", "size", "type", "material",
            "price_modifier", "sale_price", "effective_price",
            "weight_grams", "image", "is_active", "inventory",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    discount_percent = serializers.ReadOnlyField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    store_name = serializers.CharField(source="seller.store_name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "short_description",
            "base_price", "sale_price", "effective_price", "discount_percent",
            "status", "condition", "is_featured",
            "total_sales", "average_rating", "review_count",
            "category_name", "store_name", "created_at",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    effective_price = serializers.ReadOnlyField()
    discount_percent = serializers.ReadOnlyField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"


# ──────────────────────────────────────────────
# Seller
# ──────────────────────────────────────────────
class SellerProfileSerializer(serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField()
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = SellerProfile
        fields = "__all__"
        read_only_fields = [
            "total_sales", "total_revenue", "average_rating",
            "total_reviews", "response_rate", "created_at", "updated_at",
        ]


class SellerVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerVerification
        fields = "__all__"
        read_only_fields = ["reviewed_by", "reviewed_at", "created_at"]


class SellerPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerPayout
        fields = "__all__"
        read_only_fields = [
            "balance_before", "balance_after",
            "processed_at", "processed_by", "created_at",
        ]


class CommissionConfigSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = CommissionConfig
        fields = "__all__"


# ──────────────────────────────────────────────
# Cart
# ──────────────────────────────────────────────
class CartItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    product_name = serializers.CharField(source="variant.product.name", read_only=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True)
    available_quantity = serializers.IntegerField(
        source="variant.inventory.available_quantity", read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id", "variant", "product_name", "variant_name",
            "quantity", "unit_price", "subtotal", "available_quantity", "note",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ["id", "user", "session_key", "coupon", "is_active", "items", "total", "item_count"]
        read_only_fields = ["user"]


# ──────────────────────────────────────────────
# Order
# ──────────────────────────────────────────────
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id", "seller", "variant", "product_name", "variant_name",
            "sku", "product_image", "quantity", "unit_price",
            "discount", "subtotal", "commission_rate", "commission_amount",
            "seller_net", "item_status", "is_reviewed",
        ]
        read_only_fields = ["commission_rate", "commission_amount", "seller_net"]


class OrderTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTracking
        fields = [
            "id", "event", "description", "location",
            "courier_name", "tracking_number", "occurred_at",
        ]


class OrderListSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "status", "total_price",
            "payment_method", "is_paid", "item_count",
            "shipping_city", "created_at",
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    tracking_events = OrderTrackingSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"


# ──────────────────────────────────────────────
# Payment
# ──────────────────────────────────────────────
class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            "id", "transaction_id", "gateway_transaction_id", "order",
            "method", "amount", "currency", "status",
            "failure_reason", "initiated_at", "completed_at",
        ]
        read_only_fields = ["transaction_id", "initiated_at"]


class EscrowHoldingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscrowHolding
        fields = "__all__"
        read_only_fields = ["held_at", "released_at"]


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = "__all__"
        read_only_fields = [
            "status", "amount_approved", "reviewed_by",
            "reviewed_at", "processed_at", "transaction",
        ]


# ──────────────────────────────────────────────
# Marketing
# ──────────────────────────────────────────────
class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "name", "description", "coupon_type",
            "discount_value", "min_order_amount", "max_discount_amount",
            "valid_from", "valid_until", "usage_limit", "usage_per_user",
            "used_count", "is_active", "is_valid", "is_public",
            "applicable_to",
        ]
        read_only_fields = ["used_count"]


class ProductReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProductReview
        fields = [
            "id", "product", "rating", "title", "body", "images",
            "is_verified_purchase", "is_approved", "helpful_count",
            "seller_reply", "seller_replied_at", "username", "created_at",
        ]
        read_only_fields = [
            "is_verified_purchase", "is_approved", "helpful_count",
            "seller_reply", "seller_replied_at",
        ]


class PromotionCampaignSerializer(serializers.ModelSerializer):
    is_live = serializers.ReadOnlyField()

    class Meta:
        model = PromotionCampaign
        fields = [
            "id", "name", "slug", "promotion_type", "description",
            "banner_image", "discount_value", "discount_type",
            "starts_at", "ends_at", "is_active", "is_live",
            "max_items", "created_at",
        ]
