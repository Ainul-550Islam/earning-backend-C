# services/geo/TimezoneService.py
"""Timezone service"""
import logging
from typing import Dict, List, Optional
import pytz

logger = logging.getLogger(__name__)


class TimezoneService:
    """Timezone conversion, detection, and info service"""

    def get_current_time(self, timezone_name: str) -> Optional[str]:
        try:
            from django.utils import timezone
            tz = pytz.timezone(timezone_name)
            return timezone.now().astimezone(tz).isoformat()
        except Exception as e:
            logger.error(f"Get current time failed for {timezone_name}: {e}")
            return None

    def detect_from_coordinates(self, latitude: float, longitude: float) -> Optional[str]:
        """Lat/lng থেকে timezone detect করে"""
        try:
            import urllib.request, json
            url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={latitude}&longitude={longitude}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return data.get('timeZone')
        except Exception as e:
            logger.error(f"Timezone detect failed: {e}")
            return None

    def convert_time(self, datetime_str: str, from_tz: str, to_tz: str) -> Optional[str]:
        """Time একটি timezone থেকে অন্যটিতে convert করে"""
        try:
            from datetime import datetime
            from_timezone = pytz.timezone(from_tz)
            to_timezone = pytz.timezone(to_tz)
            dt = datetime.fromisoformat(datetime_str)
            if dt.tzinfo is None:
                dt = from_timezone.localize(dt)
            converted = dt.astimezone(to_timezone)
            return converted.isoformat()
        except Exception as e:
            logger.error(f"Time convert failed: {e}")
            return None

    def get_utc_offset(self, timezone_name: str) -> Optional[str]:
        try:
            from django.utils import timezone
            tz = pytz.timezone(timezone_name)
            now = timezone.now().astimezone(tz)
            offset = now.utcoffset()
            total_seconds = int(offset.total_seconds())
            sign = '+' if total_seconds >= 0 else '-'
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            return f"UTC{sign}{hours:02d}:{minutes:02d}"
        except Exception as e:
            logger.error(f"UTC offset failed: {e}")
            return None
