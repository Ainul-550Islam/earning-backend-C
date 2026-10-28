# api/djoyalty/routers.py -- FIXED: correct import paths
from rest_framework.routers import DefaultRouter
router = DefaultRouter()

# Core
from .viewsets.core.CustomerViewSet import CustomerViewSet
from .viewsets.core.TxnViewSet import TxnViewSet
from .viewsets.core.EventViewSet import EventViewSet
router.register(r'customers',    CustomerViewSet, basename='customer')
router.register(r'transactions', TxnViewSet,      basename='transaction')
router.register(r'events',       EventViewSet,    basename='event')

# Points
from .viewsets.points.PointsViewSet import PointsViewSet
from .viewsets.points.LedgerViewSet import LedgerViewSet
from .viewsets.points.PointsTransferViewSet import PointsTransferViewSet
from .viewsets.points.PointsConversionViewSet import PointsConversionViewSet
router.register(r'points',      PointsViewSet,          basename='points')
router.register(r'ledger',      LedgerViewSet,          basename='ledger')
router.register(r'transfers',   PointsTransferViewSet,  basename='transfer')
router.register(r'conversions', PointsConversionViewSet, basename='conversion')

# Tiers -- file is TierViewSet.py not LoyaltyTierViewSet.py
from .viewsets.tiers.TierViewSet import TierViewSet
from .viewsets.tiers.UserTierViewSet import UserTierViewSet
router.register(r'tiers',      TierViewSet,     basename='tier')
router.register(r'user-tiers', UserTierViewSet, basename='user-tier')

# Earn
from .viewsets.earn.EarnRuleViewSet import EarnRuleViewSet
from .viewsets.earn.BonusEventViewSet import BonusEventViewSet
router.register(r'earn-rules',   EarnRuleViewSet,   basename='earn-rule')
router.register(r'bonus-events', BonusEventViewSet, basename='bonus-event')

# Redemption
from .viewsets.redemption.RedemptionViewSet import RedemptionViewSet
from .viewsets.redemption.VoucherViewSet import VoucherViewSet
from .viewsets.redemption.GiftCardViewSet import GiftCardViewSet
router.register(r'redemptions', RedemptionViewSet, basename='redemption')
router.register(r'vouchers',    VoucherViewSet,    basename='voucher')
router.register(r'gift-cards',  GiftCardViewSet,   basename='gift-card')

# Engagement
from .viewsets.engagement.StreakViewSet import StreakViewSet
from .viewsets.engagement.BadgeViewSet import BadgeViewSet
from .viewsets.engagement.ChallengeViewSet import ChallengeViewSet
from .viewsets.engagement.LeaderboardViewSet import LeaderboardViewSet
from .viewsets.engagement.MilestoneViewSet import MilestoneViewSet
router.register(r'streaks',     StreakViewSet,     basename='streak')
router.register(r'badges',      BadgeViewSet,      basename='badge')
router.register(r'challenges',  ChallengeViewSet,  basename='challenge')
router.register(r'milestones',  MilestoneViewSet,  basename='milestone')
router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')

# Advanced -- original
from .viewsets.advanced.CampaignViewSet import CampaignViewSet
from .viewsets.advanced.InsightViewSet import InsightViewSet
from .viewsets.advanced.AdminLoyaltyViewSet import AdminLoyaltyViewSet
from .viewsets.advanced.PublicAPIViewSet import PublicAPIViewSet
from .viewsets.advanced.OfferWallViewSet import OfferWallViewSet
from .viewsets.advanced.ReferralViewSet import ReferralViewSet
from .viewsets.advanced.PartnerViewSet import PartnerViewSet
from .viewsets.advanced.RewardCatalogViewSet import RewardCatalogViewSet
router.register(r'campaigns',  CampaignViewSet,     basename='campaign')
router.register(r'insights',   InsightViewSet,      basename='insight')
router.register(r'admin',      AdminLoyaltyViewSet, basename='admin')
router.register(r'public',     PublicAPIViewSet,    basename='public')
router.register(r'offerwalls', OfferWallViewSet,    basename='offerwall')
router.register(r'referral',   ReferralViewSet,     basename='referral')
router.register(r'partners',   PartnerViewSet,      basename='partner')
router.register(r'catalog',    RewardCatalogViewSet, basename='catalog')

# Advanced -- fixed
from .viewsets.advanced.CashoutViewSet import CashoutViewSet
from .viewsets.advanced.NotificationViewSet import NotificationViewSet
router.register(r'cashout',       CashoutViewSet,      basename='cashout')
router.register(r'notifications', NotificationViewSet, basename='notification')

# NEW: Gamification
from .viewsets.advanced.GamificationViewSet import (
    SpinWheelViewSet, ScratchCardViewSet, LotteryViewSet,
    LeaderboardSeasonViewSet, QuizViewSet,
)
router.register(r'gamification/spin-wheels',         SpinWheelViewSet,         basename='spin-wheel')
router.register(r'gamification/scratch-cards',       ScratchCardViewSet,       basename='scratch-card')
router.register(r'gamification/lotteries',           LotteryViewSet,           basename='lottery')
router.register(r'gamification/leaderboard-seasons', LeaderboardSeasonViewSet, basename='leaderboard-season')
router.register(r'gamification/quizzes',             QuizViewSet,              basename='quiz')

# NEW: AI
from .viewsets.advanced.AIPersonalizationViewSet import (
    CustomerAIProfileViewSet, PersonalizedOfferViewSet,
    AIRecommendationViewSet, ChurnAlertViewSet,
)
router.register(r'ai/profiles',        CustomerAIProfileViewSet, basename='ai-profile')
router.register(r'ai/offers',          PersonalizedOfferViewSet, basename='ai-offer')
router.register(r'ai/recommendations', AIRecommendationViewSet,  basename='ai-recommendation')
router.register(r'ai/churn-alerts',    ChurnAlertViewSet,        basename='churn-alert')

# NEW: Eco/Family/Charity
from .viewsets.advanced.EcoFamilyViewSet import (
    FamilyAccountViewSet, EcoViewSet, CharityViewSet, ExperienceViewSet, ConsentViewSet,
)
router.register(r'family',         FamilyAccountViewSet, basename='family')
router.register(r'eco/actions',    EcoViewSet,           basename='eco')
router.register(r'charity/causes', CharityViewSet,       basename='charity')
router.register(r'experiences',    ExperienceViewSet,    basename='experience')
router.register(r'consent',        ConsentViewSet,       basename='consent')

# NEW: Receipt/Social/QR
from .viewsets.advanced.ReceiptSocialViewSet import (
    ReceiptViewSet, SocialShareViewSet, ReviewViewSet, QRCodeViewSet,
)
router.register(r'receipts',           ReceiptViewSet,      basename='receipt')
router.register(r'social/share-rules', SocialShareViewSet,  basename='social-share')
router.register(r'reviews',            ReviewViewSet,       basename='review')
router.register(r'qr',                 QRCodeViewSet,       basename='qr-code')

# NEW: Tenant/Audit/Config
from .viewsets.advanced.TenantViewSet import (
    TenantViewSet, AdminAuditLogViewSet, SystemConfigViewSet,
)
router.register(r'tenants',    TenantViewSet,        basename='tenant')
router.register(r'audit-logs', AdminAuditLogViewSet, basename='audit-log')
router.register(r'config',     SystemConfigViewSet,  basename='config')

# ─── NEW: TierBenefit API ──────────────────────────────────────────────────────
from .viewsets.tiers.TierBenefitViewSet import TierBenefitViewSet
router.register(r'tier-benefits', TierBenefitViewSet, basename='tier-benefit')

# ─── NEW: Analytics / LTV / Cohort ────────────────────────────────────────────
from .viewsets.advanced.AnalyticsViewSet import AnalyticsViewSet
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

# ─── NEW: Compliance / GDPR ───────────────────────────────────────────────────
from .viewsets.advanced.ComplianceViewSet import ComplianceViewSet
router.register(r'compliance', ComplianceViewSet, basename='compliance')

# ─── NEW: Search ──────────────────────────────────────────────────────────────
from .viewsets.advanced.SearchViewSet import SearchViewSet
router.register(r'search', SearchViewSet, basename='search')

# ─── NEW: Paid Membership ─────────────────────────────────────────────────────
from .viewsets.advanced.MembershipViewSet import MembershipViewSet
router.register(r'memberships', MembershipViewSet, basename='membership')

# ─── NEW: POS Integration ─────────────────────────────────────────────────────
from .viewsets.advanced.POSViewSet import POSViewSet
router.register(r'pos', POSViewSet, basename='pos')

# ─── NEW: Card Linking ────────────────────────────────────────────────────────
from .viewsets.advanced.CardLinkingViewSet import CardLinkingViewSet
router.register(r'card-linking', CardLinkingViewSet, basename='card-linking')

# ─── NEW: Pending Points ──────────────────────────────────────────────────────
from .viewsets.advanced.PendingPointsViewSet import PendingPointsViewSet
router.register(r'pending-points', PendingPointsViewSet, basename='pending-points')

# ─── NEW: Promotion Engine ────────────────────────────────────────────────────
from .viewsets.advanced.PromotionViewSet import PromotionViewSet
router.register(r'promotions', PromotionViewSet, basename='promotion')

# ─── NEW: Subscription Loyalty ────────────────────────────────────────────────
from .viewsets.advanced.SubscriptionViewSet import SubscriptionViewSet
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

# ─── NEW: Web3 + DAO Governance ───────────────────────────────────────────────
from .viewsets.advanced.Web3ViewSet import Web3ViewSet, DAOGovernanceViewSet
router.register(r'web3',  Web3ViewSet,          basename='web3')
router.register(r'dao',   DAOGovernanceViewSet,  basename='dao')

# ─── NEW: Omnichannel ─────────────────────────────────────────────────────────
from .viewsets.advanced.OmnichannelViewSet import (
    OmnichannelViewSet, PushNotificationViewSet, PointsStackingViewSet,
)
router.register(r'omnichannel',      OmnichannelViewSet,     basename='omnichannel')
router.register(r'push',             PushNotificationViewSet, basename='push')
router.register(r'points-stacking',  PointsStackingViewSet,  basename='points-stacking')

# ─── NEW: AI Realtime Offers ──────────────────────────────────────────────────
from .viewsets.advanced.AIRealtimeViewSet import AIRealtimeViewSet
router.register(r'ai-realtime', AIRealtimeViewSet, basename='ai-realtime')

# ─── NEW: SDK + Export ────────────────────────────────────────────────────────
from .viewsets.advanced.SDKViewSet import SDKViewSet
from .viewsets.advanced.ExportViewSet import ExportViewSet
router.register(r'sdk',    SDKViewSet,    basename='sdk')
router.register(r'export', ExportViewSet, basename='export')

# ─── NEW: Customer Profile ─────────────────────────────────────────────────────
from .viewsets.advanced.CustomerProfileViewSet import CustomerProfileViewSet
router.register(r'profile', CustomerProfileViewSet, basename='customer-profile')

# ─── NEW: SmartLink ───────────────────────────────────────────────────────────
from .viewsets.advanced.SmartLinkViewSet import SmartLinkViewSet
router.register(r'smart-links', SmartLinkViewSet, basename='smart-link')

# ── Webhooks ──────────────────────────────────────────────────────────────────
from .viewsets.webhooks.WebhookViewSet import WebhookViewSet
router.register(r'webhooks', WebhookViewSet, basename='webhook')

# ── Customer Devices ──────────────────────────────────────────────────────────
from .viewsets.audit.CustomerDeviceViewSet import CustomerDeviceViewSet
router.register(r'devices', CustomerDeviceViewSet, basename='device')

# ── Spin Wheel Slices (admin config) ─────────────────────────────────────────
from .viewsets.advanced.GamificationViewSet import SpinWheelSliceViewSet
router.register(r'spin-wheel-slices', SpinWheelSliceViewSet, basename='spin-wheel-slice')
