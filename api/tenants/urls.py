from rest_framework.routers import SimpleRouter
from django.urls import path, include

# Import all viewsets
from .viewsets import (
    # Core viewsets
    TenantViewSet, TenantSettingsViewSet, TenantBillingViewSet, TenantInvoiceViewSet,
    # Plan viewsets
    PlanViewSet, PlanFeatureViewSet, PlanUpgradeViewSet, PlanUsageViewSet, PlanQuotaViewSet,
    # Branding viewsets
    TenantBrandingViewSet, TenantDomainViewSet, TenantEmailViewSet, TenantSocialLinkViewSet,
    # Security viewsets
    TenantAPIKeyViewSet, TenantWebhookConfigViewSet, TenantIPWhitelistViewSet, TenantAuditLogViewSet,
    # Onboarding viewsets
    TenantOnboardingViewSet, TenantOnboardingStepViewSet, TenantTrialExtensionViewSet,
    # Analytics viewsets
    TenantMetricViewSet, TenantHealthScoreViewSet, TenantFeatureFlagViewSet, TenantNotificationViewSet,
    # Reseller viewsets
    ResellerConfigViewSet, ResellerInvoiceViewSet,
)

# Create main router
router = SimpleRouter()

# Core tenant routes
router.register(r"tenants", TenantViewSet, basename="tenant")
router.register(r"tenant-settings", TenantSettingsViewSet, basename="tenant-settings")
router.register(r"tenant-billing", TenantBillingViewSet, basename="tenant-billing")
router.register(r"tenant-invoices", TenantInvoiceViewSet, basename="tenant-invoice")

# Plan management routes
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"plan-features", PlanFeatureViewSet, basename="plan-feature")
router.register(r"plan-upgrades", PlanUpgradeViewSet, basename="plan-upgrade")
router.register(r"plan-usage", PlanUsageViewSet, basename="plan-usage")
router.register(r"plan-quotas", PlanQuotaViewSet, basename="plan-quota")

# Branding routes
router.register(r"tenant-branding", TenantBrandingViewSet, basename="tenant-branding")
router.register(r"tenant-domains", TenantDomainViewSet, basename="tenant-domain")
router.register(r"tenant-emails", TenantEmailViewSet, basename="tenant-email")
router.register(r"tenant-social-links", TenantSocialLinkViewSet, basename="tenant-social-link")

# Security routes
router.register(r"api-keys", TenantAPIKeyViewSet, basename="api-key")
router.register(r"webhook-configs", TenantWebhookConfigViewSet, basename="webhook-config")
router.register(r"ip-whitelists", TenantIPWhitelistViewSet, basename="ip-whitelist")
router.register(r"audit-logs", TenantAuditLogViewSet, basename="audit-log")

# Onboarding routes
router.register(r"onboarding", TenantOnboardingViewSet, basename="onboarding")
router.register(r"onboarding-steps", TenantOnboardingStepViewSet, basename="onboarding-step")
router.register(r"trial-extensions", TenantTrialExtensionViewSet, basename="trial-extension")

# Analytics routes
router.register(r"metrics", TenantMetricViewSet, basename="metric")
router.register(r"health-scores", TenantHealthScoreViewSet, basename="health-score")
router.register(r"feature-flags", TenantFeatureFlagViewSet, basename="feature-flag")
router.register(r"notifications", TenantNotificationViewSet, basename="notification")

# Reseller routes
router.register(r"resellers", ResellerConfigViewSet, basename="reseller")
router.register(r"reseller-invoices", ResellerInvoiceViewSet, basename="reseller-invoice")

# Custom action URLs
urlpatterns = [
    # Tenant custom actions
    path('tenants/<uuid:pk>/suspend/', TenantViewSet.as_view({'post': 'suspend'}), name='tenant-suspend'),
    path('tenants/<uuid:pk>/unsuspend/', TenantViewSet.as_view({'post': 'unsuspend'}), name='tenant-unsuspend'),
    path('tenants/<uuid:pk>/statistics/', TenantViewSet.as_view({'get': 'statistics'}), name='tenant-statistics'),
    path('tenants/<uuid:pk>/export/', TenantViewSet.as_view({'post': 'export'}), name='tenant-export'),
    
    # Plan custom actions
    path('plans/<uuid:pk>/activate/', PlanViewSet.as_view({'post': 'activate'}), name='plan-activate'),
    path('plans/<uuid:pk>/deactivate/', PlanViewSet.as_view({'post': 'deactivate'}), name='plan-deactivate'),
    path('plans/compare/', PlanViewSet.as_view({'post': 'compare'}), name='plan-compare'),
    
    # API key custom actions
    path('api-keys/<uuid:pk>/revoke/', TenantAPIKeyViewSet.as_view({'post': 'revoke'}), name='api-key-revoke'),
    path('api-keys/<uuid:pk>/regenerate/', TenantAPIKeyViewSet.as_view({'post': 'regenerate'}), name='api-key-regenerate'),
    
    # Metrics custom actions
    path('metrics/record/', TenantMetricViewSet.as_view({'post': 'record'}), name='metric-record'),
    path('metrics/trends/', TenantMetricViewSet.as_view({'get': 'trends'}), name='metric-trends'),
    
    # Audit log custom actions
    path('audit-logs/export/', TenantAuditLogViewSet.as_view({'post': 'export'}), name='audit-log-export'),
    
    # Health score custom actions
    path('health-scores/calculate/', TenantHealthScoreViewSet.as_view({'post': 'calculate'}), name='health-score-calculate'),
    
    # Notification custom actions
    path('notifications/mark-read/', TenantNotificationViewSet.as_view({'post': 'mark_read'}), name='notification-mark-read'),
    path('notifications/mark-unread/', TenantNotificationViewSet.as_view({'post': 'mark_unread'}), name='notification-mark-unread'),
    path('notifications/resend/', TenantNotificationViewSet.as_view({'post': 'resend'}), name='notification-resend'),
    
    # Domain custom actions
    path('tenant-domains/<uuid:pk>/verify/', TenantDomainViewSet.as_view({'post': 'verify'}), name='domain-verify'),
    path('tenant-domains/<uuid:pk>/check-ssl/', TenantDomainViewSet.as_view({'post': 'check_ssl'}), name='domain-check-ssl'),
    path('tenant-domains/<uuid:pk>/renew-ssl/', TenantDomainViewSet.as_view({'post': 'renew_ssl'}), name='domain-renew-ssl'),
    path('tenant-domains/<uuid:pk>/set-primary/', TenantDomainViewSet.as_view({'post': 'set_primary'}), name='domain-set-primary'),
    
    # Email custom actions
    path('tenant-emails/<uuid:pk>/test-connection/', TenantEmailViewSet.as_view({'post': 'test_connection'}), name='email-test-connection'),
    path('tenant-emails/<uuid:pk>/verify/', TenantEmailViewSet.as_view({'post': 'verify'}), name='email-verify'),
    path('tenant-emails/<uuid:pk>/send-test/', TenantEmailViewSet.as_view({'post': 'send_test'}), name='email-send-test'),
    
    # Webhook custom actions
    path('webhook-configs/<uuid:pk>/test/', TenantWebhookConfigViewSet.as_view({'post': 'test'}), name='webhook-test'),
    path('webhook-configs/<uuid:pk>/clear-stats/', TenantWebhookConfigViewSet.as_view({'post': 'clear_statistics'}), name='webhook-clear-stats'),
    
    # Onboarding custom actions
    path('onboarding/<uuid:pk>/complete/', TenantOnboardingViewSet.as_view({'post': 'complete'}), name='onboarding-complete'),
    path('onboarding/<uuid:pk>/pause/', TenantOnboardingViewSet.as_view({'post': 'pause'}), name='onboarding-pause'),
    path('onboarding/<uuid:pk>/send-reminder/', TenantOnboardingViewSet.as_view({'post': 'send_reminder'}), name='onboarding-send-reminder'),
    
    # Onboarding step custom actions
    path('onboarding-steps/<uuid:pk>/start/', TenantOnboardingStepViewSet.as_view({'post': 'start'}), name='onboarding-step-start'),
    path('onboarding-steps/<uuid:pk>/complete/', TenantOnboardingStepViewSet.as_view({'post': 'complete'}), name='onboarding-step-complete'),
    path('onboarding-steps/<uuid:pk>/skip/', TenantOnboardingStepViewSet.as_view({'post': 'skip'}), name='onboarding-step-skip'),
    path('onboarding-steps/<uuid:pk>/reset/', TenantOnboardingStepViewSet.as_view({'post': 'reset'}), name='onboarding-step-reset'),
    
    # Trial extension custom actions
    path('trial-extensions/<uuid:pk>/approve/', TenantTrialExtensionViewSet.as_view({'post': 'approve'}), name='trial-extension-approve'),
    path('trial-extensions/<uuid:pk>/reject/', TenantTrialExtensionViewSet.as_view({'post': 'reject'}), name='trial-extension-reject'),
    path('trial-extensions/<uuid:pk>/cancel/', TenantTrialExtensionViewSet.as_view({'post': 'cancel'}), name='trial-extension-cancel'),
    
    # Feature flag custom actions
    path('feature-flags/<uuid:pk>/enable/', TenantFeatureFlagViewSet.as_view({'post': 'enable'}), name='feature-flag-enable'),
    path('feature-flags/<uuid:pk>/disable/', TenantFeatureFlagViewSet.as_view({'post': 'disable'}), name='feature-flag-disable'),
    path('feature-flags/<uuid:pk>/rollout/', TenantFeatureFlagViewSet.as_view({'post': 'rollout'}), name='feature-flag-rollout'),
    path('feature-flags/<uuid:pk>/archive/', TenantFeatureFlagViewSet.as_view({'post': 'archive'}), name='feature-flag-archive'),
    
    # Reseller custom actions
    path('resellers/<uuid:pk>/verify/', ResellerConfigViewSet.as_view({'post': 'verify'}), name='reseller-verify'),
    path('resellers/<uuid:pk>/activate/', ResellerConfigViewSet.as_view({'post': 'activate'}), name='reseller-activate'),
    path('resellers/<uuid:pk>/deactivate/', ResellerConfigViewSet.as_view({'post': 'deactivate'}), name='reseller-deactivate'),
    path('resellers/<uuid:pk>/calculate-commissions/', ResellerConfigViewSet.as_view({'post': 'calculate_commissions'}), name='reseller-calculate-commissions'),
    
    # Reseller invoice custom actions
    path('reseller-invoices/<uuid:pk>/approve/', ResellerInvoiceViewSet.as_view({'post': 'approve'}), name='reseller-invoice-approve'),
    path('reseller-invoices/<uuid:pk>/reject/', ResellerInvoiceViewSet.as_view({'post': 'reject'}), name='reseller-invoice-reject'),
    path('reseller-invoices/<uuid:pk>/mark-paid/', ResellerInvoiceViewSet.as_view({'post': 'mark_paid'}), name='reseller-invoice-mark-paid'),
    path('reseller-invoices/generate-commission-reports/', ResellerInvoiceViewSet.as_view({'post': 'generate_commission_reports'}), name='reseller-invoice-generate-commission-reports'),
    
    # Bulk actions
    path('tenants/bulk-suspend/', TenantViewSet.as_view({'post': 'bulk_suspend'}), name='tenant-bulk-suspend'),
    path('tenants/bulk-unsuspend/', TenantViewSet.as_view({'post': 'bulk_unsuspend'}), name='tenant-bulk-unsuspend'),
    path('tenants/bulk-export/', TenantViewSet.as_view({'post': 'bulk_export'}), name='tenant-bulk-export'),
    
    path('plans/bulk-activate/', PlanViewSet.as_view({'post': 'bulk_activate'}), name='plan-bulk-activate'),
    path('plans/bulk-deactivate/', PlanViewSet.as_view({'post': 'bulk_deactivate'}), name='plan-bulk-deactivate'),
    path('plans/bulk-duplicate/', PlanViewSet.as_view({'post': 'bulk_duplicate'}), name='plan-bulk-duplicate'),
    
    path('api-keys/bulk-revoke/', TenantAPIKeyViewSet.as_view({'post': 'bulk_revoke'}), name='api-key-bulk-revoke'),
    path('api-keys/bulk-regenerate/', TenantAPIKeyViewSet.as_view({'post': 'bulk_regenerate'}), name='api-key-bulk-regenerate'),
    
    path('notifications/bulk-mark-read/', TenantNotificationViewSet.as_view({'post': 'bulk_mark_read'}), name='notification-bulk-mark-read'),
    path('notifications/bulk-mark-unread/', TenantNotificationViewSet.as_view({'post': 'bulk_mark_unread'}), name='notification-bulk-mark-unread'),
    path('notifications/bulk-resend/', TenantNotificationViewSet.as_view({'post': 'bulk_resend'}), name='notification-bulk-resend'),
    path('notifications/bulk-delete/', TenantNotificationViewSet.as_view({'post': 'bulk_delete'}), name='notification-bulk-delete'),
    
    # Analytics and reporting endpoints
    path('analytics/usage-report/', TenantMetricViewSet.as_view({'get': 'usage_report'}), name='analytics-usage-report'),
    path('analytics/health-report/', TenantHealthScoreViewSet.as_view({'get': 'health_report'}), name='analytics-health-report'),
    path('analytics/security-report/', TenantAuditLogViewSet.as_view({'get': 'security_report'}), name='analytics-security-report'),
    path('analytics/billing-report/', TenantInvoiceViewSet.as_view({'get': 'billing_report'}), name='analytics-billing-report'),
    path('analytics/onboarding-report/', TenantOnboardingViewSet.as_view({'get': 'onboarding_report'}), name='analytics-onboarding-report'),
    
    # Include router URLs
    path('', include(router.urls)),
]
