"""
Tenant Models Module

This module contains all the tenant-related models for the multi-tenant application.
"""

from .core import (
    Tenant,
    TenantSettings,
    TenantBilling,
    TenantInvoice,
)

from .plan import (
    Plan,
    PlanFeature,
    PlanUpgrade,
    PlanUsage,
    PlanQuota,
)

from .branding import (
    TenantBranding,
    TenantDomain,
    TenantEmail,
    TenantSocialLink,
)

from .security import (
    TenantAPIKey,
    TenantWebhookConfig,
    TenantIPWhitelist,
    TenantAuditLog,
)

from .onboarding import (
    TenantOnboarding,
    TenantOnboardingStep,
    TenantTrialExtension,
)

from .analytics import (
    TenantMetric,
    TenantHealthScore,
    TenantFeatureFlag,
    TenantNotification,
)

from .reseller import (
    ResellerConfig,
    ResellerInvoice,
)

__all__ = [
    # Core Models
    'Tenant',
    'TenantSettings',
    'TenantBilling',
    'TenantInvoice',
    
    # Plan Models
    'Plan',
    'PlanFeature',
    'PlanUpgrade',
    'PlanUsage',
    'PlanQuota',
    
    # Branding Models
    'TenantBranding',
    'TenantDomain',
    'TenantEmail',
    'TenantSocialLink',
    
    # Security Models
    'TenantAPIKey',
    'TenantWebhookConfig',
    'TenantIPWhitelist',
    'TenantAuditLog',
    
    # Onboarding Models
    'TenantOnboarding',
    'TenantOnboardingStep',
    'TenantTrialExtension',
    
    # Analytics Models
    'TenantMetric',
    'TenantHealthScore',
    'TenantFeatureFlag',
    'TenantNotification',
    
    # Reseller Models
    'ResellerConfig',
    'ResellerInvoice',
]
