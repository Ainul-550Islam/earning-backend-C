"""REVENUE_MODELS/cpa_calculator.py — CPA revenue calculator."""
from decimal import Decimal


class CPACalculator:
    """Cost Per Action / Acquisition calculator."""

    @staticmethod
    def revenue(conversions: int, cpa: Decimal) -> Decimal:
        return (Decimal(conversions) * cpa).quantize(Decimal("0.000001"))

    @staticmethod
    def cpa(revenue: Decimal, conversions: int) -> Decimal:
        if not conversions:
            return Decimal("0.0000")
        return (revenue / conversions).quantize(Decimal("0.0001"))

    @staticmethod
    def to_ecpm(cpa: Decimal, cvr_pct: Decimal, ctr_pct: Decimal) -> Decimal:
        return (cpa * cvr_pct / 100 * ctr_pct / 100 * 1000).quantize(Decimal("0.0001"))

    @staticmethod
    def roas(revenue: Decimal, spend: Decimal) -> Decimal:
        if not spend:
            return Decimal("0.0000")
        return (revenue / spend).quantize(Decimal("0.0001"))
