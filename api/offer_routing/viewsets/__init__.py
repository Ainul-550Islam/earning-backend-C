"""
Viewsets Module for Offer Routing System

All viewsets exported from this module — used by urls.py.

ADDITIONS (audit 2026-06):
  Personalization:
    - HybridRecommendationViewSet   exposes HybridRoutingService
    - CollaborativeFilterViewSet    exposes CollaborativeFilterService
    - ContentBasedViewSet           exposes ContentBasedService
  Targeting:
    - TargetingPreviewViewSet       cross-rule preview + aggregate health
  Both previously floating and not reachable via any API URL.
"""

# ── Core ──────────────────────────────────────────────────────────────────────
from .core import (
    OfferRouteViewSet, RouteConditionViewSet,
    RoutingDecisionViewSet, PublicRoutingViewSet, AdminRoutingViewSet,
)

# ── Targeting ─────────────────────────────────────────────────────────────────
from .targeting import (
    GeoRouteRuleViewSet, DeviceRouteRuleViewSet, UserSegmentRuleViewSet,
    TimeRouteRuleViewSet, BehaviorRouteRuleViewSet,
    TargetingPreviewViewSet,           # ← NEW: cross-targeting preview API
)

# ── Scoring ───────────────────────────────────────────────────────────────────
from .scoring import (
    OfferScoreConfigViewSet, OfferScoreViewSet,
    GlobalOfferRankViewSet, UserOfferHistoryViewSet,
)

# ── Personalization ───────────────────────────────────────────────────────────
from .personalization import (
    UserPreferenceVectorViewSet, ContextualSignalViewSet, OfferAffinityScoreViewSet,
    HybridRecommendationViewSet,       # ← NEW: hybrid CF+CB recommendation API
    CollaborativeFilterViewSet,        # ← NEW: direct CF recommendation API
    ContentBasedViewSet,               # ← NEW: direct CB recommendation API
)

# ── Config ────────────────────────────────────────────────────────────────────
from .config import PersonalizationConfigViewSet, RoutingConfigViewSet

# ── Cap ───────────────────────────────────────────────────────────────────────
from .cap import OfferRoutingCapViewSet, UserOfferCapViewSet, CapOverrideViewSet

# ── Fallback ──────────────────────────────────────────────────────────────────
from .fallback import FallbackRuleViewSet, DefaultOfferPoolViewSet, EmptyResultHandlerViewSet

# ── A/B Tests ─────────────────────────────────────────────────────────────────
from .ab_test import RoutingABTestViewSet, ABTestAssignmentViewSet, ABTestResultViewSet

# ── Analytics ─────────────────────────────────────────────────────────────────
from .analytics import (
    RoutingDecisionLogViewSet, RoutingInsightViewSet, RoutePerformanceStatViewSet,
    OfferExposureStatViewSet, ReportViewSet,
)

# ── Monitoring / Config / Utils ───────────────────────────────────────────────
from .monitoring import MonitoringViewSet
from .utils import ValidationViewSet, TestingViewSet, HelperViewSet

# ── Evaluator / Optimizer ─────────────────────────────────────────────────────
from .evaluator import RouteEvaluatorViewSet
from .optimizer import RoutingOptimizerViewSet

# ── Integration System ────────────────────────────────────────────────────────
from .integration import (
    IntegrationHandlerViewSet, IntegrationRegistryViewSet,
    AuthBridgeViewSet, DataBridgeViewSet, EventBusViewSet,
    IntegrationHealthViewSet, PerformanceMonitorViewSet,
)

# ── Advanced Services ─────────────────────────────────────────────────────────
from .advanced import (
    GeoRevenueViewSet, DynamicPricingViewSet, MLIntegrationViewSet,
    WaterfallViewSet, PostbackViewSet, FraudDetectionViewSet,
    OpenAIViewSet, PluginViewSet, ConfigurationViewSet,
    CacheBackendViewSet, AttachmentViewSet,
)

# ── Tenant Admin ──────────────────────────────────────────────────────────────
from .tenant_admin import (
    TenantSettingsViewSet, TenantBillingViewSet, TenantInvoiceViewSet,
    RoutingTemplateViewSet, RouteActionViewSet, SecurityEventViewSet,
)

# ── Domain Models ─────────────────────────────────────────────────────────────
from .domain import (
    RoutingBlacklistViewSet, BlacklistHitViewSet,
    ClickFraudSignalViewSet, FraudPatternViewSet,
    NetworkPerformanceCacheViewSet, OfferQualityScoreViewSet,
    UserJourneyStepViewSet,
)

# ── Aliases (backwards compat) ────────────────────────────────────────────────
RoutePerformanceViewSet = RoutePerformanceStatViewSet

# ── Public API ────────────────────────────────────────────────────────────────
__all__ = [
    # Core
    'OfferRouteViewSet', 'RouteConditionViewSet', 'RoutingDecisionViewSet',
    'PublicRoutingViewSet', 'AdminRoutingViewSet',

    # Targeting
    'GeoRouteRuleViewSet', 'DeviceRouteRuleViewSet', 'UserSegmentRuleViewSet',
    'TimeRouteRuleViewSet', 'BehaviorRouteRuleViewSet',
    'TargetingPreviewViewSet',          # ← NEW

    # Scoring
    'OfferScoreConfigViewSet', 'OfferScoreViewSet',
    'GlobalOfferRankViewSet', 'UserOfferHistoryViewSet',

    # Personalization
    'PersonalizationConfigViewSet', 'UserPreferenceVectorViewSet',
    'ContextualSignalViewSet', 'OfferAffinityScoreViewSet',
    'HybridRecommendationViewSet',      # ← NEW
    'CollaborativeFilterViewSet',       # ← NEW
    'ContentBasedViewSet',              # ← NEW

    # Cap
    'OfferRoutingCapViewSet', 'UserOfferCapViewSet', 'CapOverrideViewSet',

    # Fallback
    'FallbackRuleViewSet', 'DefaultOfferPoolViewSet', 'EmptyResultHandlerViewSet',

    # A/B Test
    'RoutingABTestViewSet', 'ABTestAssignmentViewSet', 'ABTestResultViewSet',

    # Analytics
    'RoutingDecisionLogViewSet', 'RoutingInsightViewSet', 'RoutePerformanceStatViewSet',
    'RoutePerformanceViewSet', 'OfferExposureStatViewSet', 'ReportViewSet',

    # Monitoring / Config / Utils
    'MonitoringViewSet', 'RoutingConfigViewSet',
    'ValidationViewSet', 'TestingViewSet', 'HelperViewSet',

    # Evaluator / Optimizer
    'RouteEvaluatorViewSet', 'RoutingOptimizerViewSet',

    # Integration System
    'IntegrationHandlerViewSet', 'IntegrationRegistryViewSet',
    'AuthBridgeViewSet', 'DataBridgeViewSet', 'EventBusViewSet',
    'IntegrationHealthViewSet', 'PerformanceMonitorViewSet',

    # Advanced Services
    'GeoRevenueViewSet', 'DynamicPricingViewSet', 'MLIntegrationViewSet',
    'WaterfallViewSet', 'PostbackViewSet', 'FraudDetectionViewSet',
    'OpenAIViewSet', 'PluginViewSet', 'ConfigurationViewSet',
    'CacheBackendViewSet', 'AttachmentViewSet',

    # Tenant Admin
    'TenantSettingsViewSet', 'TenantBillingViewSet', 'TenantInvoiceViewSet',
    'RoutingTemplateViewSet', 'RouteActionViewSet', 'SecurityEventViewSet',

    # Domain Models
    'RoutingBlacklistViewSet', 'BlacklistHitViewSet',
    'ClickFraudSignalViewSet', 'FraudPatternViewSet',
    'NetworkPerformanceCacheViewSet', 'OfferQualityScoreViewSet',
    'UserJourneyStepViewSet',
]
