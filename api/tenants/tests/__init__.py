"""
Tenant Test Suite

This module contains comprehensive tests for the tenant management system,
including unit tests, integration tests, and test utilities.
"""

from .test_models import (
    TestTenant,
    TestTenantSettings,
    TestTenantBilling,
    TestTenantInvoice,
)

from .test_plan import (
    TestPlan,
    TestPlanFeature,
    TestPlanUpgrade,
    TestPlanUsage,
    TestPlanQuota,
)

from .test_branding import (
    TestTenantBranding,
    TestTenantDomain,
    TestTenantEmail,
    TestTenantSocialLink,
)

from .test_security import (
    TestTenantAPIKey,
    TestTenantWebhookConfig,
    TestTenantIPWhitelist,
    TestTenantAuditLog,
)

from .test_onboarding import (
    TestTenantOnboarding,
    TestTenantOnboardingStep,
    TestTenantTrialExtension,
)

from .test_analytics import (
    TestTenantMetric,
    TestTenantHealthScore,
    TestTenantFeatureFlag,
    TestTenantNotification,
)

from .test_reseller import (
    TestResellerConfig,
    TestResellerInvoice,
)

from .test_services import (
    TestTenantService,
    TestTenantProvisioningService,
    TestTenantSuspensionService,
    TestPlanService,
    TestPlanUsageService,
    TestBrandingService,
    TestDomainService,
    TestTenantBillingService,
    TestTenantEmailService,
    TestOnboardingService,
    TestTenantAuditService,
    TestTenantMetricService,
    TestFeatureFlagService,
)

from .test_viewsets import (
    TestTenantViewSet,
    TestTenantSettingsViewSet,
    TestTenantBillingViewSet,
    TestTenantInvoiceViewSet,
    TestPlanViewSet,
    TestPlanFeatureViewSet,
    TestPlanUpgradeViewSet,
    TestPlanUsageViewSet,
    TestPlanQuotaViewSet,
    TestTenantBrandingViewSet,
    TestTenantDomainViewSet,
    TestTenantEmailViewSet,
    TestTenantSocialLinkViewSet,
    TestTenantAPIKeyViewSet,
    TestTenantWebhookConfigViewSet,
    TestTenantIPWhitelistViewSet,
    TestTenantAuditLogViewSet,
    TestTenantOnboardingViewSet,
    TestTenantOnboardingStepViewSet,
    TestTenantTrialExtensionViewSet,
    TestTenantMetricViewSet,
    TestTenantHealthScoreViewSet,
    TestTenantFeatureFlagViewSet,
    TestTenantNotificationViewSet,
    TestResellerConfigViewSet,
    TestResellerInvoiceViewSet,
)

from .test_serializers import (
    TestTenantSerializer,
    TestTenantSettingsSerializer,
    TestTenantBillingSerializer,
    TestTenantInvoiceSerializer,
    TestPlanSerializer,
    TestPlanFeatureSerializer,
    TestPlanUpgradeSerializer,
    TestPlanUsageSerializer,
    TestPlanQuotaSerializer,
    TestTenantBrandingSerializer,
    TestTenantDomainSerializer,
    TestTenantEmailSerializer,
    TestTenantSocialLinkSerializer,
    TestTenantAPIKeySerializer,
    TestTenantWebhookConfigSerializer,
    TestTenantIPWhitelistSerializer,
    TestTenantAuditLogSerializer,
    TestTenantOnboardingSerializer,
    TestTenantOnboardingStepSerializer,
    TestTenantTrialExtensionSerializer,
    TestTenantMetricSerializer,
    TestTenantHealthScoreSerializer,
    TestTenantFeatureFlagSerializer,
    TestTenantNotificationSerializer,
    TestResellerConfigSerializer,
    TestResellerInvoiceSerializer,
)

from .test_tasks import (
    TestBillingTasks,
    TestMetricsTasks,
    TestNotificationTasks,
    TestMaintenanceTasks,
    TestMonitoringTasks,
    TestOnboardingTasks,
)

from .test_signals import (
    TestCoreSignals,
    TestPlanSignals,
    TestSecuritySignals,
    TestOnboardingSignals,
    TestAnalyticsSignals,
    TestBrandingSignals,
    TestResellerSignals,
)

from .test_management_commands import (
    TestTenantCommands,
    TestBillingCommands,
    TestMetricsCommands,
    TestMaintenanceCommands,
    TestOnboardingCommands,
    TestSecurityCommands,
    TestAnalyticsCommands,
)

__all__ = [
    # Model tests
    'TestTenant', 'TestTenantSettings', 'TestTenantBilling', 'TestTenantInvoice',
    'TestPlan', 'TestPlanFeature', 'TestPlanUpgrade', 'TestPlanUsage', 'TestPlanQuota',
    'TestTenantBranding', 'TestTenantDomain', 'TestTenantEmail', 'TestTenantSocialLink',
    'TestTenantAPIKey', 'TestTenantWebhookConfig', 'TestTenantIPWhitelist', 'TestTenantAuditLog',
    'TestTenantOnboarding', 'TestTenantOnboardingStep', 'TestTenantTrialExtension',
    'TestTenantMetric', 'TestTenantHealthScore', 'TestTenantFeatureFlag', 'TestTenantNotification',
    'TestResellerConfig', 'TestResellerInvoice',
    
    # Service tests
    'TestTenantService', 'TestTenantProvisioningService', 'TestTenantSuspensionService',
    'TestPlanService', 'TestPlanUsageService', 'TestBrandingService', 'TestDomainService',
    'TestTenantBillingService', 'TestTenantEmailService', 'TestOnboardingService',
    'TestTenantAuditService', 'TestTenantMetricService', 'TestFeatureFlagService',
    
    # ViewSet tests
    'TestTenantViewSet', 'TestTenantSettingsViewSet', 'TestTenantBillingViewSet', 'TestTenantInvoiceViewSet',
    'TestPlanViewSet', 'TestPlanFeatureViewSet', 'TestPlanUpgradeViewSet', 'TestPlanUsageViewSet', 'TestPlanQuotaViewSet',
    'TestTenantBrandingViewSet', 'TestTenantDomainViewSet', 'TestTenantEmailViewSet', 'TestTenantSocialLinkViewSet',
    'TestTenantAPIKeyViewSet', 'TestTenantWebhookConfigViewSet', 'TestTenantIPWhitelistViewSet', 'TestTenantAuditLogViewSet',
    'TestTenantOnboardingViewSet', 'TestTenantOnboardingStepViewSet', 'TestTenantTrialExtensionViewSet',
    'TestTenantMetricViewSet', 'TestTenantHealthScoreViewSet', 'TestTenantFeatureFlagViewSet', 'TestTenantNotificationViewSet',
    'TestResellerConfigViewSet', 'TestResellerInvoiceViewSet',
    
    # Serializer tests
    'TestTenantSerializer', 'TestTenantSettingsSerializer', 'TestTenantBillingSerializer', 'TestTenantInvoiceSerializer',
    'TestPlanSerializer', 'TestPlanFeatureSerializer', 'TestPlanUpgradeSerializer', 'TestPlanUsageSerializer', 'TestPlanQuotaSerializer',
    'TestTenantBrandingSerializer', 'TestTenantDomainSerializer', 'TestTenantEmailSerializer', 'TestTenantSocialLinkSerializer',
    'TestTenantAPIKeySerializer', 'TestTenantWebhookConfigSerializer', 'TestTenantIPWhitelistSerializer', 'TestTenantAuditLogSerializer',
    'TestTenantOnboardingSerializer', 'TestTenantOnboardingStepSerializer', 'TestTenantTrialExtensionSerializer',
    'TestTenantMetricSerializer', 'TestTenantHealthScoreSerializer', 'TestTenantFeatureFlagSerializer', 'TestTenantNotificationSerializer',
    'TestResellerConfigSerializer', 'TestResellerInvoiceSerializer',
    
    # Task tests
    'TestBillingTasks', 'TestMetricsTasks', 'TestNotificationTasks', 'TestMaintenanceTasks',
    'TestMonitoringTasks', 'TestOnboardingTasks',
    
    # Signal tests
    'TestCoreSignals', 'TestPlanSignals', 'TestSecuritySignals', 'TestOnboardingSignals',
    'TestAnalyticsSignals', 'TestBrandingSignals', 'TestResellerSignals',
    
    # Management command tests
    'TestTenantCommands', 'TestBillingCommands', 'TestMetricsCommands', 'TestMaintenanceCommands',
    'TestOnboardingCommands', 'TestSecurityCommands', 'TestAnalyticsCommands',
]
