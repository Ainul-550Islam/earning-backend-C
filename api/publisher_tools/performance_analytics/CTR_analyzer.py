# api/publisher_tools/performance_analytics/CTR_analyzer.py
"""CTR Analyzer — Click-through rate analysis and benchmarking."""
from datetime import timedelta
from typing import Dict, List
from django.db.models import Avg, Sum
from django.utils import timezone

INDUSTRY_CTR_BENCHMARKS = {
    "banner":        0.10,
    "leaderboard":   0.07,
    "rectangle":     0.15,
    "native":        0.30,
    "interstitial":  0.50,
    "rewarded_video":1.20,
    "video":         0.40,
}


def get_ctr_by_format(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    data = list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("ad_unit__format").annotate(clicks=Sum("clicks"), impressions=Sum("impressions"), ctr=Avg("ctr"))
        .order_by("-ctr")
    )
    for row in data:
        fmt = row.get("ad_unit__format", "")
        benchmark = INDUSTRY_CTR_BENCHMARKS.get(fmt, 0.15)
        imp = row.get("impressions") or 1
        actual_ctr = float(row.get("clicks") or 0) / imp * 100
        row["actual_ctr"] = round(actual_ctr, 4)
        row["benchmark_ctr"] = benchmark
        row["vs_benchmark"] = round(actual_ctr - benchmark, 4)
        row["status"] = "above" if actual_ctr >= benchmark else "below"
    return data


def get_ctr_trend(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("date").annotate(ctr=Avg("ctr"), clicks=Sum("clicks"), impressions=Sum("impressions"))
        .order_by("date")
    )


def identify_ctr_anomalies(publisher, days: int = 7) -> List[Dict]:
    data = get_ctr_trend(publisher, days)
    if len(data) < 3:
        return []
    avg_ctr = sum(float(d.get("ctr") or 0) for d in data) / len(data)
    anomalies = []
    for d in data:
        ctr = float(d.get("ctr") or 0)
        if abs(ctr - avg_ctr) > avg_ctr * 0.5:
            anomalies.append({"date": str(d["date"]), "ctr": ctr, "avg_ctr": avg_ctr,
                               "deviation_pct": round((ctr-avg_ctr)/max(avg_ctr,0.001)*100, 2),
                               "type": "spike" if ctr > avg_ctr else "drop"})
    return anomalies
