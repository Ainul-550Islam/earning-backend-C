# api/publisher_tools/optimization_tools/device_optimizer.py
"""Device Optimizer — Device-specific ad optimization."""
from typing import Dict, List


DEVICE_ECPM_MULTIPLIERS = {"desktop": 1.5, "tablet": 1.2, "mobile": 1.0}
BEST_FORMATS_BY_DEVICE  = {
    "mobile":  ["banner", "interstitial", "rewarded_video", "native"],
    "tablet":  ["rectangle", "banner", "native", "video"],
    "desktop": ["leaderboard", "rectangle", "native", "video"],
}


def get_device_performance(publisher, days: int = 30) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    data = list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("ad_unit__format").annotate(revenue=Sum("publisher_revenue"), ecpm=Avg("ecpm"), fill=Avg("fill_rate"))
        .order_by("-revenue")
    )
    return {"format_performance": data, "period_days": days}


def recommend_device_specific_floor_prices(ad_unit) -> Dict:
    return {
        "mobile":  {"floor": float(ad_unit.floor_price) * DEVICE_ECPM_MULTIPLIERS["mobile"]},
        "tablet":  {"floor": float(ad_unit.floor_price) * DEVICE_ECPM_MULTIPLIERS["tablet"]},
        "desktop": {"floor": float(ad_unit.floor_price) * DEVICE_ECPM_MULTIPLIERS["desktop"]},
        "recommendation": "Set device-specific floor prices via targeting rules for higher eCPM",
    }


def get_best_format_for_device(device_type: str) -> List[str]:
    return BEST_FORMATS_BY_DEVICE.get(device_type, BEST_FORMATS_BY_DEVICE["mobile"])
