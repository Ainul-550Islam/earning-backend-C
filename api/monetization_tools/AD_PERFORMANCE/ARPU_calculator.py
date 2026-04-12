"""AD_PERFORMANCE/ARPU_calculator.py — Average Revenue Per User."""
from decimal import Decimal
from django.db.models import Sum, Count


class ARPUCalculator:
    """Average Revenue Per User across all revenue streams."""

    @staticmethod
    def from_ad_revenue(tenant=None, days: int = 30) -> Decimal:
        from ..models import RevenueDailySummary
        from django.utils import timezone
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        cutoff    = timezone.now().date() - timedelta(days=days)
        rev       = RevenueDailySummary.objects.filter(date__gte=cutoff)
        if tenant:
            rev = rev.filter(tenant=tenant)
        total_rev = rev.aggregate(t=Sum("total_revenue"))["t"] or Decimal("0")
        total_usr = get_user_model().objects.filter(is_active=True).count()
        if not total_usr:
            return Decimal("0")
        return (total_rev / total_usr).quantize(Decimal("0.0001"))

    @staticmethod
    def from_all_sources(tenant=None, days: int = 30) -> dict:
        from ..models import InAppPurchase, RewardTransaction
        from django.utils import timezone
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        cutoff    = timezone.now().date() - timedelta(days=days)
        iap_rev   = InAppPurchase.objects.filter(
            status="completed",
            purchased_at__date__gte=cutoff
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        total_usr = get_user_model().objects.filter(is_active=True).count()
        ad_arpu   = ARPUCalculator.from_ad_revenue(tenant, days)
        iap_arpu  = (iap_rev / total_usr).quantize(Decimal("0.0001")) if total_usr else Decimal("0")
        return {
            "ad_arpu":    ad_arpu,
            "iap_arpu":   iap_arpu,
            "total_arpu": (ad_arpu + iap_arpu).quantize(Decimal("0.0001")),
            "users":      total_usr,
        }
