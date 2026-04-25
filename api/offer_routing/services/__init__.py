"""
Services Module for Offer Routing System

This module imports all services for the offer routing system.
"""

from .core import OfferRoutingEngine, routing_engine
from .cache import RoutingCacheService, cache_service
from .targeting import (
    TargetingService, GeoTargetingService, DeviceTargetingService,
    SegmentTargetingService, TimeTargetingService, BehaviorTargetingService,
    targeting_service, geo_targeting_service, device_targeting_service,
    segment_targeting_service, time_targeting_service, behavior_targeting_service
)
from .scoring import OfferScoringService, OfferRankerService, scoring_service, ranker_service
from .personalization import (
    PersonalizationService, CollaborativeFilterService, ContentBasedService,
    AffinityService, personalization_service, collaborative_service,
    content_based_service, affinity_service
)
from .cap import CapEnforcementService, cap_service
from .fallback import FallbackService, fallback_service
from .ab_test import ABTestService, ab_test_service
from .analytics import RoutingAnalyticsService, analytics_service
from .config import ConfigurationService, config_service
from .monitoring import MonitoringService, monitoring_service
from .utils import RoutingUtilsService, ValidationService, utils_service, validation_service
from .evaluator import RouteEvaluator, route_evaluator
from .optimizer import RoutingOptimizer, routing_optimizer
from .reporter import RoutingReporter, routing_reporter

__all__ = [
    # Core Services
    'OfferRoutingEngine',
    'routing_engine',
    
    # Cache Service
    'RoutingCacheService',
    'cache_service',
    
    # Targeting Services
    'TargetingService',
    'GeoTargetingService',
    'DeviceTargetingService',
    'SegmentTargetingService',
    'TimeTargetingService',
    'BehaviorTargetingService',
    'targeting_service',
    'geo_targeting_service',
    'device_targeting_service',
    'segment_targeting_service',
    'time_targeting_service',
    'behavior_targeting_service',
    
    # Scoring Services
    'OfferScoringService',
    'OfferRankerService',
    'scoring_service',
    'ranker_service',
    
    # Personalization Services
    'PersonalizationService',
    'CollaborativeFilterService',
    'ContentBasedService',
    'AffinityService',
    'personalization_service',
    'collaborative_service',
    'content_based_service',
    'affinity_service',
    
    # Cap Service
    'CapEnforcementService',
    'cap_service',
    
    # Fallback Service
    'FallbackService',
    'fallback_service',
    
    # A/B Test Service
    'ABTestService',
    'ab_test_service',
    
    # Analytics Service
    'RoutingAnalyticsService',
    'analytics_service',
    
    # Configuration Service
    'ConfigurationService',
    'config_service',
    
    # Monitoring Service
    'MonitoringService',
    'monitoring_service',
    
    # Utility Services
    'RoutingUtilsService',
    'ValidationService',
    'utils_service',
    'validation_service',
    
    # Evaluator Service
    'RouteEvaluator',
    'route_evaluator',
    
    # Optimizer Service
    'RoutingOptimizer',
    'routing_optimizer',
    
    # Reporter Service
    'RoutingReporter',
    'routing_reporter',
]
