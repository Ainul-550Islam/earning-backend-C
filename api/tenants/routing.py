"""
Tenant Routing - URL Routing Configuration

This module contains comprehensive URL routing configuration for tenant
management with advanced URL patterns, versioning, and API endpoints.
"""

from django.urls import path, include, re_path
from django.conf import settings
from django.urls.resolvers import URLPattern, URLResolver
from django.http import HttpResponse
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework.urlpatterns import format_suffix_patterns
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from .views_improved import (
    TenantViewSet, TenantSettingsViewSet, TenantBillingViewSet,
    TenantInvoiceViewSet, TenantAuditLogViewSet
)
from .attachment_upload_view import (
    TenantAttachmentUploadView, TenantAttachmentListView, TenantAttachmentDeleteView
)
from .consumers import TenantNotificationConsumer, TenantAdminConsumer, TenantSupportConsumer

# API Router Configuration
api_router = DefaultRouter()
api_router.register(r'tenants', TenantViewSet, basename='tenant')
api_router.register(r'tenant-settings', TenantSettingsViewSet, basename='tenant-settings')
api_router.register(r'tenant-billing', TenantBillingViewSet, basename='tenant-billing')
api_router.register(r'tenant-invoices', TenantInvoiceViewSet, basename='tenant-invoices')
api_router.register(r'tenant-audit-logs', TenantAuditLogViewSet, basename='tenant-audit-logs')

# Admin Router Configuration
admin_router = SimpleRouter()
admin_router.register(r'tenants', TenantViewSet, basename='admin-tenant')
admin_router.register(r'settings', TenantSettingsViewSet, basename='admin-settings')
admin_router.register(r'billing', TenantBillingViewSet, basename='admin-billing')
admin_router.register(r'invoices', TenantInvoiceViewSet, basename='admin-invoices')
admin_router.register(r'audit-logs', TenantAuditLogViewSet, basename='admin-audit-logs')

# Public Router Configuration
public_router = SimpleRouter()
public_router.register(r'tenant-info', TenantViewSet, basename='public-tenant')

# WebSocket URL patterns
websocket_urlpatterns = [
    re_path(r'ws/tenants/(?P<tenant_slug>[\w-]+)/notifications/$', 
            TenantNotificationConsumer.as_asgi()),
    re_path(r'ws/tenants/(?P<tenant_slug>[\w-]+)/admin/$', 
            TenantAdminConsumer.as_asgi()),
    re_path(r'ws/tenants/(?P<tenant_slug>[\w-]+)/support/$', 
            TenantSupportConsumer.as_asgi()),
]

# API Documentation URLs
api_docs_patterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Health Check URLs
health_patterns = [
    path('health/', health_check, name='tenant-health-check'),
    path('health/detailed/', detailed_health_check, name='detailed-health-check'),
]

# File Upload URLs
upload_patterns = [
    path('upload/', TenantAttachmentUploadView.as_view(), name='tenant-upload'),
    path('uploads/', TenantAttachmentListView.as_view(), name='tenant-uploads'),
    path('uploads/<uuid:file_id>/', TenantAttachmentDeleteView.as_view(), name='tenant-upload-delete'),
]

# Public API URLs
public_patterns = [
    # React Native App endpoints
    path('app/tenant/', public_tenant_info, name='public-tenant-info'),
    path('app/features/', public_tenant_features, name='public-tenant-features'),
    path('app/config/', public_app_config, name='public-app-config'),
    
    # Public tenant endpoints
    path('public/<slug:tenant_slug>/', public_tenant_details, name='public-tenant-details'),
    path('public/<slug:tenant_slug>/branding/', public_tenant_branding, name='public-tenant-branding'),
    path('public/<slug:tenant_slug>/features/', public_tenant_features_list, name='public-tenant-features'),
    
    # Webhook endpoints
    path('webhook/<slug:tenant_slug>/', tenant_webhook_handler, name='tenant-webhook'),
    path('webhook/<slug:tenant_slug>/stripe/', stripe_webhook_handler, name='stripe-webhook'),
    path('webhook/<slug:tenant_slug>/paypal/', paypal_webhook_handler, name='paypal-webhook'),
]

# Admin URLs
admin_patterns = [
    path('admin/', include(admin_router.urls)),
    path('admin/dashboard/', admin_dashboard, name='admin-dashboard'),
    path('admin/statistics/', admin_statistics, name='admin-statistics'),
    path('admin/reports/', admin_reports, name='admin-reports'),
    path('admin/maintenance/', admin_maintenance, name='admin-maintenance'),
]

# Utility URLs
utility_patterns = [
    path('utils/validate-domain/', validate_domain, name='validate-domain'),
    path('utils/check-availability/', check_availability, name='check-availability'),
    path('utils/generate-slug/', generate_slug, name='generate-slug'),
    path('utils/estimate-cost/', estimate_cost, name='estimate-cost'),
]

# Feature Toggle URLs
feature_patterns = [
    path('features/<slug:tenant_slug>/', tenant_feature_toggles, name='tenant-features'),
    path('features/<slug:tenant_slug>/toggle/', toggle_tenant_feature, name='toggle-tenant-feature'),
    path('features/<slug:tenant_slug>/status/', feature_status, name='feature-status'),
]

# Integration URLs
integration_patterns = [
    path('integrations/stripe/', stripe_integration, name='stripe-integration'),
    path('integrations/paypal/', paypal_integration, name='paypal-integration'),
    path('integrations/analytics/', analytics_integration, name='analytics-integration'),
    path('integrations/notifications/', notification_integration, name='notification-integration'),
]

# Main URL Configuration
urlpatterns = [
    # API endpoints
    path('api/v1/', include(api_router.urls)),
    path('api/v1/', include(format_suffix_patterns(api_router.urls))),
    
    # File uploads
    path('api/v1/', include(upload_patterns)),
    
    # Public APIs
    path('api/v1/public/', include(public_patterns)),
    
    # Feature toggles
    path('api/v1/', include(feature_patterns)),
    
    # Utility endpoints
    path('api/v1/', include(utility_patterns)),
    
    # Integration endpoints
    path('api/v1/', include(integration_patterns)),
    
    # Admin endpoints
    path('api/v1/', include(admin_patterns)),
    
    # API documentation
    path('', include(api_docs_patterns)),
    
    # Health checks
    path('', include(health_patterns)),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='tenants/about.html'), name='tenant-about'),
    path('privacy/', TemplateView.as_view(template_name='tenants/privacy.html'), name='tenant-privacy'),
    path('terms/', TemplateView.as_view(template_name='tenants/terms.html'), name='tenant-terms'),
    path('support/', TemplateView.as_view(template_name='tenants/support.html'), name='tenant-support'),
    
    # Fallback URLs
    path('tenant/<slug:tenant_slug>/', tenant_fallback_view, name='tenant-fallback'),
    path('app/', app_fallback_view, name='app-fallback'),
]

# URL Configuration by Environment
def get_urlpatterns():
    """Get URL patterns based on environment."""
    patterns = urlpatterns.copy()
    
    if settings.DEBUG:
        # Add debug-only patterns
        patterns += [
            path('debug/tenant-info/', debug_tenant_info, name='debug-tenant-info'),
            path('debug/cache-info/', debug_cache_info, name='debug-cache-info'),
            path('debug/system-info/', debug_system_info, name='debug-system-info'),
        ]
    
    if getattr(settings, 'ENABLE_ADMIN_PANEL', True):
        # Add admin panel URLs
        patterns += [
            path('admin-panel/', TemplateView.as_view(template_name='tenants/admin_panel.html'), name='admin-panel'),
        ]
    
    return patterns

# URL Helper Functions
def tenant_url(tenant_slug, path=''):
    """Generate tenant-specific URL."""
    return f'/tenant/{tenant_slug}/{path}'

def api_url(version='v1', path=''):
    """Generate API URL."""
    return f'/api/{version}/{path}'

def websocket_url(tenant_slug, endpoint='notifications'):
    """Generate WebSocket URL."""
    protocol = 'wss' if not settings.DEBUG else 'ws'
    host = getattr(settings, 'WEBSOCKET_HOST', 'localhost:8000')
    return f'{protocol}://{host}/ws/tenants/{tenant_slug}/{endpoint}/'

# URL Validators
def validate_tenant_url(url):
    """Validate tenant URL format."""
    import re
    pattern = r'^/tenant/[\w-]+(/.*)?$'
    return bool(re.match(pattern, url))

def validate_api_url(url):
    """Validate API URL format."""
    import re
    pattern = r'^/api/v[\d\.]+(/.*)?$'
    return bool(re.match(pattern, url))

# URL Generators
class TenantURLGenerator:
    """Utility class for generating tenant URLs."""
    
    @staticmethod
    def dashboard_url(tenant_slug):
        """Generate dashboard URL."""
        return tenant_url(tenant_slug, 'dashboard/')
    
    @staticmethod
    def settings_url(tenant_slug):
        """Generate settings URL."""
        return tenant_url(tenant_slug, 'settings/')
    
    @staticmethod
    def billing_url(tenant_slug):
        """Generate billing URL."""
        return tenant_url(tenant_slug, 'billing/')
    
    @staticmethod
    def users_url(tenant_slug):
        """Generate users URL."""
        return tenant_url(tenant_slug, 'users/')
    
    @staticmethod
    def analytics_url(tenant_slug):
        """Generate analytics URL."""
        return tenant_url(tenant_slug, 'analytics/')
    
    @staticmethod
    def support_url(tenant_slug):
        """Generate support URL."""
        return tenant_url(tenant_slug, 'support/')
    
    @staticmethod
    def api_tenant_url(tenant_id):
        """Generate API tenant URL."""
        return api_url(path=f'tenants/{tenant_id}/')
    
    @staticmethod
    def api_settings_url(tenant_id):
        """Generate API settings URL."""
        return api_url(path=f'tenant-settings/{tenant_id}/')
    
    @staticmethod
    def api_billing_url(tenant_id):
        """Generate API billing URL."""
        return api_url(path=f'tenant-billing/{tenant_id}/')
    
    @staticmethod
    def websocket_notifications_url(tenant_slug):
        """Generate WebSocket notifications URL."""
        return websocket_url(tenant_slug, 'notifications')
    
    @staticmethod
    def websocket_admin_url(tenant_slug):
        """Generate WebSocket admin URL."""
        return websocket_url(tenant_slug, 'admin')
    
    @staticmethod
    def websocket_support_url(tenant_slug):
        """Generate WebSocket support URL."""
        return websocket_url(tenant_slug, 'support')


# View Functions for URL Patterns
def health_check(request):
    """Simple health check endpoint."""
    from django.utils import timezone
    return HttpResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'tenant-management',
        'version': '2.0.0'
    }, content_type='application/json')

def detailed_health_check(request):
    """Detailed health check with system information."""
    from django.utils import timezone
    from django.db import connection
    from django.core.cache import cache
    
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    
    try:
        # Check cache
        cache.set('health_check', 'ok', 10)
        cache_status = 'healthy' if cache.get('health_check') == 'ok' else 'unhealthy'
    except Exception:
        cache_status = 'unhealthy'
    
    return HttpResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'tenant-management',
        'version': '2.0.0',
        'components': {
            'database': db_status,
            'cache': cache_status,
        }
    }, content_type='application/json')

def public_tenant_info(request):
    """Public tenant information endpoint."""
    # This would be implemented in views
    return HttpResponse({'message': 'Public tenant info endpoint'})

def public_tenant_features(request):
    """Public tenant features endpoint."""
    return HttpResponse({'message': 'Public tenant features endpoint'})

def public_app_config(request):
    """Public app configuration endpoint."""
    return HttpResponse({'message': 'Public app config endpoint'})

def public_tenant_details(request, tenant_slug):
    """Public tenant details endpoint."""
    return HttpResponse({'message': f'Public tenant details for {tenant_slug}'})

def public_tenant_branding(request, tenant_slug):
    """Public tenant branding endpoint."""
    return HttpResponse({'message': f'Public tenant branding for {tenant_slug}'})

def public_tenant_features_list(request, tenant_slug):
    """Public tenant features list endpoint."""
    return HttpResponse({'message': f'Public tenant features for {tenant_slug}'})

def tenant_webhook_handler(request, tenant_slug):
    """Generic webhook handler."""
    return HttpResponse({'message': f'Webhook handler for {tenant_slug}'})

def stripe_webhook_handler(request, tenant_slug):
    """Stripe webhook handler."""
    return HttpResponse({'message': f'Stripe webhook for {tenant_slug}'})

def paypal_webhook_handler(request, tenant_slug):
    """PayPal webhook handler."""
    return HttpResponse({'message': f'PayPal webhook for {tenant_slug}'})

def admin_dashboard(request):
    """Admin dashboard endpoint."""
    return HttpResponse({'message': 'Admin dashboard'})

def admin_statistics(request):
    """Admin statistics endpoint."""
    return HttpResponse({'message': 'Admin statistics'})

def admin_reports(request):
    """Admin reports endpoint."""
    return HttpResponse({'message': 'Admin reports'})

def admin_maintenance(request):
    """Admin maintenance endpoint."""
    return HttpResponse({'message': 'Admin maintenance'})

def validate_domain(request):
    """Domain validation endpoint."""
    return HttpResponse({'message': 'Domain validation'})

def check_availability(request):
    """Availability check endpoint."""
    return HttpResponse({'message': 'Availability check'})

def generate_slug(request):
    """Slug generation endpoint."""
    return HttpResponse({'message': 'Slug generation'})

def estimate_cost(request):
    """Cost estimation endpoint."""
    return HttpResponse({'message': 'Cost estimation'})

def tenant_feature_toggles(request, tenant_slug):
    """Tenant feature toggles endpoint."""
    return HttpResponse({'message': f'Feature toggles for {tenant_slug}'})

def toggle_tenant_feature(request, tenant_slug):
    """Toggle tenant feature endpoint."""
    return HttpResponse({'message': f'Toggle feature for {tenant_slug}'})

def feature_status(request, tenant_slug):
    """Feature status endpoint."""
    return HttpResponse({'message': f'Feature status for {tenant_slug}'})

def stripe_integration(request):
    """Stripe integration endpoint."""
    return HttpResponse({'message': 'Stripe integration'})

def paypal_integration(request):
    """PayPal integration endpoint."""
    return HttpResponse({'message': 'PayPal integration'})

def analytics_integration(request):
    """Analytics integration endpoint."""
    return HttpResponse({'message': 'Analytics integration'})

def notification_integration(request):
    """Notification integration endpoint."""
    return HttpResponse({'message': 'Notification integration'})

def tenant_fallback_view(request, tenant_slug):
    """Fallback view for tenant URLs."""
    return HttpResponse({'message': f'Tenant fallback for {tenant_slug}'})

def app_fallback_view(request):
    """Fallback view for app URLs."""
    return HttpResponse({'message': 'App fallback'})

# Debug Views
def debug_tenant_info(request):
    """Debug tenant information."""
    if not settings.DEBUG:
        return HttpResponse({'error': 'Debug mode disabled'}, status=403)
    
    return HttpResponse({'message': 'Debug tenant info'})

def debug_cache_info(request):
    """Debug cache information."""
    if not settings.DEBUG:
        return HttpResponse({'error': 'Debug mode disabled'}, status=403)
    
    return HttpResponse({'message': 'Debug cache info'})

def debug_system_info(request):
    """Debug system information."""
    if not settings.DEBUG:
        return HttpResponse({'error': 'Debug mode disabled'}, status=403)
    
    return HttpResponse({'message': 'Debug system info'})

# URL Configuration Export
urlpatterns = get_urlpatterns()

# WebSocket URL Patterns Export
app_name = 'tenants'
