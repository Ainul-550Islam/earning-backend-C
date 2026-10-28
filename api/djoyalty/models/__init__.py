# api/djoyalty/models/__init__.py
"""
Djoyalty Models package -- সব models এখান থেকে import করো।

FIXED: Added 10 new models from flatfile modules that now have
migrations (via 0011_flatfile_models.py):
  dao_governance.py  -> GovernanceConfig, GovernanceProposal,
                        GovernanceVote, GovernanceExecution
  web3_loyalty.py    -> NFTBadge, CustomerWallet
  ai_realtime_offers -> AIGeneratedOffer, AIOfferConfig
  card_linking.py    -> LinkedCard, CardTransactionWebhook
Also added AbstractModels from abstracts.py (previously orphan)।
"""

# ─── Core ─────────────────────────────────────────────────────────────────────
from .core import Customer, Txn, Event, Tenant

# ─── Points ───────────────────────────────────────────────────────────────────
from .points import (
    LoyaltyPoints, PointsLedger, PointsExpiry,
    PointsTransfer, PointsConversion, PointsReservation,
    PointsRate, PointsAdjustment,
)

# ─── Tiers ────────────────────────────────────────────────────────────────────
from .tiers import LoyaltyTier, UserTier, TierBenefit, TierHistory, TierConfig

# ─── Earn Rules ───────────────────────────────────────────────────────────────
from .earn_rules import (
    EarnRule, EarnRuleCondition, EarnRuleTierMultiplier,
    EarnTransaction, BonusEvent, EarnRuleLog,
)

# ─── Redemption ───────────────────────────────────────────────────────────────
from .redemption import (
    RedemptionRule, RedemptionRequest, RedemptionHistory,
    Voucher, VoucherRedemption, GiftCard,
)

# ─── Engagement ───────────────────────────────────────────────────────────────
from .engagement import (
    DailyStreak, StreakReward, Badge, UserBadge,
    Challenge, ChallengeParticipant, Milestone, UserMilestone,
)

# ─── Campaigns ────────────────────────────────────────────────────────────────
from .campaigns import (
    LoyaltyCampaign, CampaignSegment, CampaignParticipant,
    ReferralPointsRule, PartnerMerchant,
)

# ─── Advanced ─────────────────────────────────────────────────────────────────
from .advanced import (
    LoyaltyNotification, PointsAlert, LoyaltySubscription,
    LoyaltyFraudRule, PointsAbuseLog, LoyaltyInsight,
    CoalitionEarn,
)

# ─── Gamification ─────────────────────────────────────────────────────────────
from .gamification import (
    SpinWheelConfig, SpinWheelSlice, SpinWheelResult,
    ScratchCard, LotteryDraw, LotteryTicket,
    LeaderboardSeason, QuizReward, CustomerQuizAttempt,
)

# ─── Cashout ──────────────────────────────────────────────────────────────────
from .cashout import (
    CustomerBankAccount, CustomerMobileWallet,
    CashoutRequest, CashoutRate, WalletTransaction,
)

# ─── Social ───────────────────────────────────────────────────────────────────
from .social import (
    SocialShareReward, CustomerSocialAction,
    ReviewReward, CustomerReview,
    QRCodeEarn, QRCodeScan,
    CustomerSegment, CustomerSegmentMember,
)

# ─── OfferWall ────────────────────────────────────────────────────────────────
from .offerwall import (
    OfferWall, Offer, OfferCompletion,
    ContentLock, ContentUnlock, OfferPostbackLog,
)

# ─── Referral ─────────────────────────────────────────────────────────────────
from .referral import (
    ReferralLink, ReferralClick, ReferralConversion, ReferralProgram,
)

# ─── Audit / Device / Catalog / Config ───────────────────────────────────────
from .audit import (
    AdminAuditLog, CustomerDevice,
    ProductCatalogRule, MultiCurrencyRate, SystemConfig,
)

# ─── Notification Center ──────────────────────────────────────────────────────
from .notifications import (
    NotificationTemplate, NotificationPreference, NotificationCenter,
)

# ─── Reward Catalog / SmartLink / Webhook / Digital Wallet ───────────────────
from .catalog import (
    RewardCatalogCategory, RewardCatalogItem,
    SmartLink, SmartLinkClick,
    WebhookSubscription, WebhookDeliveryLog,
    DigitalWalletCard,
)

# ─── AI Personalization ───────────────────────────────────────────────────────
from .ai_personalization import (
    CustomerAIProfile, PersonalizedOffer,
    AIRecommendation, ChurnAlert,
)

# ─── Family / Eco ─────────────────────────────────────────────────────────────
from .family_eco import (
    FamilyAccount, FamilyMember,
    EcoAction, CustomerEcoAction, CustomerEcoStats,
    CharityCause, CharityDonation,
    ExperientialReward, ExperientialRegistration,
    CustomerConsent,
    ReceiptScan, ReceiptEarnRule,
)

# ─── NEW: DAO Governance (flatfile models -- now have migrations) ──────────────
try:
    from ..dao_governance import (
        GovernanceConfig, GovernanceProposal,
        GovernanceVote, GovernanceExecution,
    )
except ImportError:
    pass

# ─── NEW: Web3 Loyalty (flatfile models -- now have migrations) ───────────────
try:
    from ..web3_loyalty import NFTBadge, CustomerWallet
except ImportError:
    pass

# ─── NEW: AI Real-time Offers (flatfile models -- now have migrations) ─────────
try:
    from ..ai_realtime_offers import AIGeneratedOffer, AIOfferConfig
except ImportError:
    pass

# ─── NEW: Card Linking (flatfile models -- now have migrations) ────────────────
try:
    from ..card_linking import LinkedCard, CardTransactionWebhook
except ImportError:
    pass

# ─── Abstract base classes (from abstracts.py -- previously orphan) ────────────
# These are abstract Models (Meta: abstract=True) -- Django does NOT
# create DB tables for them. Importing makes them available for
# subclassing in custom extensions.
try:
    from ..abstracts import (
        TimestampMixin, TenantMixin, SoftDeleteMixin,
        AuditMixin, PointsMixin,
    )
except ImportError:
    pass
