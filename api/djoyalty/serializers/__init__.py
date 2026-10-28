# api/djoyalty/serializers/__init__.py -- FIXED: only imports classes that actually exist

# Core
from .CustomerSerializer import CustomerSerializer, CustomerDetailSerializer
from .TxnSerializer import TxnSerializer
from .EventSerializer import EventSerializer

# Points
from .PointsSerializer import (
    LoyaltyPointsSerializer, PointsTransferSerializer,
    PointsConversionSerializer, PointsReservationSerializer,
)
PointsSerializer = LoyaltyPointsSerializer

from .LedgerSerializer import LedgerSerializer, PointsAdjustmentSerializer, PointsRateSerializer

# Tiers
from .TierSerializer import LoyaltyTierSerializer, TierBenefitSerializer, TierConfigSerializer
TierSerializer = LoyaltyTierSerializer

from .UserTierSerializer import (
    UserTierSerializer, UserTierHistorySerializer,
    MyTierSerializer, TierBenefitInlineSerializer,
)

# Earn Rules
from .EarnRuleSerializer import (
    EarnRuleSerializer, EarnRuleConditionSerializer, EarnRuleTierMultiplierSerializer,
    EarnTransactionSerializer, BonusEventSerializer, EarnRuleLogSerializer,
)

# Redemption
from .RedemptionSerializer import (
    RedemptionRuleSerializer, RedemptionRequestSerializer, RedemptionHistorySerializer,
)
RedemptionSerializer = RedemptionRequestSerializer

from .VoucherSerializer import VoucherSerializer, VoucherRedemptionSerializer
from .GiftCardSerializer import GiftCardSerializer

# Engagement
from .StreakSerializer import DailyStreakSerializer, StreakRewardSerializer
from .BadgeSerializer import BadgeSerializer, UserBadgeSerializer
from .ChallengeSerializer import ChallengeSerializer, ChallengeParticipantSerializer
from .MilestoneSerializer import MilestoneSerializer, UserMilestoneSerializer

# Campaigns
from .CampaignSerializer import (
    LoyaltyCampaignSerializer, CampaignSegmentSerializer,
    CampaignParticipantSerializer, ReferralPointsRuleSerializer,
)
CampaignSerializer = LoyaltyCampaignSerializer

from .LeaderboardSerializer import LeaderboardEntrySerializer
from .InsightSerializer import LoyaltyInsightSerializer, FraudLogSerializer
InsightSerializer = LoyaltyInsightSerializer

from .AdminSerializer import AdminCustomerDetailSerializer
from .PartnerSerializer import (
    PartnerMerchantSerializer, PartnerMerchantAdminSerializer, CoalitionEarnSerializer,
)
PartnerSerializer = PartnerMerchantSerializer

from .WebhookSerializer import WebhookEndpointSerializer, WebhookPayloadSerializer
from .OfferWallSerializer import OfferWallSerializer, OfferSerializer, OfferCompletionSerializer
from .NotificationSerializer import (
    NotificationCenterSerializer, NotificationTemplateSerializer, NotificationPreferenceSerializer,
)
from .CatalogSerializer import (
    RewardCatalogItemSerializer, RewardCatalogCategorySerializer,
    SmartLinkSerializer, WebhookSubscriptionSerializer, DigitalWalletCardSerializer,
)
from .ReferralSerializer import (
    ReferralLinkSerializer, ReferralConversionSerializer, ReferralProgramSerializer,
)

# NEW serializers
from .TenantSerializer import TenantSerializer, TenantAdminSerializer, TenantCreateSerializer
from .AuditSerializer import (
    AdminAuditLogSerializer, CustomerDeviceSerializer, CustomerDeviceRegisterSerializer,
    SystemConfigSerializer, MultiCurrencyRateSerializer, ProductCatalogRuleSerializer,
)
from .CashoutSerializer import (
    CashoutRequestSerializer, CashoutRequestCreateSerializer, CashoutAdminActionSerializer,
    CashoutRateSerializer,
    CustomerBankAccountSerializer, CustomerBankAccountCreateSerializer,
    CustomerMobileWalletSerializer, CustomerMobileWalletCreateSerializer,
    WalletTransactionSerializer,
)
from .PointsExtendedSerializer import (
    PointsExpirySerializer, PointsExpiryWarningSerializer,
    PointsAdjustmentDetailSerializer, PointsAdjustmentCreateSerializer,
    PointsRateDetailSerializer,
)
from .NotificationExtendedSerializer import (
    LoyaltyNotificationSerializer, PointsAlertSerializer,
    NotificationCenterListSerializer, NotificationCenterDetailSerializer,
    NotificationBulkReadSerializer, NotificationInboxSummarySerializer,
)
from .GamificationSerializer import (
    SpinWheelSliceSerializer, SpinWheelConfigSerializer,
    SpinWheelResultSerializer, SpinWheelResultPublicSerializer,
    ScratchCardSerializer,
    LotteryTicketSerializer, LotteryDrawSerializer, LotteryTicketPurchaseSerializer,
    LeaderboardSeasonSerializer,
    QuizRewardSerializer, CustomerQuizAttemptSerializer, QuizSubmitSerializer,
)
from .AIPersonalizationSerializer import (
    CustomerAIProfileSerializer, CustomerAIProfileSummarySerializer,
    PersonalizedOfferSerializer, PersonalizedOfferClaimSerializer,
    PersonalizedOfferDismissSerializer,
    AIRecommendationSerializer, AIRecommendationClickSerializer,
    ChurnAlertSerializer, ChurnAlertActionSerializer,
)
from .EcoFamilySerializer import (
    FamilyAccountSerializer, FamilyMemberSerializer, FamilyInviteSerializer,
    EcoActionSerializer, CustomerEcoActionSerializer,
    EcoActionLogSerializer, CustomerEcoStatsSerializer,
    CharityCauseSerializer, CharityDonationSerializer, CharityDonateSerializer,
    ExperientialRewardSerializer, ExperientialRegistrationSerializer,
    ExperienceRegisterSerializer, ExperienceFeedbackSerializer,
    CustomerConsentSerializer, CustomerConsentUpdateSerializer,
    ReceiptScanSerializer, ReceiptSubmitSerializer, ReceiptEarnRuleSerializer,
)
from .SocialSerializer import (
    SocialShareRewardSerializer, CustomerSocialActionSerializer,
    ReviewRewardSerializer, CustomerReviewSerializer, CustomerReviewCreateSerializer,
    QRCodeEarnSerializer, QRCodeEarnAdminSerializer,
    QRCodeScanSerializer, QRCodeScanSubmitSerializer,
)

# FIXED: schemas.py (PointsEarnRequest, CashoutRequest schemas) was orphaned
# Request/response schemas now importable from serializers package
try:
    from ..schemas import (
        PointsEarnRequest, CashoutRequestSchema,
        ReferralConvertSchema, BadgeAwardSchema,
    )
except ImportError:
    pass

# AUDIT FIX (v4): Missing serializer module exports added
# These were present as files but not exported from the package.

# AnalyticsSerializer — CustomerLTVSerializer, CohortTableSerializer, etc.
try:
    from .AnalyticsSerializer import (
        CustomerLTVSerializer,
        AnalyticsOverviewSerializer,
        CohortTableSerializer,
        CampaignAnalyticsSerializer,
    )
except ImportError:
    pass

# MissingModelSerializers — serializers for models that had no serializer
try:
    from .MissingModelSerializers import (
        EarnRuleConditionSerializer,
        EarnRuleTierMultiplierSerializer,
        EarnRuleLogSerializer,
        StreakRewardSerializer,
        UserMilestoneSerializer,
        SpinWheelSliceSerializer as SpinWheelSliceAdminSerializer,
        LotteryTicketAdminSerializer,
        RedemptionHistorySerializer,
        VoucherRedemptionSerializer,
    )
except ImportError:
    pass

# MembershipSerializer — paid membership plan serializers
try:
    from .MembershipSerializer import (
        MembershipPlanSerializer,
        LoyaltySubscriptionSerializer,
        MembershipBenefitSerializer,
    )
except ImportError:
    pass
