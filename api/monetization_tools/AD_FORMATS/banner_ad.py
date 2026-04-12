"""AD_FORMATS/banner_ad.py — Banner ad format handler."""
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional, List


BANNER_SIZES = [
    (320, 50, "Mobile Banner"),
    (300, 250, "Medium Rectangle"),
    (728, 90, "Leaderboard"),
    (320, 100, "Large Mobile Banner"),
    (300, 600, "Half Page"),
    (970, 90, "Large Leaderboard"),
    (160, 600, "Wide Skyscraper"),
    (250, 250, "Square"),
]


@dataclass
class BannerAdConfig:
    width: int
    height: int
    refresh_rate: int = 30          # seconds
    is_sticky: bool = False
    z_index: int = 1000
    animation: str = "none"         # none | fade | slide
    border_radius: int = 0
    background_color: str = "transparent"


class BannerAdHandler:
    """Handles banner ad selection, rendering config, and fill logic."""

    STANDARD_SIZES = {f"{w}x{h}": (w, h) for w, h, _ in BANNER_SIZES}

    @classmethod
    def get_config(cls, width: int, height: int, refresh: int = 30) -> BannerAdConfig:
        return BannerAdConfig(width=width, height=height, refresh_rate=refresh)

    @classmethod
    def select_size(cls, available_width: int, available_height: int) -> tuple:
        """Select best banner size that fits within given dimensions."""
        best = None
        best_area = 0
        for w, h, label in BANNER_SIZES:
            if w <= available_width and h <= available_height:
                area = w * h
                if area > best_area:
                    best      = (w, h, label)
                    best_area = area
        return best or (320, 50, "Mobile Banner")

    @classmethod
    def calculate_ecpm_estimate(cls, width: int, height: int,
                                 country: str = "US") -> Decimal:
        """Rough eCPM estimate by banner size and country tier."""
        area = width * height
        base = Decimal("0.50")
        if area >= 300 * 250:
            base = Decimal("1.20")
        if area >= 300 * 600:
            base = Decimal("2.50")
        tier_mult = {"US": Decimal("3.0"), "GB": Decimal("2.5"),
                     "BD": Decimal("0.3"), "IN": Decimal("0.4")}.get(country, Decimal("1.0"))
        return (base * tier_mult).quantize(Decimal("0.0001"))

    @classmethod
    def build_ad_tag(cls, unit_id: str, width: int, height: int,
                      network: str = "admob") -> str:
        """Build HTML ad tag snippet."""
        return (
            f'''<div class="mt-banner" data-unit="{unit_id}" '''
            f'''data-size="{width}x{height}" data-network="{network}" '''
            f'''style="width:{width}px;height:{height}px;overflow:hidden;"></div>'''
        )

    @staticmethod
    def validate_dimensions(width: int, height: int) -> bool:
        valid_sizes = {(w, h) for w, h, _ in BANNER_SIZES}
        return (width, height) in valid_sizes
