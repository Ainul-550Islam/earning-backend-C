"""OPTIMIZATION_ENGINES/geo_optimizer.py — Geographic bid optimization."""
from decimal import Decimal


COUNTRY_TIER_MAP = {
    "US": 1, "GB": 1, "CA": 1, "AU": 1, "DE": 1, "FR": 1, "JP": 1,
    "IN": 2, "BR": 2, "MX": 2, "ID": 2, "TR": 2, "SA": 2, "AE": 2,
    "BD": 3, "PK": 3, "NG": 3, "KE": 3, "GH": 3, "EG": 3,
}

TIER_ECPM_MULTIPLIER = {1: Decimal("3.0"), 2: Decimal("1.0"), 3: Decimal("0.3")}


class GeoOptimizer:
    """Geographic bid adjustment and country-tier targeting."""

    @classmethod
    def tier(cls, country: str) -> int:
        return COUNTRY_TIER_MAP.get(country.upper() if country else "", 3)

    @classmethod
    def ecpm_multiplier(cls, country: str) -> Decimal:
        return TIER_ECPM_MULTIPLIER.get(cls.tier(country), Decimal("0.3"))

    @classmethod
    def adjust_bid(cls, base_bid: Decimal, country: str) -> Decimal:
        return (base_bid * cls.ecpm_multiplier(country)).quantize(Decimal("0.0001"))

    @classmethod
    def top_revenue_countries(cls, ad_unit_id: int = None, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum, Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs     = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if ad_unit_id:
            qs = qs.filter(ad_unit_id=ad_unit_id)
        return list(
            qs.values("country")
              .annotate(revenue=Sum("total_revenue"), ecpm=Avg("ecpm"))
              .order_by("-revenue")[:20]
        )
