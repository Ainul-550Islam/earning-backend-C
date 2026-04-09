# api/djoyalty/admin/_force_register.py
def force_register_all():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        from ..models.core import Customer, Txn, Event
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..models.tiers import LoyaltyTier, UserTier
        from ..models.earn_rules import EarnRule
        from ..models.redemption import RedemptionRequest, Voucher, GiftCard
        from ..models.engagement import Badge, UserBadge, DailyStreak, Challenge
        from ..models.campaigns import LoyaltyCampaign, PartnerMerchant
        from ..models.advanced import PointsAbuseLog, LoyaltyInsight
        from .customer_admin import CustomerAdmin
        from .points_admin import LoyaltyPointsAdmin, PointsLedgerAdmin
        pairs = [
            (Customer, CustomerAdmin), (LoyaltyPoints, LoyaltyPointsAdmin),
            (PointsLedger, PointsLedgerAdmin),
        ]
        for model, admin_class in pairs:
            if model not in modern_site._registry:
                try:
                    modern_site.register(model, admin_class)
                except Exception:
                    pass
    except Exception:
        pass
