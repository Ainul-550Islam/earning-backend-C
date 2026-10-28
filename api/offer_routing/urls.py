"""
URL Configuration — all ViewSets registered via DRF DefaultRouter.

ADDITIONS (audit 2026-06):
  Personalization algorithms now have direct API endpoints:
    /api/hybrid/           — hybrid CF+CB recommendations + algorithm comparison
    /api/cf/               — direct collaborative filtering recommendations
    /api/cb/               — direct content-based recommendations

  Targeting preview:
    /api/targeting-preview/  — evaluate ALL targeting rules for a user at once

  These were previously floating (code existed but no route pointed to them).

Complete endpoint map (83 API groups):
  Core          /api/routes/, /api/conditions/, /api/decisions/
  Public        /api/route/
  Admin         /api/admin/
  Targeting     /api/geo-rules/, /api/device-rules/, /api/segment-rules/,
                /api/time-rules/, /api/behavior-rules/, /api/targeting-preview/
  Scoring       /api/score-configs/, /api/scores/, /api/global-ranks/,
                /api/offer-history/
  Personalization /api/personalization-configs/, /api/preference-vectors/,
                  /api/contextual-signals/, /api/affinity-scores/,
                  /api/hybrid/, /api/cf/, /api/cb/
  Cap           /api/caps/, /api/user-caps/, /api/cap-overrides/
  Fallback      /api/fallbacks/, /api/offer-pools/, /api/empty-handlers/
  A/B Tests     /api/ab-tests/, /api/ab-assignments/, /api/ab-results/
  Analytics     /api/decision-logs/, /api/insights/, /api/performance/,
                /api/exposure-stats/, /api/reports/
  Monitoring    /api/monitoring/
  Config        /api/config/
  Utils         /api/validate/, /api/testing/, /api/helpers/
  Evaluator     /api/evaluate/
  Optimizer     /api/optimize/
  Integration   /api/integrations/handler|registry|auth|data|events|health|performance/
  Advanced      /api/geo-revenue/, /api/dynamic-pricing/, /api/ml/,
                /api/waterfall/, /api/postback/, /api/fraud/, /api/openai/,
                /api/plugins/, /api/configuration/, /api/cache/,
                /api/attachments/
  Tenant Admin  /api/tenant/settings|billing|invoices/
                /api/routing-templates/, /api/route-actions/,
                /api/security-events/
  Domain        /api/blacklist/, /api/blacklist-hits/,
                /api/fraud-signals/, /api/fraud-patterns/,
                /api/network-performance/, /api/offer-quality/,
                /api/user-journey/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    # ── Core ─────────────────────────────────────────────────────────────
    OfferRouteViewSet, RouteConditionViewSet,
    RoutingDecisionViewSet, PublicRoutingViewSet, AdminRoutingViewSet,

    # ── Targeting ─────────────────────────────────────────────────────────
    GeoRouteRuleViewSet, DeviceRouteRuleViewSet, UserSegmentRuleViewSet,
    TimeRouteRuleViewSet, BehaviorRouteRuleViewSet,
    TargetingPreviewViewSet,              # ← NEW

    # ── Scoring ───────────────────────────────────────────────────────────
    OfferScoreConfigViewSet, OfferScoreViewSet,
    GlobalOfferRankViewSet, UserOfferHistoryViewSet,

    # ── Personalization ───────────────────────────────────────────────────
    PersonalizationConfigViewSet, UserPreferenceVectorViewSet,
    ContextualSignalViewSet, OfferAffinityScoreViewSet,
    HybridRecommendationViewSet,          # ← NEW
    CollaborativeFilterViewSet,           # ← NEW
    ContentBasedViewSet,                  # ← NEW

    # ── Cap ───────────────────────────────────────────────────────────────
    OfferRoutingCapViewSet, UserOfferCapViewSet, CapOverrideViewSet,

    # ── Fallback ──────────────────────────────────────────────────────────
    FallbackRuleViewSet, DefaultOfferPoolViewSet, EmptyResultHandlerViewSet,

    # ── A/B Tests ─────────────────────────────────────────────────────────
    RoutingABTestViewSet, ABTestAssignmentViewSet, ABTestResultViewSet,

    # ── Analytics ─────────────────────────────────────────────────────────
    RoutingDecisionLogViewSet, RoutingInsightViewSet, RoutePerformanceStatViewSet,
    OfferExposureStatViewSet, ReportViewSet,

    # ── Monitoring / Config / Utils ───────────────────────────────────────
    MonitoringViewSet, RoutingConfigViewSet,
    ValidationViewSet, TestingViewSet, HelperViewSet,

    # ── Evaluator / Optimizer ─────────────────────────────────────────────
    RouteEvaluatorViewSet, RoutingOptimizerViewSet,

    # ── Integration System ────────────────────────────────────────────────
    IntegrationHandlerViewSet, IntegrationRegistryViewSet,
    AuthBridgeViewSet, DataBridgeViewSet, EventBusViewSet,
    IntegrationHealthViewSet, PerformanceMonitorViewSet,

    # ── Advanced Services ─────────────────────────────────────────────────
    GeoRevenueViewSet, DynamicPricingViewSet, MLIntegrationViewSet,
    WaterfallViewSet, PostbackViewSet, FraudDetectionViewSet,
    OpenAIViewSet, PluginViewSet, ConfigurationViewSet,
    CacheBackendViewSet, AttachmentViewSet,

    # ── Tenant Admin ──────────────────────────────────────────────────────
    TenantSettingsViewSet, TenantBillingViewSet, TenantInvoiceViewSet,
    RoutingTemplateViewSet, RouteActionViewSet, SecurityEventViewSet,

    # ── Domain Models ─────────────────────────────────────────────────────
    RoutingBlacklistViewSet, BlacklistHitViewSet,
    ClickFraudSignalViewSet, FraudPatternViewSet,
    NetworkPerformanceCacheViewSet, OfferQualityScoreViewSet,
    UserJourneyStepViewSet,
)

router = DefaultRouter()

# ── Core ──────────────────────────────────────────────────────────────────────
router.register(r'routes',     OfferRouteViewSet,      basename='route')
router.register(r'conditions', RouteConditionViewSet,  basename='condition')
router.register(r'decisions',  RoutingDecisionViewSet, basename='decision')

# ── Targeting ─────────────────────────────────────────────────────────────────
router.register(r'geo-rules',          GeoRouteRuleViewSet,       basename='geo-rule')
router.register(r'device-rules',       DeviceRouteRuleViewSet,    basename='device-rule')
router.register(r'segment-rules',      UserSegmentRuleViewSet,    basename='segment-rule')
router.register(r'time-rules',         TimeRouteRuleViewSet,      basename='time-rule')
router.register(r'behavior-rules',     BehaviorRouteRuleViewSet,  basename='behavior-rule')
router.register(r'targeting-preview',  TargetingPreviewViewSet,   basename='targeting-preview')   # ← NEW

# ── Scoring ───────────────────────────────────────────────────────────────────
router.register(r'score-configs',  OfferScoreConfigViewSet,  basename='score-config')
router.register(r'scores',         OfferScoreViewSet,        basename='score')
router.register(r'global-ranks',   GlobalOfferRankViewSet,   basename='global-rank')
router.register(r'offer-history',  UserOfferHistoryViewSet,  basename='offer-history')

# ── Personalization ───────────────────────────────────────────────────────────
router.register(r'personalization-configs', PersonalizationConfigViewSet, basename='personalization-config')
router.register(r'preference-vectors',      UserPreferenceVectorViewSet,  basename='preference-vector')
router.register(r'contextual-signals',      ContextualSignalViewSet,      basename='contextual-signal')
router.register(r'affinity-scores',         OfferAffinityScoreViewSet,    basename='affinity-score')
router.register(r'hybrid',  HybridRecommendationViewSet, basename='hybrid')   # ← NEW
router.register(r'cf',      CollaborativeFilterViewSet,  basename='cf')       # ← NEW
router.register(r'cb',      ContentBasedViewSet,         basename='cb')       # ← NEW

# ── Cap ───────────────────────────────────────────────────────────────────────
router.register(r'caps',          OfferRoutingCapViewSet, basename='cap')
router.register(r'user-caps',     UserOfferCapViewSet,    basename='user-cap')
router.register(r'cap-overrides', CapOverrideViewSet,     basename='cap-override')

# ── A/B Tests ─────────────────────────────────────────────────────────────────
router.register(r'ab-tests',       RoutingABTestViewSet,     basename='ab-test')
router.register(r'ab-assignments', ABTestAssignmentViewSet,  basename='ab-assignment')
router.register(r'ab-results',     ABTestResultViewSet,      basename='ab-result')

# ── Fallback ──────────────────────────────────────────────────────────────────
router.register(r'fallbacks',      FallbackRuleViewSet,        basename='fallback')
router.register(r'offer-pools',    DefaultOfferPoolViewSet,    basename='offer-pool')
router.register(r'empty-handlers', EmptyResultHandlerViewSet,  basename='empty-handler')

# ── Analytics ─────────────────────────────────────────────────────────────────
router.register(r'decision-logs',   RoutingDecisionLogViewSet,   basename='decision-log')
router.register(r'insights',        RoutingInsightViewSet,       basename='insight')
router.register(r'performance',     RoutePerformanceStatViewSet, basename='performance')
router.register(r'exposure-stats',  OfferExposureStatViewSet,    basename='exposure-stat')
router.register(r'reports',         ReportViewSet,               basename='report')

# ── Monitoring / Config / Utils ───────────────────────────────────────────────
router.register(r'monitoring',  MonitoringViewSet,   basename='monitoring')
router.register(r'config',      RoutingConfigViewSet, basename='config')
router.register(r'validate',    ValidationViewSet,   basename='validate')
router.register(r'testing',     TestingViewSet,      basename='testing')
router.register(r'helpers',     HelperViewSet,       basename='helper')

# ── Evaluator / Optimizer / Admin / Public ────────────────────────────────────
router.register(r'evaluate', RouteEvaluatorViewSet,   basename='evaluate')
router.register(r'optimize',  RoutingOptimizerViewSet, basename='optimize')
router.register(r'admin',     AdminRoutingViewSet,     basename='admin')
router.register(r'route',     PublicRoutingViewSet,    basename='public-route')

# ── Integration System ────────────────────────────────────────────────────────
router.register(r'integrations/handler',     IntegrationHandlerViewSet,   basename='integration-handler')
router.register(r'integrations/registry',    IntegrationRegistryViewSet,  basename='integration-registry')
router.register(r'integrations/auth',        AuthBridgeViewSet,           basename='integration-auth')
router.register(r'integrations/data',        DataBridgeViewSet,           basename='integration-data')
router.register(r'integrations/events',      EventBusViewSet,             basename='integration-events')
router.register(r'integrations/health',      IntegrationHealthViewSet,    basename='integration-health')
router.register(r'integrations/performance', PerformanceMonitorViewSet,   basename='integration-performance')

# ── Advanced Services ─────────────────────────────────────────────────────────
router.register(r'geo-revenue',     GeoRevenueViewSet,     basename='geo-revenue')
router.register(r'dynamic-pricing', DynamicPricingViewSet, basename='dynamic-pricing')
router.register(r'ml',              MLIntegrationViewSet,  basename='ml')
router.register(r'waterfall',       WaterfallViewSet,      basename='waterfall')
router.register(r'postback',        PostbackViewSet,       basename='postback')
router.register(r'fraud',           FraudDetectionViewSet, basename='fraud')
router.register(r'openai',          OpenAIViewSet,         basename='openai')
router.register(r'plugins',         PluginViewSet,         basename='plugin')
router.register(r'configuration',   ConfigurationViewSet,  basename='configuration')
router.register(r'cache',           CacheBackendViewSet,   basename='cache')
router.register(r'attachments',     AttachmentViewSet,     basename='attachment')

# ── Tenant Admin ──────────────────────────────────────────────────────────────
router.register(r'tenant/settings',   TenantSettingsViewSet,   basename='tenant-settings')
router.register(r'tenant/billing',    TenantBillingViewSet,    basename='tenant-billing')
router.register(r'tenant/invoices',   TenantInvoiceViewSet,    basename='tenant-invoice')
router.register(r'routing-templates', RoutingTemplateViewSet,  basename='routing-template')
router.register(r'route-actions',     RouteActionViewSet,      basename='route-action')
router.register(r'security-events',   SecurityEventViewSet,    basename='security-event')

# ── Domain Models ─────────────────────────────────────────────────────────────
router.register(r'blacklist',           RoutingBlacklistViewSet,       basename='blacklist')
router.register(r'blacklist-hits',      BlacklistHitViewSet,           basename='blacklist-hit')
router.register(r'fraud-signals',       ClickFraudSignalViewSet,       basename='fraud-signal')
router.register(r'fraud-patterns',      FraudPatternViewSet,           basename='fraud-pattern')
router.register(r'network-performance', NetworkPerformanceCacheViewSet,basename='network-performance')
router.register(r'offer-quality',       OfferQualityScoreViewSet,      basename='offer-quality')
router.register(r'user-journey',        UserJourneyStepViewSet,        basename='user-journey')

app_name = 'offer_routing'
urlpatterns = [path('api/', include(router.urls))]
