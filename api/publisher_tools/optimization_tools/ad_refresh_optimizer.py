# api/publisher_tools/optimization_tools/ad_refresh_optimizer.py
"""Ad Refresh Optimizer — Optimal refresh rate calculation."""
from decimal import Decimal
from typing import Dict


REFRESH_RATE_ECPM_MULTIPLIERS = {15: 1.40, 20: 1.35, 30: 1.30, 45: 1.20, 60: 1.10, 90: 1.05, 120: 1.02}


def calculate_optimal_refresh_rate(placement, days: int = 30) -> Dict:
    """Placement-এর optimal refresh rate calculate করে।"""
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    agg = PublisherEarning.objects.filter(ad_unit=placement.ad_unit, date__gte=start).aggregate(
        ecpm=Avg("ecpm"), fill=Avg("fill_rate"), impressions=Sum("impressions"),
    )
    ecpm = float(agg.get("ecpm") or 0)
    fill = float(agg.get("fill") or 0)
    viewability = float(placement.avg_viewability)
    best_rate = 30
    best_score = 0
    for rate, multiplier in REFRESH_RATE_ECPM_MULTIPLIERS.items():
        score = ecpm * multiplier * (fill/100) * (viewability/100)
        if score > best_score:
            best_score = score
            best_rate = rate
    current = placement.refresh_interval_seconds if placement.refresh_type != "none" else 0
    return {
        "placement_id": str(placement.id),
        "current_interval_sec": current,
        "recommended_interval_sec": best_rate,
        "estimated_ecpm": round(ecpm * REFRESH_RATE_ECPM_MULTIPLIERS.get(best_rate, 1.0), 4),
        "current_ecpm": ecpm,
        "expected_uplift_pct": round((REFRESH_RATE_ECPM_MULTIPLIERS.get(best_rate, 1.0) - 1) * 100, 2),
        "condition": "viewability >= 50%" if viewability >= 50 else "improve viewability first",
    }


def estimate_refresh_revenue_lift(current_rate: int, new_rate: int, base_revenue: float) -> float:
    curr_mult = REFRESH_RATE_ECPM_MULTIPLIERS.get(current_rate, 1.0)
    new_mult  = REFRESH_RATE_ECPM_MULTIPLIERS.get(new_rate, 1.0)
    return round(base_revenue * (new_mult - curr_mult), 4)
