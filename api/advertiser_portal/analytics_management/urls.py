"""
Analytics Management URLs

This module contains URL patterns for analytics management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    AnalyticsViewSet,
    ReportingViewSet,
    DashboardViewSet,
    MetricsViewSet,
    VisualizationViewSet
)

# Create router for analytics management
router = DefaultRouter()
router.register(r'reports', ReportingViewSet, basename='report')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')

app_name = 'analytics_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
analytics_urls = [
    # Analytics endpoints
    path('analytics/campaign/', AnalyticsViewSet.as_view({'get': 'campaign_analytics'}), name='analytics-campaign'),
    path('analytics/creative/', AnalyticsViewSet.as_view({'get': 'creative_analytics'}), name='analytics-creative'),
    path('analytics/advertiser/', AnalyticsViewSet.as_view({'get': 'advertiser_analytics'}), name='analytics-advertiser'),
    path('analytics/real-time/', AnalyticsViewSet.as_view({'get': 'real_time_metrics'}), name='analytics-real-time'),
    path('analytics/attribution/', AnalyticsViewSet.as_view({'post': 'calculate_attribution'}), name='analytics-attribution'),
    
    # Reporting endpoints
    path('reports/', ReportingViewSet.as_view({'get': 'list', 'post': 'create'}), name='report-list-create'),
    path('reports/<uuid:pk>/', ReportingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='report-detail-update-delete'),
    path('reports/<uuid:pk>/generate/', ReportingViewSet.as_view({'post': 'generate'}), name='report-generate'),
    path('reports/<uuid:pk>/history/', ReportingViewSet.as_view({'get': 'history'}), name='report-history'),
    path('reports/<uuid:pk>/schedule/', ReportingViewSet.as_view({'post': 'schedule'}), name='report-schedule'),
    
    # Dashboard endpoints
    path('dashboards/', DashboardViewSet.as_view({'get': 'list', 'post': 'create'}), name='dashboard-list-create'),
    path('dashboards/<uuid:pk>/', DashboardViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='dashboard-detail-update-delete'),
    path('dashboards/<uuid:pk>/data/', DashboardViewSet.as_view({'get': 'data'}), name='dashboard-data'),
    path('dashboards/<uuid:pk>/share/', DashboardViewSet.as_view({'post': 'share'}), name='dashboard-share'),
    
    # Metrics endpoints
    path('metrics/calculate/', MetricsViewSet.as_view({'post': 'calculate'}), name='metrics-calculate'),
    path('metrics/definitions/', MetricsViewSet.as_view({'get': 'definitions'}), name='metrics-definitions'),
    
    # Visualization endpoints
    path('visualization/create/', VisualizationViewSet.as_view({'post': 'create_visualization'}), name='visualization-create'),
    path('visualization/chart-data/', VisualizationViewSet.as_view({'post': 'generate_chart_data'}), name='visualization-chart-data'),
    path('visualization/chart-types/', VisualizationViewSet.as_view({'get': 'chart_types'}), name='visualization-chart-types'),
]
