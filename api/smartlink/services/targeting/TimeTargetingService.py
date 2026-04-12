import logging
from django.utils import timezone

logger = logging.getLogger('smartlink.targeting.time')


class TimeTargetingService:
    """Day-of-week and hour-of-day targeting evaluation."""

    def matches(self, time_targeting, day_of_week: int, hour: int) -> bool:
        if time_targeting is None:
            return True
        return time_targeting.matches(day_of_week=day_of_week, hour=hour)

    def get_current_day_hour(self, timezone_name: str = 'UTC') -> tuple:
        """
        Get current day of week and hour in the specified timezone.
        Returns (day_of_week, hour) where day_of_week: 0=Monday, 6=Sunday.
        """
        try:
            import pytz
            tz = pytz.timezone(timezone_name)
            now = timezone.now().astimezone(tz)
            return now.weekday(), now.hour
        except Exception:
            now = timezone.now()
            return now.weekday(), now.hour
