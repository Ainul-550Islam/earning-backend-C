"""
Models Module for Offer Routing System

This module imports all models for the offer routing system and ensures
Django discovers every model for migrations. Synced with models/__init__.py.
"""

from .models.core import (
    OfferRoute, RouteCondition, RouteAction,
    TenantSettings, TenantBilling, TenantInvoice,
    RoutingConfig, RoutingTemplate,
)

from .models.targeting import (
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule,
)

from .models.scoring import (
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore,
)

from .models.personalization import (
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,
)

from .models.cap import (
    OfferRoutingCap, UserOfferCap, CapOverride,
)

from .models.fallback import (
    FallbackRule, DefaultOfferPool, EmptyResultHandler,
)

from .models.ab_test import (
    RoutingABTest, ABTestAssignment, ABTestResult,
)

from .models.analytics import (
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat, OfferExposureStat,
)

from .models.routing_blacklist import RoutingBlacklist, BlacklistHit
from .models.offer_quality import OfferQualityScore
from .models.network_cache import NetworkPerformanceCache
from .models.click_fraud import ClickFraudSignal, FraudPattern
from .models.user_journey import UserJourneyStep

__all__ = [
    # Core Models
    'OfferRoute',
    'RouteCondition',
    'RouteAction',
    'TenantSettings',
    'TenantBilling',
    'TenantInvoice',
    'RoutingConfig',
    'RoutingTemplate',

    # Targeting Models
    'GeoRouteRule',
    'DeviceRouteRule',
    'UserSegmentRule',
    'TimeRouteRule',
    'BehaviorRouteRule',

    # Scoring Models
    'OfferScore',
    'OfferScoreConfig',
    'GlobalOfferRank',
    'UserOfferHistory',
    'OfferAffinityScore',

    # Personalization Models
    'UserPreferenceVector',
    'ContextualSignal',
    'PersonalizationConfig',

    # Cap Models
    'OfferRoutingCap',
    'UserOfferCap',
    'CapOverride',

    # Fallback Models
    'FallbackRule',
    'DefaultOfferPool',
    'EmptyResultHandler',

    # A/B Test Models
    'RoutingABTest',
    'ABTestAssignment',
    'ABTestResult',

    # Analytics Models
    'RoutingDecisionLog',
    'RoutingInsight',
    'RoutePerformanceStat',
    'OfferExposureStat',

    # Additional Models
    'RoutingBlacklist',
    'BlacklistHit',
    'OfferQualityScore',
    'NetworkPerformanceCache',
    'ClickFraudSignal',
    'FraudPattern',
    'UserJourneyStep',
]

from .models.security import SecurityEvent
