"""OPTIMIZATION_ENGINES/budget_allocator.py — Campaign budget allocation."""
from decimal import Decimal
from typing import List


class BudgetAllocator:
    """Allocates budget across ad units and networks to maximize ROAS."""

    @classmethod
    def allocate_proportional(cls, total_budget: Decimal,
                               weights: List[dict]) -> List[dict]:
        total_w = sum(Decimal(str(w["weight"])) for w in weights)
        if not total_w:
            return weights
        for w in weights:
            w["allocation"] = (total_budget * Decimal(str(w["weight"])) / total_w).quantize(Decimal("0.01"))
        return weights

    @classmethod
    def allocate_by_roas(cls, total_budget: Decimal,
                          network_roas: List[dict]) -> List[dict]:
        """Allocate more to higher ROAS networks."""
        total_roas = sum(Decimal(str(n.get("roas", 1))) for n in network_roas)
        if not total_roas:
            return cls.allocate_proportional(total_budget,
                                              [{"weight": 1, **n} for n in network_roas])
        for n in network_roas:
            share           = Decimal(str(n.get("roas", 1))) / total_roas
            n["allocation"] = (total_budget * share).quantize(Decimal("0.01"))
        return network_roas

    @staticmethod
    def check_pacing(campaign_id: int) -> dict:
        from .ad_pacing_engine import AdPacingEngine
        rate      = AdPacingEngine.pacing_rate(campaign_id)
        remaining = AdPacingEngine.daily_budget_remaining(campaign_id)
        return {
            "pacing_rate": rate,
            "remaining":   remaining,
            "throttle":    rate >= Decimal("1.5"),
        }
