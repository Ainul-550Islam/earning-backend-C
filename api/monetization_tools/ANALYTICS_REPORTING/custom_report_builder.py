"""ANALYTICS_REPORTING/custom_report_builder.py — Flexible report builder."""
from decimal import Decimal
from typing import List, Optional


METRIC_MAP = {
    "revenue":     "total_revenue",
    "impressions": "impressions",
    "clicks":      "clicks",
    "ecpm":        "ecpm",
    "ctr":         "ctr",
    "fill_rate":   "fill_rate",
    "conversions": "conversions",
}

DIMENSION_MAP = {
    "date":    "date",
    "network": "ad_network__display_name",
    "country": "country",
    "format":  "ad_unit__ad_format",
    "device":  "device_type",
}


class CustomReportBuilder:
    """Build custom reports with flexible dimensions and metrics."""

    @classmethod
    def build(cls, dimensions: List[str], metrics: List[str],
               tenant=None, start=None, end=None,
               order_by: str = "-revenue", limit: int = 500) -> list:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum, Avg

        qs = AdPerformanceDaily.objects.all()
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(date__gte=start)
        if end:    qs = qs.filter(date__lte=end)

        dims   = [DIMENSION_MAP[d] for d in dimensions if d in DIMENSION_MAP]
        ann    = {}
        for m in metrics:
            field = METRIC_MAP.get(m)
            if field:
                ann[m] = Sum(field) if m in ("revenue","impressions","clicks","conversions") else Avg(field)

        qs = qs.values(*dims).annotate(**ann).order_by(order_by)[:limit]
        return list(qs)

    @classmethod
    def available_dimensions(cls) -> List[str]:
        return list(DIMENSION_MAP.keys())

    @classmethod
    def available_metrics(cls) -> List[str]:
        return list(METRIC_MAP.keys())

    @classmethod
    def validate(cls, dimensions: List[str], metrics: List[str]) -> list:
        errors = []
        for d in dimensions:
            if d not in DIMENSION_MAP:
                errors.append(f"Unknown dimension: {d}")
        for m in metrics:
            if m not in METRIC_MAP:
                errors.append(f"Unknown metric: {m}")
        if not metrics:
            errors.append("At least 1 metric required.")
        return errors
