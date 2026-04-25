"""
Models Module for Offer Routing System

This module imports all models for the offer routing system.
"""

from .core import (
    OfferRoute, RouteCondition, RouteAction,
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule,
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore,
    RoutingABTest, ABTestAssignment, ABTestResult,
    OfferRoutingCap, UserOfferCap, CapOverride,
    FallbackRule, DefaultOfferPool, EmptyResultHandler,
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat
)

from .targeting import (
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule
)

from .scoring import (
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore
)

from .ab_test import (
    RoutingABTest, ABTestAssignment, ABTestResult
)

from .cap import (
    OfferRoutingCap, UserOfferCap, CapOverride
)

from .fallback import (
    FallbackRule, DefaultOfferPool, EmptyResultHandler
)

from .personalization import (
    UserPreferenceVector, ContextualSignal, PersonalizationConfig
)

from .analytics import (
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat
)

__all__ = [
    # Core Models
    'OfferRoute', 'RouteCondition', 'RouteAction',
    
    # Targeting Models
    'GeoRouteRule', 'DeviceRouteRule', 'UserSegmentRule',
    'TimeRouteRule', 'BehaviorRouteRule',
    
    # Scoring Models
    'OfferScore', 'OfferScoreConfig', 'GlobalOfferRank',
    'UserOfferHistory', 'OfferAffinityScore',
    
    # A/B Test Models
    'RoutingABTest', 'ABTestAssignment', 'ABTestResult',
    
    # Cap Models
    'OfferRoutingCap', 'UserOfferCap', 'CapOverride',
    
    # Fallback Models
    'FallbackRule', 'DefaultOfferPool', 'EmptyResultHandler',
    
    # Personalization Models
    'UserPreferenceVector', 'ContextualSignal', 'PersonalizationConfig',
    
    # Analytics Models
    'RoutingDecisionLog', 'RoutingInsight', 'RoutePerformanceStat',
    'OfferExposureStat',
]
