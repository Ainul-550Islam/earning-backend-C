"""
Tenant Serializers Module

This module contains all serializer classes for the tenant management system,
including serializers for models, requests, and responses.
"""

from .core import (
    TenantSerializer,
    TenantCreateSerializer,
    TenantUpdateSerializer,
    TenantSettingsSerializer,
    TenantBillingSerializer,
    TenantInvoiceSerializer,
    TenantInvoiceCreateSerializer,
)

from .plan import (
    PlanSerializer,
    PlanCreateSerializer,
    PlanUpdateSerializer,
    PlanFeatureSerializer,
    PlanUpgradeSerializer,
    PlanUsageSerializer,
    PlanQuotaSerializer,
)

from .branding import (
    TenantBrandingSerializer,
    TenantDomainSerializer,
    TenantDomainCreateSerializer,
    TenantEmailSerializer,
    TenantEmailUpdateSerializer,
    TenantSocialLinkSerializer,
    TenantSocialLinkCreateSerializer,
)

from .security import (
    TenantAPIKeySerializer,
    TenantAPIKeyCreateSerializer,
    TenantWebhookConfigSerializer,
    TenantWebhookConfigCreateSerializer,
    TenantIPWhitelistSerializer,
    TenantIPWhitelistCreateSerializer,
    TenantAuditLogSerializer,
)

from .onboarding import (
    TenantOnboardingSerializer,
    TenantOnboardingStepSerializer,
    TenantOnboardingStepCompleteSerializer,
    TenantTrialExtensionSerializer,
    TenantTrialExtensionCreateSerializer,
)

from .analytics import (
    TenantMetricSerializer,
    TenantHealthScoreSerializer,
    TenantFeatureFlagSerializer,
    TenantFeatureFlagCreateSerializer,
    TenantNotificationSerializer,
)

from .reseller import (
    ResellerConfigSerializer,
    ResellerConfigCreateSerializer,
    ResellerInvoiceSerializer,
)

__all__ = [
    # Core serializers
    'TenantSerializer',
    'TenantCreateSerializer',
    'TenantUpdateSerializer',
    'TenantSettingsSerializer',
    'TenantBillingSerializer',
    'TenantInvoiceSerializer',
    'TenantInvoiceCreateSerializer',
    
    # Plan serializers
    'PlanSerializer',
    'PlanCreateSerializer',
    'PlanUpdateSerializer',
    'PlanFeatureSerializer',
    'PlanUpgradeSerializer',
    'PlanUsageSerializer',
    'PlanQuotaSerializer',
    
    # Branding serializers
    'TenantBrandingSerializer',
    'TenantDomainSerializer',
    'TenantDomainCreateSerializer',
    'TenantEmailSerializer',
    'TenantEmailUpdateSerializer',
    'TenantSocialLinkSerializer',
    'TenantSocialLinkCreateSerializer',
    
    # Security serializers
    'TenantAPIKeySerializer',
    'TenantAPIKeyCreateSerializer',
    'TenantWebhookConfigSerializer',
    'TenantWebhookConfigCreateSerializer',
    'TenantIPWhitelistSerializer',
    'TenantIPWhitelistCreateSerializer',
    'TenantAuditLogSerializer',
    
    # Onboarding serializers
    'TenantOnboardingSerializer',
    'TenantOnboardingStepSerializer',
    'TenantOnboardingStepCompleteSerializer',
    'TenantTrialExtensionSerializer',
    'TenantTrialExtensionCreateSerializer',
    
    # Analytics serializers
    'TenantMetricSerializer',
    'TenantHealthScoreSerializer',
    'TenantFeatureFlagSerializer',
    'TenantFeatureFlagCreateSerializer',
    'TenantNotificationSerializer',
    
    # Reseller serializers
    'ResellerConfigSerializer',
    'ResellerConfigCreateSerializer',
    'ResellerInvoiceSerializer',
]
