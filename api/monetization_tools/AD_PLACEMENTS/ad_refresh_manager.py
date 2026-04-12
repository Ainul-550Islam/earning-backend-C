"""AD_PLACEMENTS/ad_refresh_manager.py — Banner auto-refresh logic."""
import time
from typing import Optional


class AdRefreshManager:
    """Manages banner auto-refresh timing and viewability gates."""

    DEFAULT_REFRESH_SEC    = 30
    MIN_REFRESH_SEC        = 10
    MAX_REFRESH_SEC        = 300
    MIN_VIEWABILITY_PCT    = 50.0  # must be 50% visible to refresh

    def __init__(self, refresh_rate: int = DEFAULT_REFRESH_SEC):
        self.refresh_rate   = max(self.MIN_REFRESH_SEC,
                                   min(self.MAX_REFRESH_SEC, refresh_rate))
        self._last_refresh  = time.monotonic()
        self._refresh_count = 0

    def should_refresh(self, viewability_pct: float = 100.0) -> bool:
        elapsed = time.monotonic() - self._last_refresh
        if elapsed < self.refresh_rate:
            return False
        if viewability_pct < self.MIN_VIEWABILITY_PCT:
            return False
        return True

    def record_refresh(self):
        self._last_refresh   = time.monotonic()
        self._refresh_count += 1

    @property
    def total_refreshes(self) -> int:
        return self._refresh_count

    @classmethod
    def get_optimal_rate(cls, position: str) -> int:
        rates = {
            "top": 30, "bottom": 30, "mid_content": 45,
            "sidebar": 60, "in_feed": 0,  # no refresh for in-feed
        }
        return rates.get(position, cls.DEFAULT_REFRESH_SEC)
