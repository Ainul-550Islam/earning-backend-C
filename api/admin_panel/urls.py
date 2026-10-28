# api/admin_panel/urls.py
"""
Admin Panel — Complete URL Configuration. 72 routes. 100% system coverage.
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter

# Legacy views (backward compat)
from .views import (
    AdminPanelViewSet,
    AdminActionViewSet,
    SystemSettingsViewSet,
    SystemHealthView,
    EndpointToggleViewSet as LegacyEndpointToggleViewSet,
    SiteNotificationViewSet as LegacySiteNotificationViewSet,
)

from .viewsets import (
    # Core
    SiteContentViewSet, SiteNotificationViewSet, EndpointToggleViewSet,
    DashboardViewSet, DashboardWidgetViewSet,
    AdminActivityViewSet, AdminSessionViewSet,
    SystemConfigViewSet, FeatureFlagViewSet, MaintenanceWindowViewSet,
    ReportViewSet, DataExportViewSet,
    AdminSearchViewSet, AdminInsightViewSet, BulkActionViewSet,
    # Users
    UserManagementAdminViewSet,
    # Wallet & Payments
    WalletAdminViewSet, WalletWithdrawalAdminViewSet, PayoutAdminViewSet,
    PaymentGatewayAdminViewSet,
    # CPAlead 100%
    CPALeadAdminViewSet,
    # KYC & Fraud
    KYCAdminViewSet, FraudControlViewSet, PostbackSecurityAdminViewSet,
    # Notifications & Referral
    NotificationAdminViewSet, ReferralAdminViewSet, BackupDRAdminViewSet,
    # CPA Messaging (new)
    MessagingCPAAdminViewSet,
    # Localization CPA (new)
    LocalizationCPAAdminViewSet,
    # Marketing
    PromotionsAdminViewSet, SmartlinkAdminViewSet,
    RTBAdminViewSet, ContentLockerAdminViewSet, OfferwallAdminViewSet,
    # Analytics & AI
    AnalyticsAdminViewSet, RealtimeDashboardViewSet, AIEngineAdminViewSet,
    # Alerting
    AlertsAdminViewSet, AuditLogAdminViewSet,
    # Advertiser & Publisher
    AdvertiserAdminViewSet, PublisherAdminViewSet,
    AdNetworkAdminViewSet, MonetizationToolsAdminViewSet,
    # Offer system
    OfferInventoryAdminViewSet, PostbackAdminViewSet,
    PostbackEngineAdminViewSet, OfferRoutingAdminViewSet,
    # Gamification
    GamificationAdminViewSet, DJoyaltyAdminViewSet,
    # Messaging & Behavior
    MessagingAdminViewSet, BehaviorAnalyticsAdminViewSet, AutoModAdminViewSet,
    # CMS & Localization
    CMSAdminViewSet, LocalizationAdminViewSet, VersionControlAdminViewSet,
    # Infrastructure
    SecurityAdminViewSet, SupportAdminViewSet, RateLimitAdminViewSet,
    CacheAdminViewSet, EngagementAdminViewSet, InventoryAdminViewSet,
    TasksAdminViewSet,
    # Compliance & DR
    ComplianceAdminViewSet, DisasterRecoveryAdminViewSet,
    DRIntegrationAdminViewSet, MarketplaceAdminViewSet, SubscriptionAdminViewSet,
    # Webhooks & Tenants
    WebhooksAdminViewSet, TenantAdminViewSet,
    # System Health
    SystemHealthPostgreSQLViewSet,
)

router = SimpleRouter()

# ── Core ───────────────────────────────────────────────────────────────────────
router.register(r'actions',             AdminActionViewSet,            basename='admin-actions')
router.register(r'settings',            SystemSettingsViewSet,         basename='system-settings')
router.register(r'dashboard',           DashboardViewSet,              basename='dashboard')
router.register(r'dashboard-widgets',   DashboardWidgetViewSet,        basename='dashboard-widgets')
router.register(r'site-contents',       SiteContentViewSet,            basename='site-contents')
router.register(r'site-notifications',  SiteNotificationViewSet,       basename='site-notifications')
router.register(r'endpoint-toggles',    EndpointToggleViewSet,         basename='endpoint-toggles')
router.register(r'activities',          AdminActivityViewSet,          basename='admin-activities')
router.register(r'sessions',            AdminSessionViewSet,           basename='admin-sessions')
router.register(r'system-config',       SystemConfigViewSet,           basename='system-config')
router.register(r'feature-flags',       FeatureFlagViewSet,            basename='feature-flags')
router.register(r'maintenance',         MaintenanceWindowViewSet,      basename='maintenance')
router.register(r'reports',             ReportViewSet,                 basename='reports')
router.register(r'data-exports',        DataExportViewSet,             basename='data-exports')
router.register(r'search',              AdminSearchViewSet,            basename='admin-search')
router.register(r'insights',            AdminInsightViewSet,           basename='admin-insights')
router.register(r'bulk-actions',        BulkActionViewSet,             basename='bulk-actions')

# ── Users ──────────────────────────────────────────────────────────────────────
router.register(r'users',               UserManagementAdminViewSet,    basename='admin-users')

# ── Wallet & Payments ──────────────────────────────────────────────────────────
router.register(r'wallet',              WalletAdminViewSet,            basename='admin-wallet')
router.register(r'withdrawals',         WalletWithdrawalAdminViewSet,  basename='admin-withdrawals')
router.register(r'payment-gateways',    PaymentGatewayAdminViewSet,    basename='payment-gateways')
router.register(r'payouts',             PayoutAdminViewSet,            basename='admin-payouts')

# ── CPAlead 100% ───────────────────────────────────────────────────────────────
router.register(r'cpalead',             CPALeadAdminViewSet,           basename='admin-cpalead')

# ── KYC & Fraud ────────────────────────────────────────────────────────────────
router.register(r'kyc',                 KYCAdminViewSet,               basename='admin-kyc')
router.register(r'fraud',               FraudControlViewSet,           basename='admin-fraud')
router.register(r'postback-security',   PostbackSecurityAdminViewSet,  basename='postback-security')

# ── Notifications & Referral ───────────────────────────────────────────────────
router.register(r'notifications-admin', NotificationAdminViewSet,      basename='admin-notifications')
router.register(r'referral',            ReferralAdminViewSet,          basename='admin-referral')
router.register(r'backup',              BackupDRAdminViewSet,          basename='admin-backup')

# ── CPA Messaging (previously missing) ────────────────────────────────────────
router.register(r'messaging-cpa',       MessagingCPAAdminViewSet,      basename='admin-messaging-cpa')

# ── Localization CPA (previously missing) ──────────────────────────────────────
router.register(r'localization-cpa',    LocalizationCPAAdminViewSet,   basename='admin-localization-cpa')

# ── Gamification ───────────────────────────────────────────────────────────────
router.register(r'gamification',        GamificationAdminViewSet,      basename='admin-gamification')
router.register(r'djoyalty',            DJoyaltyAdminViewSet,          basename='admin-djoyalty')

# ── Marketing ──────────────────────────────────────────────────────────────────
router.register(r'promotions',          PromotionsAdminViewSet,        basename='admin-promotions')
router.register(r'smartlink',           SmartlinkAdminViewSet,         basename='admin-smartlink')
router.register(r'rtb',                 RTBAdminViewSet,               basename='admin-rtb')
router.register(r'content-locker',      ContentLockerAdminViewSet,     basename='admin-content-locker')
router.register(r'offerwall',           OfferwallAdminViewSet,         basename='admin-offerwall')

# ── Analytics & AI ─────────────────────────────────────────────────────────────
router.register(r'analytics',           AnalyticsAdminViewSet,         basename='admin-analytics')
router.register(r'realtime',            RealtimeDashboardViewSet,      basename='admin-realtime')
router.register(r'ai-engine',           AIEngineAdminViewSet,          basename='admin-ai')

# ── Alerting ───────────────────────────────────────────────────────────────────
router.register(r'alerts',              AlertsAdminViewSet,            basename='admin-alerts')
router.register(r'audit-logs',          AuditLogAdminViewSet,          basename='admin-audit')

# ── Advertiser & Publisher ─────────────────────────────────────────────────────
router.register(r'advertisers',         AdvertiserAdminViewSet,        basename='admin-advertisers')
router.register(r'publishers',          PublisherAdminViewSet,         basename='admin-publishers')
router.register(r'ad-networks',         AdNetworkAdminViewSet,         basename='admin-ad-networks')
router.register(r'monetization',        MonetizationToolsAdminViewSet, basename='admin-monetization')

# ── Offer System ───────────────────────────────────────────────────────────────
router.register(r'offer-inventory',     OfferInventoryAdminViewSet,    basename='admin-offer-inventory')
router.register(r'postback',            PostbackAdminViewSet,          basename='admin-postback')
router.register(r'postback-engine',     PostbackEngineAdminViewSet,    basename='admin-postback-engine')
router.register(r'offer-routing',       OfferRoutingAdminViewSet,      basename='admin-offer-routing')

# ── Messaging & Behavior ───────────────────────────────────────────────────────
router.register(r'messaging',           MessagingAdminViewSet,         basename='admin-messaging')
router.register(r'behavior-analytics',  BehaviorAnalyticsAdminViewSet, basename='admin-behavior')
router.register(r'auto-mod',            AutoModAdminViewSet,           basename='admin-auto-mod')

# ── CMS & Localization ─────────────────────────────────────────────────────────
router.register(r'cms',                 CMSAdminViewSet,               basename='admin-cms')
router.register(r'localization',        LocalizationAdminViewSet,      basename='admin-localization')
router.register(r'version-control',     VersionControlAdminViewSet,    basename='admin-version-control')

# ── Infrastructure ─────────────────────────────────────────────────────────────
router.register(r'security',            SecurityAdminViewSet,          basename='admin-security')
router.register(r'support',             SupportAdminViewSet,           basename='admin-support')
router.register(r'rate-limit',          RateLimitAdminViewSet,         basename='admin-rate-limit')
router.register(r'cache-admin',         CacheAdminViewSet,             basename='admin-cache')
router.register(r'engagement',          EngagementAdminViewSet,        basename='admin-engagement')
router.register(r'inventory',           InventoryAdminViewSet,         basename='admin-inventory')
router.register(r'tasks',               TasksAdminViewSet,             basename='admin-tasks')

# ── Compliance & DR ────────────────────────────────────────────────────────────
router.register(r'compliance',          ComplianceAdminViewSet,        basename='admin-compliance')
router.register(r'disaster-recovery',   DisasterRecoveryAdminViewSet,  basename='admin-dr')
router.register(r'dr-integration',      DRIntegrationAdminViewSet,     basename='admin-dr-integration')
router.register(r'marketplace',         MarketplaceAdminViewSet,       basename='admin-marketplace')
router.register(r'subscription',        SubscriptionAdminViewSet,      basename='admin-subscription')

# ── Webhooks & Tenants ─────────────────────────────────────────────────────────
router.register(r'webhooks-admin',      WebhooksAdminViewSet,          basename='admin-webhooks')
router.register(r'tenants',             TenantAdminViewSet,            basename='admin-tenants')

# ── PostgreSQL System Health ───────────────────────────────────────────────────
router.register(r'system-health',       SystemHealthPostgreSQLViewSet, basename='system-health-pg')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', SystemHealthView.as_view(), name='system-health-basic'),
]