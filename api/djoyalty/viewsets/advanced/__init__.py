# api/djoyalty/viewsets/advanced/__init__.py
"""
Djoyalty Advanced ViewSets Package -- UPDATED।
All new viewsets registered for clean imports।
"""
from .CampaignViewSet import CampaignViewSet
from .InsightViewSet import InsightViewSet
from .AdminLoyaltyViewSet import AdminLoyaltyViewSet
from .PublicAPIViewSet import PublicAPIViewSet
from .OfferWallViewSet import OfferWallViewSet
from .ReferralViewSet import ReferralViewSet
from .PartnerViewSet import PartnerViewSet
from .RewardCatalogViewSet import RewardCatalogViewSet

# Fixed
from .CashoutViewSet import CashoutViewSet
from .NotificationViewSet import NotificationViewSet

# NEW
from .GamificationViewSet import (
    SpinWheelViewSet, ScratchCardViewSet, LotteryViewSet,
    LeaderboardSeasonViewSet, QuizViewSet,
)
from .AIPersonalizationViewSet import (
    CustomerAIProfileViewSet, PersonalizedOfferViewSet,
    AIRecommendationViewSet, ChurnAlertViewSet,
)
from .EcoFamilyViewSet import (
    FamilyAccountViewSet, EcoViewSet, CharityViewSet,
    ExperienceViewSet, ConsentViewSet,
)
from .ReceiptSocialViewSet import (
    ReceiptViewSet, SocialShareViewSet, ReviewViewSet, QRCodeViewSet,
)
from .TenantViewSet import (
    TenantViewSet, AdminAuditLogViewSet, SystemConfigViewSet,
)

__all__ = [
    'CampaignViewSet', 'InsightViewSet', 'AdminLoyaltyViewSet', 'PublicAPIViewSet',
    'OfferWallViewSet', 'ReferralViewSet', 'PartnerViewSet', 'RewardCatalogViewSet',
    'CashoutViewSet', 'NotificationViewSet',
    'SpinWheelViewSet', 'ScratchCardViewSet', 'LotteryViewSet',
    'LeaderboardSeasonViewSet', 'QuizViewSet',
    'CustomerAIProfileViewSet', 'PersonalizedOfferViewSet',
    'AIRecommendationViewSet', 'ChurnAlertViewSet',
    'FamilyAccountViewSet', 'EcoViewSet', 'CharityViewSet',
    'ExperienceViewSet', 'ConsentViewSet',
    'ReceiptViewSet', 'SocialShareViewSet', 'ReviewViewSet', 'QRCodeViewSet',
    'TenantViewSet', 'AdminAuditLogViewSet', 'SystemConfigViewSet',
]

# NEW: Previously unexposed logic
from .AnalyticsViewSet import AnalyticsViewSet
from .ComplianceViewSet import ComplianceViewSet
from .SearchViewSet import SearchViewSet
from .MembershipViewSet import MembershipViewSet
from .POSViewSet import POSViewSet
from .CardLinkingViewSet import CardLinkingViewSet
from .PendingPointsViewSet import PendingPointsViewSet
from .PromotionViewSet import PromotionViewSet
from .SubscriptionViewSet import SubscriptionViewSet
from .Web3ViewSet import Web3ViewSet, DAOGovernanceViewSet
from .OmnichannelViewSet import OmnichannelViewSet, PushNotificationViewSet, PointsStackingViewSet
from .AIRealtimeViewSet import AIRealtimeViewSet
from .SDKViewSet import SDKViewSet, ExportViewSet
