"""
api/ai_engine/AUTOMATION_AGENTS/scheduling_agent.py
====================================================
Scheduling Agent — intelligent timing for campaigns, notifications, tasks।
Peak engagement time detection ও optimal send time calculation।
Timezone-aware, user behavior pattern based scheduling।
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SchedulingAgent:
    """
    Intelligent scheduling agent।
    Best time to send push notifications, emails, campaigns।
    User timezone + peak hours + behavioral patterns।
    """

    # Default peak hours by type (Bangladesh standard)
    PEAK_HOURS_BD = {
        "push_notification": [8, 9, 10, 13, 18, 19, 20, 21],
        "email":             [9, 10, 11, 14, 15, 18, 19],
        "sms":               [10, 11, 14, 18, 19, 20],
        "offer_launch":      [9, 10, 13, 18, 19, 20],
        "campaign_start":    [9, 10, 14, 18],
    }

    WEEKDAY_WEIGHTS = {
        0: 0.85,  # Monday
        1: 0.90,  # Tuesday
        2: 0.95,  # Wednesday
        3: 1.00,  # Thursday
        4: 1.05,  # Friday
        5: 1.10,  # Saturday (highest)
        6: 1.05,  # Sunday
    }

    def get_optimal_send_time(self, user=None, channel: str = "push_notification",
                               user_timezone: str = "Asia/Dhaka",
                               preferred_hour: int = None) -> dict:
        """
        Individual user বা general peak এর জন্য optimal send time।
        """
        from django.utils import timezone

        now = timezone.now()

        # User-specific preferred hour
        if preferred_hour and preferred_hour in self.PEAK_HOURS_BD.get(channel, []):
            return {
                "optimal_hour":       preferred_hour,
                "optimal_datetime":   self._next_occurrence(preferred_hour, user_timezone),
                "confidence":         0.90,
                "reason":             "Based on user preference history",
                "channel":            channel,
            }

        # User behavior-based optimal hour
        if user:
            user_hour = self._get_user_peak_hour(user)
            if user_hour:
                return {
                    "optimal_hour":       user_hour,
                    "optimal_datetime":   self._next_occurrence(user_hour, user_timezone),
                    "confidence":         0.85,
                    "reason":             "Based on user's historical activity pattern",
                    "channel":            channel,
                }

        # Default: next peak hour
        peak_hours = self.PEAK_HOURS_BD.get(channel, self.PEAK_HOURS_BD["push_notification"])
        current_hour = now.hour
        upcoming     = [h for h in peak_hours if h > current_hour]
        optimal_hour = upcoming[0] if upcoming else peak_hours[0]

        return {
            "optimal_hour":       optimal_hour,
            "optimal_datetime":   self._next_occurrence(optimal_hour, user_timezone),
            "confidence":         0.75,
            "reason":             "Based on general population peak engagement",
            "channel":            channel,
            "peak_hours":         peak_hours,
        }

    def _get_user_peak_hour(self, user) -> Optional[int]:
        """User এর historical login patterns থেকে peak hour বের করো।"""
        try:
            from ..models import PredictionLog
            from django.db.models import Count

            logs = PredictionLog.objects.filter(
                user=user
            ).values("created_at__hour").annotate(count=Count("id")).order_by("-count")[:3]

            if logs:
                return logs[0]["created_at__hour"]
        except Exception:
            pass
        return None

    def _next_occurrence(self, hour: int, timezone_str: str = "Asia/Dhaka") -> str:
        """Next occurrence of a given hour।"""
        from django.utils import timezone as dj_tz
        import pytz

        try:
            tz  = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            from django.utils import timezone
            return str(timezone.now())

    def schedule_campaign(self, campaign: dict, audience_size: int,
                           start_date: datetime = None) -> dict:
        """
        Campaign scheduling plan তৈরি করো।
        Audience size অনুযায়ী send rate calculate করো।
        """
        from django.utils import timezone

        start   = start_date or timezone.now()
        channel = campaign.get("channel", "push_notification")
        name    = campaign.get("name", "Campaign")

        # Sending rate limits (to avoid spam perception)
        MAX_PER_HOUR = {
            "push_notification": 50000,
            "email":             20000,
            "sms":               10000,
        }.get(channel, 10000)

        hours_needed = max(1, audience_size // MAX_PER_HOUR)
        peak_hours   = self.PEAK_HOURS_BD.get(channel, self.PEAK_HOURS_BD["push_notification"])

        # Build schedule
        schedule = []
        remaining = audience_size
        current_time = start

        for i in range(min(hours_needed + 1, 24)):
            send_at_hour = peak_hours[i % len(peak_hours)]
            batch_size   = min(remaining, MAX_PER_HOUR)
            if batch_size <= 0:
                break

            send_dt = current_time.replace(hour=send_at_hour, minute=0)
            if send_dt <= current_time:
                send_dt += timedelta(days=1 if send_at_hour <= current_time.hour else 0)

            schedule.append({
                "batch":      i + 1,
                "send_at":    send_dt.strftime("%Y-%m-%d %H:%M"),
                "batch_size": batch_size,
                "channel":    channel,
            })
            remaining  -= batch_size
            current_time = send_dt + timedelta(hours=1)

        end_date = schedule[-1]["send_at"] if schedule else str(start)

        return {
            "campaign_name":    name,
            "total_audience":   audience_size,
            "channel":          channel,
            "schedule":         schedule,
            "total_batches":    len(schedule),
            "estimated_start":  schedule[0]["send_at"] if schedule else None,
            "estimated_end":    end_date,
            "recommended_time": self.get_optimal_send_time(channel=channel),
        }

    def bulk_schedule(self, users: List, channel: str = "push_notification",
                       message: str = "") -> dict:
        """Multiple users group করে optimal time এ schedule করো।"""
        timezone_groups: Dict[str, List] = {}
        for user in users:
            tz = getattr(user, "timezone", "Asia/Dhaka")
            timezone_groups.setdefault(tz, []).append(user)

        schedules = []
        for tz, tz_users in timezone_groups.items():
            optimal = self.get_optimal_send_time(
                user=tz_users[0] if tz_users else None,
                channel=channel,
                user_timezone=tz
            )
            schedules.append({
                "timezone":     tz,
                "user_count":   len(tz_users),
                "send_at":      optimal["optimal_datetime"],
                "optimal_hour": optimal["optimal_hour"],
            })

        return {
            "total_users":    len(users),
            "channel":        channel,
            "timezone_groups": len(timezone_groups),
            "schedules":      schedules,
        }

    def get_engagement_calendar(self, month: int, year: int) -> List[Dict]:
        """Monthly engagement calendar — best days ও hours।"""
        import calendar
        cal = calendar.monthcalendar(year, month)
        result = []

        for week in cal:
            for day in week:
                if day == 0:
                    continue
                dow      = datetime(year, month, day).weekday()
                weight   = self.WEEKDAY_WEIGHTS.get(dow, 1.0)
                day_name = calendar.day_name[dow]

                result.append({
                    "date":            f"{year}-{month:02d}-{day:02d}",
                    "day_name":        day_name,
                    "engagement_weight": weight,
                    "is_peak_day":     weight >= 1.05,
                    "best_hours":      self.PEAK_HOURS_BD["push_notification"][:3],
                    "recommendation":  "High engagement day — launch campaigns" if weight >= 1.05 else "Normal day",
                })

        return sorted(result, key=lambda x: x["engagement_weight"], reverse=True)
