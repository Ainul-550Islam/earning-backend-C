"""AD_PERFORMANCE/revenue_tracker.py — Revenue attribution and tracking."""
import logging
from decimal import Decimal
from django.db.models import Sum, Avg
from ..models import RevenueDailySummary, AdPerformanceDaily

logger = logging.getLogger(__name__)


class RevenueTracker:
    """Tracks and aggregates ad revenue across all channels."""

    @classmethod
    def today_revenue(cls, tenant=None) -> Decimal:
        from django.utils import timezone
        qs = RevenueDailySummary.objects.filter(date=timezone.now().date())
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.aggregate(t=Sum("total_revenue"))["t"] or Decimal("0")

    @classmethod
    def mtd_revenue(cls, tenant=None) -> Decimal:
        from django.utils import timezone
        now = timezone.now()
        qs  = RevenueDailySummary.objects.filter(
            date__year=now.year, date__month=now.month
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.aggregate(t=Sum("total_revenue"))["t"] or Decimal("0")

    @classmethod
    def revenue_by_network(cls, tenant=None, days: int = 30) -> list:
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("ad_network__display_name")
              .annotate(revenue=Sum("total_revenue"), avg_ecpm=Avg("ecpm"))
              .order_by("-revenue")
        )

    @classmethod
    def revenue_trend(cls, tenant=None, days: int = 30) -> list:
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = RevenueDailySummary.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("date")
              .annotate(revenue=Sum("total_revenue"), impressions=Sum("impressions"))
              .order_by("date")
        )
