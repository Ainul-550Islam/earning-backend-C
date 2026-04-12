"""AD_CREATIVES/dynamic_creative.py — Dynamic creative optimization (DCO)."""
from typing import Optional


class DynamicCreativeOptimizer:
    """Selects the best performing creative dynamically per user context."""

    @classmethod
    def select(cls, ad_unit_id: int, user=None,
                context: dict = None) -> Optional[object]:
        from ..models import AdCreative
        from .creative_performance import CreativePerformanceAnalyzer

        approved = list(
            AdCreative.objects.filter(
                ad_unit_id=ad_unit_id, status="approved", is_active=True
            ).order_by("-revenue")
        )
        if not approved:
            return None
        if len(approved) == 1:
            return approved[0]
        # Score each creative
        best   = None
        best_s = -1
        country = (context or {}).get("country", "")
        for creative in approved:
            score = float(CreativePerformanceAnalyzer.ctr(creative.id))
            # Boost by historical revenue
            score += float(creative.revenue or 0) * 0.001
            if score > best_s:
                best   = creative
                best_s = score
        return best

    @classmethod
    def personalize(cls, creative, user=None, context: dict = None) -> dict:
        """Return personalized variables to inject into creative template."""
        variables = {}
        if user:
            variables["user_name"] = getattr(user, "username", "Friend")
            variables["country"]   = getattr(user, "country", "")
        if context:
            variables.update(context)
        return variables
