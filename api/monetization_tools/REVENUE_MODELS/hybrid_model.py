"""REVENUE_MODELS/hybrid_model.py — Hybrid pricing model (CPM+CPC+CPA)."""
from decimal import Decimal


class HybridRevenueModel:
    """Combines CPM, CPC, and CPA in a single revenue calculation."""

    def __init__(self, cpm_weight: Decimal = Decimal("0.5"),
                  cpc_weight: Decimal = Decimal("0.3"),
                  cpa_weight: Decimal = Decimal("0.2")):
        total = cpm_weight + cpc_weight + cpa_weight
        self.cpm_w = cpm_weight / total
        self.cpc_w = cpc_weight / total
        self.cpa_w = cpa_weight / total

    def calculate(self, impressions: int, ecpm: Decimal,
                   clicks: int, cpc: Decimal,
                   conversions: int, cpa: Decimal) -> dict:
        from .cpm_calculator import CPMCalculator
        from .cpc_calculator import CPCCalculator
        from .cpa_calculator import CPACalculator
        r_cpm = CPMCalculator.revenue(impressions, ecpm)
        r_cpc = CPCCalculator.revenue(clicks, cpc)
        r_cpa = CPACalculator.revenue(conversions, cpa)
        blended = (r_cpm * self.cpm_w + r_cpc * self.cpc_w + r_cpa * self.cpa_w)
        return {
            "cpm_revenue": r_cpm, "cpc_revenue": r_cpc, "cpa_revenue": r_cpa,
            "blended": blended.quantize(Decimal("0.000001")),
            "total":   (r_cpm + r_cpc + r_cpa).quantize(Decimal("0.000001")),
        }
