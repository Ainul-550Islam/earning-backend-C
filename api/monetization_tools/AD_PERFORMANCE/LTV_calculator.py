"""AD_PERFORMANCE/LTV_calculator.py — Lifetime Value (LTV) calculator."""
from decimal import Decimal
from django.db.models import Sum, Count, Avg


class LTVCalculator:
    """User Lifetime Value from ad revenue + purchases."""

    @staticmethod
    def from_revenue(arpu: Decimal, churn_rate_pct: Decimal,
                      months: int = 1) -> Decimal:
        """LTV = ARPU / monthly_churn_rate"""
        if not churn_rate_pct:
            return Decimal("0")
        monthly_churn = churn_rate_pct / 100
        return (arpu * months / monthly_churn).quantize(Decimal("0.01"))

    @staticmethod
    def cohort_ltv(cohort_month: str, tenant=None) -> Decimal:
        from ..models import RewardTransaction
        from django.db.models import Q
        qs = RewardTransaction.objects.filter(amount__gt=0)
        if tenant:
            qs = qs.filter(tenant=tenant)
        # Approximate: sum of all rewards in cohort
        total = qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        users = qs.values("user").distinct().count()
        if not users:
            return Decimal("0")
        return (total / users).quantize(Decimal("0.01"))

    @staticmethod
    def by_segment(tenant=None) -> list:
        from ..models import UserSegment, UserSegmentMembership, RewardTransaction
        from django.db.models import OuterRef, Subquery
        segments = list(
            UserSegment.objects.filter(is_active=True)
              .values("id", "name", "member_count")
        )
        for seg in segments:
            users_in = UserSegmentMembership.objects.filter(
                segment_id=seg["id"]
            ).values_list("user_id", flat=True)
            avg = RewardTransaction.objects.filter(
                user_id__in=users_in, amount__gt=0
            ).aggregate(avg=Avg("amount"))["avg"] or Decimal("0")
            seg["avg_ltv"] = Decimal(str(avg)).quantize(Decimal("0.01"))
        return segments
