# api/admin_panel/api_router.py
"""
Central DRF router — registers ALL admin viewsets in one place.
Import this in urls.py: from api.admin_panel.api_router import router
"""
from rest_framework.routers import DefaultRouter
from api.admin_panel.viewsets import (
    DashboardViewSet, DashboardWidgetViewSet, AdminActivityViewSet,
    AdminSessionViewSet, AdminSearchViewSet, AdminInsightViewSet,
    BulkActionViewSet, SystemConfigViewSet, FeatureFlagViewSet,
    MaintenanceWindowViewSet, ReportViewSet, DataExportViewSet,
    SiteContentViewSet, SiteNotificationViewSet, EndpointToggleViewSet,
    UserManagementAdminViewSet, PromotionsAdminViewSet, SmartlinkAdminViewSet,
    FraudControlViewSet, PayoutAdminViewSet, RTBAdminViewSet,
    ContentLockerAdminViewSet, OfferwallAdminViewSet, AIEngineAdminViewSet,
    AdvertiserAdminViewSet, PublisherAdminViewSet,
    KYCAdminViewSet, DJoyaltyAdminViewSet, AdNetworkAdminViewSet,
    AnalyticsAdminViewSet, AlertsAdminViewSet, AuditLogAdminViewSet,
    CMSAdminViewSet, VersionControlAdminViewSet, GamificationAdminViewSet,
    OfferInventoryAdminViewSet, PostbackAdminViewSet, LocalizationAdminViewSet,
    WalletAdminViewSet, MessagingAdminViewSet, BehaviorAnalyticsAdminViewSet,
    AutoModAdminViewSet, PostbackEngineAdminViewSet, OfferRoutingAdminViewSet,
    MonetizationToolsAdminViewSet, ComplianceAdminViewSet,
    DisasterRecoveryAdminViewSet, MarketplaceAdminViewSet,
    SubscriptionAdminViewSet, RealtimeDashboardViewSet, CrossAppAdminViewSet,
)
from api.admin_panel.viewsets.RemainingAppsViewSet import (
    PaymentGatewayAdminViewSet, SecurityAdminViewSet, SupportAdminViewSet,
    EngagementAdminViewSet, InventoryAdminViewSet, RateLimitAdminViewSet,
    CacheAdminViewSet, DRIntegrationAdminViewSet, TasksAdminViewSet,
)
from api.admin_panel.webhooks import AdminWebhookViewSet

router = DefaultRouter()

# ── Core admin ──────────────────────────────────────────────────────────────
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'dashboard/widgets', DashboardWidgetViewSet, basename='dashboard-widgets')
router.register(r'activity', AdminActivityViewSet, basename='admin-activity')
router.register(r'sessions', AdminSessionViewSet, basename='admin-sessions')
router.register(r'search', AdminSearchViewSet, basename='admin-search')
router.register(r'insights', AdminInsightViewSet, basename='admin-insights')
router.register(r'bulk-actions', BulkActionViewSet, basename='bulk-actions')
router.register(r'config', SystemConfigViewSet, basename='system-config')
router.register(r'feature-flags', FeatureFlagViewSet, basename='feature-flags')
router.register(r'maintenance', MaintenanceWindowViewSet, basename='maintenance')
router.register(r'reports', ReportViewSet, basename='reports')
router.register(r'exports', DataExportViewSet, basename='data-exports')
router.register(r'site-content', SiteContentViewSet, basename='site-content')
router.register(r'notifications', SiteNotificationViewSet, basename='site-notifications')
router.register(r'endpoint-toggles', EndpointToggleViewSet, basename='endpoint-toggles')
router.register(r'webhooks', AdminWebhookViewSet, basename='webhooks')

# ── App control ──────────────────────────────────────────────────────────────
router.register(r'users', UserManagementAdminViewSet, basename='user-management')
router.register(r'offers', PromotionsAdminViewSet, basename='promotions')
router.register(r'smartlinks', SmartlinkAdminViewSet, basename='smartlinks')
router.register(r'fraud', FraudControlViewSet, basename='fraud-control')
router.register(r'payouts', PayoutAdminViewSet, basename='payouts')
router.register(r'rtb', RTBAdminViewSet, basename='rtb')
router.register(r'content-lockers', ContentLockerAdminViewSet, basename='content-lockers')
router.register(r'offerwall', OfferwallAdminViewSet, basename='offerwall')
router.register(r'ai-engine', AIEngineAdminViewSet, basename='ai-engine')
router.register(r'advertisers', AdvertiserAdminViewSet, basename='advertisers')
router.register(r'publishers', PublisherAdminViewSet, basename='publishers')
router.register(r'kyc', KYCAdminViewSet, basename='kyc')
router.register(r'loyalty', DJoyaltyAdminViewSet, basename='loyalty')
router.register(r'ad-networks', AdNetworkAdminViewSet, basename='ad-networks')
router.register(r'analytics', AnalyticsAdminViewSet, basename='analytics')
router.register(r'alerts', AlertsAdminViewSet, basename='alerts')
router.register(r'audit-logs', AuditLogAdminViewSet, basename='audit-logs')
router.register(r'cms', CMSAdminViewSet, basename='cms')
router.register(r'version-control', VersionControlAdminViewSet, basename='version-control')
router.register(r'gamification', GamificationAdminViewSet, basename='gamification')
router.register(r'offer-inventory', OfferInventoryAdminViewSet, basename='offer-inventory')
router.register(r'postback', PostbackAdminViewSet, basename='postback')
router.register(r'localization', LocalizationAdminViewSet, basename='localization')
router.register(r'wallet', WalletAdminViewSet, basename='wallet')
router.register(r'messaging', MessagingAdminViewSet, basename='messaging')
router.register(r'behavior', BehaviorAnalyticsAdminViewSet, basename='behavior')
router.register(r'auto-mod', AutoModAdminViewSet, basename='auto-mod')
router.register(r'postback-engine', PostbackEngineAdminViewSet, basename='postback-engine')
router.register(r'offer-routing', OfferRoutingAdminViewSet, basename='offer-routing')
router.register(r'monetization', MonetizationToolsAdminViewSet, basename='monetization')
router.register(r'compliance', ComplianceAdminViewSet, basename='compliance')
router.register(r'disaster-recovery', DisasterRecoveryAdminViewSet, basename='disaster-recovery')
router.register(r'marketplace', MarketplaceAdminViewSet, basename='marketplace')
router.register(r'subscriptions', SubscriptionAdminViewSet, basename='subscriptions')
router.register(r'payment-gateways', PaymentGatewayAdminViewSet, basename='payment-gateways')
router.register(r'security', SecurityAdminViewSet, basename='security')
router.register(r'support', SupportAdminViewSet, basename='support')
router.register(r'engagement', EngagementAdminViewSet, basename='engagement')
router.register(r'inventory', InventoryAdminViewSet, basename='inventory')
router.register(r'rate-limits', RateLimitAdminViewSet, basename='rate-limits')
router.register(r'cache', CacheAdminViewSet, basename='cache')
router.register(r'dr-integration', DRIntegrationAdminViewSet, basename='dr-integration')
router.register(r'tasks', TasksAdminViewSet, basename='tasks')
router.register(r'realtime', RealtimeDashboardViewSet, basename='realtime')
router.register(r'cross-app', CrossAppAdminViewSet, basename='cross-app')