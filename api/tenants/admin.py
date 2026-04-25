"""
Tenant Admin Module

This module contains Django admin classes for the tenant management system,
including admin interfaces for models, custom actions, and admin utilities.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone

# Import all admin classes from admin directory
from .admin.core import (
    TenantAdmin,
    TenantSettingsAdmin,
    TenantBillingAdmin,
    TenantInvoiceAdmin,
)

from .admin.plan import (
    PlanAdmin,
    PlanFeatureAdmin,
    PlanUpgradeAdmin,
    PlanUsageAdmin,
    PlanQuotaAdmin,
)

from .admin.branding import (
    TenantBrandingAdmin,
    TenantDomainAdmin,
    TenantEmailAdmin,
    TenantSocialLinkAdmin,
)

from .admin.security import (
    TenantAPIKeyAdmin,
    TenantWebhookConfigAdmin,
    TenantIPWhitelistAdmin,
    TenantAuditLogAdmin,
)

from .admin.onboarding import (
    TenantOnboardingAdmin,
    TenantOnboardingStepAdmin,
    TenantTrialExtensionAdmin,
)

from .admin.analytics import (
    TenantMetricAdmin,
    TenantHealthScoreAdmin,
    TenantFeatureFlagAdmin,
    TenantNotificationAdmin,
)

from .admin.reseller import (
    ResellerConfigAdmin,
    ResellerInvoiceAdmin,
)

# Register all admin classes
admin.site.register(Tenant, TenantAdmin)
admin.site.register(TenantSettings, TenantSettingsAdmin)
admin.site.register(TenantBilling, TenantBillingAdmin)
admin.site.register(TenantInvoice, TenantInvoiceAdmin)

# Plan admin classes
admin.site.register(Plan, PlanAdmin)
admin.site.register(PlanFeature, PlanFeatureAdmin)
admin.site.register(PlanUpgrade, PlanUpgradeAdmin)
admin.site.register(PlanUsage, PlanUsageAdmin)
admin.site.register(PlanQuota, PlanQuotaAdmin)

# Branding admin classes
admin.site.register(TenantBranding, TenantBrandingAdmin)
admin.site.register(TenantDomain, TenantDomainAdmin)
admin.site.register(TenantEmail, TenantEmailAdmin)
admin.site.register(TenantSocialLink, TenantSocialLinkAdmin)

# Security admin classes
admin.site.register(TenantAPIKey, TenantAPIKeyAdmin)
admin.site.register(TenantWebhookConfig, TenantWebhookConfigAdmin)
admin.site.register(TenantIPWhitelist, TenantIPWhitelistAdmin)
admin.site.register(TenantAuditLog, TenantAuditLogAdmin)

# Onboarding admin classes
admin.site.register(TenantOnboarding, TenantOnboardingAdmin)
admin.site.register(TenantOnboardingStep, TenantOnboardingStepAdmin)
admin.site.register(TenantTrialExtension, TenantTrialExtensionAdmin)

# Analytics admin classes
admin.site.register(TenantMetric, TenantMetricAdmin)
admin.site.register(TenantHealthScore, TenantHealthScoreAdmin)
admin.site.register(TenantFeatureFlag, TenantFeatureFlagAdmin)
admin.site.register(TenantNotification, TenantNotificationAdmin)

# Reseller admin classes
admin.site.register(ResellerConfig, ResellerConfigAdmin)
admin.site.register(ResellerInvoice, ResellerInvoiceAdmin)

# Custom admin site configuration
class TenantAdminSite(admin.AdminSite):
    """
    Custom admin site for tenant management with enhanced features.
    """
    site_header = 'Tenant Management'
    site_title = 'Tenant Management Admin'
    index_title = 'Welcome to Tenant Management Admin'
    
    def get_urls(self):
        from django.urls import path
        from django.views.generic import TemplateView
        
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(TemplateView.as_view(template_name='admin/tenant_dashboard.html')), name='tenant-dashboard'),
            path('reports/', self.admin_view(TemplateView.as_view(template_name='admin/tenant_reports.html')), name='tenant-reports'),
        ]
        return custom_urls + urls
    
    def each_context(self, request):
        context = super().each_context(request)
        context['tenant_stats'] = self.get_tenant_statistics()
        return context
    
    def get_tenant_statistics(self):
        """Get tenant statistics for dashboard."""
        try:
            from ..models import Tenant
            from ..models.analytics import TenantMetric, TenantHealthScore
            
            stats = {
                'total_tenants': Tenant.objects.filter(is_deleted=False).count(),
                'active_tenants': Tenant.objects.filter(is_deleted=False, status='active').count(),
                'trial_tenants': Tenant.objects.filter(is_deleted=False, status='trial').count(),
                'suspended_tenants': Tenant.objects.filter(is_deleted=False, status='suspended').count(),
                'total_metrics': TenantMetric.objects.count(),
                'health_scores': TenantHealthScore.objects.count(),
            }
            
            # Calculate recent activity
            from django.utils import timezone
            from datetime import timedelta
            
            last_30_days = timezone.now() - timedelta(days=30)
            stats['recent_signups'] = Tenant.objects.filter(
                created_at__gte=last_30_days
            ).count()
            
            return stats
        except Exception:
            return {
                'total_tenants': 0,
                'active_tenants': 0,
                'trial_tenants': 0,
                'suspended_tenants': 0,
                'total_metrics': 0,
                'health_scores': 0,
                'recent_signups': 0,
            }

# Create custom admin site instance
tenant_admin_site = TenantAdminSite(name='tenant_admin')

# Register models with custom admin site
tenant_admin_site.register(Tenant, TenantAdmin)
tenant_admin_site.register(TenantSettings, TenantSettingsAdmin)
tenant_admin_site.register(TenantBilling, TenantBillingAdmin)
tenant_admin_site.register(TenantInvoice, TenantInvoiceAdmin)

# Plan admin classes
tenant_admin_site.register(Plan, PlanAdmin)
tenant_admin_site.register(PlanFeature, PlanFeatureAdmin)
tenant_admin_site.register(PlanUpgrade, PlanUpgradeAdmin)
tenant_admin_site.register(PlanUsage, PlanUsageAdmin)
tenant_admin_site.register(PlanQuota, PlanQuotaAdmin)

# Branding admin classes
tenant_admin_site.register(TenantBranding, TenantBrandingAdmin)
tenant_admin_site.register(TenantDomain, TenantDomainAdmin)
tenant_admin_site.register(TenantEmail, TenantEmailAdmin)
tenant_admin_site.register(TenantSocialLink, TenantSocialLinkAdmin)

# Security admin classes
tenant_admin_site.register(TenantAPIKey, TenantAPIKeyAdmin)
tenant_admin_site.register(TenantWebhookConfig, TenantWebhookConfigAdmin)
tenant_admin_site.register(TenantIPWhitelist, TenantIPWhitelistAdmin)
tenant_admin_site.register(TenantAuditLog, TenantAuditLogAdmin)

# Onboarding admin classes
tenant_admin_site.register(TenantOnboarding, TenantOnboardingAdmin)
tenant_admin_site.register(TenantOnboardingStep, TenantOnboardingStepAdmin)
tenant_admin_site.register(TenantTrialExtension, TenantTrialExtensionAdmin)

# Analytics admin classes
tenant_admin_site.register(TenantMetric, TenantMetricAdmin)
tenant_admin_site.register(TenantHealthScore, TenantHealthScoreAdmin)
tenant_admin_site.register(TenantFeatureFlag, TenantFeatureFlagAdmin)
tenant_admin_site.register(TenantNotification, TenantNotificationAdmin)

# Reseller admin classes
tenant_admin_site.register(ResellerConfig, ResellerConfigAdmin)
tenant_admin_site.register(ResellerInvoice, ResellerInvoiceAdmin)


def _force_register_tenants():
    """
    Force register tenant admin classes with the modern admin site.
    This function ensures compatibility with existing admin panels.
    """
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        
        admin_classes = [
            (Tenant, TenantAdmin),
            (TenantSettings, TenantSettingsAdmin),
            (TenantBilling, TenantBillingAdmin),
            (TenantInvoice, TenantInvoiceAdmin),
            (Plan, PlanAdmin),
            (PlanFeature, PlanFeatureAdmin),
            (PlanUpgrade, PlanUpgradeAdmin),
            (PlanUsage, PlanUsageAdmin),
            (PlanQuota, PlanQuotaAdmin),
            (TenantBranding, TenantBrandingAdmin),
            (TenantDomain, TenantDomainAdmin),
            (TenantEmail, TenantEmailAdmin),
            (TenantSocialLink, TenantSocialLinkAdmin),
            (TenantAPIKey, TenantAPIKeyAdmin),
            (TenantWebhookConfig, TenantWebhookConfigAdmin),
            (TenantIPWhitelist, TenantIPWhitelistAdmin),
            (TenantAuditLog, TenantAuditLogAdmin),
            (TenantOnboarding, TenantOnboardingAdmin),
            (TenantOnboardingStep, TenantOnboardingStepAdmin),
            (TenantTrialExtension, TenantTrialExtensionAdmin),
            (TenantMetric, TenantMetricAdmin),
            (TenantHealthScore, TenantHealthScoreAdmin),
            (TenantFeatureFlag, TenantFeatureFlagAdmin),
            (TenantNotification, TenantNotificationAdmin),
            (ResellerConfig, ResellerConfigAdmin),
            (ResellerInvoice, ResellerInvoiceAdmin),
        ]
        
        registered = 0
        for model, model_admin in admin_classes:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                print(f"[WARN] Failed to register {model.__name__}: {ex}")
        
        print(f"[OK] Tenants registered {registered} models with modern admin site")
        
    except Exception as e:
        print(f"[WARN] Failed to register tenants with modern admin site: {e}")


# Auto-register with modern admin site on import
try:
    _force_register_tenants()
except Exception as e:
    print(f"[WARN] Auto-registration failed: {e}")


# Export admin classes for external use
__all__ = [
    # Core admin classes
    'TenantAdmin',
    'TenantSettingsAdmin',
    'TenantBillingAdmin',
    'TenantInvoiceAdmin',
    
    # Plan admin classes
    'PlanAdmin',
    'PlanFeatureAdmin',
    'PlanUpgradeAdmin',
    'PlanUsageAdmin',
    'PlanQuotaAdmin',
    
    # Branding admin classes
    'TenantBrandingAdmin',
    'TenantDomainAdmin',
    'TenantEmailAdmin',
    'TenantSocialLinkAdmin',
    
    # Security admin classes
    'TenantAPIKeyAdmin',
    'TenantWebhookConfigAdmin',
    'TenantIPWhitelistAdmin',
    'TenantAuditLogAdmin',
    
    # Onboarding admin classes
    'TenantOnboardingAdmin',
    'TenantOnboardingStepAdmin',
    'TenantTrialExtensionAdmin',
    
    # Analytics admin classes
    'TenantMetricAdmin',
    'TenantHealthScoreAdmin',
    'TenantFeatureFlagAdmin',
    'TenantNotificationAdmin',
    
    # Reseller admin classes
    'ResellerConfigAdmin',
    'ResellerInvoiceAdmin',
    
    # Custom admin site
    'tenant_admin_site',
]
