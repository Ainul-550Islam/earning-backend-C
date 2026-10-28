"""
api/offerwall/urls.py — Complete URL configuration

All logic is now exposed:
  Core ViewSets     → router (offers, conversions, categories, providers, clicks, walls, locks)
  Webhooks          → /webhooks/  (Tapjoy, AdGem, OfferToro, bulk, chargeback)
  Publisher SDK     → /publisher/ (embed-token, sdk-config, stats, keys)
  Exports           → /exports/   (csv, xlsx, json)
  Surveys           → /surveys/   (list, providers, config, webhooks per provider)
  Admin Utilities   → /admin/     (analytics, fraud, reward calc, factory, adapters, b2b quota)
  B2B SaaS          → /b2b/       (plans, register, dashboard, invoices, onboarding, admin)
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter

app_name = "offerwall"

# ── Core ViewSets ─────────────────────────────────────────────
from .views import (
    OfferViewSet,
    PublicOfferListView,
    OfferConversionViewSet,
    OfferCategoryViewSet,
    OfferProviderViewSet,
    OfferClickViewSet,
    OfferWallViewSet,
)

# ── Webhooks ──────────────────────────────────────────────────
from .webhooks.TapjoyWebhook  import TapjoyWebhookView
from .webhooks.AdGemWebhook   import AdGemWebhookView
from .webhooks.OfferwallWebhook import OfferwallWebhookView
from .chargeback import (ChargebackWebhookView, TapjoyChargebackView, AdGateChargebackView, PersonaChargebackView)
from .bulk_conversion import BulkConversionWebhookView
# FIX: AdGate and Persona webhooks were missing — conversions were silently lost
from .webhooks.AdGateWebhook   import AdGateWebhookView
from .webhooks.PersonaWebhook  import PersonaWebhookView

# Phase 2 — new network webhooks
from .webhooks.MonlixWebhook   import MonlixWebhookView
from .webhooks.OGAdsWebhook    import OGAdsWebhookView
from .webhooks.FyberWebhook    import FyberWebhookView
from .webhooks.LiftoffWebhook  import LiftoffWebhookView
from .webhooks.AppLiftWebhook  import AppLiftWebhookView

# ── Publisher SDK ─────────────────────────────────────────────
from .publisher import (
    EmbedTokenView,
    SDKConfigView,
    PublisherStatsView,
    PublisherAPIKeyViewSet,
)

# ── Exports ───────────────────────────────────────────────────
from .exports import EarningsExportView, AdminEarningsExportView

# ── Content Lock ──────────────────────────────────────────────
from .content_lock import ContentLockViewSet

# ── Survey Views (newly exposed) ──────────────────────────────
from .survey_views import (
    SurveyListView,
    SurveyProviderListView,
    SurveySDKConfigView,
    CPXResearchWebhookView,
    BitLabsWebhookView,
    PollfishWebhookView,
    SurveyAnalyticsView,
)

# ── Admin API Views (newly exposed) ───────────────────────────
from .admin_api_views import (
    # Analytics
    OfferPerformanceView,
    ProviderPerformanceView,
    PerformanceReportView,
    UserOfferAnalyticsView,
    # Reward Calculator
    RewardPreviewView,
    AllBonusesPreviewView,
    # Fraud Detector
    FraudCheckView,
    UserBehaviorAnalysisView,
    IPReputationView,
    # OfferFactory
    ProviderValidateView,
    ProviderCapabilitiesView,
    SyncAllProvidersView,
    ProcessorRegistryView,
    # Adapter Health
    AdapterHealthView,
    AdapterResetView,
    # B2B Quota
    B2BQuotaStatusView,
    B2BUsageIncrementView,
)

# ═════════════════════════════════════════════════════════════
# Router registration
# ═════════════════════════════════════════════════════════════
router = SimpleRouter()
router.register(r"offers",      OfferViewSet,           basename="offer")
router.register(r"conversions", OfferConversionViewSet, basename="conversion")
router.register(r"categories",  OfferCategoryViewSet,   basename="category")
router.register(r"providers",   OfferProviderViewSet,   basename="provider")
router.register(r"clicks",      OfferClickViewSet,      basename="click")
router.register(r"walls",       OfferWallViewSet,       basename="wall")
router.register(r"locks",       ContentLockViewSet,     basename="content-lock")

# ═════════════════════════════════════════════════════════════
# Webhook sub-patterns
# ═════════════════════════════════════════════════════════════
webhook_patterns = [
    path("tapjoy/",               TapjoyWebhookView.as_view(),      name="tapjoy-webhook"),
    path("adgem/",                AdGemWebhookView.as_view(),       name="adgem-webhook"),
    path("offertoro/",            OfferwallWebhookView.as_view(),   name="offertoro-webhook"),
    path("bulk/",                 BulkConversionWebhookView.as_view(), name="bulk-conversion"),
    path("chargeback/",           ChargebackWebhookView.as_view(),  name="chargeback-webhook"),
    path("tapjoy/chargeback/",    TapjoyChargebackView.as_view(),   name="tapjoy-chargeback"),
    path("adgate/chargeback/",    AdGateChargebackView.as_view(),   name="adgate-chargeback"),
    path("persona/chargeback/",   PersonaChargebackView.as_view(),  name="persona-chargeback"),
    # Survey webhooks
    path("survey/cpx/",           CPXResearchWebhookView.as_view(), name="survey-cpx-webhook"),
    path("survey/bitlabs/",       BitLabsWebhookView.as_view(),     name="survey-bitlabs-webhook"),
    path("survey/pollfish/",      PollfishWebhookView.as_view(),    name="survey-pollfish-webhook"),
    # FIX: AdGate and Persona routes were missing
    path("adgate/",               AdGateWebhookView.as_view(),      name="adgate-webhook"),
    path("persona/",              PersonaWebhookView.as_view(),     name="persona-webhook"),

    # Phase 2 — new network webhooks
    path("monlix/",               MonlixWebhookView.as_view(),      name="monlix-webhook"),
    path("ogads/",                OGAdsWebhookView.as_view(),       name="ogads-webhook"),
    path("fyber/",                FyberWebhookView.as_view(),       name="fyber-webhook"),
    path("liftoff/",              LiftoffWebhookView.as_view(),     name="liftoff-webhook"),
    path("applift/",              AppLiftWebhookView.as_view(),     name="applift-webhook"),
]

# ═════════════════════════════════════════════════════════════
# Survey sub-patterns
# ═════════════════════════════════════════════════════════════
survey_patterns = [
    path("",            SurveyListView.as_view(),           name="survey-list"),
    path("providers/",  SurveyProviderListView.as_view(),   name="survey-providers"),
    path("config/",     SurveySDKConfigView.as_view(),      name="survey-sdk-config"),
    path("webhooks/cpx/",      CPXResearchWebhookView.as_view(), name="survey-cpx"),
    path("webhooks/bitlabs/",  BitLabsWebhookView.as_view(),     name="survey-bitlabs"),
    path("webhooks/pollfish/", PollfishWebhookView.as_view(),    name="survey-pollfish"),
]

# ═════════════════════════════════════════════════════════════
# Admin sub-patterns
# ═════════════════════════════════════════════════════════════
admin_patterns = [
    # ── Analytics ───────────────────────────────────────────
    path("analytics/offer/<uuid:offer_id>/",
         OfferPerformanceView.as_view(),      name="admin-offer-analytics"),
    path("analytics/provider/<uuid:provider_id>/",
         ProviderPerformanceView.as_view(),   name="admin-provider-analytics"),
    path("analytics/report/",
         PerformanceReportView.as_view(),     name="admin-perf-report"),
    path("analytics/user/<int:user_id>/",
         UserOfferAnalyticsView.as_view(),    name="admin-user-analytics"),

    # ── Reward Calculator ────────────────────────────────────
    path("rewards/bonuses/",
         AllBonusesPreviewView.as_view(),     name="admin-bonus-preview"),

    # ── Fraud Detector ───────────────────────────────────────
    path("fraud/check/",
         FraudCheckView.as_view(),            name="admin-fraud-check"),
    path("fraud/user/<int:user_id>/behavior/",
         UserBehaviorAnalysisView.as_view(),  name="admin-user-behavior"),
    path("fraud/ip/",
         IPReputationView.as_view(),          name="admin-ip-reputation"),

    # ── OfferFactory ─────────────────────────────────────────
    path("providers/<uuid:provider_id>/validate/",
         ProviderValidateView.as_view(),      name="admin-provider-validate"),
    path("providers/<uuid:provider_id>/capabilities/",
         ProviderCapabilitiesView.as_view(),  name="admin-provider-capabilities"),
    path("sync-all/",
         SyncAllProvidersView.as_view(),      name="admin-sync-all"),
    path("processors/",
         ProcessorRegistryView.as_view(),     name="admin-processors"),

    # ── Adapter Health ───────────────────────────────────────
    path("adapters/health/",
         AdapterHealthView.as_view(),         name="admin-adapter-health"),
    path("adapters/reset/<str:adapter_name>/",
         AdapterResetView.as_view(),          name="admin-adapter-reset"),

    # ── B2B Quota ────────────────────────────────────────────
    path("b2b/quota/<uuid:client_id>/",
         B2BQuotaStatusView.as_view(),        name="admin-b2b-quota"),
    path("b2b/quota/<uuid:client_id>/increment/",
         B2BUsageIncrementView.as_view(),     name="admin-b2b-quota-increment"),

    # ── Survey Analytics ─────────────────────────────────────
    path("surveys/analytics/",
         SurveyAnalyticsView.as_view(),       name="admin-survey-analytics"),
]

# ═════════════════════════════════════════════════════════════
# Main URL patterns
# ═════════════════════════════════════════════════════════════
urlpatterns = [
    # ── Public ──────────────────────────────────────────────
    path("public/",   PublicOfferListView.as_view(),  name="public-offers"),

    # ── Custom list-level Offer actions ─────────────────────
    # (must be before router to avoid /{pk}/ conflict)
    path("offers/stats/",       OfferViewSet.as_view({"get": "stats"}),       name="offer-stats"),
    path("offers/featured/",    OfferViewSet.as_view({"get": "featured"}),    name="offer-featured"),
    path("offers/trending/",    OfferViewSet.as_view({"get": "trending"}),    name="offer-trending"),
    path("offers/recommended/", OfferViewSet.as_view({"get": "recommended"}), name="offer-recommended"),

    # ── Custom detail-level Offer actions ───────────────────
    path("offers/<pk>/toggle_featured/",
         OfferViewSet.as_view({"post": "toggle_featured"}),     name="offer-toggle-featured"),
    path("offers/<pk>/toggle_trending/",
         OfferViewSet.as_view({"post": "toggle_trending"}),     name="offer-toggle-trending"),
    # FIX: toggle_recommended was added to views.py but never had a URL
    path("offers/<pk>/toggle_recommended/",
         OfferViewSet.as_view({"post": "toggle_recommended"}),  name="offer-toggle-recommended"),
    path("offers/<pk>/calculate_quality/",
         OfferViewSet.as_view({"post": "calculate_quality"}),   name="offer-quality"),
    path("offers/<pk>/click/",
         OfferViewSet.as_view({"post": "click"}),               name="offer-click"),
    # Reward preview — exposed via RewardCalculator.calculate_conversion_value()
    path("offers/<uuid:offer_id>/reward-preview/",
         RewardPreviewView.as_view(),                           name="offer-reward-preview"),

    # ── Conversion actions ───────────────────────────────────
    path("conversions/stats/",
         OfferConversionViewSet.as_view({"get": "stats"}),      name="conversion-stats"),
    path("conversions/bulk-approve/",
         OfferConversionViewSet.as_view({"post": "bulk_approve"}), name="conversion-bulk-approve"),
    path("conversions/bulk-reject/",
         OfferConversionViewSet.as_view({"post": "bulk_reject"}),  name="conversion-bulk-reject"),
    path("conversions/<pk>/approve/",
         OfferConversionViewSet.as_view({"post": "approve"}),   name="conversion-approve"),
    path("conversions/<pk>/reject/",
         OfferConversionViewSet.as_view({"post": "reject"}),    name="conversion-reject"),
    # FIX: chargeback and reverse were added to views.py but had no URLs
    path("conversions/<pk>/chargeback/",
         OfferConversionViewSet.as_view({"post": "chargeback"}), name="conversion-chargeback"),
    path("conversions/<pk>/reverse/",
         OfferConversionViewSet.as_view({"post": "reverse"}),    name="conversion-reverse"),

    # ── Click actions ────────────────────────────────────────
    path("clicks/stats/",
         OfferClickViewSet.as_view({"get": "stats"}),            name="click-stats"),

    # ── Wall actions ─────────────────────────────────────────
    path("walls/<pk>/offers/",
         OfferWallViewSet.as_view({"get": "get_offers"}),        name="wall-offers"),

    # ── Provider actions ─────────────────────────────────────
    # GAP 2 FIX: sync action existed in views but had no URL → 404
    path("providers/<pk>/sync/",
         OfferProviderViewSet.as_view({"post": "sync"}),         name="provider-sync"),

    # ── Content Lock ─────────────────────────────────────────
    path("locks/by_token/<str:token>/",
         ContentLockViewSet.as_view({"get": "by_token"}),        name="lock-by-token"),
    path("locks/<pk>/check/",
         ContentLockViewSet.as_view({"get": "check"}),           name="lock-check"),
    path("locks/<pk>/unlock/",
         ContentLockViewSet.as_view({"post": "unlock"}),         name="lock-unlock"),

    # ── Publisher / Embed SDK ────────────────────────────────
    path("publisher/embed-token/",  EmbedTokenView.as_view(),        name="publisher-embed-token"),
    path("publisher/sdk-config/",   SDKConfigView.as_view(),         name="publisher-sdk-config"),
    path("publisher/stats/",        PublisherStatsView.as_view(),    name="publisher-stats"),
    path("publisher/keys/",
         PublisherAPIKeyViewSet.as_view({"get": "list", "post": "create"}),
         name="publisher-keys"),
    path("publisher/keys/<pk>/",
         PublisherAPIKeyViewSet.as_view({"delete": "destroy"}),
         name="publisher-key-detail"),

    # ── Exports ──────────────────────────────────────────────
    path("exports/earnings/",        EarningsExportView.as_view(),      name="earnings-export"),
    path("exports/admin/earnings/",  AdminEarningsExportView.as_view(), name="admin-earnings-export"),

    # ── Surveys (newly exposed) ──────────────────────────────
    path("surveys/",     include((survey_patterns, "surveys"))),

    # ── Admin Utilities (newly exposed) ─────────────────────
    path("admin/",       include((admin_patterns, "admin"))),

    # ── B2B SaaS ─────────────────────────────────────────────
    path("b2b/",         include("api.offerwall.b2b.urls", namespace="b2b")),

    # ── Webhooks ─────────────────────────────────────────────
    path("webhooks/",    include((webhook_patterns, "webhooks"))),

    # ── Router (handles /{pk}/, @action decorators) ─────────
    path("",             include(router.urls)),
]
