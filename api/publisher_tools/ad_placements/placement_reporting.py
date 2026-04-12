# api/publisher_tools/ad_placements/placement_reporting.py
"""Placement Reporting — Performance reports for placements."""
from decimal import Decimal
from datetime import timedelta
from typing import List, Dict
from django.db.models import Sum, Avg, Count
from django.utils import timezone


def generate_placement_report(publisher, start_date, end_date) -> Dict:
    """Publisher-এর সব placements-এর performance report।"""
    from api.publisher_tools.models import AdPlacement, PublisherEarning
    placements = AdPlacement.objects.filter(
        ad_unit__publisher=publisher
    ).select_related("ad_unit")

    report_data = []
    total_revenue = Decimal("0")
    total_impressions = 0

    for placement in placements:
        agg = PublisherEarning.objects.filter(
            ad_unit=placement.ad_unit, date__range=[start_date, end_date],
        ).aggregate(
            revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
            clicks=Sum("clicks"), ecpm=Avg("ecpm"),
        )
        rev = agg.get("revenue") or Decimal("0")
        imp = agg.get("impressions") or 0
        total_revenue += rev
        total_impressions += imp

        report_data.append({
            "placement_id":   str(placement.id),
            "name":           placement.name,
            "position":       placement.position,
            "format":         placement.ad_unit.format,
            "is_active":      placement.is_active,
            "revenue":        float(rev),
            "impressions":    imp,
            "clicks":         agg.get("clicks") or 0,
            "ecpm":           float(rev / imp * 1000) if imp > 0 else 0,
            "avg_viewability":float(placement.avg_viewability),
            "floor_price":    float(placement.effective_floor_price),
            "revenue_share":  float(rev / total_revenue * 100) if total_revenue > 0 else 0,
        })

    report_data.sort(key=lambda x: x["revenue"], reverse=True)
    return {
        "publisher_id":    publisher.publisher_id,
        "period":          {"start": str(start_date), "end": str(end_date)},
        "total_revenue":   float(total_revenue),
        "total_impressions": total_impressions,
        "total_placements":  len(report_data),
        "active_placements": sum(1 for p in report_data if p["is_active"]),
        "placements":        report_data,
    }


def get_placement_efficiency_score(placement) -> Dict:
    """Placement efficiency score — কতটা revenue generate করছে।"""
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=30)
    agg = PublisherEarning.objects.filter(
        ad_unit=placement.ad_unit, date__gte=start,
    ).aggregate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))

    rev = float(agg.get("revenue") or 0)
    ecpm = float(agg.get("ecpm") or 0)
    viewability = float(placement.avg_viewability)

    # Efficiency score: weighted combination
    score = (
        min(100, ecpm / 5.0 * 100) * 0.40 +
        viewability * 0.40 +
        (rev / max(rev, 1) * 100) * 0.20
    )

    return {
        "placement_id":  str(placement.id),
        "efficiency_score": round(score, 2),
        "ecpm_score":       round(min(100, ecpm / 5.0 * 100), 2),
        "viewability_score":viewability,
        "revenue_30d":      rev,
        "grade":            "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
    }
