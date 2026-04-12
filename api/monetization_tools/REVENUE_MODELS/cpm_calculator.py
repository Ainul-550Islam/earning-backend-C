"""REVENUE_MODELS/cpm_calculator.py — CPM revenue calculator."""
from decimal import Decimal


class CPMCalculator:
    """Cost Per Mille (1000 impressions) calculator."""

    @staticmethod
    def revenue(impressions: int, ecpm: Decimal) -> Decimal:
        return (Decimal(impressions) / 1000 * ecpm).quantize(Decimal("0.000001"))

    @staticmethod
    def ecpm(revenue: Decimal, impressions: int) -> Decimal:
        if not impressions:
            return Decimal("0.0000")
        return (revenue / impressions * 1000).quantize(Decimal("0.0001"))

    @staticmethod
    def impressions_needed(target_revenue: Decimal, ecpm: Decimal) -> int:
        if not ecpm:
            return 0
        return int((target_revenue / ecpm * 1000).to_integral_value())

    @staticmethod
    def effective_ecpm(total_revenue: Decimal, total_impressions: int) -> Decimal:
        return CPMCalculator.ecpm(total_revenue, total_impressions)
