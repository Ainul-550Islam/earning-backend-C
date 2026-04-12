# api/publisher_tools/optimization_tools/geo_optimizer.py
"""Geo Optimizer — Geographic targeting optimization."""
from typing import Dict, List


HIGH_VALUE_COUNTRIES = {
    "US": 5.0, "GB": 4.0, "AU": 3.5, "CA": 3.5, "DE": 3.0,
    "FR": 2.5, "JP": 3.0, "SG": 3.5, "AE": 4.0, "NL": 2.5,
    "SE": 2.5, "NO": 2.5, "CH": 3.5, "DK": 2.5, "FI": 2.0,
}


def get_geo_optimization_recommendations(publisher, days: int = 30) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    top_countries = list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("country", "country_name").annotate(revenue=Sum("publisher_revenue"), ecpm=Avg("ecpm"))
        .order_by("-revenue")[:15]
    )
    high_value_untapped = [c for c in HIGH_VALUE_COUNTRIES if not any(r["country"] == c for r in top_countries)]
    recommendations = []
    for country in high_value_untapped[:5]:
        recommendations.append({
            "country": country, "potential_ecpm_multiplier": HIGH_VALUE_COUNTRIES[country],
            "action": f"Target {country} traffic — high eCPM country with no current traffic",
        })
    low_ecpm = [r for r in top_countries if float(r.get("ecpm") or 0) < 0.5 and float(r.get("revenue") or 0) > 0]
    for row in low_ecpm[:3]:
        recommendations.append({
            "country": row["country"], "current_ecpm": float(row.get("ecpm") or 0),
            "action": f"Consider floor price for {row['country_name']} — very low eCPM",
        })
    return {"top_countries": top_countries, "recommendations": recommendations, "high_value_untapped": high_value_untapped[:5]}


def get_ecpm_by_country_benchmark() -> Dict:
    return {c: {"expected_ecpm_multiplier": v} for c, v in HIGH_VALUE_COUNTRIES.items()}
