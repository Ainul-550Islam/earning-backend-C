"""
Targeting Management URLs

This module contains URL patterns for targeting management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    TargetingViewSet,
    AudienceSegmentViewSet,
    GeographicTargetingViewSet,
    DeviceTargetingViewSet,
    BehavioralTargetingViewSet,
    TargetingOptimizationViewSet
)

# Create router for targeting management
router = DefaultRouter()
router.register(r'targetings', TargetingViewSet, basename='targeting')
router.register(r'audience-segments', AudienceSegmentViewSet, basename='audience-segment')

app_name = 'targeting_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
targeting_urls = [
    # Targeting endpoints
    path('targetings/', TargetingViewSet.as_view({'get': 'list', 'post': 'create'}), name='targeting-list-create'),
    path('targetings/<uuid:pk>/', TargetingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='targeting-detail-update-delete'),
    
    # Targeting actions
    path('targetings/<uuid:pk>/validate/', TargetingViewSet.as_view({'post': 'validate'}), name='targeting-validate'),
    path('targetings/<uuid:pk>/summary/', TargetingViewSet.as_view({'get': 'summary'}), name='targeting-summary'),
    path('targetings/<uuid:pk>/estimate-reach/', TargetingViewSet.as_view({'get': 'estimate_reach'}), name='targeting-estimate-reach'),
    path('targetings/<uuid:pk>/calculate-score/', TargetingViewSet.as_view({'get': 'calculate_score'}), name='targeting-calculate-score'),
    path('targetings/<uuid:pk>/check-overlap/', TargetingViewSet.as_view({'post': 'check_overlap'}), name='targeting-check-overlap'),
    path('targetings/<uuid:pk>/expand/', TargetingViewSet.as_view({'post': 'expand'}), name='targeting-expand'),
    path('targetings/<uuid:pk>/optimize/', TargetingViewSet.as_view({'post': 'optimize'}), name='targeting-optimize'),
    
    # Audience segment endpoints
    path('audience-segments/', AudienceSegmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='audience-segment-list-create'),
    path('audience-segments/<uuid:pk>/', AudienceSegmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='audience-segment-detail-update-delete'),
    
    # Audience segment actions
    path('audience-segments/<uuid:pk>/refresh/', AudienceSegmentViewSet.as_view({'post': 'refresh'}), name='audience-segment-refresh'),
    path('audience-segments/<uuid:pk>/insights/', AudienceSegmentViewSet.as_view({'get': 'insights'}), name='audience-segment-insights'),
    
    # Geographic targeting endpoints
    path('targeting/geo/countries-by-region/', GeographicTargetingViewSet.as_view({'get': 'countries_by_region'}), name='geo-countries-by-region'),
    path('targeting/geo/cities-by-country/', GeographicTargetingViewSet.as_view({'get': 'cities_by_country'}), name='geo-cities-by-country'),
    path('targeting/geo/validate-coordinates/', GeographicTargetingViewSet.as_view({'post': 'validate_coordinates'}), name='geo-validate-coordinates'),
    path('targeting/geo/calculate-distance/', GeographicTargetingViewSet.as_view({'post': 'calculate_distance'}), name='geo-calculate-distance'),
    path('targeting/geo/get-timezone/', GeographicTargetingViewSet.as_view({'post': 'get_timezone'}), name='geo-get-timezone'),
    path('targeting/geo/location-insights/', GeographicTargetingViewSet.as_view({'post': 'location_insights'}), name='geo-location-insights'),
    
    # Device targeting endpoints
    path('targeting/device/statistics/', DeviceTargetingViewSet.as_view({'get': 'device_statistics'}), name='device-statistics'),
    path('targeting/device/os-statistics/', DeviceTargetingViewSet.as_view({'get': 'os_statistics'}), name='device-os-statistics'),
    path('targeting/device/browser-statistics/', DeviceTargetingViewSet.as_view({'get': 'browser_statistics'}), name='device-browser-statistics'),
    path('targeting/device/performance-insights/', DeviceTargetingViewSet.as_view({'post': 'performance_insights'}), name='device-performance-insights'),
    
    # Behavioral targeting endpoints
    path('targeting/behavioral/create-segment/', BehavioralTargetingViewSet.as_view({'post': 'create_segment'}), name='behavioral-create-segment'),
    path('targeting/behavioral/behavioral-patterns/', BehavioralTargetingViewSet.as_view({'get': 'behavioral_patterns'}), name='behavioral-patterns'),
    path('targeting/behavioral/interest-affinity/', BehavioralTargetingViewSet.as_view({'post': 'interest_affinity'}), name='behavioral-interest-affinity'),
    
    # Targeting optimization endpoints
    path('targeting/optimization/optimize-configuration/', TargetingOptimizationViewSet.as_view({'post': 'optimize_configuration'}), name='targeting-optimization-configure'),
    path('targeting/optimization/optimization-report/', TargetingOptimizationViewSet.as_view({'get': 'optimization_report'}), name='targeting-optimization-report'),
]
