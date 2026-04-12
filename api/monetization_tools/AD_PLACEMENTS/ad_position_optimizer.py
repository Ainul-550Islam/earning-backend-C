"""AD_PLACEMENTS/ad_position_optimizer.py — Optimizes ad position selection."""
from decimal import Decimal
from typing import List


POSITION_ECPM_WEIGHTS = {
    "fullscreen":   Decimal("3.0"),
    "mid_content":  Decimal("2.5"),
    "after_action": Decimal("2.2"),
    "top":          Decimal("1.5"),
    "in_feed":      Decimal("1.8"),
    "sidebar":      Decimal("1.2"),
    "bottom":       Decimal("1.0"),
    "on_exit":      Decimal("0.8"),
}


class AdPositionOptimizer:
    """Recommends optimal ad positions based on eCPM and UX."""

    @classmethod
    def rank_positions(cls, available: List[str]) -> List[tuple]:
        """Return positions sorted by estimated eCPM weight."""
        scored = [
            (pos, POSITION_ECPM_WEIGHTS.get(pos, Decimal("1.0")))
            for pos in available
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    @classmethod
    def best_position(cls, screen_name: str,
                       available: List[str]) -> Optional[str]:
        ranked = cls.rank_positions(available)
        return ranked[0][0] if ranked else None

    @classmethod
    def get_position_ecpm_multiplier(cls, position: str) -> Decimal:
        return POSITION_ECPM_WEIGHTS.get(position, Decimal("1.0"))

    @classmethod
    def ux_score(cls, position: str, refresh_rate: int,
                  freq_cap: int) -> float:
        """Lower is more intrusive. 1.0=ideal. Used to balance revenue vs UX."""
        base = {"fullscreen": 0.4, "mid_content": 0.7, "bottom": 1.0,
                "top": 0.9, "sidebar": 1.0, "in_feed": 0.8}.get(position, 0.8)
        if refresh_rate and refresh_rate < 15:
            base -= 0.1
        if freq_cap and freq_cap > 5:
            base -= 0.05
        return max(0.1, base)
