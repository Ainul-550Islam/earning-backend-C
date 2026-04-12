"""AD_PLACEMENTS/behavioral_placement.py — Behavioral targeting for ad placement."""
from typing import List, Optional


class BehavioralPlacementEngine:
    """Selects ad placements based on user behavior signals."""

    @staticmethod
    def get_user_signals(user) -> dict:
        """Extract behavioral signals from user profile."""
        return {
            "country":       getattr(user, "country", ""),
            "language":      getattr(user, "language", "bn"),
            "account_level": getattr(user, "account_level", "normal"),
            "coin_balance":  float(getattr(user, "coin_balance", 0)),
            "total_earned":  float(getattr(user, "total_earned", 0)),
            "is_verified":   getattr(user, "is_verified", False),
        }

    @classmethod
    def score_user(cls, signals: dict) -> float:
        """Score user engagement level 0.0–1.0."""
        score = 0.3
        if signals.get("is_verified"):
            score += 0.2
        if signals.get("account_level") == "vip":
            score += 0.3
        earned = signals.get("total_earned", 0)
        if earned > 10000:
            score += 0.2
        elif earned > 1000:
            score += 0.1
        return min(1.0, score)

    @classmethod
    def recommend_format(cls, user_score: float, screen: str = "") -> str:
        """Recommend highest-value ad format based on user value."""
        if user_score >= 0.8:
            return "rewarded_video"
        if user_score >= 0.5:
            return "interstitial"
        if user_score >= 0.3:
            return "native"
        return "banner"

    @classmethod
    def filter_placements_for_user(cls, placements: list,
                                    user_signals: dict) -> list:
        """Remove placements inappropriate for user context."""
        country = user_signals.get("country", "")
        return [
            p for p in placements
            if not getattr(p.ad_unit, "target_countries", None)
            or not country
            or country.upper() in (p.ad_unit.target_countries or [])
        ] if placements else []
