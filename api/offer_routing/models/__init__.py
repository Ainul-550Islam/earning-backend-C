"""
Models Module for Offer Routing System

This module contains all models for the offer routing system.
Models are organized into separate files for better maintainability.
"""

# Import all models to ensure Django discovers them
from .core import OfferRoute, RouteCondition, RouteAction, TenantSettings, TenantBilling, TenantInvoice, RoutingConfig, RoutingTemplate
from .targeting import GeoRouteRule, DeviceRouteRule, UserSegmentRule, TimeRouteRule, BehaviorRouteRule
from .scoring import OfferScore, OfferScoreConfig, GlobalOfferRank, UserOfferHistory, OfferAffinityScore
from .personalization import UserPreferenceVector, ContextualSignal, PersonalizationConfig
from .cap import OfferRoutingCap, UserOfferCap, CapOverride
from .fallback import FallbackRule, DefaultOfferPool, EmptyResultHandler
from .ab_test import RoutingABTest, ABTestAssignment, ABTestResult
from .analytics import RoutingDecisionLog, RoutingInsight, RoutePerformanceStat, OfferExposureStat
from .routing_blacklist import RoutingBlacklist, BlacklistHit
from .offer_quality import OfferQualityScore
from .network_cache import NetworkPerformanceCache
from .click_fraud import ClickFraudSignal, FraudPattern
from .user_journey import UserJourneyStep

# Explicitly list all model names for Django's model discovery
# This ensures Django recognizes all models for makemigrations and migrate commands
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

# Django will discover models through the app registry
# The models will be available for makemigrations and migrate commands
# when Django apps are loaded properly.

# Django will discover models through the app registry
# The models will be available for makemigrations and migrate commands
# when Django apps are loaded properly.
