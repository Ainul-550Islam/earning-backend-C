"""REVENUE_MODELS/revshare_calculator.py — Revenue share calculator."""
from decimal import Decimal


class RevShareCalculator:
    """Publisher revenue share calculations."""

    @staticmethod
    def publisher_revenue(gross: Decimal, share_pct: Decimal) -> Decimal:
        return (gross * share_pct / 100).quantize(Decimal("0.000001"))

    @staticmethod
    def platform_revenue(gross: Decimal, share_pct: Decimal) -> Decimal:
        return (gross * (100 - share_pct) / 100).quantize(Decimal("0.000001"))

    @staticmethod
    def split(gross: Decimal, publisher_pct: Decimal) -> dict:
        pub  = RevShareCalculator.publisher_revenue(gross, publisher_pct)
        plat = gross - pub
        return {
            "gross":     gross,
            "publisher": pub,
            "platform":  plat,
            "pub_pct":   publisher_pct,
        }

    @staticmethod
    def net_after_fee(gross: Decimal, fee_pct: Decimal) -> Decimal:
        return (gross * (1 - fee_pct / 100)).quantize(Decimal("0.0001"))
