# api/publisher_tools/optimization_tools/time_optimizer.py
"""Time Optimizer — Time-based ad optimization."""
from typing import Dict, List


HOUR_ECPM_INDEX = {
    0:  0.50, 1:  0.45, 2:  0.40, 3:  0.35, 4:  0.40, 5:  0.55,
    6:  0.70, 7:  0.85, 8:  1.00, 9:  1.10, 10: 1.20, 11: 1.25,
    12: 1.20, 13: 1.15, 14: 1.20, 15: 1.25, 16: 1.30, 17: 1.35,
    18: 1.40, 19: 1.45, 20: 1.50, 21: 1.45, 22: 1.30, 23: 1.00,
}

DAY_OF_WEEK_INDEX = {0: 1.0, 1: 1.05, 2: 1.08, 3: 1.08, 4: 1.10, 5: 0.95, 6: 0.90}


def get_peak_hours() -> List[Dict]:
    return sorted(
        [{"hour": h, "ecpm_index": idx, "is_peak": idx >= 1.30} for h, idx in HOUR_ECPM_INDEX.items()],
        key=lambda x: x["ecpm_index"], reverse=True
    )[:8]


def get_optimal_schedule(publisher, ad_unit) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=30)
    hourly = list(
        PublisherEarning.objects.filter(publisher=publisher, ad_unit=ad_unit, date__gte=start, granularity="hourly")
        .values("hour").annotate(ecpm=Avg("ecpm")).order_by("hour")
    )
    if not hourly:
        return {"recommendation": "Use default schedule", "best_hours": list(range(8, 22))}
    best_hours = [h["hour"] for h in sorted(hourly, key=lambda x: float(x.get("ecpm") or 0), reverse=True)[:12]]
    return {
        "best_hours": sorted(best_hours),
        "worst_hours": [h for h in range(24) if h not in best_hours][:6],
        "recommendation": f"Consider scheduling ads during hours {min(best_hours)}-{max(best_hours)} for highest eCPM",
        "expected_improvement_pct": 10.0,
    }


def get_day_of_week_analysis(publisher, days: int = 28) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    earnings = PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    results = []
    for i in range(7):
        day_earnings = [e for e in earnings if e.date.weekday() == i]
        revenue = sum(float(e.publisher_revenue) for e in day_earnings)
        results.append({"day": day_names[i], "weekday": i, "revenue": revenue, "index": DAY_OF_WEEK_INDEX[i]})
    return sorted(results, key=lambda x: x["revenue"], reverse=True)
