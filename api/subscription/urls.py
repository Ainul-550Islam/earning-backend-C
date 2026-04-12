"""urls.py – URL routing for the subscription module (v2 with all features)."""
from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter
from rest_framework_nested import routers as nested_routers

from .viewsets import (
    SafeSubscriptionPlanViewSet,   # replaces SubscriptionPlanViewSet
    SubscriptionPaymentViewSet,
    UserSubscriptionViewSet,
    MembershipBenefitViewSet,
    CouponViewSet,
    AdminSubscriptionViewSet,
)
from .views import (
    AdminDashboardSummaryView,
    MySubscriptionView,
    PaymentWebhookView,
    PricingPageView,
)

app_name = "subscription"

# ── Main Router ───────────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r"plans",         SafeSubscriptionPlanViewSet, basename="plan")
router.register(r"subscriptions", UserSubscriptionViewSet,     basename="subscription")
router.register(r"payments",      SubscriptionPaymentViewSet,  basename="payment")
router.register(r"coupons",       CouponViewSet,               basename="coupon")
router.register(r"admin/subscriptions", AdminSubscriptionViewSet, basename="admin-subscription")

# ── Nested Router: /plans/{plan_slug}/benefits/ ───────────────────────────────
plans_router = nested_routers.NestedDefaultRouter(router, r"plans", lookup="plan")
plans_router.register(r"benefits", MembershipBenefitViewSet, basename="plan-benefit")

urlpatterns = [
    # ── Router URLs ────────────────────────────────────────────────────────────
    path("", include(router.urls)),
    path("plans/<slug:plan_slug>/benefits/", include(plans_router.urls)),

    # ── Convenience / Public ──────────────────────────────────────────────────
    path("pricing/",         PricingPageView.as_view(),         name="pricing"),
    path("my-subscription/", MySubscriptionView.as_view(),      name="my-subscription"),

    # ── Webhooks ──────────────────────────────────────────────────────────────
    path("webhooks/payment/", PaymentWebhookView.as_view(), name="webhook-payment"),

    # ── Admin (legacy summary view kept for backward compat) ──────────────────
    path("admin/summary/", AdminDashboardSummaryView.as_view(), name="admin-summary"),
]

# ── Full URL Reference ────────────────────────────────────────────────────────
#
# PLANS ───────────────────────────────────────────────────────────────────────
# GET    /api/subscriptions/plans/                          → plan list (public)
# POST   /api/subscriptions/plans/                          → create plan (admin)
# GET    /api/subscriptions/plans/{slug}/                   → plan detail
# PUT    /api/subscriptions/plans/{slug}/                   → update (admin)
# DELETE /api/subscriptions/plans/{slug}/                   → protected delete (admin)
# POST   /api/subscriptions/plans/{slug}/archive/           → soft-delete (admin)
# GET    /api/subscriptions/plans/{slug}/subscriber-count/  → count (admin)
#
# BENEFITS ────────────────────────────────────────────────────────────────────
# GET    /api/subscriptions/plans/{slug}/benefits/          → list benefits
# POST   /api/subscriptions/plans/{slug}/benefits/          → add benefit (admin)
# GET    /api/subscriptions/plans/{slug}/benefits/{id}/     → detail
# PUT    /api/subscriptions/plans/{slug}/benefits/{id}/     → update (admin)
# DELETE /api/subscriptions/plans/{slug}/benefits/{id}/     → delete (admin)
#
# SUBSCRIPTIONS ───────────────────────────────────────────────────────────────
# GET    /api/subscriptions/subscriptions/                  → user's subs
# GET    /api/subscriptions/subscriptions/me/               → active sub
# POST   /api/subscriptions/subscriptions/subscribe/        → subscribe
# POST   /api/subscriptions/subscriptions/{id}/cancel/      → cancel
# POST   /api/subscriptions/subscriptions/{id}/change-plan/ → change plan
# POST   /api/subscriptions/subscriptions/{id}/pause/       → pause
# POST   /api/subscriptions/subscriptions/{id}/resume/      → resume
#
# PAYMENTS ────────────────────────────────────────────────────────────────────
# GET    /api/subscriptions/payments/                       → payment list
# GET    /api/subscriptions/payments/{id}/                  → detail
# POST   /api/subscriptions/payments/{id}/refund/           → refund (admin)
#
# COUPONS ─────────────────────────────────────────────────────────────────────
# GET    /api/subscriptions/coupons/                        → admin list
# POST   /api/subscriptions/coupons/                        → create (admin)
# GET    /api/subscriptions/coupons/{id}/                   → detail (admin)
# PUT    /api/subscriptions/coupons/{id}/                   → update (admin)
# DELETE /api/subscriptions/coupons/{id}/                   → delete (admin)
# POST   /api/subscriptions/coupons/validate/               → validate code (auth user)
# GET    /api/subscriptions/coupons/{id}/usages/            → usage log (admin)
#
# ADMIN SUBSCRIPTION MANAGEMENT ───────────────────────────────────────────────
# GET    /api/subscriptions/admin/subscriptions/                  → all subs (admin)
# GET    /api/subscriptions/admin/subscriptions/{id}/             → any sub detail
# POST   /api/subscriptions/admin/subscriptions/grant/            → force-create
# POST   /api/subscriptions/admin/subscriptions/{id}/force-status/→ force status
# GET    /api/subscriptions/admin/subscriptions/summary/          → stats
