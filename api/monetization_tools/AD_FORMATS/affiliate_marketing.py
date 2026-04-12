"""AD_FORMATS/affiliate_marketing.py — Affiliate / CPA offer ad format."""
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


@dataclass
class AffiliateAdConfig:
    offer_name: str
    affiliate_url: str
    tracking_param: str = "ref"
    commission_type: str = "cpa"   # cpa | cps | cpl | revshare
    commission_value: Decimal = Decimal("0")
    cookie_duration_days: int = 30
    image_url: str = ""
    description: str = ""
    category: str = ""
    is_exclusive: bool = False


class AffiliateMarketingHandler:
    """Builds affiliate offer ads with tracking links."""

    @classmethod
    def build(cls, name: str, url: str, commission: Decimal,
               commission_type: str = "cpa") -> AffiliateAdConfig:
        return AffiliateAdConfig(
            offer_name=name, affiliate_url=url,
            commission_value=commission, commission_type=commission_type,
        )

    @classmethod
    def build_tracking_url(cls, base_url: str, affiliate_id: str,
                            sub_id: str = "", campaign: str = "") -> str:
        params = [f"aff={affiliate_id}"]
        if sub_id:
            params.append(f"sub={sub_id}")
        if campaign:
            params.append(f"campaign={campaign}")
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}{'&'.join(params)}"

    @classmethod
    def calculate_estimated_revenue(cls, clicks: int, cvr_pct: Decimal,
                                     commission: Decimal) -> Decimal:
        conversions = clicks * cvr_pct / 100
        return (Decimal(str(conversions)) * commission).quantize(Decimal("0.0001"))
