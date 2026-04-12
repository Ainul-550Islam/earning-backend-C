"""ANALYTICS_REPORTING/revenue_report.py — Revenue analytics report."""
from decimal import Decimal
from django.db.models import Sum, Avg, Count


class RevenueReport:
    """Comprehensive revenue report builder."""

    @classmethod
    def generate(cls, tenant=None, start=None, end=None) -> dict:
        from ..models import RevenueDailySummary
        qs = RevenueDailySummary.objects.all()
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(date__gte=start)
        if end:    qs = qs.filter(date__lte=end)
        agg = qs.aggregate(
            total_revenue=Sum("total_revenue"),
            total_impressions=Sum("impressions"),
            total_clicks=Sum("clicks"),
            avg_ecpm=Avg("ecpm"),
            avg_ctr=Avg("ctr"),
            avg_fill=Avg("fill_rate"),
        )
        return {
            "period": {"start": str(start) if start else None, "end": str(end) if end else None},
            "totals": agg,
            "daily":  list(qs.values("date").annotate(
                revenue=Sum("total_revenue"), ecpm=Avg("ecpm")
            ).order_by("date")),
        }

    @classmethod
    def by_network(cls, tenant=None, start=None, end=None) -> list:
        from ..models import AdPerformanceDaily
        qs = AdPerformanceDaily.objects.all()
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(date__gte=start)
        if end:    qs = qs.filter(date__lte=end)
        return list(
            qs.values("ad_network__display_name")
              .annotate(revenue=Sum("total_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))
              .order_by("-revenue")
        )
