"""
Campaign Management URLs

This module contains URL patterns for campaign management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    CampaignViewSet,
    CampaignOptimizationViewSet,
    CampaignTargetingViewSet,
    CampaignAnalyticsViewSet,
    CampaignBudgetViewSet
)

# Create router for campaign management
router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')

app_name = 'campaign_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
campaign_urls = [
    # Campaign endpoints
    path('campaigns/', CampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-list-create'),
    path('campaigns/<uuid:pk>/', CampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-detail-update-delete'),
    
    # Campaign actions
    path('campaigns/<uuid:pk>/activate/', CampaignViewSet.as_view({'post': 'activate'}), name='campaign-activate'),
    path('campaigns/<uuid:pk>/pause/', CampaignViewSet.as_view({'post': 'pause'}), name='campaign-pause'),
    path('campaigns/<uuid:pk>/duplicate/', CampaignViewSet.as_view({'post': 'duplicate'}), name='campaign-duplicate'),
    path('campaigns/<uuid:pk>/performance/', CampaignViewSet.as_view({'get': 'performance'}), name='campaign-performance'),
    path('campaigns/<uuid:pk>/can-spend/', CampaignViewSet.as_view({'get': 'can_spend'}), name='campaign-can-spend'),
    path('campaigns/<uuid:pk>/add-spend/', CampaignViewSet.as_view({'post': 'add_spend'}), name='campaign-add-spend'),
    path('campaigns/<uuid:pk>/targeting/', CampaignViewSet.as_view({'get': 'targeting'}), name='campaign-targeting'),
    
    # Optimization endpoints
    path('campaigns/optimize/', CampaignOptimizationViewSet.as_view({'post': 'optimize'}), name='campaign-optimize'),
    path('campaigns/optimization-report/', CampaignOptimizationViewSet.as_view({'get': 'optimization_report'}), name='campaign-optimization-report'),
    
    # Targeting endpoints
    path('campaigns/targeting/update/', CampaignTargetingViewSet.as_view({'post': 'update_targeting'}), name='campaign-targeting-update'),
    path('campaigns/targeting/validate/', CampaignTargetingViewSet.as_view({'post': 'validate_targeting'}), name='campaign-targeting-validate'),
    path('campaigns/targeting/summary/', CampaignTargetingViewSet.as_view({'get': 'targeting_summary'}), name='campaign-targeting-summary'),
    path('campaigns/targeting/expand/', CampaignTargetingViewSet.as_view({'post': 'expand_targeting'}), name='campaign-targeting-expand'),
    
    # Analytics endpoints
    path('campaigns/analytics/', CampaignAnalyticsViewSet.as_view({'get': 'analytics'}), name='campaign-analytics'),
    path('campaigns/generate-report/', CampaignAnalyticsViewSet.as_view({'post': 'generate_report'}), name='campaign-generate-report'),
    
    # Budget endpoints
    path('campaigns/budget/update/', CampaignBudgetViewSet.as_view({'post': 'update_budget'}), name='campaign-budget-update'),
    path('campaigns/budget/summary/', CampaignBudgetViewSet.as_view({'get': 'budget_summary'}), name='campaign-budget-summary'),
    path('campaigns/budget/alerts/', CampaignBudgetViewSet.as_view({'get': 'budget_alerts'}), name='campaign-budget-alerts'),
]
