"""ANALYTICS_REPORTING/ad_performance_report.py — Ad unit performance report."""
from django.db.models import Sum, Avg


class AdPerformanceReport:
    @classmethod
    def by_unit(cls, tenant=None, start=None, end=None) -> list:
        from ..models import AdPerformanceDaily
        qs = AdPerformanceDaily.objects.all()
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(date__gte=start)
        if end:    qs = qs.filter(date__lte=end)
        return list(
            qs.values("ad_unit_id", "ad_unit__name", "ad_unit__ad_format")
              .annotate(
                  revenue=Sum("total_revenue"), impressions=Sum("impressions"),
                  clicks=Sum("clicks"), ecpm=Avg("ecpm"), ctr=Avg("ctr"),
              )
              .order_by("-revenue")
        )

    @classmethod
    def by_format(cls, tenant=None, start=None, end=None) -> list:
        from ..models import AdPerformanceDaily
        qs = AdPerformanceDaily.objects.all()
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(date__gte=start)
        if end:    qs = qs.filter(date__lte=end)
        return list(
            qs.values("ad_unit__ad_format")
              .annotate(revenue=Sum("total_revenue"), ecpm=Avg("ecpm"))
              .order_by("-revenue")
        )
