"""
Retargeting Engines URLs

This module defines URL patterns for retargeting engines endpoints including
pixels, audience segments, retargeting campaigns, and conversion tracking.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    RetargetingViewSet,
    PixelViewSet,
    AudienceSegmentViewSet,
    ConversionTrackingViewSet
)

# Create router for retargeting engines
router = DefaultRouter()
router.register(r'campaigns', RetargetingViewSet, basename='retargeting-campaign')
router.register(r'pixels', PixelViewSet, basename='retargeting-pixel')
router.register(r'segments', AudienceSegmentViewSet, basename='audience-segment')

# URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Conversion tracking URLs
    path('tracking/', ConversionTrackingViewSet.as_view({'get': 'list'}), name='conversion-tracking'),
    path('tracking/track/', ConversionTrackingViewSet.as_view({'post': 'track'}), name='conversion-tracking-track'),
    path('tracking/statistics/', ConversionTrackingViewSet.as_view({'get': 'statistics'}), name='conversion-tracking-statistics'),
    path('tracking/pixels/', ConversionTrackingViewSet.as_view({'get': 'pixels'}), name='conversion-tracking-pixels'),
]

# Export router for inclusion in main URLs
retargeting_urls = urlpatterns
