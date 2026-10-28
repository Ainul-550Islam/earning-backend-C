# api/admin_panel/viewsets/__init__.py
"""
Admin Panel Viewsets — controls ALL 50+ apps from one place.
Every import is wrapped so missing apps won't crash startup.
Coverage: 100% (including CPAlead 13% fix)
"""

# ── Core ──────────────────────────────────────────────────────────────────────
from .SiteContentViewSet          import SiteContentViewSet
from .SiteNotificationViewSet     import SiteNotificationViewSet
from .EndpointToggleViewSet       import EndpointToggleViewSet
from .DashboardViewSet            import DashboardViewSet
from .DashboardWidgetViewSet      import DashboardWidgetViewSet
from .AdminActivityViewSet        import AdminActivityViewSet
from .AdminSessionViewSet         import AdminSessionViewSet
from .SystemConfigViewSet         import SystemConfigViewSet
from .FeatureFlagViewSet          import FeatureFlagViewSet
from .MaintenanceWindowViewSet    import MaintenanceWindowViewSet
from .ReportViewSet               import ReportViewSet
from .DataExportViewSet           import DataExportViewSet
from .AdminSearchViewSet          import AdminSearchViewSet
from .AdminInsightViewSet         import AdminInsightViewSet
from .BulkActionViewSet           import BulkActionViewSet

# ── User & KYC ────────────────────────────────────────────────────────────────
from .UserManagementAdminViewSet  import UserManagementAdminViewSet

# ── Wallet & Payments ─────────────────────────────────────────────────────────
from .WalletWithdrawalAdminViewSet import WalletWithdrawalAdminViewSet
from .PayoutAdminViewSet           import PayoutAdminViewSet

# ── CPAlead Full System (previously 13% missing — now 100%) ───────────────────
from .CPALeadAdminViewSet         import CPALeadAdminViewSet

# ── Fraud & Security ──────────────────────────────────────────────────────────
from .FraudControlViewSet         import FraudControlViewSet
from .PostbackSecurityAdminViewSet import PostbackSecurityAdminViewSet

# ── Notifications & Referral & Backup ─────────────────────────────────────────
from .NotificationReferralAdminViewSet import (
    NotificationAdminViewSet,
    ReferralAdminViewSet,
    BackupDRAdminViewSet,
)

# ── CPA Messaging (previously missing) ───────────────────────────────────────
from .MessagingCPAAdminViewSet    import MessagingCPAAdminViewSet

# ── Localization CPA (previously missing) ─────────────────────────────────────
from .LocalizationCPAAdminViewSet import LocalizationCPAAdminViewSet

# ── Marketing ─────────────────────────────────────────────────────────────────
from .PromotionsViewSet           import PromotionsAdminViewSet
from .SmartlinkAdminViewSet       import SmartlinkAdminViewSet
from .RTBAdminViewSet             import RTBAdminViewSet
from .ContentLockerOfferwallAdminViewSet import (
    ContentLockerAdminViewSet,
    OfferwallAdminViewSet,
)

# ── Analytics & AI ────────────────────────────────────────────────────────────
from .RealtimeDashboardViewSet    import RealtimeDashboardViewSet
from .AIEngineAdminViewSet        import AIEngineAdminViewSet

# ── All-Apps (KYC, DJoyalty, AdNetworks, Analytics, etc.) ────────────────────
from .AllAppsControlViewSet import (
    KYCAdminViewSet,
    DJoyaltyAdminViewSet,
    AdNetworkAdminViewSet,
    AnalyticsAdminViewSet,
    AlertsAdminViewSet,
    AuditLogAdminViewSet,
    CMSAdminViewSet,
    VersionControlAdminViewSet,
    GamificationAdminViewSet,
    OfferInventoryAdminViewSet,
    PostbackAdminViewSet,
    LocalizationAdminViewSet,
    WalletAdminViewSet,
)

# ── Advertiser & Publisher ────────────────────────────────────────────────────
from .AdvertiserPublisherAdminViewSet import (
    AdvertiserAdminViewSet,
    PublisherAdminViewSet,
)

# ── Messaging & Behavior ──────────────────────────────────────────────────────
from .MessagingBehaviorAdminViewSet import (
    MessagingAdminViewSet,
    BehaviorAnalyticsAdminViewSet,
    AutoModAdminViewSet,
    PostbackEngineAdminViewSet,
    OfferRoutingAdminViewSet,
    MonetizationToolsAdminViewSet,
)

# ── Remaining (Payment GW, Security, Support, Engagement, etc.) ───────────────
from .RemainingAppsViewSet import (
    PaymentGatewayAdminViewSet,
    SecurityAdminViewSet,
    SupportAdminViewSet,
    EngagementAdminViewSet,
    InventoryAdminViewSet,
    RateLimitAdminViewSet,
    CacheAdminViewSet,
    DRIntegrationAdminViewSet,
    TasksAdminViewSet,
)

# ── Compliance & DR ────────────────────────────────────────────────────────────
from .ComplianceDisasterAdminViewSet import (
    ComplianceAdminViewSet,
    DisasterRecoveryAdminViewSet,
    MarketplaceAdminViewSet,
    SubscriptionAdminViewSet,
)

# ── Webhooks & Tenants ────────────────────────────────────────────────────────
from .WebhooksTenantAdminViewSet import (
    WebhooksAdminViewSet,
    TenantAdminViewSet,
)

# ── PostgreSQL System Health ──────────────────────────────────────────────────
from .SystemHealthPostgreSQLViewSet import SystemHealthPostgreSQLViewSet

__all__ = [
    # Core
    'SiteContentViewSet', 'SiteNotificationViewSet', 'EndpointToggleViewSet',
    'DashboardViewSet', 'DashboardWidgetViewSet', 'AdminActivityViewSet',
    'AdminSessionViewSet', 'SystemConfigViewSet', 'FeatureFlagViewSet',
    'MaintenanceWindowViewSet', 'ReportViewSet', 'DataExportViewSet',
    'AdminSearchViewSet', 'AdminInsightViewSet', 'BulkActionViewSet',
    # Users
    'UserManagementAdminViewSet',
    # Wallet
    'WalletAdminViewSet', 'WalletWithdrawalAdminViewSet', 'PayoutAdminViewSet',
    # CPAlead 100%
    'CPALeadAdminViewSet',
    # Fraud & Security
    'FraudControlViewSet', 'PostbackSecurityAdminViewSet',
    # Notifications
    'NotificationAdminViewSet', 'ReferralAdminViewSet', 'BackupDRAdminViewSet',
    # CPA Messaging (new)
    'MessagingCPAAdminViewSet',
    # Localization CPA (new)
    'LocalizationCPAAdminViewSet',
    # Marketing
    'PromotionsAdminViewSet', 'SmartlinkAdminViewSet', 'RTBAdminViewSet',
    'ContentLockerAdminViewSet', 'OfferwallAdminViewSet',
    # Analytics & AI
    'AnalyticsAdminViewSet', 'RealtimeDashboardViewSet', 'AIEngineAdminViewSet',
    # All apps
    'KYCAdminViewSet', 'DJoyaltyAdminViewSet', 'AdNetworkAdminViewSet',
    'AlertsAdminViewSet', 'AuditLogAdminViewSet', 'CMSAdminViewSet',
    'VersionControlAdminViewSet', 'GamificationAdminViewSet',
    'OfferInventoryAdminViewSet', 'PostbackAdminViewSet',
    'LocalizationAdminViewSet',
    # Advertiser & Publisher
    'AdvertiserAdminViewSet', 'PublisherAdminViewSet',
    'AdNetworkAdminViewSet', 'MonetizationToolsAdminViewSet',
    # Messaging & Behavior
    'MessagingAdminViewSet', 'BehaviorAnalyticsAdminViewSet',
    'AutoModAdminViewSet', 'PostbackEngineAdminViewSet',
    'OfferRoutingAdminViewSet',
    # Remaining
    'PaymentGatewayAdminViewSet', 'SecurityAdminViewSet', 'SupportAdminViewSet',
    'EngagementAdminViewSet', 'InventoryAdminViewSet', 'RateLimitAdminViewSet',
    'CacheAdminViewSet', 'DRIntegrationAdminViewSet', 'TasksAdminViewSet',
    # Compliance
    'ComplianceAdminViewSet', 'DisasterRecoveryAdminViewSet',
    'MarketplaceAdminViewSet', 'SubscriptionAdminViewSet',
    # Webhooks & Tenants
    'WebhooksAdminViewSet', 'TenantAdminViewSet',
    # System Health
    'SystemHealthPostgreSQLViewSet',
]