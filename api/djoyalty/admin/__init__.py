# api/djoyalty/admin/__init__.py
"""
Djoyalty Admin registration।

FIXED: catalog_admin, notification_admin, offerwall_admin existed
as files but were only loaded via try/except with no explicit exports।
Now explicitly imported with proper class names in __all__।
"""

# ─── Core ─────────────────────────────────────────────────────────────────────
from .customer_admin import CustomerAdmin, TenantAdmin
from .points_admin import (
    LoyaltyPointsAdmin, PointsLedgerAdmin, PointsExpiryAdmin,
    PointsAdjustmentAdmin, PointsTransferAdmin,
)
from .tier_admin import (
    LoyaltyTierAdmin, UserTierAdmin, TierBenefitAdmin,
    TierHistoryAdmin, TierConfigAdmin,
)
from .earn_rule_admin import EarnRuleAdmin, BonusEventAdmin, EarnTransactionAdmin
from .redemption_admin import (
    RedemptionRuleAdmin, RedemptionRequestAdmin, RedemptionHistoryAdmin,
)
from .voucher_admin import VoucherAdmin, VoucherRedemptionAdmin, GiftCardAdmin
from .badge_admin import (
    BadgeAdmin, UserBadgeAdmin, DailyStreakAdmin,
    ChallengeAdmin, MilestoneAdmin,
)
from .campaign_admin import (
    LoyaltyCampaignAdmin, CampaignParticipantAdmin,
    PartnerMerchantAdmin, ReferralPointsRuleAdmin,
)
from .fraud_admin import PointsAbuseLogAdmin, LoyaltyFraudRuleAdmin
from .insight_admin import (
    LoyaltyInsightAdmin, LoyaltyNotificationAdmin, LoyaltySubscriptionAdmin,
)
from .partner_admin import CoalitionEarnAdmin

# ─── Previously orphaned admin modules -- now explicit ────────────────────────
# FIXED: these 3 files existed but were loaded via silent try/except
# with no named exports. Now imported explicitly।

from .catalog_admin import (
    RewardCatalogCategoryAdmin, RewardCatalogItemAdmin,
    SmartLinkAdmin, WebhookSubscriptionAdmin, DigitalWalletCardAdmin,
)
from .notification_admin import (
    NotificationTemplateAdmin, NotificationPreferenceAdmin,
    NotificationCenterAdmin,
)
from .offerwall_admin import (
    OfferWallAdmin, OfferAdmin, OfferCompletionAdmin, OfferPostbackLogAdmin,
)

__all__ = [
    # Customer / Tenant
    'CustomerAdmin', 'TenantAdmin',
    # Points
    'LoyaltyPointsAdmin', 'PointsLedgerAdmin', 'PointsExpiryAdmin',
    'PointsAdjustmentAdmin', 'PointsTransferAdmin',
    # Tiers
    'LoyaltyTierAdmin', 'UserTierAdmin', 'TierBenefitAdmin',
    'TierHistoryAdmin', 'TierConfigAdmin',
    # Earn Rules
    'EarnRuleAdmin', 'BonusEventAdmin', 'EarnTransactionAdmin',
    # Redemption
    'RedemptionRuleAdmin', 'RedemptionRequestAdmin', 'RedemptionHistoryAdmin',
    # Vouchers
    'VoucherAdmin', 'VoucherRedemptionAdmin', 'GiftCardAdmin',
    # Badges / Streaks / Challenges
    'BadgeAdmin', 'UserBadgeAdmin', 'DailyStreakAdmin',
    'ChallengeAdmin', 'MilestoneAdmin',
    # Campaigns
    'LoyaltyCampaignAdmin', 'CampaignParticipantAdmin',
    'PartnerMerchantAdmin', 'ReferralPointsRuleAdmin',
    # Fraud
    'PointsAbuseLogAdmin', 'LoyaltyFraudRuleAdmin',
    # Insights / Notifications / Subscriptions
    'LoyaltyInsightAdmin', 'LoyaltyNotificationAdmin', 'LoyaltySubscriptionAdmin',
    # Partners
    'CoalitionEarnAdmin',
    # Catalog
    'RewardCatalogCategoryAdmin', 'RewardCatalogItemAdmin',
    'SmartLinkAdmin', 'WebhookSubscriptionAdmin', 'DigitalWalletCardAdmin',
    # Notifications
    'NotificationTemplateAdmin', 'NotificationPreferenceAdmin', 'NotificationCenterAdmin',
    # OfferWall
    'OfferWallAdmin', 'OfferAdmin', 'OfferCompletionAdmin', 'OfferPostbackLogAdmin',
]

# AUDIT FIX (v4): Gamification and missing model admin registrations
from .gamification_admin import (
    SpinWheelConfigAdmin, SpinWheelResultAdmin,
    ScratchCardAdmin,
    LotteryDrawAdmin, LotteryTicketAdmin,
    LeaderboardSeasonAdmin, LeaderboardEntryAdmin,
    QuizRewardAdmin, CustomerQuizAttemptAdmin,
)

from .advanced_admin import (
    # advanced.py
    PointsAlertAdmin, LoyaltyFraudRuleAdmin, LoyaltySubscriptionAdmin,
    # audit.py
    ProductCatalogRuleAdmin, MultiCurrencyRateAdmin, SystemConfigAdmin,
    # campaigns.py
    CampaignSegmentAdmin, ReferralPointsRuleAdmin,
    # cashout.py
    CustomerMobileWalletAdmin, CashoutRateAdmin,
    # catalog.py
    RewardCatalogCategoryAdmin, SmartLinkClickAdmin, WebhookSubscriptionAdmin,
    # earn_rules.py
    EarnRuleConditionAdmin, EarnRuleTierMultiplierAdmin, EarnRuleLogAdmin,
    # engagement.py
    StreakRewardAdmin, MilestoneAdmin, UserMilestoneAdmin,
    # family_eco.py
    EcoActionAdmin, CustomerEcoStatsAdmin, CharityCauseAdmin, CharityDonationAdmin,
    ExperientialRewardAdmin, ExperientialRegistrationAdmin, ReceiptEarnRuleAdmin,
    # notifications.py
    NotificationTemplateAdmin, NotificationPreferenceAdmin,
    # offerwall.py
    OfferWallAdmin, ContentLockAdmin, ContentUnlockAdmin,
    # redemption.py
    RedemptionHistoryAdmin, VoucherRedemptionAdmin,
    # referral.py
    ReferralProgramAdmin,
    # social.py
    SocialShareConfigAdmin, ReviewRewardAdmin, CustomerReviewAdmin, CustomerSegmentAdmin,
    # tiers.py
    TierBenefitAdmin, TierConfigAdmin,
)
