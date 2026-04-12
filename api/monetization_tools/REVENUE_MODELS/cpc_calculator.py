"""REVENUE_MODELS/cpc_calculator.py — CPC revenue calculator."""
from decimal import Decimal


class CPCCalculator:
    """Cost Per Click calculator."""

    @staticmethod
    def revenue(clicks: int, cpc: Decimal) -> Decimal:
        return (Decimal(clicks) * cpc).quantize(Decimal("0.000001"))

    @staticmethod
    def cpc(revenue: Decimal, clicks: int) -> Decimal:
        if not clicks:
            return Decimal("0.0000")
        return (revenue / clicks).quantize(Decimal("0.0001"))

    @staticmethod
    def to_ecpm(cpc: Decimal, ctr_pct: Decimal) -> Decimal:
        """Convert CPC + CTR to effective eCPM."""
        return (cpc * ctr_pct / 100 * 1000).quantize(Decimal("0.0001"))

    @staticmethod
    def clicks_needed(target_revenue: Decimal, cpc: Decimal) -> int:
        if not cpc:
            return 0
        return int((target_revenue / cpc).to_integral_value())
