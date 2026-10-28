# api/rate_limit/adapters/__init__.py
"""
Rate Limit Adapters — Complete coverage for all 54 api/ apps.
"""

from .users import UsersRateLimitAdapter
from .wallet import WalletRateLimitAdapter
from .offerwall import OfferwallRateLimitAdapter
from .referral import ReferralRateLimitAdapter
from .postback import PostbackRateLimitAdapter
from .kyc import KYCRateLimitAdapter
from .fraud import FraudRateLimitAdapter
from .messaging import MessagingRateLimitAdapter
from .ad_networks import AdNetworksRateLimitAdapter
from .webhooks import WebhooksRateLimitAdapter
from .security import SecurityRateLimitAdapter
from .tenants import TenantsRateLimitAdapter
from .djoyalty import DjoyaltyRateLimitAdapter
from .remaining_apps import (
    AdminPanelRateLimitAdapter,
    AdvertiserPortalRateLimitAdapter,
    AIEngineRateLimitAdapter,
    AlertsRateLimitAdapter,
    AnalyticsRateLimitAdapter,
    AuditLogsRateLimitAdapter,
    AutoModRateLimitAdapter,
    BackupRateLimitAdapter,
    BehaviorAnalyticsRateLimitAdapter,
    CacheRateLimitAdapter,
    CMSRateLimitAdapter,
    DisasterRecoveryRateLimitAdapter,
    EngagementRateLimitAdapter,
    GamificationRateLimitAdapter,
    InventoryRateLimitAdapter,
    LocalizationRateLimitAdapter,
    MarketplaceRateLimitAdapter,
    MonetizationToolsRateLimitAdapter,
    NotificationsRateLimitAdapter,
    OfferInventoryRateLimitAdapter,
    OfferRoutingRateLimitAdapter,
    PaymentGatewaysRateLimitAdapter,
    PayoutQueueRateLimitAdapter,
    PromotionsRateLimitAdapter,
    ProxyIntelligenceRateLimitAdapter,
    PublisherToolsRateLimitAdapter,
    SmartlinkRateLimitAdapter,
    SubscriptionRateLimitAdapter,
    SupportRateLimitAdapter,
    TasksRateLimitAdapter,
    VersionControlRateLimitAdapter,
    GenericApiRateLimitAdapter,
    register_new_actions,
)

__all__ = [
    # Core adapters (13)
    'UsersRateLimitAdapter',
    'WalletRateLimitAdapter',
    'OfferwallRateLimitAdapter',
    'ReferralRateLimitAdapter',
    'PostbackRateLimitAdapter',
    'KYCRateLimitAdapter',
    'FraudRateLimitAdapter',
    'MessagingRateLimitAdapter',
    'AdNetworksRateLimitAdapter',
    'WebhooksRateLimitAdapter',
    'SecurityRateLimitAdapter',
    'TenantsRateLimitAdapter',
    'DjoyaltyRateLimitAdapter',
    # Remaining apps (20+)
    'AdminPanelRateLimitAdapter',
    'AdvertiserPortalRateLimitAdapter',
    'AIEngineRateLimitAdapter',
    'AlertsRateLimitAdapter',
    'AnalyticsRateLimitAdapter',
    'AuditLogsRateLimitAdapter',
    'AutoModRateLimitAdapter',
    'BackupRateLimitAdapter',
    'BehaviorAnalyticsRateLimitAdapter',
    'CacheRateLimitAdapter',
    'CMSRateLimitAdapter',
    'DisasterRecoveryRateLimitAdapter',
    'EngagementRateLimitAdapter',
    'GamificationRateLimitAdapter',
    'InventoryRateLimitAdapter',
    'LocalizationRateLimitAdapter',
    'MarketplaceRateLimitAdapter',
    'MonetizationToolsRateLimitAdapter',
    'NotificationsRateLimitAdapter',
    'OfferInventoryRateLimitAdapter',
    'OfferRoutingRateLimitAdapter',
    'PaymentGatewaysRateLimitAdapter',
    'PayoutQueueRateLimitAdapter',
    'PromotionsRateLimitAdapter',
    'ProxyIntelligenceRateLimitAdapter',
    'PublisherToolsRateLimitAdapter',
    'SmartlinkRateLimitAdapter',
    'SubscriptionRateLimitAdapter',
    'SupportRateLimitAdapter',
    'TasksRateLimitAdapter',
    'VersionControlRateLimitAdapter',
    'GenericApiRateLimitAdapter',
    'register_new_actions',
]
