"""REVENUE_MODELS/subscription_revenue.py — Subscription MRR/ARR analytics."""
from decimal import Decimal
from django.db.models import Count, Sum


class SubscriptionRevenueAnalytics:
    """Calculates MRR, ARR, churn, and LTV for subscription revenue."""

    @staticmethod
    def mrr(tenant=None) -> Decimal:
        from ..models import UserSubscription, SubscriptionPlan
        from django.db.models import F
        qs = UserSubscription.objects.filter(status="active")
        if tenant:
            qs = qs.filter(tenant=tenant)
        total = Decimal("0")
        for sub in qs.select_related("plan"):
            p = sub.plan
            if p.interval == "monthly":
                total += p.price
            elif p.interval == "yearly":
                total += p.price / 12
            elif p.interval == "weekly":
                total += p.price * Decimal("4.33")
            elif p.interval == "daily":
                total += p.price * 30
        return total.quantize(Decimal("0.01"))

    @staticmethod
    def arr(tenant=None) -> Decimal:
        return (SubscriptionRevenueAnalytics.mrr(tenant) * 12).quantize(Decimal("0.01"))

    @staticmethod
    def churn_rate(tenant=None, months: int = 1) -> Decimal:
        from ..models import UserSubscription
        from django.utils import timezone
        from datetime import timedelta
        now    = timezone.now()
        start  = now - timedelta(days=30 * months)
        total  = UserSubscription.objects.filter(
            started_at__lte=start
        )
        if tenant:
            total = total.filter(tenant=tenant)
        churned = total.filter(
            status__in=["cancelled", "expired"], cancelled_at__gte=start
        )
        t_count = total.count()
        if not t_count:
            return Decimal("0.0000")
        return (Decimal(churned.count()) / t_count * 100).quantize(Decimal("0.0001"))

    @staticmethod
    def ltv(arpu: Decimal, churn_rate_pct: Decimal) -> Decimal:
        if not churn_rate_pct:
            return Decimal("0")
        return (arpu / (churn_rate_pct / 100)).quantize(Decimal("0.01"))
