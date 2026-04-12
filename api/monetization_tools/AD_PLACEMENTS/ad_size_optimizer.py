"""AD_PLACEMENTS/ad_size_optimizer.py — Selects optimal creative size."""
from decimal import Decimal
from typing import Optional, List, Tuple


RECOMMENDED_SIZES = {
    "mobile":  [(320, 50), (300, 250), (320, 100)],
    "tablet":  [(728, 90), (300, 250), (300, 600)],
    "desktop": [(970, 90), (300, 600), (728, 90), (300, 250)],
}

ECPM_BY_SIZE = {
    (300, 600): Decimal("3.00"),
    (300, 250): Decimal("2.00"),
    (728, 90):  Decimal("1.80"),
    (970, 90):  Decimal("2.20"),
    (320, 100): Decimal("1.20"),
    (320, 50):  Decimal("0.80"),
}


class AdSizeOptimizer:
    """Selects best ad size for device type and available space."""

    @classmethod
    def best_size(cls, device_type: str = "mobile",
                   max_width: int = 320,
                   max_height: int = 480) -> Tuple[int, int]:
        sizes = RECOMMENDED_SIZES.get(device_type, RECOMMENDED_SIZES["mobile"])
        fitting = [(w, h) for w, h in sizes if w <= max_width and h <= max_height]
        if not fitting:
            return (320, 50)
        return max(fitting, key=lambda s: ECPM_BY_SIZE.get(s, Decimal("0")))

    @classmethod
    def ecpm_for_size(cls, width: int, height: int) -> Decimal:
        return ECPM_BY_SIZE.get((width, height), Decimal("1.00"))

    @classmethod
    def recommend_for_placement(cls, position: str,
                                 device: str = "mobile") -> Tuple[int, int]:
        if position == "fullscreen":
            return (320, 480) if device == "mobile" else (728, 1024)
        if position in ("top", "bottom"):
            return cls.best_size(device, 728, 90)
        return cls.best_size(device)
