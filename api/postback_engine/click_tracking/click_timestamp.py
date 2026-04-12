"""
click_tracking/click_timestamp.py
───────────────────────────────────
Click timestamp management and validation.
Tracks click timing for conversion window enforcement,
time-anomaly fraud detection, and performance analytics.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Optional, Tuple
from django.utils import timezone
from ..models import ClickLog

logger = logging.getLogger(__name__)


class ClickTimestamp:

    def get_time_to_convert(self, click_log: ClickLog) -> Optional[int]:
        """
        Return seconds between click and now.
        Returns None if click has not converted yet.
        """
        if not click_log.converted_at:
            return None
        delta = click_log.converted_at - click_log.clicked_at
        return max(0, int(delta.total_seconds()))

    def is_within_window(self, click_log: ClickLog, window_hours: int) -> bool:
        """Check if a click is within the conversion window."""
        if window_hours == 0:
            return True
        cutoff = timezone.now() - timedelta(hours=window_hours)
        return click_log.clicked_at >= cutoff

    def is_suspicious_timing(self, time_to_convert_seconds: int) -> Tuple[bool, str]:
        """
        Check if the conversion timing is suspicious.
        Returns (is_suspicious, reason).
        """
        if time_to_convert_seconds < 3:
            return True, f"Conversion in {time_to_convert_seconds}s — possible click injection."
        if time_to_convert_seconds < 10:
            return True, f"Conversion in {time_to_convert_seconds}s — very fast (possible bot)."
        return False, ""

    def get_average_conversion_time(self, offer_id: str, days: int = 30) -> Optional[float]:
        """Return average click-to-conversion time for an offer in seconds."""
        from django.db.models import Avg
        cutoff = timezone.now() - timedelta(days=days)
        result = ClickLog.objects.filter(
            offer_id=offer_id,
            converted=True,
            converted_at__gte=cutoff,
        ).aggregate(avg=Avg("converted_at") - Avg("clicked_at"))
        # Note: direct timedelta avg not straightforward in ORM,
        # so return a rough estimate from available data
        sample = ClickLog.objects.filter(
            offer_id=offer_id,
            converted=True,
            clicked_at__gte=cutoff,
        ).values_list("clicked_at", "converted_at")[:100]
        if not sample:
            return None
        total_seconds = sum(
            (c - k).total_seconds() for k, c in sample if c and k
        )
        return total_seconds / len(sample) if sample else None

    def flag_late_conversion(
        self, click_log: ClickLog, max_days: int = 30
    ) -> bool:
        """Flag if conversion came suspiciously late (> max_days after click)."""
        if not click_log.converted_at:
            return False
        delta = click_log.converted_at - click_log.clicked_at
        return delta.days > max_days


click_timestamp = ClickTimestamp()
