"""
Offer Routing System

A comprehensive Django application for intelligent offer routing, targeting,
scoring, and personalization with A/B testing capabilities.
"""

default_app_config = 'api.offer_routing.apps.OfferRoutingConfig'

__version__ = '1.0.0'
__author__ = 'Offer Routing Team'
__email__ = 'support@offerrouting.com'

# Models and services will be imported through Django's app registry
# No direct imports needed here to avoid "Apps aren't loaded yet" error

__all__ = [
    # Models
    'OfferRoute', 'RouteCondition', 'RouteAction',
    'GeoRouteRule', 'DeviceRouteRule', 'UserSegmentRule',
    'TimeRouteRule', 'BehaviorRouteRule',
    'OfferScore', 'OfferScoreConfig', 'GlobalOfferRank',
    'UserOfferHistory', 'OfferAffinityScore',
    'UserPreferenceVector', 'ContextualSignal', 'PersonalizationConfig',
    'OfferRoutingCap', 'UserOfferCap', 'CapOverride',
    'FallbackRule', 'DefaultOfferPool', 'EmptyResultHandler',
    'RoutingABTest', 'ABTestAssignment', 'ABTestResult',
    'RoutingDecisionLog', 'RoutingInsight', 'RoutePerformanceStat',
    'OfferExposureStat',
    
    # Services
    'OfferRoutingEngine', 'RouteEvaluator', 'OfferScorer',
    'OfferRanker', 'RoutingCacheService',
]
