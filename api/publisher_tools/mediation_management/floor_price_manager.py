# api/publisher_tools/mediation_management/floor_price_manager.py
"""Floor Price Manager — Dynamic floor price optimization."""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List
from django.db.models import Avg, Percentile
from django.utils import timezone


def get_floor_price_recommendations(publisher) -> List[Dict]:
    """Publisher-এর সব ad units-এর floor price recommendations।"""
    from api.publisher_tools.models import AdUnit, PublisherEarning
    units = AdUnit.objects.filter(publisher=publisher, status="active")
    recommendations = []
    for unit in units:
        rec = calculate_optimal_floor(unit)
        if rec["recommended_floor"] > float(unit.floor_price) * 1.10:
            recommendations.append(rec)
    return sorted(recommendations, key=lambda x: x["potential_lift"], reverse=True)


def calculate_optimal_floor(ad_unit, days: int = 30) -> Dict:
    """eCPM data থেকে optimal floor price calculate করে।"""
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Avg, Sum
    start = timezone.now().date() - timedelta(days=days)
    agg = PublisherEarning.objects.filter(
        ad_unit=ad_unit, date__gte=start, impressions__gt=0,
    ).aggregate(avg_ecpm=Avg("ecpm"), impressions=Sum("impressions"), revenue=Sum("publisher_revenue"))
    avg_ecpm = float(agg.get("avg_ecpm") or 0)
    current = float(ad_unit.floor_price)
    # Recommended: 70-80% of average eCPM
    recommended = round(avg_ecpm * 0.75, 4) if avg_ecpm > 0 else 0
    potential_lift = round((recommended - current) / max(current, 0.01) * 100, 2) if recommended > current else 0
    return {
        "unit_id": ad_unit.unit_id, "unit_name": ad_unit.name, "format": ad_unit.format,
        "current_floor": current, "avg_ecpm_30d": avg_ecpm,
        "recommended_floor": recommended, "potential_lift": potential_lift,
        "impressions_30d": agg.get("impressions") or 0,
        "confidence": "high" if (agg.get("impressions") or 0) > 10000 else "medium",
    }


def apply_floor_price_update(ad_unit, new_floor: Decimal) -> bool:
    """Floor price update করে।"""
    ad_unit.floor_price = new_floor
    ad_unit.save(update_fields=["floor_price", "updated_at"])
    # Invalidate cache
    from api.publisher_tools.cache import AdUnitCache
    AdUnitCache.invalidate_unit(ad_unit.unit_id)
    return True


def bulk_update_floor_prices(publisher, strategy: str = "conservative") -> Dict:
    """Bulk floor price update। strategy: conservative(70%), moderate(75%), aggressive(80%)"""
    from api.publisher_tools.models import AdUnit
    multipliers = {"conservative": 0.70, "moderate": 0.75, "aggressive": 0.80}
    multiplier = multipliers.get(strategy, 0.75)
    units = AdUnit.objects.filter(publisher=publisher, status="active")
    updated = 0
    for unit in units:
        rec = calculate_optimal_floor(unit)
        if rec["avg_ecpm_30d"] > 0:
            new_floor = Decimal(str(round(rec["avg_ecpm_30d"] * multiplier, 4)))
            if new_floor > unit.floor_price:
                apply_floor_price_update(unit, new_floor)
                updated += 1
    return {"strategy": strategy, "units_updated": updated, "total_units": units.count()}
