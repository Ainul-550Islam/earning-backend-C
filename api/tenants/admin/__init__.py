"""
Tenant Admin Module

This module contains all Django admin classes for the tenant management system,
including admin interfaces for models, custom actions, and admin utilities.
"""

from .core import (
    TenantAdmin,
    TenantSettingsAdmin,
    TenantBillingAdmin,
    TenantInvoiceAdmin,
)

from .plan import (
    PlanAdmin,
    PlanFeatureAdmin,
    PlanUpgradeAdmin,
    PlanUsageAdmin,
    PlanQuotaAdmin,
)

from .branding import (
    TenantBrandingAdmin,
    TenantDomainAdmin,
    TenantEmailAdmin,
    TenantSocialLinkAdmin,
)

from .security import (
    TenantAPIKeyAdmin,
    TenantWebhookConfigAdmin,
    TenantIPWhitelistAdmin,
    TenantAuditLogAdmin,
)

from .onboarding import (
    TenantOnboardingAdmin,
    TenantOnboardingStepAdmin,
    TenantTrialExtensionAdmin,
)

from .analytics import (
    TenantMetricAdmin,
    TenantHealthScoreAdmin,
    TenantFeatureFlagAdmin,
    TenantNotificationAdmin,
)

from .reseller import (
    ResellerConfigAdmin,
    ResellerInvoiceAdmin,
)

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
]
