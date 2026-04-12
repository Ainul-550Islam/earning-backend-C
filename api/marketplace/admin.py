"""
marketplace/admin.py — Django Admin registrations
"""
from django.contrib import admin
from .models import (
    Category, Product, ProductVariant, ProductInventory, ProductAttribute,
    SellerProfile, SellerVerification, SellerPayout, CommissionConfig,
    Cart, CartItem, Order, OrderItem, OrderTracking,
    PaymentTransaction, EscrowHolding, RefundRequest,
    Coupon, ProductReview, PromotionCampaign,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "level", "is_active", "sort_order"]
    list_filter = ["is_active", "level"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["name", "sku", "color", "size", "price_modifier", "is_active"]


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    fields = ["name", "value", "unit", "sort_order"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "seller", "category", "base_price", "sale_price", "status", "is_featured", "total_sales"]
    list_filter = ["status", "condition", "is_featured", "category"]
    search_fields = ["name", "slug", "seller__store_name"]
    inlines = [ProductVariantInline, ProductAttributeInline]
    readonly_fields = ["total_sales", "average_rating", "review_count", "created_at", "updated_at"]


@admin.register(ProductInventory)
class ProductInventoryAdmin(admin.ModelAdmin):
    list_display = ["variant", "quantity", "reserved_quantity", "available_quantity", "is_low_stock"]
    list_filter = ["track_quantity", "allow_backorder"]
    search_fields = ["variant__product__name", "variant__sku", "warehouse_location"]


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ["store_name", "user", "status", "total_sales", "total_revenue", "average_rating", "created_at"]
    list_filter = ["status", "business_type", "is_featured"]
    search_fields = ["store_name", "store_slug", "user__username", "phone"]
    readonly_fields = ["total_sales", "total_revenue", "average_rating", "created_at", "updated_at"]


@admin.register(SellerVerification)
class SellerVerificationAdmin(admin.ModelAdmin):
    list_display = ["seller", "status", "reviewed_by", "reviewed_at"]
    list_filter = ["status"]
    search_fields = ["seller__store_name", "nid_number"]

    actions = ["approve_verifications", "reject_verifications"]

    def approve_verifications(self, request, queryset):
        for v in queryset:
            v.approve(reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} seller(s) approved.")
    approve_verifications.short_description = "✅ Approve selected sellers"

    def reject_verifications(self, request, queryset):
        for v in queryset:
            v.reject(reviewed_by=request.user, reason="Rejected via bulk action")
        self.message_user(request, f"{queryset.count()} seller(s) rejected.")
    reject_verifications.short_description = "❌ Reject selected sellers"


@admin.register(SellerPayout)
class SellerPayoutAdmin(admin.ModelAdmin):
    list_display = ["seller", "amount", "method", "account_number", "status", "created_at"]
    list_filter = ["status", "method"]
    search_fields = ["seller__store_name", "account_number", "reference_id"]
    readonly_fields = ["balance_before", "balance_after", "created_at"]


@admin.register(CommissionConfig)
class CommissionConfigAdmin(admin.ModelAdmin):
    list_display = ["category", "rate", "flat_fee", "is_active", "effective_from"]
    list_filter = ["is_active"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["commission_amount", "seller_net", "subtotal"]
    fields = ["variant", "product_name", "quantity", "unit_price", "discount",
              "subtotal", "commission_rate", "commission_amount", "seller_net", "item_status"]


class OrderTrackingInline(admin.TabularInline):
    model = OrderTracking
    extra = 1
    fields = ["event", "description", "location", "courier_name", "tracking_number", "occurred_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "user", "status", "total_price", "payment_method", "is_paid", "created_at"]
    list_filter = ["status", "payment_method", "is_paid"]
    search_fields = ["order_number", "user__username", "shipping_name", "shipping_phone"]
    readonly_fields = ["order_number", "created_at", "updated_at"]
    inlines = [OrderItemInline, OrderTrackingInline]


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["order", "method", "amount", "currency", "status", "gateway_transaction_id", "initiated_at"]
    list_filter = ["status", "method", "currency"]
    search_fields = ["order__order_number", "gateway_transaction_id", "transaction_id"]
    readonly_fields = ["transaction_id", "initiated_at", "completed_at"]


@admin.register(EscrowHolding)
class EscrowHoldingAdmin(admin.ModelAdmin):
    list_display = ["order_item", "seller", "gross_amount", "net_amount", "status", "release_after", "released_at"]
    list_filter = ["status"]
    search_fields = ["seller__store_name", "order_item__order__order_number"]
    readonly_fields = ["held_at", "released_at"]


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ["order_item", "user", "reason", "amount_requested", "amount_approved", "status", "created_at"]
    list_filter = ["status", "reason"]
    search_fields = ["order_item__order__order_number", "user__username"]
    readonly_fields = ["reviewed_by", "reviewed_at", "processed_at"]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "coupon_type", "discount_value", "valid_from", "valid_until", "used_count", "is_active"]
    list_filter = ["coupon_type", "is_active", "is_public"]
    search_fields = ["code", "name"]
    readonly_fields = ["used_count"]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "is_verified_purchase", "is_approved", "created_at"]
    list_filter = ["rating", "is_approved", "is_verified_purchase"]
    search_fields = ["product__name", "user__username", "title"]


@admin.register(PromotionCampaign)
class PromotionCampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "promotion_type", "discount_value", "starts_at", "ends_at", "is_active", "is_live"]
    list_filter = ["promotion_type", "is_active", "discount_type"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


def _force_register_marketplace():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (Category, CategoryAdmin),(Product, ProductAdmin),
            (ProductInventory, ProductInventoryAdmin),(SellerProfile, SellerProfileAdmin),
            (SellerVerification, SellerVerificationAdmin),(SellerPayout, SellerPayoutAdmin),
            (CommissionConfig, CommissionConfigAdmin),(Order, OrderAdmin),
            (PaymentTransaction, PaymentTransactionAdmin),(EscrowHolding, EscrowHoldingAdmin),
            (RefundRequest, RefundRequestAdmin),(Coupon, CouponAdmin),
            (ProductReview, ProductReviewAdmin),(PromotionCampaign, PromotionCampaignAdmin),
        ]
        registered=0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered+=1
            except Exception as ex:
                print(f"[WARN] {model.__name__}: {ex}")
        print(f"[OK] Marketplace registered {registered} models")
    except Exception as e:
        print(f"[WARN] Marketplace force-register: {e}")
