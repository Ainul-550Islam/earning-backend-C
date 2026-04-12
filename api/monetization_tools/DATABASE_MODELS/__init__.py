"""
DATABASE_MODELS package
========================
QuerySet + Manager classes for every monetization model.
Import in models.py via:
    from .DATABASE_MODELS.ad_campaign_model import AdCampaignManager
"""
from .ad_campaign_model       import AdCampaignManager, AdCampaignQuerySet
from .ad_unit_model           import AdUnitManager, AdCreativeManager
from .ad_placement_model      import AdPlacementManager, WaterfallConfigManager
from .ad_network_model        import AdNetworkManager, AdNetworkDailyStatManager
from .ad_impression_model     import ImpressionLogManager
from .ad_click_model          import ClickLogManager
from .ad_conversion_model     import ConversionLogManager
from .ad_revenue_model        import RevenueDailySummaryManager
from .offerwall_model         import OfferwallManager, OfferManager, OfferCompletionManager
from .reward_history_model    import RewardTransactionManager, SpinWheelLogManager
from .user_subscription_model import (SubscriptionPlanManager, UserSubscriptionManager,
                                       RecurringBillingManager)
from .user_purchase_model     import InAppPurchaseManager, PayoutRequestManager
from .payment_transaction_model import (PaymentTransactionManager, PostbackLogManager,
                                          FraudAlertManager)
from .ab_test_model           import ABTestManager, ABTestAssignmentManager, FloorPriceConfigManager
from .monetization_config_model import (MonetizationConfigManager, RevenueGoalManager,
                                         PublisherAccountManager, FlashSaleManager,
                                         CouponManager, ReferralCommissionManager)

__all__ = [
    'AdCampaignManager', 'AdCampaignQuerySet',
    'AdUnitManager', 'AdCreativeManager',
    'AdPlacementManager', 'WaterfallConfigManager',
    'AdNetworkManager', 'AdNetworkDailyStatManager',
    'ImpressionLogManager', 'ClickLogManager',
    'ConversionLogManager', 'RevenueDailySummaryManager',
    'OfferwallManager', 'OfferManager', 'OfferCompletionManager',
    'RewardTransactionManager', 'SpinWheelLogManager',
    'SubscriptionPlanManager', 'UserSubscriptionManager', 'RecurringBillingManager',
    'InAppPurchaseManager', 'PayoutRequestManager',
    'PaymentTransactionManager', 'PostbackLogManager', 'FraudAlertManager',
    'ABTestManager', 'ABTestAssignmentManager', 'FloorPriceConfigManager',
    'MonetizationConfigManager', 'RevenueGoalManager', 'PublisherAccountManager',
    'FlashSaleManager', 'CouponManager', 'ReferralCommissionManager',
]
