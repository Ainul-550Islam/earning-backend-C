"""ANALYTICS_REPORTING/daily_summary.py — End-of-day analytics summary."""
from decimal import Decimal
from django.utils import timezone


class DailySummaryReport:
    @classmethod
    def generate(cls, date=None, tenant=None) -> dict:
        date = date or timezone.now().date()
        from ..models import (RevenueDailySummary, OfferCompletion,
                               PayoutRequest, FraudAlert, UserSubscription)
        from django.db.models import Sum, Count

        revenue_qs = RevenueDailySummary.objects.filter(date=date)
        offers_qs  = OfferCompletion.objects.filter(created_at__date=date)
        payouts_qs = PayoutRequest.objects.filter(created_at__date=date)
        fraud_qs   = FraudAlert.objects.filter(created_at__date=date)
        subs_qs    = UserSubscription.objects.filter(started_at__date=date)

        if tenant:
            for qs in [revenue_qs, offers_qs, payouts_qs, fraud_qs, subs_qs]:
                qs = qs.filter(tenant=tenant)

        rev_agg = revenue_qs.aggregate(total=Sum("total_revenue"), imp=Sum("impressions"))
        return {
            "date":              str(date),
            "total_revenue":     rev_agg["total"] or Decimal("0"),
            "total_impressions": rev_agg["imp"] or 0,
            "offers_completed":  offers_qs.filter(status="approved").count(),
            "new_subscriptions": subs_qs.filter(status="active").count(),
            "payout_requests":   payouts_qs.count(),
            "fraud_alerts":      fraud_qs.count(),
            "generated_at":      str(timezone.now()),
        }
