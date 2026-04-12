# promotions/performance_bonus/tasks.py
from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def check_all_milestones():
    """Check and award milestones for all publishers — runs at 3 AM."""
    from django.contrib.auth import get_user_model
    from api.promotions.performance_bonus.milestone_bonus import MilestoneBonus
    User = get_user_model()
    bonus = MilestoneBonus()
    total_awarded = 0
    for user in User.objects.filter(is_active=True)[:1000]:
        try:
            awarded = bonus.check_and_award(user.id)
            total_awarded += len(awarded)
        except Exception as e:
            logger.error(f'Milestone check failed user {user.id}: {e}')
    logger.info(f'Milestone check done: {total_awarded} bonuses awarded')
    return {'total_awarded': total_awarded}
