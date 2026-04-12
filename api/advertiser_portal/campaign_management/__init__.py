"""
Campaign Management Package

This package contains all modules related to campaign management,
including campaign creation, optimization, targeting, and performance tracking.
"""

from .services import *
from .views import *
from .serializers import *
from .urls import *

__all__ = [
    # Services
    'CampaignService',
    'CampaignOptimizationService',
    'CampaignTargetingService',
    'CampaignAnalyticsService',
    'CampaignBudgetService',
    
    # Views
    'CampaignViewSet',
    'CampaignOptimizationViewSet',
    'CampaignTargetingViewSet',
    'CampaignAnalyticsViewSet',
    'CampaignBudgetViewSet',
    
    # Serializers
    'CampaignSerializer',
    'CampaignDetailSerializer',
    'CampaignCreateSerializer',
    'CampaignUpdateSerializer',
    'CampaignOptimizationSerializer',
    'CampaignTargetingSerializer',
    'CampaignAnalyticsSerializer',
    'CampaignBudgetSerializer',
    
    # URLs
    'campaign_urls',
]
