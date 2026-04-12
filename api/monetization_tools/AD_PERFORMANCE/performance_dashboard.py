"""AD_PERFORMANCE/performance_dashboard.py — Unified performance dashboard builder."""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class PerformanceDashboard:
    """Builds comprehensive performance dashboard data."""

    @classmethod
    def overview(cls, tenant=None, days: int = 7) -> dict:
        from .revenue_tracker import RevenueTracker
        from .eCPM_calculator import ECPMCalculator
        from .fill_rate_analyzer import FillRateAnalyzer
        from .CTR_analyzer import CTRAnalyzer
        from ..models import AdPerformanceDaily
        from django.db.models import Sum, Avg
        cutoff = timezone.now().date() - timedelta(days=days)
        qs     = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        agg = qs.aggregate(
            total_revenue=Sum("total_revenue"),
            total_impressions=Sum("impressions"),
            total_clicks=Sum("clicks"),
            total_conversions=Sum("conversions"),
            avg_ecpm=Avg("ecpm"),
            avg_fill=Avg("fill_rate"),
            avg_ctr=Avg("ctr"),
        )
        return {
            "period_days":        days,
            "total_revenue":      agg["total_revenue"] or Decimal("0"),
            "total_impressions":  agg["total_impressions"] or 0,
            "total_clicks":       agg["total_clicks"] or 0,
            "total_conversions":  agg["total_conversions"] or 0,
            "avg_ecpm":           agg["avg_ecpm"] or Decimal("0"),
            "avg_fill_rate":      agg["avg_fill"] or Decimal("0"),
            "avg_ctr":            agg["avg_ctr"] or Decimal("0"),
            "today_revenue":      RevenueTracker.today_revenue(tenant),
            "mtd_revenue":        RevenueTracker.mtd_revenue(tenant),
        }

    @classmethod
    def network_breakdown(cls, tenant=None, days: int = 7) -> list:
        from .revenue_tracker import RevenueTracker
        return RevenueTracker.revenue_by_network(tenant, days)

    @classmethod
    def daily_trend(cls, tenant=None, days: int = 30) -> list:
        from .revenue_tracker import RevenueTracker
        return RevenueTracker.revenue_trend(tenant, days)

    @classmethod
    def alerts(cls, tenant=None) -> list:
        from .fill_rate_analyzer import FillRateAnalyzer
        low_fill = FillRateAnalyzer.low_fill_units(tenant)
        alerts   = []
        for unit in low_fill:
            alerts.append({
                "type":     "low_fill_rate",
                "unit_id":  unit["ad_unit_id"],
                "unit_name": unit.get("ad_unit__name", ""),
                "value":    unit["avg_fill"],
                "message":  f"Fill rate {unit['avg_fill']:.1f}% — below threshold.",
            })
        return alerts
