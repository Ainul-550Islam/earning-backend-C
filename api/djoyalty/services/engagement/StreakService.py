# api/djoyalty/services/engagement/StreakService.py
import logging
from django.utils import timezone
from ...models.engagement import DailyStreak, StreakReward
from ...constants import STREAK_MILESTONES, STREAK_RESET_AFTER_DAYS
from .BadgeService import BadgeService

logger = logging.getLogger(__name__)

class StreakService:
    @staticmethod
    def record_activity(customer, activity_date=None, tenant=None):
        today = (activity_date or timezone.now()).date()
        streak, _ = DailyStreak.objects.get_or_create(
            customer=customer, tenant=tenant or customer.tenant,
            defaults={'current_streak': 0, 'longest_streak': 0, 'is_active': True},
        )
        last = streak.last_activity_date
        if last == today:
            return streak
        from datetime import timedelta
        if last and (today - last).days == 1:
            streak.current_streak += 1
        elif last and (today - last).days > STREAK_RESET_AFTER_DAYS:
            streak.current_streak = 1
            streak.is_active = True
            streak.started_at = today
        else:
            streak.current_streak = 1
            streak.started_at = today
        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
        streak.last_activity_date = today
        streak.save()
        StreakService._check_milestones(customer, streak)
        return streak

    @staticmethod
    def _check_milestones(customer, streak):
        for days, bonus_points in sorted(STREAK_MILESTONES.items()):
            if streak.current_streak >= days:
                if not StreakReward.objects.filter(customer=customer, milestone_days=days).exists():
                    from ..earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        customer, bonus_points,
                        reason=f'{days}-day streak milestone',
                        triggered_by='streak',
                    )
                    StreakReward.objects.create(
                        customer=customer, streak=streak,
                        milestone_days=days, points_awarded=bonus_points,
                    )
