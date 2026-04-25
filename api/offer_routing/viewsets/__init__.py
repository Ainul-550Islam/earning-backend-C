"""
Viewsets Module for Offer Routing System

This module imports all viewsets for the offer routing system.
"""

from .core import OfferRouteViewSet, RoutingDecisionViewSet, PublicRoutingViewSet, AdminRoutingViewSet
from .targeting import (
    GeoRouteRuleViewSet, DeviceRouteRuleViewSet, UserSegmentRuleViewSet,
    TimeRouteRuleViewSet, BehaviorRouteRuleViewSet
)
from .scoring import (
    OfferScoreConfigViewSet, OfferScoreViewSet, GlobalOfferRankViewSet,
    UserOfferHistoryViewSet, OfferAffinityScoreViewSet
)
from .personalization import (
    UserPreferenceVectorViewSet,
    ContextualSignalViewSet, OfferAffinityScoreViewSet
)
from .config import PersonalizationConfigViewSet
from .cap import (
    OfferRoutingCapViewSet, UserOfferCapViewSet, CapOverrideViewSet
)
from .fallback import (
    FallbackRuleViewSet, DefaultOfferPoolViewSet, EmptyResultHandlerViewSet
)
from .ab_test import (
    RoutingABTestViewSet, ABTestAssignmentViewSet, ABTestResultViewSet
)
from .analytics import (
    RoutingDecisionLogViewSet, RoutingInsightViewSet, RoutePerformanceStatViewSet,
    OfferExposureStatViewSet, ReportViewSet
)
from .monitoring import MonitoringViewSet
from .config import RoutingConfigViewSet, PersonalizationConfigViewSet
from .utils import ValidationViewSet, TestingViewSet, HelperViewSet
from .evaluator import RouteEvaluatorViewSet
from .optimizer import RoutingOptimizerViewSet

__all__ = [
    # Core Viewsets
    'OfferRouteViewSet',
    'RoutingDecisionViewSet',
    'PublicRoutingViewSet',
    
    # Targeting Viewsets
    'GeoRouteRuleViewSet',
    'DeviceRouteRuleViewSet',
    'UserSegmentRuleViewSet',
    'TimeRouteRuleViewSet',
    'BehaviorRouteRuleViewSet',
    
    # Scoring Viewsets
    'OfferScoreConfigViewSet',
    'OfferScoreViewSet',
    'GlobalOfferRankViewSet',
    'UserOfferHistoryViewSet',
    'OfferAffinityScoreViewSet',
    
    # Personalization Viewsets
    'PersonalizationConfigViewSet',
    'UserPreferenceVectorViewSet',
    'ContextualSignalViewSet',
    'OfferAffinityScoreViewSet',
    
    # Cap Viewsets
    'OfferRoutingCapViewSet',
    'UserOfferCapViewSet',
    'CapOverrideViewSet',
    
    # Fallback Viewsets
    'FallbackRuleViewSet',
    'DefaultOfferPoolViewSet',
    'EmptyResultHandlerViewSet',
    
    # A/B Test Viewsets
    'RoutingABTestViewSet',
    'ABTestAssignmentViewSet',
    'ABTestResultViewSet',
    
    # Analytics Viewsets
    'RoutingDecisionLogViewSet',
    'RoutingInsightViewSet',
    'RoutePerformanceStatViewSet',
    'OfferExposureStatViewSet',
    'ReportViewSet',
    
    # Monitoring Viewsets
    'MonitoringViewSet',
    
    # Configuration Viewsets
    'RoutingConfigViewSet',
    'PersonalizationConfigViewSet',
    
    # Utility Viewsets
    'ValidationViewSet',
    'TestingViewSet',
    'HelperViewSet',
    
    # Evaluator Viewsets
    'RouteEvaluatorViewSet',
    
    # Optimizer Viewsets
    'RoutingOptimizerViewSet',
]

# Aliases for missing viewsets
RouteConditionViewSet = RoutingDecisionViewSet

RoutePerformanceViewSet = RoutePerformanceStatViewSet  # alias
