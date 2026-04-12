"""AD_QUALITY/viewability_tracker.py — Ad viewability tracking."""
from decimal import Decimal
from django.core.cache import cache


class ViewabilityTracker:
    MRC_THRESHOLD_DISPLAY_PCT = 50.0
    MRC_THRESHOLD_DISPLAY_SEC = 1.0
    MRC_THRESHOLD_VIDEO_PCT   = 50.0
    MRC_THRESHOLD_VIDEO_SEC   = 2.0

    @classmethod
    def is_viewable(cls, pct_visible: float, duration_sec: float,
                     ad_format: str = "banner") -> bool:
        if ad_format in ("video", "rewarded_video"):
            return pct_visible >= cls.MRC_THRESHOLD_VIDEO_PCT and duration_sec >= cls.MRC_THRESHOLD_VIDEO_SEC
        return pct_visible >= cls.MRC_THRESHOLD_DISPLAY_PCT and duration_sec >= cls.MRC_THRESHOLD_DISPLAY_SEC

    @classmethod
    def update_rate(cls, ad_unit_id: int, viewable: bool):
        key    = f"mt:vr:{ad_unit_id}"
        total  = int(cache.get(f"{key}_total", 0)) + 1
        viewed = int(cache.get(f"{key}_viewed", 0)) + (1 if viewable else 0)
        cache.set(f"{key}_total",  total,  86400)
        cache.set(f"{key}_viewed", viewed, 86400)

    @classmethod
    def current_rate(cls, ad_unit_id: int) -> Decimal:
        key    = f"mt:vr:{ad_unit_id}"
        total  = int(cache.get(f"{key}_total", 0))
        viewed = int(cache.get(f"{key}_viewed", 0))
        if not total:
            return Decimal("0")
        return (Decimal(viewed) / total * 100).quantize(Decimal("0.0001"))
