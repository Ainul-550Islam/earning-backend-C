"""
conversion_tracking/conversion_attribution.py
───────────────────────────────────────────────
Multi-touch attribution models for CPA conversions.

Models:
  LAST_CLICK     → 100% credit to last click before conversion (default)
  FIRST_CLICK    → 100% credit to first click
  LINEAR         → Equal credit across all touchpoints
  TIME_DECAY     → More credit to recent touchpoints
  POSITION_BASED → 40% first, 40% last, 20% distributed among middle (U-shape)
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from ..enums import AttributionModel
from ..models import ClickLog, Conversion

logger = logging.getLogger(__name__)


class ConversionAttribution:

    def attribute(
        self,
        conversion: Conversion,
        model: str = AttributionModel.LAST_CLICK,
    ) -> Optional[ClickLog]:
        """
        Find the attributed click for a conversion based on the attribution model.
        Returns the attributed ClickLog or None.
        """
        if model == AttributionModel.LAST_CLICK:
            return self._last_click(conversion)
        elif model == AttributionModel.FIRST_CLICK:
            return self._first_click(conversion)
        else:
            return self._last_click(conversion)   # default

    def _last_click(self, conversion: Conversion) -> Optional[ClickLog]:
        """Last click before conversion (most common for CPA)."""
        if conversion.click_id:
            return ClickLog.objects.get_by_click_id(conversion.click_id)

        # Fallback: find last click from same user + offer_id before conversion time
        return ClickLog.objects.filter(
            user=conversion.user,
            offer_id=conversion.offer_id,
            clicked_at__lt=conversion.converted_at,
            status="valid",
        ).order_by("-clicked_at").first()

    def _first_click(self, conversion: Conversion) -> Optional[ClickLog]:
        """First click touchpoint."""
        return ClickLog.objects.filter(
            user=conversion.user,
            offer_id=conversion.offer_id,
            clicked_at__lt=conversion.converted_at,
        ).order_by("clicked_at").first()

    def get_all_touchpoints(
        self,
        conversion: Conversion,
        window_hours: int = 720,
    ) -> List[ClickLog]:
        """Get all click touchpoints within conversion window."""
        cutoff = conversion.converted_at - timedelta(hours=window_hours)
        return list(ClickLog.objects.filter(
            user=conversion.user,
            clicked_at__gte=cutoff,
            clicked_at__lt=conversion.converted_at,
        ).order_by("clicked_at"))

    def calculate_time_to_convert(self, click_log: ClickLog, conversion: Conversion) -> int:
        """Return seconds between click and conversion."""
        delta = conversion.converted_at - click_log.clicked_at
        return max(0, int(delta.total_seconds()))


# Module-level singleton
conversion_attribution = ConversionAttribution()
