"""
MARKETPLACE_ANALYTICS/seller_analytics.py — Platform-wide Seller Analytics
"""
from django.db.models import Sum, Count, Avg


def seller_performance_report(tenant, days: int = 30) -> list:
    from api.marketplace.models import SellerProfile, OrderItem
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    result = []
    for seller in SellerProfile.objects.filter(tenant=tenant, status="active").iterator(chunk_size=50):
        agg = OrderItem.objects.filter(seller=seller, created_at__gte=since).aggregate(
            revenue=Sum("seller_net"),
            orders=Count("order", distinct=True),
            units=Sum("quantity"),
        )
        result.append({
            "seller_id":    seller.pk,
            "store_name":   seller.store_name,
            "revenue":      str(agg["revenue"] or 0),
            "orders":       agg["orders"] or 0,
            "units":        agg["units"] or 0,
            "avg_rating":   str(seller.average_rating),
            "total_reviews":seller.total_reviews,
        })
    return sorted(result, key=lambda x: float(x["revenue"]), reverse=True)


def seller_growth_rate(seller, current_days: int = 30, prior_days: int = 30) -> dict:
    from api.marketplace.models import OrderItem
    from django.utils import timezone
    from django.db.models import Sum
    now    = timezone.now()
    c_start = now - timezone.timedelta(days=current_days)
    p_end   = c_start
    p_start = p_end - timezone.timedelta(days=prior_days)
    current = OrderItem.objects.filter(seller=seller, created_at__gte=c_start).aggregate(r=Sum("seller_net"))["r"] or 0
    prior   = OrderItem.objects.filter(seller=seller, created_at__range=[p_start,p_end]).aggregate(r=Sum("seller_net"))["r"] or 0
    growth  = round((current - prior) / max(1, prior) * 100, 1)
    return {"current_period": str(current), "prior_period": str(prior), "growth_pct": growth}
