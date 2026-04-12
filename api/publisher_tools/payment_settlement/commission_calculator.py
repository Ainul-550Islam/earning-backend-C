# api/publisher_tools/payment_settlement/commission_calculator.py
"""Commission Calculator — Revenue share and commission calculations."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


def calculate_publisher_share(gross_revenue: Decimal, revenue_share_pct: Decimal) -> Decimal:
    share = gross_revenue * (revenue_share_pct / 100)
    return share.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_platform_share(gross_revenue: Decimal, revenue_share_pct: Decimal) -> Decimal:
    publisher = calculate_publisher_share(gross_revenue, revenue_share_pct)
    return (gross_revenue - publisher).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_tiered_commission(gross_revenue: Decimal, tier: str = "standard") -> Dict:
    """Tier-based commission calculation।"""
    tiers = {
        "standard":   Decimal("70.00"),
        "premium":    Decimal("75.00"),
        "enterprise": Decimal("80.00"),
    }
    share_pct = tiers.get(tier, Decimal("70.00"))
    publisher_share = calculate_publisher_share(gross_revenue, share_pct)
    platform_share  = gross_revenue - publisher_share
    return {
        "gross_revenue":    float(gross_revenue),
        "revenue_share_pct":float(share_pct),
        "publisher_share":  float(publisher_share),
        "platform_share":   float(platform_share),
        "tier":             tier,
    }


def calculate_referral_commission(base_amount: Decimal, level: int = 1) -> Decimal:
    level_rates = {1: Decimal("5.00"), 2: Decimal("2.00"), 3: Decimal("1.00")}
    rate = level_rates.get(level, Decimal("1.00"))
    return (base_amount * rate / 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_performance_bonus(publisher_revenue: Decimal, target_revenue: Decimal, bonus_rate: Decimal = Decimal("10.00")) -> Decimal:
    if publisher_revenue >= target_revenue:
        excess = publisher_revenue - target_revenue
        return (excess * bonus_rate / 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return Decimal("0")
