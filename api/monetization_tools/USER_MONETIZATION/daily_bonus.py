"""USER_MONETIZATION/daily_bonus.py — Daily login bonus management."""
from ..services import DailyStreakService


class DailyBonus:
    @classmethod
    def claim(cls, user) -> dict:
        return DailyStreakService.check_in(user)

    @classmethod
    def status(cls, user) -> dict:
        from ..models import DailyStreak
        from django.utils import timezone
        streak, _ = DailyStreak.objects.get_or_create(user=user)
        return {
            "current_streak":  streak.current_streak,
            "today_claimed":   streak.today_claimed,
            "last_login_date": str(streak.last_login_date) if streak.last_login_date else None,
            "total_coins":     str(streak.total_streak_coins),
        }
