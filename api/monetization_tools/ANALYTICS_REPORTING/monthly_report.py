"""ANALYTICS_REPORTING/monthly_report.py — Monthly analytics report."""
from decimal import Decimal
from django.utils import timezone


class MonthlyReport:
    @classmethod
    def generate(cls, year: int = None, month: int = None, tenant=None) -> dict:
        now   = timezone.now()
        year  = year or now.year
        month = month or now.month
        from ..models import RevenueDailySummary, UserSubscription, InAppPurchase
        from django.db.models import Sum, Avg, Count
        rev_qs = RevenueDailySummary.objects.filter(date__year=year, date__month=month)
        sub_qs = UserSubscription.objects.filter(started_at__year=year, started_at__month=month)
        iap_qs = InAppPurchase.objects.filter(
            purchased_at__year=year, purchased_at__month=month, status="completed"
        )
        if tenant:
            for qs in [rev_qs, sub_qs, iap_qs]:
                qs = qs.filter(tenant=tenant)
        rev_agg = rev_qs.aggregate(revenue=Sum("total_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))
        iap_agg = iap_qs.aggregate(iap_rev=Sum("amount"), iap_count=Count("id"))
        return {
            "year": year, "month": month,
            "ad_revenue":       rev_agg["revenue"] or Decimal("0"),
            "iap_revenue":      iap_agg["iap_rev"] or Decimal("0"),
            "total_revenue":    (rev_agg["revenue"] or Decimal("0")) + (iap_agg["iap_rev"] or Decimal("0")),
            "impressions":      rev_agg["impressions"] or 0,
            "avg_ecpm":         rev_agg["ecpm"] or Decimal("0"),
            "new_subscribers":  sub_qs.count(),
            "iap_purchases":    iap_agg["iap_count"] or 0,
        }
