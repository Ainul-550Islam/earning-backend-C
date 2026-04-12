"""
click_tracking/click_device_tracker.py
────────────────────────────────────────
Device-based click tracking.
Tracks clicks per device fingerprint to detect device farms.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from ..models import ClickLog

logger = logging.getLogger(__name__)


class ClickDeviceTracker:

    def get_offer_count_for_device(
        self, fingerprint: str, hours: int = 24
    ) -> int:
        """How many different offers this device clicked in last N hours."""
        if not fingerprint:
            return 0
        cutoff = timezone.now() - timedelta(hours=hours)
        return ClickLog.objects.filter(
            device_fingerprint=fingerprint,
            clicked_at__gte=cutoff,
        ).values("offer_id").distinct().count()

    def get_user_count_for_device(
        self, fingerprint: str, hours: int = 24
    ) -> int:
        """
        How many different users clicked from this device.
        > 1 = shared device or device farm.
        """
        if not fingerprint:
            return 0
        cutoff = timezone.now() - timedelta(hours=hours)
        return (
            ClickLog.objects.filter(
                device_fingerprint=fingerprint,
                clicked_at__gte=cutoff,
            )
            .exclude(user=None)
            .values("user_id")
            .distinct()
            .count()
        )

    def is_device_farm(self, fingerprint: str) -> bool:
        """
        A device is likely a farm if it:
        - Served > 3 different users in 24h, OR
        - Clicked > 20 different offers in 1h
        """
        if not fingerprint:
            return False
        return (
            self.get_user_count_for_device(fingerprint, hours=24) > 3
            or self.get_offer_count_for_device(fingerprint, hours=1) > 20
        )


click_device_tracker = ClickDeviceTracker()
