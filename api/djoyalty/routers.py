# api/djoyalty/routers.py
"""
Custom DRF router for Djoyalty।
Nested routes, versioning support।
"""
from rest_framework.routers import DefaultRouter, Route, DynamicRoute


class DjoyaltyRouter(DefaultRouter):
    """
    Extended DefaultRouter:
    - Trailing slash optional
    - Custom route names with djoyalty- prefix
    """
    include_root_view = True
    include_format_suffixes = False

    def get_urls(self):
        urls = super().get_urls()
        return urls

    def get_default_basename(self, viewset):
        """djoyalty- prefix add করো।"""
        basename = super().get_default_basename(viewset)
        return basename


def get_djoyalty_router():
    """Pre-configured router with all Djoyalty ViewSets।"""
    from .viewsets.core.CustomerViewSet import CustomerViewSet
    from .viewsets.core.TxnViewSet import TxnViewSet
    from .viewsets.core.EventViewSet import EventViewSet
    from .viewsets.points.PointsViewSet import PointsViewSet
    from .viewsets.points.LedgerViewSet import LedgerViewSet
    from .viewsets.points.PointsTransferViewSet import PointsTransferViewSet
    from .viewsets.points.PointsConversionViewSet import PointsConversionViewSet
    from .viewsets.tiers.TierViewSet import TierViewSet
    from .viewsets.tiers.UserTierViewSet import UserTierViewSet
    from .viewsets.earn.EarnRuleViewSet import EarnRuleViewSet
    from .viewsets.earn.BonusEventViewSet import BonusEventViewSet
    from .viewsets.redemption.RedemptionViewSet import RedemptionViewSet
    from .viewsets.redemption.VoucherViewSet import VoucherViewSet
    from .viewsets.redemption.GiftCardViewSet import GiftCardViewSet
    from .viewsets.engagement.StreakViewSet import StreakViewSet
    from .viewsets.engagement.BadgeViewSet import BadgeViewSet
    from .viewsets.engagement.ChallengeViewSet import ChallengeViewSet
    from .viewsets.engagement.LeaderboardViewSet import LeaderboardViewSet
    from .viewsets.advanced.CampaignViewSet import CampaignViewSet
    from .viewsets.advanced.InsightViewSet import InsightViewSet
    from .viewsets.advanced.AdminLoyaltyViewSet import AdminLoyaltyViewSet
    from .viewsets.advanced.PublicAPIViewSet import PublicAPIViewSet

    router = DjoyaltyRouter()
    router.register(r'customers', CustomerViewSet, basename='customer')
    router.register(r'transactions', TxnViewSet, basename='txn')
    router.register(r'events', EventViewSet, basename='event')
    router.register(r'points', PointsViewSet, basename='points')
    router.register(r'ledger', LedgerViewSet, basename='ledger')
    router.register(r'transfers', PointsTransferViewSet, basename='transfer')
    router.register(r'conversions', PointsConversionViewSet, basename='conversion')
    router.register(r'tiers', TierViewSet, basename='tier')
    router.register(r'user-tiers', UserTierViewSet, basename='user-tier')
    router.register(r'earn-rules', EarnRuleViewSet, basename='earn-rule')
    router.register(r'bonus-events', BonusEventViewSet, basename='bonus-event')
    router.register(r'redemptions', RedemptionViewSet, basename='redemption')
    router.register(r'vouchers', VoucherViewSet, basename='voucher')
    router.register(r'gift-cards', GiftCardViewSet, basename='gift-card')
    router.register(r'streaks', StreakViewSet, basename='streak')
    router.register(r'badges', BadgeViewSet, basename='badge')
    router.register(r'challenges', ChallengeViewSet, basename='challenge')
    router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')
    router.register(r'campaigns', CampaignViewSet, basename='campaign')
    router.register(r'insights', InsightViewSet, basename='insight')
    router.register(r'admin-loyalty', AdminLoyaltyViewSet, basename='admin-loyalty')
    router.register(r'public', PublicAPIViewSet, basename='public')
    return router
