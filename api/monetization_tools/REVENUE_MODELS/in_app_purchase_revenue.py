"""REVENUE_MODELS/in_app_purchase_revenue.py — IAP revenue analytics."""
from decimal import Decimal
from django.db.models import Sum, Count, Avg


class IAPRevenueAnalytics:
    """In-app purchase revenue analysis."""

    @staticmethod
    def total_revenue(tenant=None, start=None, end=None) -> Decimal:
        from ..models import InAppPurchase
        qs = InAppPurchase.objects.filter(status="completed")
        if tenant:
            qs = qs.filter(tenant=tenant)
        if start:
            qs = qs.filter(purchased_at__date__gte=start)
        if end:
            qs = qs.filter(purchased_at__date__lte=end)
        return qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @staticmethod
    def arppu(tenant=None, start=None, end=None) -> Decimal:
        """Average Revenue Per Paying User."""
        from ..models import InAppPurchase
        qs = InAppPurchase.objects.filter(status="completed")
        if tenant: qs = qs.filter(tenant=tenant)
        agg = qs.aggregate(total=Sum("amount"), buyers=Count("user", distinct=True))
        if not agg["buyers"]:
            return Decimal("0")
        return (agg["total"] / agg["buyers"]).quantize(Decimal("0.01"))

    @staticmethod
    def conversion_rate(tenant=None) -> Decimal:
        from ..models import InAppPurchase
        from django.contrib.auth import get_user_model
        buyers = InAppPurchase.objects.filter(
            status="completed"
        ).values("user").distinct().count()
        total  = get_user_model().objects.filter(is_active=True).count()
        if not total:
            return Decimal("0")
        return (Decimal(buyers) / total * 100).quantize(Decimal("0.0001"))

    @staticmethod
    def top_products(tenant=None, limit: int = 10) -> list:
        from ..models import InAppPurchase
        qs = InAppPurchase.objects.filter(status="completed")
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("product_id", "product_name")
              .annotate(revenue=Sum("amount"), count=Count("id"))
              .order_by("-revenue")[:limit]
        )
