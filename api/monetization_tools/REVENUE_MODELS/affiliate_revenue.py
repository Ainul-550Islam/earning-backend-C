"""REVENUE_MODELS/affiliate_revenue.py — Affiliate / CPA revenue tracking."""
from decimal import Decimal
from django.db.models import Sum, Count


class AffiliateRevenueTracker:
    """Tracks affiliate commission revenue."""

    @staticmethod
    def total_commission(tenant=None, start=None, end=None) -> Decimal:
        from ..models import ReferralCommission
        qs = ReferralCommission.objects.filter(is_paid=True)
        if tenant: qs = qs.filter(tenant=tenant)
        if start:  qs = qs.filter(created_at__date__gte=start)
        if end:    qs = qs.filter(created_at__date__lte=end)
        return qs.aggregate(t=Sum("commission_coins"))["t"] or Decimal("0")

    @staticmethod
    def commission_by_level(tenant=None) -> list:
        from ..models import ReferralCommission
        qs = ReferralCommission.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("level")
              .annotate(total=Sum("commission_coins"), count=Count("id"))
              .order_by("level")
        )

    @staticmethod
    def top_affiliates(tenant=None, limit: int = 20) -> list:
        from ..models import ReferralCommission
        qs = ReferralCommission.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("referrer__username", "referrer_id")
              .annotate(earned=Sum("commission_coins"), refs=Count("referee", distinct=True))
              .order_by("-earned")[:limit]
        )
