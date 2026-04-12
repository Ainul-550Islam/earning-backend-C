# api/publisher_tools/optimization_tools/ad_format_optimizer.py
"""Ad Format Optimizer — Best ad format selection per context."""
from typing import Dict, List


FORMAT_ECPM_INDEX = {
    "rewarded_video": 10.0, "interstitial": 7.0, "native": 5.0,
    "video": 6.0, "offerwall": 4.0, "rectangle": 2.5,
    "leaderboard": 2.0, "banner": 1.0, "sticky": 1.5,
}

FORMAT_FILL_INDEX = {
    "banner": 90, "sticky": 85, "rectangle": 80,
    "leaderboard": 75, "native": 65, "video": 60,
    "interstitial": 70, "rewarded_video": 55, "offerwall": 50,
}


def recommend_formats_for_site(site) -> List[Dict]:
    category = site.category
    category_format_scores = {
        "news":          ["banner", "native", "leaderboard", "rectangle"],
        "gaming":        ["rewarded_video", "interstitial", "offerwall", "banner"],
        "blog":          ["native", "rectangle", "banner", "leaderboard"],
        "entertainment": ["video", "native", "banner", "interstitial"],
        "ecommerce":     ["native", "banner", "rectangle"],
    }
    recommended = category_format_scores.get(category, ["banner", "native", "rectangle"])
    return [
        {"format": fmt, "expected_ecpm": FORMAT_ECPM_INDEX.get(fmt, 1.0),
         "expected_fill_pct": FORMAT_FILL_INDEX.get(fmt, 70),
         "priority": i + 1}
        for i, fmt in enumerate(recommended)
    ]


def compare_formats(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("ad_unit__format").annotate(revenue=Sum("publisher_revenue"), ecpm=Avg("ecpm"), fill=Avg("fill_rate"))
        .order_by("-revenue")
    )


def get_format_optimization_score(ad_unit) -> int:
    ecpm = float(ad_unit.avg_ecpm)
    fill = float(ad_unit.fill_rate)
    expected_ecpm = FORMAT_ECPM_INDEX.get(ad_unit.format, 1.0)
    expected_fill = FORMAT_FILL_INDEX.get(ad_unit.format, 70)
    ecpm_score = min(100, ecpm / expected_ecpm * 100)
    fill_score = min(100, fill / expected_fill * 100)
    return round(ecpm_score * 0.6 + fill_score * 0.4)
