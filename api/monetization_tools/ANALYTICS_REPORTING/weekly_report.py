"""ANALYTICS_REPORTING/weekly_report.py — Weekly analytics summary."""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class WeeklyReport:
    @classmethod
    def generate(cls, week_offset: int = 0, tenant=None) -> dict:
        now        = timezone.now().date()
        week_start = now - timedelta(days=now.weekday() + 7 * week_offset)
        week_end   = week_start + timedelta(days=6)
        from ..models import RevenueDailySummary, OfferCompletion
        from django.db.models import Sum, Avg
        rev_qs = RevenueDailySummary.objects.filter(date__range=(week_start, week_end))
        ofc_qs = OfferCompletion.objects.filter(created_at__date__range=(week_start, week_end))
        if tenant:
            rev_qs = rev_qs.filter(tenant=tenant)
            ofc_qs = ofc_qs.filter(tenant=tenant)
        agg = rev_qs.aggregate(
            revenue=Sum("total_revenue"), impressions=Sum("impressions"),
            ecpm=Avg("ecpm"), fill_rate=Avg("fill_rate"),
        )
        return {
            "week_start":    str(week_start),
            "week_end":      str(week_end),
            "total_revenue": agg["revenue"] or Decimal("0"),
            "impressions":   agg["impressions"] or 0,
            "avg_ecpm":      agg["ecpm"] or Decimal("0"),
            "avg_fill_rate": agg["fill_rate"] or Decimal("0"),
            "offers_approved": ofc_qs.filter(status="approved").count(),
        }
