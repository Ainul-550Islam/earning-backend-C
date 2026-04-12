"""AD_PLACEMENTS/contextual_placement.py — Context-aware ad selection."""
from typing import Optional


CONTEXT_KEYWORD_MAP = {
    "gaming":      ["unity", "ironsource", "chartboost", "applovin"],
    "finance":     ["admob", "facebook", "criteo"],
    "shopping":    ["criteo", "facebook", "admob"],
    "news":        ["admob", "facebook", "pubmatic"],
    "social":      ["facebook", "admob"],
    "health":      ["admob", "facebook"],
    "travel":      ["admob", "criteo", "facebook"],
    "education":   ["admob", "facebook"],
}


class ContextualPlacementEngine:
    """Selects ad networks/units based on content context."""

    @classmethod
    def get_preferred_networks(cls, context: str) -> list:
        return CONTEXT_KEYWORD_MAP.get(context.lower(), ["admob", "facebook"])

    @classmethod
    def score_placement(cls, placement, context: str,
                         user_interests: list = None) -> float:
        """Score a placement 0.0–1.0 for contextual relevance."""
        score = 0.5
        preferred = cls.get_preferred_networks(context)
        if hasattr(placement, "ad_network") and placement.ad_network:
            if placement.ad_network.network_type in preferred:
                score += 0.3
        if user_interests:
            for interest in user_interests:
                if interest.lower() in CONTEXT_KEYWORD_MAP.get(context.lower(), []):
                    score += 0.1
        return min(1.0, score)

    @classmethod
    def select_best_placement(cls, placements: list, context: str,
                               user_interests: list = None) -> Optional[object]:
        if not placements:
            return None
        scored = [
            (p, cls.score_placement(p, context, user_interests))
            for p in placements
        ]
        return max(scored, key=lambda x: x[1])[0]
