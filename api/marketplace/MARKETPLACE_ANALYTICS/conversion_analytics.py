"""
MARKETPLACE_ANALYTICS/conversion_analytics.py — Funnel & Conversion Analytics
"""
from django.db.models import Count


def checkout_funnel(tenant, days: int = 30) -> dict:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import get_funnel
    class FakeTenant:
        pk = tenant.pk
    funnel = get_funnel(tenant, days)
    total  = funnel.get("product_view", 1)
    return {
        "product_views":    funnel.get("product_view", 0),
        "add_to_cart":      funnel.get("add_to_cart", 0),
        "checkout_started": funnel.get("checkout_start", 0),
        "purchased":        funnel.get("purchase", 0),
        "view_to_cart_rate":      _pct(funnel.get("add_to_cart",0), total),
        "cart_to_checkout_rate":  _pct(funnel.get("checkout_start",0), funnel.get("add_to_cart",1)),
        "checkout_to_purchase":   _pct(funnel.get("purchase",0), funnel.get("checkout_start",1)),
        "overall_conversion_rate":_pct(funnel.get("purchase",0), total),
    }


def coupon_conversion(tenant, days: int = 30) -> dict:
    from api.marketplace.models import Order, Coupon
    from django.utils import timezone
    since   = timezone.now() - timezone.timedelta(days=days)
    orders  = Order.objects.filter(tenant=tenant, created_at__gte=since)
    total   = orders.count()
    with_coupon = orders.filter(coupon__isnull=False).count()
    return {
        "orders_with_coupon": with_coupon,
        "coupon_usage_rate":  _pct(with_coupon, total),
        "top_coupons": list(
            orders.filter(coupon__isnull=False)
            .values("coupon_code")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        ),
    }


def _pct(num, denom) -> float:
    return round(num / denom * 100, 1) if denom else 0
