"""REVENUE_MODELS/cpi_calculator.py — CPI (Cost Per Install) calculator."""
from decimal import Decimal


class CPICalculator:
    """Cost Per Install calculator — for app-install campaigns."""

    @staticmethod
    def revenue(installs: int, cpi: Decimal) -> Decimal:
        return (Decimal(installs) * cpi).quantize(Decimal("0.000001"))

    @staticmethod
    def cpi(revenue: Decimal, installs: int) -> Decimal:
        if not installs:
            return Decimal("0.0000")
        return (revenue / installs).quantize(Decimal("0.0001"))

    @staticmethod
    def install_rate(installs: int, clicks: int) -> Decimal:
        if not clicks:
            return Decimal("0.0000")
        return (Decimal(installs) / clicks * 100).quantize(Decimal("0.0001"))

    @staticmethod
    def to_ecpm(cpi: Decimal, install_rate_pct: Decimal,
                 ctr_pct: Decimal) -> Decimal:
        return (cpi * install_rate_pct / 100 * ctr_pct / 100 * 1000).quantize(Decimal("0.0001"))
