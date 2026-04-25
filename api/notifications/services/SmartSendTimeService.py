# earning_backend/api/notifications/services/SmartSendTimeService.py
"""
SmartSendTimeService — Send-time optimization (like OneSignal/Braze Intelligent Timing).

Analyzes each user's historical notification open times to find their
optimal delivery window. Falls back to timezone-aware defaults.

Algorithm:
  1. Collect last 30 days of notification open_at times for the user
  2. Build an hourly histogram of opens
  3. Find the peak hour — that's the optimal send time
  4. If no history → use timezone-based defaults (morning 9am / evening 7pm)
  5. Respect DND schedule — shift if needed

OneSignal calls this "Intelligent Delivery".
Braze calls this "Intelligent Timing".
"""

import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple

import pytz
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default send windows per timezone offset (UTC+N)
DEFAULT_SEND_HOUR_BY_REGION = {
    # Asia/Dhaka (UTC+6) → 9am local
    6: 9,
    # UTC+5.5 (India)
    5: 9,
    # UTC+8 (China, Malaysia, Philippines)
    8: 9,
    # UTC+0 (UK, West Africa)
    0: 10,
    # UTC-5 (US Eastern)
    -5: 10,
    # Default
    'default': 9,
}


class SmartSendTimeService:
    """
    Calculates the optimal notification send time for a user based on
    their historical open behaviour and timezone.
    """

    ANALYSIS_DAYS = 30        # Look back window
    MIN_OPENS_FOR_ANALYSIS = 5  # Min data points before using ML prediction
    FALLBACK_MORNING_HOUR = 9   # 9 AM local time
    FALLBACK_EVENING_HOUR = 19  # 7 PM local time

    def get_optimal_send_time(
        self,
        user,
        notification=None,
        prefer_window: str = 'any',
    ) -> datetime:
        """
        Return the next optimal UTC datetime to send a notification to this user.

        Args:
            user:           Django User instance.
            notification:   Optional Notification instance (used to check priority).
            prefer_window:  'morning' | 'evening' | 'any' — preferred send window.

        Returns:
            UTC datetime for optimal send time.
        """
        # Critical/urgent notifications: send immediately
        if notification:
            priority = getattr(notification, 'priority', 'medium') or 'medium'
            if priority in ('critical', 'urgent'):
                return timezone.now()

        user_tz = self._get_user_timezone(user)
        optimal_hour = self._get_optimal_hour(user, user_tz, prefer_window)
        send_dt = self._next_occurrence_of_hour(optimal_hour, user_tz)

        # Check DND and shift if needed
        send_dt = self._respect_dnd(user, send_dt, user_tz)

        logger.debug(
            f'SmartSendTime: user #{user.pk} → {send_dt.isoformat()} '
            f'(optimal hour {optimal_hour}, tz {user_tz})'
        )
        return send_dt

    def get_optimal_hour(self, user) -> int:
        """Return the optimal send hour (0-23) in user's local timezone."""
        user_tz = self._get_user_timezone(user)
        return self._get_optimal_hour(user, user_tz, 'any')

    def bulk_optimal_times(self, user_ids: List[int]) -> Dict[int, datetime]:
        """
        Return optimal send times for multiple users.
        Used by CampaignService for timezone-aware campaign sends.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        result: Dict[int, datetime] = {}
        users = User.objects.filter(pk__in=user_ids, is_active=True).select_related('profile')

        for user in users:
            try:
                result[user.pk] = self.get_optimal_send_time(user)
            except Exception as exc:
                logger.warning(f'SmartSendTime.bulk: user #{user.pk}: {exc}')
                result[user.pk] = timezone.now() + timedelta(minutes=5)

        return result

    def analyze_user_open_history(self, user) -> Dict:
        """
        Analyze user's notification open history.

        Returns dict with:
            - hourly_histogram: {0..23: count}
            - peak_hour: int
            - open_count: int
            - confidence: float (0.0-1.0)
        """
        from notifications.models import Notification

        cutoff = timezone.now() - timedelta(days=self.ANALYSIS_DAYS)
        opens = Notification.objects.filter(
            user=user,
            is_read=True,
            read_at__gte=cutoff,
            read_at__isnull=False,
        ).values_list('read_at', flat=True)

        user_tz = self._get_user_timezone(user)
        tz = pytz.timezone(user_tz)

        hourly: Dict[int, int] = {h: 0 for h in range(24)}
        for read_at in opens:
            local_dt = read_at.astimezone(tz)
            hourly[local_dt.hour] += 1

        total_opens = sum(hourly.values())
        peak_hour = max(hourly, key=hourly.get) if total_opens > 0 else self.FALLBACK_MORNING_HOUR
        confidence = min(1.0, total_opens / (self.MIN_OPENS_FOR_ANALYSIS * 4))

        return {
            'hourly_histogram': hourly,
            'peak_hour': peak_hour,
            'open_count': total_opens,
            'confidence': round(confidence, 2),
            'has_enough_data': total_opens >= self.MIN_OPENS_FOR_ANALYSIS,
            'user_timezone': user_tz,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_optimal_hour(self, user, user_tz: str, prefer_window: str) -> int:
        """Determine the optimal send hour using history or defaults."""
        try:
            analysis = self.analyze_user_open_history(user)
            if analysis['has_enough_data']:
                peak_hour = analysis['peak_hour']
                # Apply window preference
                if prefer_window == 'morning' and not (6 <= peak_hour <= 12):
                    return self.FALLBACK_MORNING_HOUR
                if prefer_window == 'evening' and not (17 <= peak_hour <= 22):
                    return self.FALLBACK_EVENING_HOUR
                return peak_hour
        except Exception as exc:
            logger.debug(f'_get_optimal_hour analysis error: {exc}')

        # Fallback to timezone-based default
        return self._timezone_default_hour(user_tz, prefer_window)

    def _timezone_default_hour(self, user_tz: str, prefer_window: str) -> int:
        """Return a reasonable default send hour for a timezone."""
        try:
            tz = pytz.timezone(user_tz)
            # Get UTC offset in hours
            now_local = datetime.now(tz)
            utc_offset = int(now_local.utcoffset().total_seconds() / 3600)
            base_hour = DEFAULT_SEND_HOUR_BY_REGION.get(utc_offset, 9)
        except Exception:
            base_hour = 9

        if prefer_window == 'evening':
            return self.FALLBACK_EVENING_HOUR
        return base_hour

    def _get_user_timezone(self, user) -> str:
        """Get the user's timezone string. Falls back to 'Asia/Dhaka'."""
        # Try DeviceToken timezone
        try:
            from notifications.models import DeviceToken
            device = DeviceToken.objects.filter(
                user=user, is_active=True
            ).exclude(timezone='').first()
            if device and device.timezone:
                pytz.timezone(device.timezone)  # validate
                return device.timezone
        except Exception:
            pass

        # Try user profile timezone
        for attr in ('timezone', 'time_zone'):
            tz_str = getattr(getattr(user, 'profile', None), attr, None)
            if tz_str:
                try:
                    pytz.timezone(tz_str)
                    return tz_str
                except Exception:
                    pass

        return 'Asia/Dhaka'  # Default for BD earning sites

    def _next_occurrence_of_hour(self, hour: int, user_tz: str) -> datetime:
        """Return the next UTC datetime when it will be `hour` in user's timezone."""
        try:
            tz = pytz.timezone(user_tz)
            now_local = datetime.now(tz)
            target = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now_local:
                target += timedelta(days=1)
            return target.astimezone(pytz.utc).replace(tzinfo=timezone.utc)
        except Exception:
            return timezone.now() + timedelta(hours=1)

    def _respect_dnd(self, user, send_dt: datetime, user_tz: str) -> datetime:
        """Shift send_dt forward if it falls inside user's DND window."""
        try:
            from notifications.models import NotificationPreference
            pref = NotificationPreference.objects.filter(user=user).first()
            if not pref:
                return send_dt

            dnd_enabled = getattr(pref, 'quiet_hours_enabled', False) or getattr(pref, 'do_not_disturb', False)
            if not dnd_enabled:
                return send_dt

            dnd_start = getattr(pref, 'quiet_hours_start', None)
            dnd_end = getattr(pref, 'quiet_hours_end', None)
            if not dnd_start or not dnd_end:
                return send_dt

            tz = pytz.timezone(user_tz)
            local_dt = send_dt.astimezone(tz)
            local_time = local_dt.time()

            in_dnd = (
                (dnd_start > dnd_end and (local_time >= dnd_start or local_time <= dnd_end)) or
                (dnd_start <= dnd_end and dnd_start <= local_time <= dnd_end)
            )

            if in_dnd:
                # Shift to just after DND end
                next_ok = local_dt.replace(
                    hour=dnd_end.hour,
                    minute=dnd_end.minute + 5,
                    second=0, microsecond=0,
                )
                if next_ok <= local_dt:
                    next_ok += timedelta(days=1)
                return next_ok.astimezone(pytz.utc).replace(tzinfo=timezone.utc)

        except Exception as exc:
            logger.debug(f'_respect_dnd: {exc}')

        return send_dt


# Singleton
smart_send_time_service = SmartSendTimeService()
