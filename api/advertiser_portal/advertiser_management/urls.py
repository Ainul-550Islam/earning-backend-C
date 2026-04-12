"""
Advertiser Management URLs

This module contains URL patterns for advertiser management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    AdvertiserViewSet,
    AdvertiserVerificationViewSet,
    AdvertiserUserViewSet,
    AdvertiserSettingsViewSet
)

# Create router for advertiser management
router = DefaultRouter()
router.register(r'advertisers', AdvertiserViewSet, basename='advertiser')
router.register(r'verifications', AdvertiserVerificationViewSet, basename='verification')
router.register(r'users', AdvertiserUserViewSet, basename='user')
router.register(r'settings', AdvertiserSettingsViewSet, basename='settings')

app_name = 'advertiser_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
advertiser_urls = [
    # Advertiser endpoints
    path('advertisers/', AdvertiserViewSet.as_view({'get': 'list', 'post': 'create'}), name='advertiser-list-create'),
    path('advertisers/<uuid:pk>/', AdvertiserViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='advertiser-detail-update-delete'),
    
    # Advertiser actions
    path('advertisers/<uuid:pk>/performance/', AdvertiserViewSet.as_view({'get': 'performance'}), name='advertiser-performance'),
    path('advertisers/<uuid:pk>/add-credit/', AdvertiserViewSet.as_view({'post': 'add_credit'}), name='advertiser-add-credit'),
    path('advertisers/<uuid:pk>/can-create-campaign/', AdvertiserViewSet.as_view({'get': 'can_create_campaign'}), name='advertiser-can-create-campaign'),
    path('advertisers/<uuid:pk>/billing-profile/', AdvertiserViewSet.as_view({'get': 'billing_profile'}), name='advertiser-billing-profile'),
    
    # Verification endpoints
    path('verifications/', AdvertiserVerificationViewSet.as_view({'get': 'list', 'post': 'create'}), name='verification-list-create'),
    path('verifications/<uuid:pk>/', AdvertiserVerificationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='verification-detail-update-delete'),
    
    # Verification actions
    path('verifications/send/', AdvertiserVerificationViewSet.as_view({'post': 'send_verification'}), name='verification-send'),
    path('verifications/verify/', AdvertiserVerificationViewSet.as_view({'post': 'verify'}), name='verification-verify'),
    path('verifications/submit-documents/', AdvertiserVerificationViewSet.as_view({'post': 'submit_documents'}), name='verification-submit-documents'),
    path('verifications/<uuid:pk>/review/', AdvertiserVerificationViewSet.as_view({'post': 'review'}), name='verification-review'),
    
    # User endpoints
    path('users/', AdvertiserUserViewSet.as_view({'get': 'list', 'post': 'create'}), name='user-list-create'),
    path('users/<uuid:pk>/', AdvertiserUserViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='user-detail-update-delete'),
    
    # User actions
    path('users/<uuid:pk>/update-permissions/', AdvertiserUserViewSet.as_view({'post': 'update_permissions'}), name='user-update-permissions'),
    path('users/<uuid:pk>/deactivate/', AdvertiserUserViewSet.as_view({'post': 'deactivate'}), name='user-deactivate'),
    path('users/<uuid:pk>/activity-log/', AdvertiserUserViewSet.as_view({'get': 'activity_log'}), name='user-activity-log'),
    
    # Settings endpoints
    path('settings/', AdvertiserSettingsViewSet.as_view({'get': 'get_settings', 'post': 'update_settings'}), name='settings-get-update'),
    path('settings/reset/', AdvertiserSettingsViewSet.as_view({'post': 'reset_settings'}), name='settings-reset'),
]
