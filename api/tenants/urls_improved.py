"""
Tenant URLs - Improved Version with Enhanced Security and Routing

This module contains comprehensive URL configuration for tenant management
with proper security, versioning, and API documentation.
"""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework.urlpatterns import format_suffix_patterns
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views_improved import (
    TenantViewSet, TenantSettingsViewSet, TenantBillingViewSet,
    TenantInvoiceViewSet, TenantAuditLogViewSet,
    tenant_health_check, webhook_handler, TenantPublicAPIView
)
from .permissions_improved import (
    IsSuperAdminOrTenantOwner, CanManageUsers, CanManageBilling,
    CanViewAnalytics, CanAccessAPI
)

# Create router for API endpoints
router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'tenant-settings', TenantSettingsViewSet, basename='tenant-settings')
router.register(r'tenant-billing', TenantBillingViewSet, basename='tenant-billing')
router.register(r'tenant-invoices', TenantInvoiceViewSet, basename='tenant-invoices')
router.register(r'tenant-audit-logs', TenantAuditLogViewSet, basename='tenant-audit-logs')

# API URL patterns
app_name = 'tenants'

urlpatterns = [
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='tenants:schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='tenants:schema'), name='redoc'),
    
    # Health Check
    path('health/', tenant_health_check, name='tenant_health_check'),
    
    # Public API Endpoints
    path('public/<slug:slug>/', TenantPublicAPIView.as_view(), name='tenant_public'),
    path('webhook/<slug:slug>/', webhook_handler, name='webhook_handler'),
    
    # API Endpoints
    path('api/v1/', include(router.urls)),
]

# Add format suffix patterns for API endpoints
urlpatterns = format_suffix_patterns(urlpatterns)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# API Version 2 (Future expansion)
v2_router = SimpleRouter()
# v2_router.register(r'tenants', TenantV2ViewSet, basename='tenant-v2')

v2_urlpatterns = [
    path('api/v2/', include(v2_router.urls)),
]

# Add v2 patterns to main urlpatterns
urlpatterns += v2_urlpatterns


# Custom URL patterns for specific functionality
tenant_feature_urls = [
    # Feature-specific endpoints
    path('api/v1/tenants/<uuid:pk>/features/referral/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_referral_feature'),
    path('api/v1/tenants/<uuid:pk>/features/offerwall/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_offerwall_feature'),
    path('api/v1/tenants/<uuid:pk>/features/kyc/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_kyc_feature'),
    path('api/v1/tenants/<uuid:pk>/features/leaderboard/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_leaderboard_feature'),
    path('api/v1/tenants/<uuid:pk>/features/chat/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_chat_feature'),
    path('api/v1/tenants/<uuid:pk>/features/push-notifications/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_push_notifications_feature'),
    path('api/v1/tenants/<uuid:pk>/features/analytics/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_analytics_feature'),
    path('api/v1/tenants/<uuid:pk>/features/api-access/', 
         TenantViewSet.as_view({'post': 'toggle_feature'}), 
         name='toggle_api_access_feature'),
]

# Add feature URLs to main patterns
urlpatterns += tenant_feature_urls


# Admin-specific URLs
admin_urls = [
    # Admin dashboard endpoints
    path('api/v1/admin/tenants/overview/', 
         TenantViewSet.as_view({'get': 'overview'}), 
         name='admin_tenants_overview'),
    
    # Admin management endpoints
    path('api/v1/admin/tenants/<uuid:pk>/suspend/', 
         TenantViewSet.as_view({'post': 'toggle_status'}), 
         name='admin_suspend_tenant'),
    path('api/v1/admin/tenants/<uuid:pk>/activate/', 
         TenantViewSet.as_view({'post': 'toggle_status'}), 
         name='admin_activate_tenant'),
    
    # Admin billing management
    path('api/v1/admin/tenants/<uuid:pk>/billing/manage/', 
         TenantViewSet.as_view({'patch': 'manage_subscription'}), 
         name='admin_manage_billing'),
    path('api/v1/admin/tenants/<uuid:pk>/billing/extend-trial/', 
         TenantBillingViewSet.as_view({'post': 'extend_trial'}), 
         name='admin_extend_trial'),
]

# Add admin URLs to main patterns
urlpatterns += admin_urls


# Public React Native App URLs
react_native_urls = [
    # React Native app configuration
    path('api/v1/app/tenant/', 
         TenantViewSet.as_view({'get': 'my_tenant'}), 
         name='react_native_tenant_config'),
    
    # React Native app features
    path('api/v1/app/features/', 
         TenantViewSet.as_view({'get': 'my_tenant'}), 
         name='react_native_features'),
]

# Add React Native URLs to main patterns
urlpatterns += react_native_urls


# Webhook URLs
webhook_urls = [
    # Webhook endpoints
    path('api/v1/webhooks/<slug:slug>/stripe/', 
         webhook_handler, 
         name='stripe_webhook'),
    path('api/v1/webhooks/<slug:slug>/paypal/', 
         webhook_handler, 
         name='paypal_webhook'),
    path('api/v1/webhooks/<slug:slug>/custom/', 
         webhook_handler, 
         name='custom_webhook'),
]

# Add webhook URLs to main patterns
urlpatterns += webhook_urls


# Utility URLs
utility_urls = [
    # Utility endpoints
    path('api/v1/utils/tenant-exists/<slug:slug>/', 
         TenantViewSet.as_view({'get': 'check_exists'}), 
         name='check_tenant_exists'),
    path('api/v1/utils/domain-available/', 
         TenantViewSet.as_view({'post': 'check_domain_availability'}), 
         name='check_domain_availability'),
]

# Add utility URLs to main patterns
urlpatterns += utility_urls


# Export URL patterns for Django settings
urlpatterns = urlpatterns
