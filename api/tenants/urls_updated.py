"""
Tenant URLs - Updated Version with Improved Structure

This module contains comprehensive URL routing for tenant management
with improved organization, security, and API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

# Import existing views
from .views import (
    TenantViewSet, TenantSettingsViewSet, TenantBillingViewSet, TenantInvoiceViewSet
)

# Import improved views if available
try:
    from .views_improved import (
        TenantViewSet as ImprovedTenantViewSet,
        TenantSettingsViewSet as ImprovedTenantSettingsViewSet,
        TenantBillingViewSet as ImprovedTenantBillingViewSet,
        TenantInvoiceViewSet as ImprovedTenantInvoiceViewSet,
    )
    VIEWS_AVAILABLE = True
except ImportError:
    VIEWS_AVAILABLE = False

# Create routers for different API versions
v1_router = SimpleRouter()
v2_router = SimpleRouter()

# API v1 routes (original views)
v1_router.register(r'tenants', TenantViewSet, basename='tenant')
v1_router.register(r'tenant-settings', TenantSettingsViewSet, basename='tenant-settings')
v1_router.register(r'tenant-billing', TenantBillingViewSet, basename='tenant-billing')
v1_router.register(r'tenant-invoices', TenantInvoiceViewSet, basename='tenant-invoices')

# API v2 routes (improved views) - only if available
if VIEWS_AVAILABLE:
    v2_router.register(r'tenants', ImprovedTenantViewSet, basename='v2-tenant')
    v2_router.register(r'tenant-settings', ImprovedTenantSettingsViewSet, basename='v2-tenant-settings')
    v2_router.register(r'tenant-billing', ImprovedTenantBillingViewSet, basename='v2-tenant-billing')
    v2_router.register(r'tenant-invoices', ImprovedTenantInvoiceViewSet, basename='v2-tenant-invoices')

# Public API endpoints (no authentication required)
public_patterns = [
    # Public tenant info for React Native apps
    path('public/tenant/<slug:tenant_slug>/', public_tenant_info, name='public-tenant-info'),
    path('public/tenant/<slug:tenant_slug>/branding/', public_tenant_branding, name='public-tenant-branding'),
    path('public/tenant/<slug:tenant_slug>/features/', public_tenant_features, name='public-tenant-features'),
    path('public/tenant/<slug:tenant_slug>/config/', public_tenant_config, name='public-tenant-config'),
    
    # Webhook endpoints
    path('webhook/<slug:tenant_slug>/', tenant_webhook_handler, name='tenant-webhook'),
    path('webhook/<slug:tenant_slug>/stripe/', stripe_webhook_handler, name='stripe-webhook'),
    path('webhook/<slug:tenant_slug>/paypal/', paypal_webhook_handler, name='paypal-webhook'),
]

# Admin API endpoints (admin only)
admin_patterns = [
    # Admin dashboard
    path('admin/dashboard/', admin_dashboard, name='admin-dashboard'),
    path('admin/statistics/', admin_statistics, name='admin-statistics'),
    path('admin/reports/', admin_reports, name='admin-reports'),
    path('admin/maintenance/', admin_maintenance, name='admin-maintenance'),
    
    # Bulk operations
    path('admin/tenants/bulk-suspend/', bulk_suspend_tenants, name='bulk-suspend-tenants'),
    path('admin/tenants/bulk-unsuspend/', bulk_unsuspend_tenants, name='bulk-unsuspend-tenants'),
    path('admin/tenants/bulk-export/', bulk_export_tenants, name='bulk-export-tenants'),
]

# Utility endpoints
utility_patterns = [
    # Validation and utilities
    path('utils/validate-domain/', validate_domain, name='validate-domain'),
    path('utils/check-availability/', check_availability, name='check-availability'),
    path('utils/generate-slug/', generate_slug, name='generate-slug'),
    path('utils/estimate-cost/', estimate_cost, name='estimate-cost'),
    path('utils/health-check/', health_check, name='health-check'),
]

# Main URL configuration
urlpatterns = [
    # API versioning
    path('api/v1/', include(v1_router.urls)),
    
    # API v2 (improved views) - only if available
    path('api/v2/', include(v2_router.urls)) if VIEWS_AVAILABLE else path('', include([])),
    
    # Public endpoints
    path('api/public/', include(public_patterns)),
    
    # Admin endpoints
    path('api/admin/', include(admin_patterns)),
    
    # Utility endpoints
    path('api/utils/', include(utility_patterns)),
    
    # File upload endpoints
    path('api/upload/', TenantAttachmentUploadView.as_view(), name='tenant-upload'),
    path('api/uploads/', TenantAttachmentListView.as_view(), name='tenant-uploads'),
    path('api/uploads/<uuid:file_id>/', TenantAttachmentDeleteView.as_view(), name='tenant-upload-delete'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='tenants/about.html'), name='tenant-about'),
    path('privacy/', TemplateView.as_view(template_name='tenants/privacy.html'), name='tenant-privacy'),
    path('terms/', TemplateView.as_view(template_name='tenants/terms.html'), name='tenant-terms'),
    path('support/', TemplateView.as_view(template_name='tenants/support.html'), name='tenant-support'),
    
    # Health check
    path('health/', health_check, name='tenant-health'),
]

# View functions for URL patterns
@require_http_methods(["GET"])
def public_tenant_info(request, tenant_slug):
    """Public tenant information endpoint."""
    try:
        from .models import Tenant
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        
        data = {
            'name': tenant.name,
            'slug': tenant.slug,
            'domain': tenant.domain,
            'primary_color': tenant.primary_color,
            'secondary_color': tenant.secondary_color,
            'logo_url': tenant.logo.url if tenant.logo else None,
            'plan': tenant.plan,
            'created_at': tenant.created_at,
        }
        
        return JsonResponse(data)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["GET"])
def public_tenant_branding(request, tenant_slug):
    """Public tenant branding information."""
    try:
        from .models import Tenant, TenantSettings
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        settings = TenantSettings.objects.get(tenant=tenant)
        
        data = {
            'app_name': settings.app_name,
            'primary_color': tenant.primary_color,
            'secondary_color': tenant.secondary_color,
            'logo_url': tenant.logo.url if tenant.logo else None,
            'favicon_url': None,  # Add if you have favicon field
            'custom_css': getattr(settings, 'custom_css', ''),
            'custom_js': getattr(settings, 'custom_js', ''),
        }
        
        return JsonResponse(data)
    except (Tenant.DoesNotExist, TenantSettings.DoesNotExist):
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["GET"])
def public_tenant_features(request, tenant_slug):
    """Public tenant features information."""
    try:
        from .models import Tenant, TenantSettings
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        settings = TenantSettings.objects.get(tenant=tenant)
        
        data = {
            'enable_referral': settings.enable_referral,
            'enable_offerwall': settings.enable_offerwall,
            'enable_kyc': settings.enable_kyc,
            'enable_leaderboard': settings.enable_leaderboard,
            'enable_chat': settings.enable_chat,
            'enable_push_notifications': settings.enable_push_notifications,
            'min_withdrawal': float(settings.min_withdrawal),
            'withdrawal_fee_percent': float(settings.withdrawal_fee_percent),
        }
        
        return JsonResponse(data)
    except (Tenant.DoesNotExist, TenantSettings.DoesNotExist):
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["GET"])
def public_tenant_config(request, tenant_slug):
    """Public tenant configuration for React Native apps."""
    try:
        from .models import Tenant, TenantSettings
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        settings = TenantSettings.objects.get(tenant=tenant)
        
        data = {
            'app_name': settings.app_name,
            'app_version': getattr(settings, 'app_version', '1.0.0'),
            'android_package_name': settings.android_package_name,
            'ios_bundle_id': settings.ios_bundle_id,
            'support_email': settings.support_email,
            'privacy_policy_url': settings.privacy_policy_url,
            'terms_url': settings.terms_url,
            'features': {
                'enable_referral': settings.enable_referral,
                'enable_offerwall': settings.enable_offerwall,
                'enable_kyc': settings.enable_kyc,
                'enable_leaderboard': settings.enable_leaderboard,
                'enable_chat': settings.enable_chat,
                'enable_push_notifications': settings.enable_push_notifications,
            },
            'payout': {
                'min_withdrawal': float(settings.min_withdrawal),
                'withdrawal_fee_percent': float(settings.withdrawal_fee_percent),
            }
        }
        
        return JsonResponse(data)
    except (Tenant.DoesNotExist, TenantSettings.DoesNotExist):
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["POST"])
def tenant_webhook_handler(request, tenant_slug):
    """Generic webhook handler for tenants."""
    try:
        from .models import Tenant
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        
        # Basic webhook validation
        if 'X-Tenant-Secret' in request.headers:
            if request.headers['X-Tenant-Secret'] != str(tenant.api_key):
                return JsonResponse({'error': 'Invalid tenant secret'}, status=401)
        
        # Process webhook data (implement your logic here)
        data = {
            'status': 'received',
            'tenant': tenant_slug,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["POST"])
def stripe_webhook_handler(request, tenant_slug):
    """Stripe webhook handler."""
    try:
        from .models import Tenant
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        
        # Implement Stripe webhook processing
        data = {
            'status': 'stripe_webhook_received',
            'tenant': tenant_slug,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["POST"])
def paypal_webhook_handler(request, tenant_slug):
    """PayPal webhook handler."""
    try:
        from .models import Tenant
        tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        
        # Implement PayPal webhook processing
        data = {
            'status': 'paypal_webhook_received',
            'tenant': tenant_slug,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)

@require_http_methods(["GET", "POST"])
def admin_dashboard(request):
    """Admin dashboard endpoint."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    from .models import Tenant
    stats = {
        'total_tenants': Tenant.objects.count(),
        'active_tenants': Tenant.objects.filter(is_active=True).count(),
        'trial_tenants': Tenant.objects.filter(plan='trial').count(),
        'pro_tenants': Tenant.objects.filter(plan='pro').count(),
        'enterprise_tenants': Tenant.objects.filter(plan='enterprise').count(),
    }
    
    return JsonResponse(stats)

@require_http_methods(["GET"])
def admin_statistics(request):
    """Admin statistics endpoint."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement statistics logic
    return JsonResponse({'message': 'Admin statistics endpoint'})

@require_http_methods(["GET"])
def admin_reports(request):
    """Admin reports endpoint."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement reports logic
    return JsonResponse({'message': 'Admin reports endpoint'})

@require_http_methods(["GET", "POST"])
def admin_maintenance(request):
    """Admin maintenance endpoint."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement maintenance logic
    return JsonResponse({'message': 'Admin maintenance endpoint'})

@require_http_methods(["POST"])
def bulk_suspend_tenants(request):
    """Bulk suspend tenants."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement bulk suspend logic
    return JsonResponse({'message': 'Bulk suspend tenants'})

@require_http_methods(["POST"])
def bulk_unsuspend_tenants(request):
    """Bulk unsuspend tenants."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement bulk unsuspend logic
    return JsonResponse({'message': 'Bulk unsuspend tenants'})

@require_http_methods(["POST"])
def bulk_export_tenants(request):
    """Bulk export tenants."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Admin access required'}, status=403)
    
    # Implement bulk export logic
    return JsonResponse({'message': 'Bulk export tenants'})

@require_http_methods(["POST"])
def validate_domain(request):
    """Validate domain availability."""
    domain = request.POST.get('domain')
    if not domain:
        return JsonResponse({'error': 'Domain required'}, status=400)
    
    from .models import Tenant
    exists = Tenant.objects.filter(domain=domain).exists()
    
    return JsonResponse({
        'domain': domain,
        'available': not exists,
        'message': 'Domain is available' if not exists else 'Domain is already taken'
    })

@require_http_methods(["POST"])
def check_availability(request):
    """Check slug availability."""
    slug = request.POST.get('slug')
    if not slug:
        return JsonResponse({'error': 'Slug required'}, status=400)
    
    from .models import Tenant
    exists = Tenant.objects.filter(slug=slug).exists()
    
    return JsonResponse({
        'slug': slug,
        'available': not exists,
        'message': 'Slug is available' if not exists else 'Slug is already taken'
    })

@require_http_methods(["POST"])
def generate_slug(request):
    """Generate slug from name."""
    name = request.POST.get('name')
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    
    from django.utils.text import slugify
    slug = slugify(name)
    
    # Ensure uniqueness
    from .models import Tenant
    original_slug = slug
    counter = 1
    while Tenant.objects.filter(slug=slug).exists():
        slug = f"{original_slug}-{counter}"
        counter += 1
    
    return JsonResponse({
        'name': name,
        'slug': slug,
        'original_slug': original_slug,
    })

@require_http_methods(["POST"])
def estimate_cost(request):
    """Estimate tenant cost."""
    plan = request.POST.get('plan', 'basic')
    users = int(request.POST.get('users', 100))
    
    # Simple cost estimation logic
    pricing = {
        'basic': {'monthly': 0, 'yearly': 0},
        'pro': {'monthly': 29, 'yearly': 290},
        'enterprise': {'monthly': 99, 'yearly': 990},
    }
    
    base_cost = pricing.get(plan, pricing['basic'])
    user_cost = max(0, users - 100) * 0.10  # $0.10 per additional user
    
    total_monthly = base_cost['monthly'] + user_cost
    total_yearly = base_cost['yearly'] + (user_cost * 12)
    
    return JsonResponse({
        'plan': plan,
        'users': users,
        'monthly_cost': total_monthly,
        'yearly_cost': total_yearly,
        'currency': 'USD',
    })

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint."""
    from django.utils import timezone
    from django.db import connection
    
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'tenant-management',
        'version': '2.0.0',
        'database': db_status,
    })

# Import views that might not exist
try:
    from .attachment_upload_view import (
        TenantAttachmentUploadView, TenantAttachmentListView, TenantAttachmentDeleteView
    )
except ImportError:
    # Create dummy views if not available
    from django.views import View
    TenantAttachmentUploadView = TenantAttachmentListView = TenantAttachmentDeleteView = View
