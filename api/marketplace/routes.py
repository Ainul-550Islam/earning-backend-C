"""
marketplace/routes.py — URL Routing (acts as urls.py)
=======================================================
Include in main urls.py:
    path("api/marketplace/", include("api.marketplace.routes")),
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    ProductViewSet,
    ProductVariantViewSet,
    ProductInventoryViewSet,
    SellerProfileViewSet,
    SellerVerificationViewSet,
    SellerPayoutViewSet,
    CommissionConfigViewSet,
    CartViewSet,
    OrderViewSet,
    PaymentTransactionViewSet,
    EscrowHoldingViewSet,
    RefundRequestViewSet,
    CouponViewSet,
    ProductReviewViewSet,
    PromotionCampaignViewSet,
)

router = DefaultRouter()

# 🛍️ Products
router.register(r"categories", CategoryViewSet, basename="marketplace-category")
router.register(r"products", ProductViewSet, basename="marketplace-product")
router.register(r"product-variants", ProductVariantViewSet, basename="marketplace-variant")
router.register(r"inventory", ProductInventoryViewSet, basename="marketplace-inventory")

# 👥 Sellers
router.register(r"sellers", SellerProfileViewSet, basename="marketplace-seller")
router.register(r"seller-verification", SellerVerificationViewSet, basename="marketplace-seller-verification")
router.register(r"seller-payouts", SellerPayoutViewSet, basename="marketplace-seller-payout")
router.register(r"commission-configs", CommissionConfigViewSet, basename="marketplace-commission")

# 🛒 Cart & Orders
router.register(r"cart", CartViewSet, basename="marketplace-cart")
router.register(r"orders", OrderViewSet, basename="marketplace-order")

# 💳 Payment
router.register(r"transactions", PaymentTransactionViewSet, basename="marketplace-transaction")
router.register(r"escrow", EscrowHoldingViewSet, basename="marketplace-escrow")
router.register(r"refunds", RefundRequestViewSet, basename="marketplace-refund")

# 🎁 Marketing
router.register(r"coupons", CouponViewSet, basename="marketplace-coupon")
router.register(r"reviews", ProductReviewViewSet, basename="marketplace-review")
router.register(r"promotions", PromotionCampaignViewSet, basename="marketplace-promotion")

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "marketplace"
