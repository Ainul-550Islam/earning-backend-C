# api/publisher_tools/performance_analytics/monthly_report.py
"""Monthly Report — Monthly earnings summary, invoice generation."""
from decimal import Decimal
from datetime import date
from calendar import monthrange
from typing import Dict, List
from django.db.models import Sum, Avg
from django.utils import timezone


def generate_monthly_report(publisher, year: int = None, month: int = None) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    now = timezone.now()
    year = year or now.year
    month = month or now.month
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end   = date(year, month, last_day)
    agg = PublisherEarning.objects.filter(publisher=publisher, date__range=[start, end]).aggregate(
        gross=Sum("gross_revenue"), revenue=Sum("publisher_revenue"),
        impressions=Sum("impressions"), clicks=Sum("clicks"),
        ecpm=Avg("ecpm"), fill=Avg("fill_rate"), ivt=Sum("invalid_traffic_deduction"),
    )
    by_unit = list(
        PublisherEarning.objects.filter(publisher=publisher, date__range=[start, end])
        .values("ad_unit__unit_id", "ad_unit__name", "ad_unit__format")
        .annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))
        .order_by("-revenue")[:10]
    )
    by_country = list(
        PublisherEarning.objects.filter(publisher=publisher, date__range=[start, end])
        .values("country", "country_name").annotate(revenue=Sum("publisher_revenue"))
        .order_by("-revenue")[:10]
    )
    return {
        "year": year, "month": month, "period": {"start": str(start), "end": str(end)},
        "gross_revenue":    float(agg.get("gross") or 0),
        "publisher_revenue":float(agg.get("revenue") or 0),
        "ivt_deduction":    float(agg.get("ivt") or 0),
        "net_revenue":      float((agg.get("revenue") or 0) - (agg.get("ivt") or 0)),
        "impressions":      agg.get("impressions") or 0,
        "clicks":           agg.get("clicks") or 0,
        "avg_ecpm":         float(agg.get("ecpm") or 0),
        "avg_fill_rate":    float(agg.get("fill") or 0),
        "top_ad_units":     by_unit,
        "top_countries":    by_country,
    }


def get_monthly_growth_trend(publisher, months: int = 6) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    now = timezone.now()
    results = []
    for i in range(months, 0, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year - ((i - now.month + 1) // 12 + (1 if (i - now.month + 1) > 0 else 0))
        last_day = monthrange(y, m)[1]
        agg = PublisherEarning.objects.filter(
            publisher=publisher, date__range=[date(y,m,1), date(y,m,last_day)]
        ).aggregate(revenue=Sum("publisher_revenue"))
        results.append({"year": y, "month": m, "revenue": float(agg.get("revenue") or 0)})
    # Add MoM growth
    for i in range(1, len(results)):
        prev = results[i-1]["revenue"]
        curr = results[i]["revenue"]
        results[i]["mom_growth_pct"] = round((curr-prev)/max(prev,0.01)*100, 2)
    return results
