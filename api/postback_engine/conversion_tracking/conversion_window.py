"""
conversion_tracking/conversion_window.py
──────────────────────────────────────────
Conversion window management.
Validates that a conversion falls within the allowed attribution window.
"""
from __future__ import annotations
from datetime import timedelta
from django.utils import timezone
from ..models import AdNetworkConfig, ClickLog
from ..exceptions import ConversionWindowExpiredException


class ConversionWindowChecker:

    def is_within_window(self, click_log: ClickLog, network: AdNetworkConfig) -> bool:
        window_hours = network.conversion_window_hours
        if window_hours == 0:
            return True
        cutoff = timezone.now() - timedelta(hours=window_hours)
        return click_log.clicked_at >= cutoff

    def assert_within_window(self, click_log: ClickLog, network: AdNetworkConfig) -> None:
        if not self.is_within_window(click_log, network):
            raise ConversionWindowExpiredException(
                f"Click {click_log.click_id} outside {network.conversion_window_hours}h window."
            )

    def get_window_end(self, click_log: ClickLog, network: AdNetworkConfig):
        return click_log.clicked_at + timedelta(hours=network.conversion_window_hours)


conversion_window_checker = ConversionWindowChecker()
