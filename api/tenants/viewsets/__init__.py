"""
Tenant Viewsets Module

This module contains all viewset classes for the tenant management system,
including viewsets for models, business logic, and API endpoints.
"""

from .core import (
    TenantViewSet,
    TenantSettingsViewSet,
    TenantBillingViewSet,
    TenantInvoiceViewSet,
)

from .plan import (
    PlanViewSet,
    PlanFeatureViewSet,
    PlanUpgradeViewSet,
    PlanUsageViewSet,
    PlanQuotaViewSet,
)

from .branding import (
    TenantBrandingViewSet,
    TenantDomainViewSet,
    TenantEmailViewSet,
    TenantSocialLinkViewSet,
)

from .security import (
    TenantAPIKeyViewSet,
    TenantWebhookConfigViewSet,
    TenantIPWhitelistViewSet,
    TenantAuditLogViewSet,
)

from .onboarding import (
    TenantOnboardingViewSet,
    TenantOnboardingStepViewSet,
    TenantTrialExtensionViewSet,
)

from .analytics import (
    TenantMetricViewSet,
    TenantHealthScoreViewSet,
    TenantFeatureFlagViewSet,
    TenantNotificationViewSet,
)

from .reseller import (
    ResellerConfigViewSet,
    ResellerInvoiceViewSet,
)

__all__ = [
    # Core viewsets
    'TenantViewSet',
    'TenantSettingsViewSet',
    'TenantBillingViewSet',
    'TenantInvoiceViewSet',
    
    # Plan viewsets
    'PlanViewSet',
    'PlanFeatureViewSet',
    'PlanUpgradeViewSet',
    'PlanUsageViewSet',
    'PlanQuotaViewSet',
    
    # Branding viewsets
    'TenantBrandingViewSet',
    'TenantDomainViewSet',
    'TenantEmailViewSet',
    'TenantSocialLinkViewSet',
    
    # Security viewsets
    'TenantAPIKeyViewSet',
    'TenantWebhookConfigViewSet',
    'TenantIPWhitelistViewSet',
    'TenantAuditLogViewSet',
    
    # Onboarding viewsets
    'TenantOnboardingViewSet',
    'TenantOnboardingStepViewSet',
    'TenantTrialExtensionViewSet',
    
    # Analytics viewsets
    'TenantMetricViewSet',
    'TenantHealthScoreViewSet',
    'TenantFeatureFlagViewSet',
    'TenantNotificationViewSet',
    
    # Reseller viewsets
    'ResellerConfigViewSet',
    'ResellerInvoiceViewSet',
]
