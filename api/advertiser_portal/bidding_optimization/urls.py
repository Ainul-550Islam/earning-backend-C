"""
Bidding Optimization URLs

This module defines URL patterns for bidding optimization endpoints including
bids, strategies, budget optimization, and automated bidding.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    BiddingViewSet,
    BidStrategyViewSet,
    BudgetOptimizationViewSet,
    PerformanceBiddingViewSet,
    AutomatedBiddingViewSet
)

# Create router for bidding optimization
router = DefaultRouter()
router.register(r'bids', BiddingViewSet, basename='bid')
router.register(r'strategies', BidStrategyViewSet, basename='bidstrategy')

# URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Budget optimization URLs
    path('budget/', BudgetOptimizationViewSet.as_view({'get': 'list'}), name='budget-optimization'),
    path('budget/optimize/', BudgetOptimizationViewSet.as_view({'post': 'optimize'}), name='budget-optimize'),
    path('budget/recommendations/', BudgetOptimizationViewSet.as_view({'get': 'recommendations'}), name='budget-recommendations'),
    
    # Performance bidding URLs
    path('performance/', PerformanceBiddingViewSet.as_view({'get': 'list'}), name='performance-bidding'),
    path('performance/enable/', PerformanceBiddingViewSet.as_view({'post': 'enable'}), name='performance-bidding-enable'),
    
    # Automated bidding URLs
    path('automated/', AutomatedBiddingViewSet.as_view({'get': 'list'}), name='automated-bidding'),
    path('automated/rules/', AutomatedBiddingViewSet.as_view({'get': 'rules'}), name='automated-bidding-rules'),
    path('automated/create-rule/', AutomatedBiddingViewSet.as_view({'post': 'create_rule'}), name='automated-bidding-create-rule'),
]

# Export router for inclusion in main URLs
bidding_urls = urlpatterns
