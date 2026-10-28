# api/djoyalty/viewsets/__init__.py
"""
Djoyalty ViewSets Package -- UPDATED।
FIX: All new viewsets registered here for router discovery।

Sub-packages:
  core/       - Customer, Txn, Event
  points/     - Points, Ledger, Transfer, Conversion
  tiers/      - LoyaltyTier, UserTier
  earn/       - EarnRule, BonusEvent
  redemption/ - Redemption, Voucher, GiftCard
  engagement/ - Streak, Badge, Challenge, Leaderboard
  advanced/   - Campaign, Insight, AdminLoyalty, PublicAPI
               + NEW: Gamification, AI, Eco/Family, Cashout(fixed),
                      Notification(fixed), Tenant, ReceiptSocial
"""

# ── Core ─────────────────────────────────────────────────────────────────────
from .core.CustomerViewSet import CustomerViewSet
from .core.TxnViewSet import TxnViewSet
from .core.EventViewSet import EventViewSet

# ── Points ────────────────────────────────────────────────────────────────────
from .points.PointsViewSet import PointsViewSet
from .points.LedgerViewSet import LedgerViewSet
from .points.PointsTransferViewSet import PointsTransferViewSet
from .points.PointsConversionViewSet import PointsConversionViewSet

# ── Tiers ─────────────────────────────────────────────────────────────────────
from .tiers.TierViewSet import TierViewSet
from .tiers.UserTierViewSet import UserTierViewSet

# ── Earn ──────────────────────────────────────────────────────────────────────
from .earn.EarnRuleViewSet import EarnRuleViewSet
from .earn.BonusEventViewSet import BonusEventViewSet

# ── Redemption ────────────────────────────────────────────────────────────────
from .redemption.RedemptionViewSet import RedemptionViewSet
from .redemption.VoucherViewSet import VoucherViewSet
from .redemption.GiftCardViewSet import GiftCardViewSet

# ── Engagement ────────────────────────────────────────────────────────────────
from .engagement.StreakViewSet import StreakViewSet
from .engagement.BadgeViewSet import BadgeViewSet
from .engagement.ChallengeViewSet import ChallengeViewSet
from .engagement.LeaderboardViewSet import LeaderboardViewSet
from .engagement.MilestoneViewSet import MilestoneViewSet

# ── Advanced (original) ───────────────────────────────────────────────────────
from .advanced.CampaignViewSet import CampaignViewSet
from .advanced.InsightViewSet import InsightViewSet
from .advanced.AdminLoyaltyViewSet import AdminLoyaltyViewSet
from .advanced.PublicAPIViewSet import PublicAPIViewSet
from .advanced.OfferWallViewSet import OfferWallViewSet
from .advanced.ReferralViewSet import ReferralViewSet
from .advanced.PartnerViewSet import PartnerViewSet
from .advanced.RewardCatalogViewSet import RewardCatalogViewSet

# ── Advanced (fixed) ──────────────────────────────────────────────────────────
from .advanced.CashoutViewSet import CashoutViewSet          # FIXED
from .advanced.NotificationViewSet import NotificationViewSet  # FIXED

# ── Advanced (NEW) ────────────────────────────────────────────────────────────
from .advanced.GamificationViewSet import (
    SpinWheelViewSet,
    ScratchCardViewSet,
    LotteryViewSet,
    LeaderboardSeasonViewSet,
    QuizViewSet,
)
from .advanced.AIPersonalizationViewSet import (
    CustomerAIProfileViewSet,
    PersonalizedOfferViewSet,
    AIRecommendationViewSet,
    ChurnAlertViewSet,
)
from .advanced.EcoFamilyViewSet import (
    FamilyAccountViewSet,
    EcoViewSet,
    CharityViewSet,
    ExperienceViewSet,
    ConsentViewSet,
)
from .advanced.ReceiptSocialViewSet import (
    ReceiptViewSet,
    SocialShareViewSet,
    ReviewViewSet,
    QRCodeViewSet,
)
from .advanced.TenantViewSet import (
    TenantViewSet,
    AdminAuditLogViewSet,
    SystemConfigViewSet,
)


__all__ = [
    # Core
    'CustomerViewSet', 'TxnViewSet', 'EventViewSet',
    # Points
    'PointsViewSet', 'LedgerViewSet', 'PointsTransferViewSet', 'PointsConversionViewSet',
    # Tiers
    'TierViewSet', 'UserTierViewSet',
    # Earn
    'EarnRuleViewSet', 'BonusEventViewSet',
    # Redemption
    'RedemptionViewSet', 'VoucherViewSet', 'GiftCardViewSet',
    # Engagement
    'StreakViewSet', 'BadgeViewSet', 'ChallengeViewSet', 'LeaderboardViewSet',
    # Advanced -- original
    'CampaignViewSet', 'InsightViewSet', 'AdminLoyaltyViewSet', 'PublicAPIViewSet',
    'OfferWallViewSet', 'ReferralViewSet', 'PartnerViewSet', 'RewardCatalogViewSet',
    # Advanced -- fixed
    'CashoutViewSet', 'NotificationViewSet',
    # Advanced -- NEW: Gamification
    'SpinWheelViewSet', 'ScratchCardViewSet', 'LotteryViewSet',
    'LeaderboardSeasonViewSet', 'QuizViewSet',
    # Advanced -- NEW: AI
    'CustomerAIProfileViewSet', 'PersonalizedOfferViewSet',
    'AIRecommendationViewSet', 'ChurnAlertViewSet',
    # Advanced -- NEW: Eco/Family
    'FamilyAccountViewSet', 'EcoViewSet', 'CharityViewSet',
    'ExperienceViewSet', 'ConsentViewSet',
    # Advanced -- NEW: Social/Receipt
    'ReceiptViewSet', 'SocialShareViewSet', 'ReviewViewSet', 'QRCodeViewSet',
    # Advanced -- NEW: Tenant/Admin
    'TenantViewSet', 'AdminAuditLogViewSet', 'SystemConfigViewSet',
]

# ── NEW: Customer Profile ─────────────────────────────────────────────────────
from .advanced.CustomerProfileViewSet import CustomerProfileViewSet

# ── NEW: SmartLink ────────────────────────────────────────────────────────────
from .advanced.SmartLinkViewSet import SmartLinkViewSet

# FIXED: decorators.py (audit_action, require_loyalty_active) was orphaned
# Imported here so viewsets can use: from ..viewsets import audit_action
try:
    from ..decorators import audit_action, require_loyalty_active, loyalty_rate_limit
except ImportError:
    pass

# FIXED: mixins.py (DjoyaltyTenantMixin, DjoyaltyAuditMixin) was orphaned
# Now exported from viewsets package for use in any ViewSet
try:
    from ..mixins import DjoyaltyTenantMixin, DjoyaltyAuditMixin, DjoyaltyOwnershipMixin
except ImportError:
    pass

# FIXED: dependencies.py (LoyaltyDependencies, get_customer_from_request) was orphaned
try:
    from ..dependencies import (
        LoyaltyDependencies,
        get_customer_from_request,
        get_tenant_from_request,
    )
except ImportError:
    pass
