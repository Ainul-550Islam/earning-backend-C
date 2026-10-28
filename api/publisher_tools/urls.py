# publisher_tools/urls.py  — ABSOLUTE FINAL COMPLETE VERSION (+ analytics_warehouse)
# ===================================================================================
# Every ViewSet + APIView registered.
# Replace your existing urls.py with this file.
# After applying: delete routes.py (merged here).
#
# নতুন যোগ করা হয়েছে:
#   ✅ analytics_warehouse URLs  → /api/warehouse/ (project urls.py-তে include করো)
#   ✅ publisher-advanced এ নতুন endpoints (kyc-submit, store, business, etc.)
#   ✅ admin-scripts-এ নতুন backup/clean/sync/invoices endpoints
# ===================================================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# ── Core ViewSets (original views.py) ────────────────────────────────────────
from .views import (
    PublisherViewSet, SiteViewSet, AppViewSet,
    InventoryVerificationViewSet, AdUnitViewSet,
    AdPlacementViewSet, MediationGroupViewSet,
    WaterfallItemViewSet, HeaderBiddingConfigViewSet,
    PublisherEarningViewSet, PayoutThresholdViewSet,
    PublisherInvoiceViewSet, TrafficSafetyLogViewSet,
    SiteQualityMetricViewSet,
)

# ── Fix Package 1: Webhooks + A/B Testing + Analytics ────────────────────────
from .views_webhooks   import PublisherWebhookViewSet
from .views_abtest     import ABTestViewSet
from .views_analytics  import AnalyticsViewSet

# ── Fix Package 2: Optimization + Network + Integrations ─────────────────────
from .views_optimization   import OptimizationViewSet
from .views_network_config  import NetworkConfigViewSet
from .views_integrations    import IntegrationsViewSet

# ── Fix Package 3: Fraud + Payment + Site/Publisher/App mgmt ─────────────────
from .views_fraud               import FraudViewSet
from .views_payment             import PaymentViewSet
from .views_site_management     import SiteManagementViewSet
from .views_publisher_management import PublisherManagementViewSet
from .views_app_management      import AppManagementViewSet
from .views_mediation_full      import MediationToolsViewSet
from .views_scripts             import ScriptRunnerViewSet

# ── Extended mixin injection (ad unit, placement, mediation, publisher) ───────
from .views_extended_actions import (
    AdUnitExtendedMixin, AdPlacementExtendedMixin,
    MediationGroupExtendedMixin, PublisherExtendedMixin,
)
AdUnitViewSet.__bases__         = (AdUnitExtendedMixin,)         + AdUnitViewSet.__bases__
AdPlacementViewSet.__bases__    = (AdPlacementExtendedMixin,)    + AdPlacementViewSet.__bases__
MediationGroupViewSet.__bases__ = (MediationGroupExtendedMixin,) + MediationGroupViewSet.__bases__
PublisherViewSet.__bases__      = (PublisherExtendedMixin,)      + PublisherViewSet.__bases__

# ── Extra APIViews (merged from routes.py) ────────────────────────────────────
from .api_endpoints.publisher_api import PublisherDashboardView, PublisherStatsAPIView
from .api_endpoints.payment_api   import PaymentAPIView, PayoutRequestAPIView
from .api_endpoints.fraud_api     import FraudSummaryAPIView, IPBlockAPIView
from .api_endpoints.reporting_api import CustomReportAPIView, ScheduledReportAPIView
from .api_endpoints.settings_api  import PublisherSettingsAPIView
from .api_endpoints.site_api      import SiteBulkAPIView
from .api_endpoints.app_api       import AppBulkAPIView
from .api_endpoints.ad_unit_api   import AdUnitBulkAPIView
from .api_endpoints.placement_api import PlacementBulkAPIView

# ── Subfolder Extended ViewSets (Parts 1-10: floating logic → API) ────────────
from .views_abtest_extended        import ABTestExtendedViewSet
from .views_network_extended       import AdNetworkExtendedViewSet
from .views_integrations_extended  import IntegrationsExtendedViewSet
from .views_mediation_extended     import MediationExtendedViewSet
from .views_payment_extended       import PaymentExtendedViewSet
from .views_fraud_extended         import FraudExtendedViewSet
from .views_optimization_extended  import OptimizationExtendedViewSet
from .views_placements_extended    import PlacementExtendedViewSet
from .views_adunit_extended        import AdUnitExtendedViewSet
from .views_analytics_extended     import AnalyticsExtendedViewSet

from .views_ad_network_wired      import AdNetworkConfigViewSet
from .views_app_management_full   import AppManagementFullViewSet
from .views_scripts_remaining     import ScriptRunnerExtendedViewSet

# ── New viewsets — floating logic wired (DRY audit) ──────────────────────────
from .views_reporting             import ReportingViewSet
from .views_payout                import PayoutViewSet
from .views_fraud_report          import FraudReportViewSet
from .views_realtime              import RealtimeViewSet

router = DefaultRouter()

# ── Original 15 ViewSets ──────────────────────────────────────────────────────
router.register(r'publishers',        PublisherViewSet,             basename='publisher')
router.register(r'sites',             SiteViewSet,                  basename='site')
router.register(r'apps',              AppViewSet,                   basename='app')
router.register(r'verifications',     InventoryVerificationViewSet, basename='verification')
router.register(r'ad-units',          AdUnitViewSet,                basename='ad-unit')
router.register(r'placements',        AdPlacementViewSet,           basename='placement')
router.register(r'mediation-groups',  MediationGroupViewSet,        basename='mediation-group')
router.register(r'waterfall-items',   WaterfallItemViewSet,         basename='waterfall-item')
router.register(r'header-bidding',    HeaderBiddingConfigViewSet,   basename='header-bidding')
router.register(r'earnings',          PublisherEarningViewSet,      basename='earning')
router.register(r'payout-thresholds', PayoutThresholdViewSet,       basename='payout-threshold')
router.register(r'invoices',          PublisherInvoiceViewSet,      basename='invoice')
router.register(r'traffic-safety',    TrafficSafetyLogViewSet,      basename='traffic-safety')
router.register(r'quality-metrics',   SiteQualityMetricViewSet,     basename='quality-metric')

# ── New ViewSets (Fix Package 1) ──────────────────────────────────────────────
router.register(r'webhooks',          PublisherWebhookViewSet,      basename='webhook')
router.register(r'ab-tests',          ABTestViewSet,                basename='ab-test')
router.register(r'analytics',         AnalyticsViewSet,             basename='analytics')

# ── New ViewSets (Fix Package 2) ──────────────────────────────────────────────
router.register(r'optimizations',     OptimizationViewSet,          basename='optimization')
router.register(r'network-configs',   NetworkConfigViewSet,         basename='network-config')
router.register(r'integrations',      IntegrationsViewSet,          basename='integration')

# ── New ViewSets (Fix Package 3) ──────────────────────────────────────────────
router.register(r'fraud',             FraudViewSet,                 basename='fraud')
router.register(r'payments',          PaymentViewSet,               basename='payment')
router.register(r'site-tools',        SiteManagementViewSet,        basename='site-tool')
router.register(r'publisher-tools',   PublisherManagementViewSet,   basename='publisher-tool')
router.register(r'app-tools',         AppManagementViewSet,         basename='app-tool')
router.register(r'mediation-tools',   MediationToolsViewSet,        basename='mediation-tool')
router.register(r'admin-scripts',     ScriptRunnerViewSet,          basename='admin-script')

# ── Subfolder Extended ViewSets (130 floating functions → API) ────────────────
router.register(r'ab-tests-extended',    ABTestExtendedViewSet,        basename='abtest-extended')
router.register(r'ad-networks',          AdNetworkExtendedViewSet,     basename='ad-network')
router.register(r'integrations-ext',     IntegrationsExtendedViewSet,  basename='integrations-ext')
router.register(r'mediation-extended',   MediationExtendedViewSet,     basename='mediation-ext')
router.register(r'payments-extended',    PaymentExtendedViewSet,       basename='payment-ext')
router.register(r'fraud-tools',          FraudExtendedViewSet,         basename='fraud-ext')
router.register(r'optimizations-ext',    OptimizationExtendedViewSet,  basename='opt-ext')
router.register(r'placement-tools',      PlacementExtendedViewSet,     basename='placement-tools')
router.register(r'ad-unit-tools',        AdUnitExtendedViewSet,        basename='adunit-tools')
router.register(r'analytics-ext',        AnalyticsExtendedViewSet,     basename='analytics-ext')

# ── Round 2: Remaining floating → API (165 functions) ────────────────────────
from .views_webhooks_extended      import WebhookExtendedViewSet
from .views_publisher_advanced     import PublisherAdvancedViewSet
from .views_payment_advanced       import PaymentAdvancedViewSet
from .views_analytics_advanced     import AnalyticsAdvancedViewSet
from .views_fraud_advanced         import FraudAdvancedViewSet
from .views_integrations_embed     import IntegrationsEmbedViewSet
from .views_site_advanced          import SiteAdvancedViewSet
from .views_abtest_advanced        import ABTestAdvancedViewSet
from .views_adunit_advanced        import AdUnitAdvancedViewSet
from .views_mediation_advanced     import MediationAdvancedViewSet

router.register(r'webhooks-ext',       WebhookExtendedViewSet,       basename='webhook-ext')
router.register(r'publisher-advanced', PublisherAdvancedViewSet,     basename='publisher-adv')
router.register(r'payment-advanced',   PaymentAdvancedViewSet,       basename='payment-adv')
router.register(r'analytics-adv',      AnalyticsAdvancedViewSet,     basename='analytics-adv')
router.register(r'fraud-advanced',     FraudAdvancedViewSet,         basename='fraud-adv')
router.register(r'integrations-embed', IntegrationsEmbedViewSet,     basename='int-embed')
router.register(r'site-advanced',      SiteAdvancedViewSet,          basename='site-adv')
router.register(r'ab-tests-adv',       ABTestAdvancedViewSet,        basename='abtest-adv')
router.register(r'ad-unit-adv',        AdUnitAdvancedViewSet,        basename='adunit-adv')
router.register(r'mediation-adv',      MediationAdvancedViewSet,     basename='mediation-adv')

# ── Extra APIView patterns (merged from routes.py) ────────────────────────────
extra_patterns = [
    path('dashboard/',                      PublisherDashboardView.as_view(),  name='publisher-dashboard'),
    path('publishers/<str:pub_id>/stats/',  PublisherStatsAPIView.as_view(),   name='publisher-stats-detail'),
    path('old-payments/',                   PaymentAPIView.as_view(),           name='payment-legacy'),
    path('old-payments/payout-request/',    PayoutRequestAPIView.as_view(),     name='payout-request-legacy'),
    path('fraud/summary/',                  FraudSummaryAPIView.as_view(),      name='fraud-summary'),
    path('fraud/ip-block/',                 IPBlockAPIView.as_view(),           name='ip-block'),
    path('reports/custom/',                 CustomReportAPIView.as_view(),       name='custom-report'),
    path('reports/scheduled/',              ScheduledReportAPIView.as_view(),    name='scheduled-report'),
    path('settings/',                       PublisherSettingsAPIView.as_view(),  name='publisher-settings'),
    path('sites/bulk/',                     SiteBulkAPIView.as_view(),           name='site-bulk'),
    path('apps/bulk/',                      AppBulkAPIView.as_view(),            name='app-bulk'),
    path('ad-units/bulk/',                  AdUnitBulkAPIView.as_view(),         name='ad-unit-bulk'),
    path('placements/bulk/',                PlacementBulkAPIView.as_view(),      name='placement-bulk'),
]


# ── Fix: Remaining floating subfolders wired ──────────────────────────────────
router.register(r'ad-networks-config',  AdNetworkConfigViewSet,    basename='ad-network-config')
router.register(r'app-management',      AppManagementFullViewSet,   basename='app-mgmt-full')
router.register(r'admin-scripts-ext',   ScriptRunnerExtendedViewSet,basename='admin-script-ext')

# ── New viewsets — floating logic wired (DRY audit) ──────────────────────────
# Prefix: /api/publisher-tools/
router.register(r'reports',       ReportingViewSet,    basename='reports')
router.register(r'payout',        PayoutViewSet,       basename='payout')
router.register(r'fraud-reports', FraudReportViewSet,  basename='fraud-report')
router.register(r'realtime',      RealtimeViewSet,     basename='realtime')

urlpatterns = [path('', include(router.urls)), *extra_patterns]

# ════════════════════════════════════════════════════════════════════════════════
# ANALYTICS WAREHOUSE — আলাদা app, project urls.py-তে add করো:
#
#   # project/urls.py
#   from django.urls import path, include
#   urlpatterns += [
#       path('api/warehouse/', include('analytics_warehouse.urls')),
#   ]
#
# এতে নিচের endpoints পাওয়া যাবে:
#   GET  /api/warehouse/publisher-records/
#   GET  /api/warehouse/revenue-records/
#   GET  /api/warehouse/revenue-records/totals/
#   GET  /api/warehouse/fraud-log-records/unresolved/
#   GET  /api/warehouse/alert-records/active/
#   GET  /api/warehouse/api-key-log-records/top-endpoints/
#   GET  /api/warehouse/health/
#   GET  /api/warehouse/health/counts/
#   POST /api/warehouse/health/ingest/
#   POST /api/warehouse/health/mark-processed/
#   ... (মোট 21টি ViewSet, 50+ endpoints)
# ════════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════════
# COMPLETE ENDPOINT REFERENCE  (prefix: /api/publisher-tools/)
# ════════════════════════════════════════════════════════════════════════════════
#
# ORIGINAL 15 ViewSets + extended actions from views_extended_actions.py:
#   /publishers/          + overview/, top-content/, profile-completion/
#   /sites/               + verify/, approve/, reject/, refresh_ads_txt/, analytics/, quality_metrics/, ad_units/
#   /apps/                + approve/, reject/, ad_units/
#   /verifications/       + check/
#   /ad-units/            + pause/, activate/, tag_code/, performance/, targeting/, placements/, mediation/, trend/, compare/, recommendations/, format-score/
#   /placements/          + toggle/, suggest-floor/, optimize/, report/, position-alternatives/, analysis/
#   /mediation-groups/    + waterfall/, reorder/, optimize/, bid-analysis/, floor-recommendations/, network-comparison/
#   /waterfall-items/     + toggle_status/
#   /header-bidding/      CRUD
#   /earnings/            + summary/, by_country/, by_ad_unit/
#   /payout-thresholds/   + set_primary/, verify/
#   /invoices/            + generate/, issue/, mark_paid/, dispute/
#   /traffic-safety/      + take_action/, mark_false_positive/, summary/
#   /quality-metrics/     + alerts/, trend/
#
# NEW ViewSets (Fix Package 1):
#   /webhooks/            + test/, deliveries/, pause/, resume/
#   /ab-tests/            + start/, pause/, resume/, complete/, results/, declare-winner/
#   /analytics/           + dashboard/, realtime/, ecpm/, ctr/, rpm/, fill-rate/, revenue/, forecast/, report/*
#
# NEW ViewSets (Fix Package 2):
#   /optimizations/       + yield/, format/, geo/, device/, refresh/, viewability/, ...
#   /network-configs/     + networks/, config/, test-connection/, performance/
#   /integrations/        + available/, connected/, connect/, disconnect/, test/
#
# NEW ViewSets (Fix Package 3):
#   /fraud/               + my-summary/, ip-check/, alerts/, block-ip/, unblock-ip/
#   /payments/            + earnings/, invoice-preview/, tax-estimate/, payout-history/, ...
#   /site-tools/          + verify-ads-txt/, verify-meta-tag/, domain-check/, ...
#   /publisher-tools/     + overview/, revenue-breakdown/, forecast/, health-score/
#   /app-tools/           + performance/, by-format/, top-countries/
#   /mediation-tools/     + performance/, network-compare/, waterfall-report/, ...
#   /admin-scripts/       + run-fraud-detection/, health-check/, calculate-earnings/,
#                           backup-publisher-earnings/, backup-invoices/, export-publisher-data/,
#                           clean-webhook-logs/, clean-traffic-logs/, clean-fraud-alerts/,
#                           clean-performance-snapshots/, clean-verification-tokens/,
#                           clean-database-records/, run-full-clean/,
#                           sync-revenue-totals/, sync-status-consistency/,
#                           sync-payout-schedules/, run-full-sync/,
#                           generate-invoices/, generate-reports/,
#                           process-payments/, update-ad-units/
#
# publisher-advanced/ endpoints:
#   + subscription/, subscription-plans/, can-add-site/, subscription-history/
#   + kyc-status/, kyc-submit/, kyc-documents/, kyc-verify-token/
#   + bank-accounts/, bank-accounts/add/, bank-accounts/primary/,
#     bank-accounts/validate/, bank-accounts/remove/
#   + commissions/, commission-breakdown/, referral-commission/, referrals/
#   + comparison/, period-stats/, performance-goals/, achievement/
#   + rating/, brand/, next-payout/
#   + store/, store/contact/, business/
#   + verification-status/
#   + leaderboard/
#   + performance-targets/
#   + blacklist-status/
#
# TOTAL: 42 ViewSets, 400+ API endpoints
# ════════════════════════════════════════════════════════════════════════════════
