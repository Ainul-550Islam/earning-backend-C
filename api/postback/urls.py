"""urls.py – URL routing for the postback module."""
from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .viewsets import (
    DuplicateLeadCheckViewSet,
    NetworkPostbackConfigViewSet,
    PostbackLogViewSet,
    PostbackInsightViewSet,
    PostbackTemplateViewSet,
    PostbackIPWhitelistViewSet,
    PostbackRateLimitViewSet,
)
from .views import PostbackDashboardView, PostbackRetryView
from .webhooks import PostbackWebhookView

app_name = "postback"

router = DefaultRouter()
router.register(r"networks", NetworkPostbackConfigViewSet, basename="network")
router.register(r"logs", PostbackLogViewSet, basename="log")
router.register(r"duplicates", DuplicateLeadCheckViewSet, basename="duplicate")

# ── New Model Endpoints ───────────────────────────────────────────────────────
router.register(r"insights", PostbackInsightViewSet, basename="insight")
router.register(r"templates", PostbackTemplateViewSet, basename="template")
router.register(r"ip-whitelists", PostbackIPWhitelistViewSet, basename="ip-whitelist")
router.register(r"rate-limits", PostbackRateLimitViewSet, basename="rate-limit")

urlpatterns = [
    # ── Router ────────────────────────────────────────────────────────────────
    path("", include(router.urls)),

    # ── Webhook Ingestion (public – security handled inside the view) ─────────
    path("receive/<str:network_key>/", PostbackWebhookView.as_view(), name="webhook"),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("admin/dashboard/", PostbackDashboardView.as_view(), name="dashboard"),
    path("admin/logs/<uuid:pk>/retry/", PostbackRetryView.as_view(), name="retry-log"),
]

# ── URL Summary ───────────────────────────────────────────────────────────────
# GET/POST  /api/postback/receive/{network_key}/          → webhook ingestion
#
# GET       /api/postback/networks/                       → list networks
# POST      /api/postback/networks/                       → create network
# GET       /api/postback/networks/{id}/                  → network detail
# PUT/PATCH /api/postback/networks/{id}/                  → update network
# DELETE    /api/postback/networks/{id}/                  → delete network
# POST      /api/postback/networks/{id}/activate/         → activate
# POST      /api/postback/networks/{id}/deactivate/       → deactivate
# GET/POST  /api/postback/networks/{id}/validators/       → list/create validators
# GET       /api/postback/networks/{id}/stats/            → per-network stats
#
# GET       /api/postback/logs/                           → list logs (filterable)
# GET       /api/postback/logs/{id}/                      → log detail (with raw_payload)
# POST      /api/postback/logs/{id}/retry/                → re-queue failed log
# GET       /api/postback/logs/{id}/s2s-logs/             → outbound S2S attempts for this log
# POST      /api/postback/logs/{id}/reverse/              → create reversal record
#
# GET       /api/postback/duplicates/                     → dedup table
# DELETE    /api/postback/duplicates/{id}/                → clear a dedup entry
#
# ── New Model Endpoints ───────────────────────────────────────────────────────
# GET       /api/postback/insights/                      → list analytics insights
# GET       /api/postback/insights/{id}/                 → insight detail with rates
# POST      /api/postback/insights/{id}/detect-anomalies/ → run anomaly detection
# POST      /api/postback/insights/{id}/recalculate/       → force recalculation
#
# GET       /api/postback/templates/                      → list postback templates
# POST      /api/postback/templates/                      → create template
# GET       /api/postback/templates/{id}/                 → template detail
# PUT/PATCH /api/postback/templates/{id}/                 → update template
# DELETE    /api/postback/templates/{id}/                 → delete template
# POST      /api/postback/templates/{id}/render/          → render template with context
# POST      /api/postback/templates/{id}/clone/           → clone template
# GET       /api/postback/templates/{id}/verify-integrity/ → verify integrity hash
#
# GET       /api/postback/ip-whitelists/                  → list IP whitelist rules
# POST      /api/postback/ip-whitelists/                  → create IP whitelist
# GET       /api/postback/ip-whitelists/{id}/             → whitelist detail
# PUT/PATCH /api/postback/ip-whitelists/{id}/             → update whitelist
# DELETE    /api/postback/ip-whitelists/{id}/             → delete whitelist
# POST      /api/postback/ip-whitelists/{id}/test-ip/      → test IP against rule
# POST      /api/postback/ip-whitelists/{id}/verify-integrity/ → verify integrity hash
#
# GET       /api/postback/rate-limits/                    → list rate limit configs
# POST      /api/postback/rate-limits/                    → create rate limit
# GET       /api/postback/rate-limits/{id}/               → rate limit detail
# PUT/PATCH /api/postback/rate-limits/{id}/               → update rate limit
# DELETE    /api/postback/rate-limits/{id}/               → delete rate limit
# POST      /api/postback/rate-limits/{id}/reset-window/  → reset counting window
# POST      /api/postback/rate-limits/{id}/unblock/        → manually unblock
# POST      /api/postback/rate-limits/{id}/verify-integrity/ → verify integrity hash
#
# GET       /api/postback/admin/dashboard/                → 24h stats summary
# POST      /api/postback/admin/logs/{id}/retry/          → admin retry
from .viewsets_new import (
    OfferCategoryViewSet, OfferViewSet, OfferClickViewSet, UserOfferCompletionViewSet,
    PaymentMethodViewSet, WithdrawalRequestViewSet,
    ReferralProgramViewSet, UserReferralViewSet,
    UserTierViewSet, UserTierMembershipViewSet,
    DailyBonusViewSet, LeaderboardViewSet,
    GeoTargetingRuleViewSet, SurveyRouterViewSet, OfferwallSDKConfigViewSet,
)
from .views_new import (
    PostbackURLBuilderView, OfferwallEmbedView,
    DailyBonusScheduleView, SurveyRouterRedirectView,
)

router.register(r'offer-categories', OfferCategoryViewSet, basename='offer-category')
router.register(r'offers', OfferViewSet, basename='offer')
router.register(r'offer-clicks', OfferClickViewSet, basename='offer-click')
router.register(r'completions', UserOfferCompletionViewSet, basename='completion')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'withdrawals', WithdrawalRequestViewSet, basename='withdrawal')
router.register(r'referral-programs', ReferralProgramViewSet, basename='referral-program')
router.register(r'referrals', UserReferralViewSet, basename='referral')
router.register(r'tiers', UserTierViewSet, basename='tier')
router.register(r'tier-membership', UserTierMembershipViewSet, basename='tier-membership')
router.register(r'daily-bonus', DailyBonusViewSet, basename='daily-bonus')
router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')
router.register(r'geo-rules', GeoTargetingRuleViewSet, basename='geo-rule')
router.register(r'survey-routers', SurveyRouterViewSet, basename='survey-router')
router.register(r'sdk-configs', OfferwallSDKConfigViewSet, basename='sdk-config')

# ── Round-2 routes ────────────────────────────────────────────────────────────
from .viewsets_new import (
    SiteConfigViewSet, CurrencyRateViewSet,
    ManualPointAdjustmentViewSet, FCMDeviceViewSet, OfferImpressionViewSet,
)
router.register(r"site-config", SiteConfigViewSet, basename="site-config")
router.register(r"currency-rates", CurrencyRateViewSet, basename="currency-rate")
router.register(r"manual-adjustments", ManualPointAdjustmentViewSet, basename="manual-adjustment")
router.register(r"fcm-devices", FCMDeviceViewSet, basename="fcm-device")
router.register(r"offer-impressions", OfferImpressionViewSet, basename="offer-impression")

# ── B2B routes ────────────────────────────────────────────────────────────────
from .b2b_viewsets import (
    OrganizationAccountViewSet, B2BAPIKeyViewSet, OrganizationRoleViewSet,
    OrganizationMemberViewSet, RevenueShareRuleViewSet, AdvertiserBudgetCapViewSet,
    B2BContractViewSet, B2BInvoiceViewSet, OutboundWebhookSubViewSet,
    WhiteLabelConfigViewSet, ImpersonationLogViewSet, PartnerCreditLedgerViewSet,
)
router.register(r"b2b/organizations",    OrganizationAccountViewSet,  basename="b2b-org")
router.register(r"b2b/api-keys",         B2BAPIKeyViewSet,             basename="b2b-apikey")
router.register(r"b2b/roles",            OrganizationRoleViewSet,      basename="b2b-role")
router.register(r"b2b/members",          OrganizationMemberViewSet,    basename="b2b-member")
router.register(r"b2b/rev-share-rules",  RevenueShareRuleViewSet,      basename="b2b-revshare")
router.register(r"b2b/budget-caps",      AdvertiserBudgetCapViewSet,   basename="b2b-budgetcap")
router.register(r"b2b/contracts",        B2BContractViewSet,           basename="b2b-contract")
router.register(r"b2b/invoices",         B2BInvoiceViewSet,            basename="b2b-invoice")
router.register(r"b2b/webhooks",         OutboundWebhookSubViewSet,    basename="b2b-webhook")
router.register(r"b2b/white-label",      WhiteLabelConfigViewSet,      basename="b2b-whitelabel")
router.register(r"b2b/impersonation",    ImpersonationLogViewSet,      basename="b2b-impersonation")
router.register(r"b2b/credit-ledger",    PartnerCreditLedgerViewSet,   basename="b2b-credit")
