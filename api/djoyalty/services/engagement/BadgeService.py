# api/djoyalty/services/engagement/BadgeService.py
import logging
from decimal import Decimal
from ...models.engagement import Badge, UserBadge
from ...exceptions import BadgeAlreadyUnlockedError

logger = logging.getLogger(__name__)

class BadgeService:
    @staticmethod
    def check_and_award(customer, trigger: str, current_value: Decimal = None, tenant=None):
        badges = Badge.objects.filter(trigger=trigger, is_active=True)
        awarded = []
        for badge in badges:
            if current_value is not None and current_value < badge.threshold:
                continue
            if badge.is_unique and UserBadge.objects.filter(customer=customer, badge=badge).exists():
                continue
            ub = UserBadge.objects.create(
                customer=customer, badge=badge, points_awarded=badge.points_reward,
            )
            if badge.points_reward > 0:
                from ..earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, badge.points_reward,
                    reason=f'Badge unlocked: {badge.name}',
                    triggered_by='badge', tenant=tenant,
                )
            awarded.append(ub)
            logger.info('Badge %s awarded to %s', badge.name, customer)
        return awarded
