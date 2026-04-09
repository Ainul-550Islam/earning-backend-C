# api/djoyalty/services/engagement/MilestoneService.py
import logging
from decimal import Decimal
from ...models.engagement import Milestone, UserMilestone

logger = logging.getLogger(__name__)

class MilestoneService:
    @staticmethod
    def check_milestones(customer, milestone_type: str, current_value: Decimal, tenant=None):
        milestones = Milestone.objects.filter(milestone_type=milestone_type, is_active=True, threshold__lte=current_value)
        for milestone in milestones:
            if not UserMilestone.objects.filter(customer=customer, milestone=milestone).exists():
                UserMilestone.objects.create(
                    customer=customer, milestone=milestone, points_awarded=milestone.points_reward,
                )
                if milestone.points_reward > 0:
                    from ..earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        customer, milestone.points_reward,
                        reason=f'Milestone: {milestone.name}',
                        triggered_by='milestone', tenant=tenant,
                    )
