"""
Tests Module for Offer Routing System

This module imports all test cases for the offer routing system.
"""

from .core import OfferRoutingEngineTestCase, RoutingCacheServiceTestCase, IntegrationTestCase
from .scoring import OfferScoringServiceTestCase, OfferRankerServiceTestCase, ScoringIntegrationTestCase
from .personalization import (
    PersonalizationServiceTestCase, CollaborativeFilterServiceTestCase,
    ContentBasedServiceTestCase, AffinityServiceTestCase, PersonalizationIntegrationTestCase
)
from .targeting import (
    TargetingServiceTestCase, GeoTargetingServiceTestCase, DeviceTargetingServiceTestCase,
    SegmentTargetingServiceTestCase, TimeTargetingServiceTestCase, BehaviorTargetingServiceTestCase,
    TargetingIntegrationTestCase
)
from .cap import CapEnforcementServiceTestCase, CapIntegrationTestCase
from .fallback import (
    FallbackServiceTestCase, DefaultOfferPoolTestCase, EmptyResultHandlerTestCase,
    FallbackIntegrationTestCase
)
from .ab_test import (
    ABTestServiceTestCase, ABTestIntegrationTestCase
)
from .analytics import (
    RoutingAnalyticsServiceTestCase, RoutePerformanceStatTestCase, OfferExposureStatTestCase,
    AnalyticsIntegrationTestCase
)
from .monitoring import (
    MonitoringServiceTestCase, MonitoringIntegrationTestCase
)
from .config import (
    ConfigurationServiceTestCase, ConfigurationIntegrationTestCase
)
from .utils import (
    RoutingUtilsServiceTestCase, ValidationServiceTestCase, RouteEvaluatorTestCase,
    UtilsIntegrationTestCase
)
from .evaluator import (
    RouteEvaluatorTestCase, OptimizationIntegrationTestCase
)
from .optimizer import (
    RoutingOptimizerTestCase, OptimizationIntegrationTestCase as OptimizerIntegrationTestCase
)
from .integration import (
    EndToEndRoutingTestCase, ComponentIntegrationTestCase,
    PerformanceIntegrationTestCase, ErrorHandlingIntegrationTestCase
)

__all__ = [
    # Core Tests
    'OfferRoutingEngineTestCase',
    'RoutingCacheServiceTestCase',
    'IntegrationTestCase',
    
    # Scoring Tests
    'OfferScoringServiceTestCase',
    'OfferRankerServiceTestCase',
    'ScoringIntegrationTestCase',
    
    # Personalization Tests
    'PersonalizationServiceTestCase',
    'CollaborativeFilterServiceTestCase',
    'ContentBasedServiceTestCase',
    'AffinityServiceTestCase',
    'PersonalizationIntegrationTestCase',
    
    # Targeting Tests
    'TargetingServiceTestCase',
    'GeoTargetingServiceTestCase',
    'DeviceTargetingServiceTestCase',
    'SegmentTargetingServiceTestCase',
    'TimeTargetingServiceTestCase',
    'BehaviorTargetingServiceTestCase',
    'TargetingIntegrationTestCase',
    
    # Cap Tests
    'CapEnforcementServiceTestCase',
    'CapIntegrationTestCase',
    
    # Fallback Tests
    'FallbackServiceTestCase',
    'DefaultOfferPoolTestCase',
    'EmptyResultHandlerTestCase',
    'FallbackIntegrationTestCase',
    
    # A/B Test Tests
    'ABTestServiceTestCase',
    'ABTestIntegrationTestCase',
    
    # Analytics Tests
    'RoutingAnalyticsServiceTestCase',
    'RoutePerformanceStatTestCase',
    'OfferExposureStatTestCase',
    'AnalyticsIntegrationTestCase',
    
    # Monitoring Tests
    'MonitoringServiceTestCase',
    'MonitoringIntegrationTestCase',
    
    # Configuration Tests
    'ConfigurationServiceTestCase',
    'ConfigurationIntegrationTestCase',
    
    # Utility Tests
    'RoutingUtilsServiceTestCase',
    'ValidationServiceTestCase',
    'RouteEvaluatorTestCase',
    'UtilsIntegrationTestCase',
    
    # Evaluator Tests
    'RouteEvaluatorTestCase',
    'OptimizationIntegrationTestCase',
    
    # Optimizer Tests
    'RoutingOptimizerTestCase',
    'OptimizerIntegrationTestCase',
    
    # Integration Tests
    'EndToEndRoutingTestCase',
    'ComponentIntegrationTestCase',
    'PerformanceIntegrationTestCase',
    'ErrorHandlingIntegrationTestCase',
]
