# api/publisher_tools/performance_analytics/custom_report.py
"""Custom Report — Flexible report builder."""
from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional
from django.db.models import Sum, Avg, Count
from django.utils import timezone


VALID_DIMENSIONS = ["date", "hour", "country", "ad_unit", "site", "app", "earning_type", "network", "device_type"]
VALID_METRICS    = ["revenue", "impressions", "clicks", "ecpm", "fill_rate", "ctr", "requests", "ivt_deduction"]


def build_custom_report(
    publisher,
    start_date: date,
    end_date: date,
    dimensions: List[str] = None,
    metrics: List[str] = None,
    filters: Dict = None,
    limit: int = 1000,
) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    if not dimensions:
        dimensions = ["date"]
    if not metrics:
        metrics = ["revenue", "impressions", "ecpm"]
    # Validate
    invalid_dims = [d for d in dimensions if d not in VALID_DIMENSIONS]
    invalid_mets = [m for m in metrics if m not in VALID_METRICS]
    if invalid_dims or invalid_mets:
        return {"error": f"Invalid dimensions: {invalid_dims} or metrics: {invalid_mets}"}
    qs = PublisherEarning.objects.filter(publisher=publisher, date__range=[start_date, end_date])
    # Apply filters
    if filters:
        if filters.get("country"):
            qs = qs.filter(country=filters["country"])
        if filters.get("earning_type"):
            qs = qs.filter(earning_type=filters["earning_type"])
        if filters.get("site_id"):
            qs = qs.filter(site__site_id=filters["site_id"])
        if filters.get("app_id"):
            qs = qs.filter(app__app_id=filters["app_id"])
        if filters.get("ad_unit_id"):
            qs = qs.filter(ad_unit__unit_id=filters["ad_unit_id"])
    # Group by dimensions
    dim_fields = {"date": "date", "hour": "hour", "country": "country", "earning_type": "earning_type",
                  "ad_unit": "ad_unit__unit_id", "site": "site__site_id", "app": "app__app_id",
                  "network": "network__name"}
    group_fields = [dim_fields.get(d, d) for d in dimensions if d in dim_fields]
    # Annotate metrics
    metric_annotations = {
        "revenue": Sum("publisher_revenue"), "impressions": Sum("impressions"),
        "clicks": Sum("clicks"), "ecpm": Avg("ecpm"), "fill_rate": Avg("fill_rate"),
        "ctr": Avg("ctr"), "requests": Sum("ad_requests"), "ivt_deduction": Sum("invalid_traffic_deduction"),
    }
    selected = {m: metric_annotations[m] for m in metrics if m in metric_annotations}
    data = list(qs.values(*group_fields).annotate(**selected).order_by(*group_fields)[:limit])
    # Serialize decimals
    for row in data:
        for k, v in row.items():
            if v is not None and hasattr(v, '__float__'):
                row[k] = round(float(v), 6)
    return {
        "publisher_id": publisher.publisher_id,
        "period":       {"start": str(start_date), "end": str(end_date)},
        "dimensions":   dimensions, "metrics": metrics,
        "row_count":    len(data), "data": data,
    }


def export_report_to_csv(report_data: Dict) -> str:
    """Report data CSV-তে convert করে।"""
    import csv, io
    output = io.StringIO()
    if not report_data.get("data"):
        return ""
    writer = csv.DictWriter(output, fieldnames=report_data["data"][0].keys())
    writer.writeheader()
    writer.writerows(report_data["data"])
    return output.getvalue()
