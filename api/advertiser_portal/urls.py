"""
Advertiser Portal URL Configuration

This module contains the main URL configuration for the Advertiser Portal,
including all module URL patterns and API routing.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

# Import module URL patterns
from .advertiser_management.urls import advertiser_urls
from .campaign_management.urls import campaign_urls
from .creative_management.urls import creative_urls
from .targeting_management.urls import targeting_urls
from .analytics_management.urls import analytics_urls
from .billing_management.urls import billing_urls

# Create main router
router = DefaultRouter()

# API endpoints
urlpatterns = [
    # Advertiser Management
    path('api/v1/advertiser/', include(advertiser_urls)),
    
    # Campaign Management
    path('api/v1/campaign/', include(campaign_urls)),
    
    # Creative Management
    path('api/v1/creative/', include(creative_urls)),
    
    # Targeting Management
    path('api/v1/targeting/', include(targeting_urls)),
    
    # Analytics Management
    path('api/v1/analytics/', include(analytics_urls)),
    
    # Billing Management
    path('api/v1/billing/', include(billing_urls)),
    
    # API Documentation
    path('api/v1/docs/', include('rest_framework.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
