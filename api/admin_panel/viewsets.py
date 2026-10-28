# api/admin_panel/viewsets.py
"""
Convenience import module — re-exports all viewsets from viewsets/ package.
Usage: from api.admin_panel.viewsets import DashboardViewSet, UserManagementAdminViewSet
Also includes viewset_cap.CrossAppAdminViewSet.
"""

# ── Core admin viewsets ────────────────────────────────────────────────────
from api.admin_panel.viewsets.DashboardViewSet       import DashboardViewSet
from api.admin_panel.viewsets.DashboardWidgetViewSet import DashboardWidgetViewSet
from api.admin_panel.viewsets.AdminActivityViewSet   import AdminActivityViewSet
from api.admin_panel.viewsets.AdminSessionViewSet    import AdminSessionViewSet
from api.admin_panel.viewsets.AdminSearchViewSet     import AdminSearchViewSet
from api.admin_panel.viewsets.AdminInsightViewSet    import AdminInsightViewSet
from api.admin_panel.viewsets.BulkActionViewSet      import BulkActionViewSet
from api.admin_panel.viewsets.SystemConfigViewSet    import SystemConfigViewSet
from api.admin_panel.viewsets.FeatureFlagViewSet     import FeatureFlagViewSet
from api.admin_panel.viewsets.MaintenanceWindowViewSet import MaintenanceWindowViewSet
from api.admin_panel.viewsets.ReportViewSet          import ReportViewSet
from api.admin_panel.viewsets.DataExportViewSet      import DataExportViewSet
from api.admin_panel.viewsets.SiteContentViewSet     import SiteContentViewSet
from api.admin_panel.viewsets.SiteNotificationViewSet import SiteNotificationViewSet
from api.admin_panel.viewsets.EndpointToggleViewSet  import EndpointToggleViewSet

# ── App-control viewsets ───────────────────────────────────────────────────
from api.admin_panel.viewsets.UserManagementAdminViewSet     import UserManagementAdminViewSet
from api.admin_panel.viewsets.PromotionsViewSet              import PromotionsAdminViewSet
from api.admin_panel.viewsets.SmartlinkAdminViewSet          import SmartlinkAdminViewSet
from api.admin_panel.viewsets.FraudControlViewSet            import FraudControlViewSet
from api.admin_panel.viewsets.PayoutAdminViewSet             import PayoutAdminViewSet
from api.admin_panel.viewsets.RTBAdminViewSet                import RTBAdminViewSet
from api.admin_panel.viewsets.ContentLockerOfferwallAdminViewSet import (
    ContentLockerAdminViewSet, OfferwallAdminViewSet,
)
from api.admin_panel.viewsets.AIEngineAdminViewSet           import AIEngineAdminViewSet
from api.admin_panel.viewsets.AdvertiserPublisherAdminViewSet import (
    AdvertiserAdminViewSet, PublisherAdminViewSet,
)
from api.admin_panel.viewsets.AllAppsControlViewSet          import (
    KYCAdminViewSet, DJoyaltyAdminViewSet, AdNetworkAdminViewSet,
    AnalyticsAdminViewSet, AlertsAdminViewSet, AuditLogAdminViewSet,
    CMSAdminViewSet, VersionControlAdminViewSet, GamificationAdminViewSet,
    OfferInventoryAdminViewSet, PostbackAdminViewSet,
    LocalizationAdminViewSet, WalletAdminViewSet,
)
from api.admin_panel.viewsets.MessagingBehaviorAdminViewSet  import (
    MessagingAdminViewSet, BehaviorAnalyticsAdminViewSet,
    AutoModAdminViewSet, PostbackEngineAdminViewSet,
    OfferRoutingAdminViewSet, MonetizationToolsAdminViewSet,
)
from api.admin_panel.viewsets.ComplianceDisasterAdminViewSet import (
    ComplianceAdminViewSet, DisasterRecoveryAdminViewSet,
    MarketplaceAdminViewSet, SubscriptionAdminViewSet,
)
from api.admin_panel.viewsets.RealtimeDashboardViewSet       import RealtimeDashboardViewSet

# ── Cross-app propagation viewset ─────────────────────────────────────────
from api.admin_panel.viewset_cap import CrossAppAdminViewSet

__all__ = [
    # Core
    'DashboardViewSet', 'DashboardWidgetViewSet', 'AdminActivityViewSet',
    'AdminSessionViewSet', 'AdminSearchViewSet', 'AdminInsightViewSet',
    'BulkActionViewSet', 'SystemConfigViewSet', 'FeatureFlagViewSet',
    'MaintenanceWindowViewSet', 'ReportViewSet', 'DataExportViewSet',
    'SiteContentViewSet', 'SiteNotificationViewSet', 'EndpointToggleViewSet',
    # App control
    'UserManagementAdminViewSet', 'PromotionsAdminViewSet', 'SmartlinkAdminViewSet',
    'FraudControlViewSet', 'PayoutAdminViewSet', 'RTBAdminViewSet',
    'ContentLockerAdminViewSet', 'OfferwallAdminViewSet', 'AIEngineAdminViewSet',
    'AdvertiserAdminViewSet', 'PublisherAdminViewSet',
    'KYCAdminViewSet', 'DJoyaltyAdminViewSet', 'AdNetworkAdminViewSet',
    'AnalyticsAdminViewSet', 'AlertsAdminViewSet', 'AuditLogAdminViewSet',
    'CMSAdminViewSet', 'VersionControlAdminViewSet', 'GamificationAdminViewSet',
    'OfferInventoryAdminViewSet', 'PostbackAdminViewSet',
    'LocalizationAdminViewSet', 'WalletAdminViewSet',
    'MessagingAdminViewSet', 'BehaviorAnalyticsAdminViewSet',
    'AutoModAdminViewSet', 'PostbackEngineAdminViewSet',
    'OfferRoutingAdminViewSet', 'MonetizationToolsAdminViewSet',
    'ComplianceAdminViewSet', 'DisasterRecoveryAdminViewSet',
    'MarketplaceAdminViewSet', 'SubscriptionAdminViewSet',
    'RealtimeDashboardViewSet',
    # Cross-app
    'CrossAppAdminViewSet',
]