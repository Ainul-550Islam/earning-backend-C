"""
Creative Management URLs

This module contains URL patterns for creative management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    CreativeViewSet,
    CreativeApprovalViewSet,
    CreativeOptimizationViewSet,
    CreativeAnalyticsViewSet,
    CreativeAssetViewSet
)

# Create router for creative management
router = DefaultRouter()
router.register(r'creatives', CreativeViewSet, basename='creative')

app_name = 'creative_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
creative_urls = [
    # Creative endpoints
    path('creatives/', CreativeViewSet.as_view({'get': 'list', 'post': 'create'}), name='creative-list-create'),
    path('creatives/<uuid:pk>/', CreativeViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='creative-detail-update-delete'),
    
    # Creative actions
    path('creatives/<uuid:pk>/activate/', CreativeViewSet.as_view({'post': 'activate'}), name='creative-activate'),
    path('creatives/<uuid:pk>/pause/', CreativeViewSet.as_view({'post': 'pause'}), name='creative-pause'),
    path('creatives/<uuid:pk>/duplicate/', CreativeViewSet.as_view({'post': 'duplicate'}), name='creative-duplicate'),
    path('creatives/<uuid:pk>/performance/', CreativeViewSet.as_view({'get': 'performance'}), name='creative-performance'),
    path('creatives/<uuid:pk>/assets/', CreativeViewSet.as_view({'get': 'assets'}), name='creative-assets'),
    path('creatives/<uuid:pk>/add-asset/', CreativeViewSet.as_view({'post': 'add_asset'}), name='creative-add-asset'),
    
    # Approval endpoints
    path('creatives/approval/submit/', CreativeApprovalViewSet.as_view({'post': 'submit_for_approval'}), name='creative-submit-approval'),
    path('creatives/approval/approve/', CreativeApprovalViewSet.as_view({'post': 'approve'}), name='creative-approve'),
    path('creatives/approval/reject/', CreativeApprovalViewSet.as_view({'post': 'reject'}), name='creative-reject'),
    path('creatives/approval/history/', CreativeApprovalViewSet.as_view({'get': 'approval_history'}), name='creative-approval-history'),
    
    # Optimization endpoints
    path('creatives/optimize/', CreativeOptimizationViewSet.as_view({'post': 'optimize'}), name='creative-optimize'),
    path('creatives/optimization-report/', CreativeOptimizationViewSet.as_view({'get': 'optimization_report'}), name='creative-optimization-report'),
    
    # Analytics endpoints
    path('creatives/analytics/', CreativeAnalyticsViewSet.as_view({'get': 'analytics'}), name='creative-analytics'),
    path('creatives/generate-report/', CreativeAnalyticsViewSet.as_view({'post': 'generate_report'}), name='creative-generate-report'),
    
    # Asset endpoints
    path('creatives/assets/add/', CreativeAssetViewSet.as_view({'post': 'add_asset'}), name='creative-asset-add'),
    path('creatives/assets/remove/', CreativeAssetViewSet.as_view({'post': 'remove_asset'}), name='creative-asset-remove'),
    path('creatives/assets/', CreativeAssetViewSet.as_view({'get': 'get_assets'}), name='creative-assets-list'),
]
