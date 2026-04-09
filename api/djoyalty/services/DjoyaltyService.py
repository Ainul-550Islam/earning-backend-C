# api/djoyalty/services/DjoyaltyService.py
"""
Main DjoyaltyService facade — সব sub-services এর entry point।
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class DjoyaltyService:
    """Loyalty system main facade।"""

    @staticmethod
    def get_customer_balance(customer) -> Decimal:
        try:
            lp = customer.loyalty_points.first()
            return lp.balance if lp else Decimal('0')
        except Exception as e:
            logger.debug('Balance error: %s', e)
            return Decimal('0')

    @staticmethod
    def earn_points(customer, spend_amount: Decimal, txn=None, tenant=None) -> Decimal:
        from .points.PointsEngine import PointsEngine
        return PointsEngine.process_earn(customer, spend_amount, txn=txn, tenant=tenant)

    @staticmethod
    def redeem_points(customer, points: Decimal, redemption_type: str = 'cashback', tenant=None):
        from .redemption.RedemptionService import RedemptionService
        return RedemptionService.create_request(customer, points, redemption_type, tenant=tenant)

    @staticmethod
    def get_or_create_loyalty_points(customer, tenant=None):
        from ..models.points import LoyaltyPoints
        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
        )
        return lp

    @staticmethod
    def evaluate_tier(customer, tenant=None):
        from .tiers.TierEvaluationService import TierEvaluationService
        return TierEvaluationService.evaluate(customer, tenant=tenant)

    @staticmethod
    def get_active_campaigns(tenant=None):
        from ..models.campaigns import LoyaltyCampaign
        qs = LoyaltyCampaign.active_campaigns.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def award_badge(customer, badge_trigger: str, current_value: Decimal = None):
        from .engagement.BadgeService import BadgeService
        return BadgeService.check_and_award(customer, badge_trigger, current_value)

    @staticmethod
    def update_streak(customer, activity_date=None):
        from .engagement.StreakService import StreakService
        return StreakService.record_activity(customer, activity_date)

    @staticmethod
    def get_leaderboard(tenant=None, limit: int = 10):
        from .engagement.LeaderboardService import LeaderboardService
        return LeaderboardService.get_top_customers(tenant=tenant, limit=limit)
