"""
MARKETPLACE_ANALYTICS/competitor_analytics.py — Internal Competitive Intelligence
"""
from django.db.models import Avg, Count


def compare_sellers(tenant, category=None) -> list:
    """Compare seller performance metrics within the platform."""
    from api.marketplace.models import SellerProfile, OrderItem
    from django.db.models import Sum
    sellers = SellerProfile.objects.filter(tenant=tenant, status="active")
    if category:
        sellers = sellers.filter(products__category=category).distinct()

    result = []
    for seller in sellers[:20]:
        agg = OrderItem.objects.filter(seller=seller).aggregate(
            revenue=Sum("seller_net"), orders=Count("order",distinct=True)
        )
        result.append({
            "seller":         seller.store_name,
            "revenue":        str(agg["revenue"] or 0),
            "orders":         agg["orders"] or 0,
            "avg_rating":     str(seller.average_rating),
            "product_count":  seller.products.filter(status="active").count(),
        })
    return sorted(result, key=lambda x: float(x["revenue"]), reverse=True)


def market_share_by_seller(tenant) -> list:
    from api.marketplace.models import OrderItem
    from django.db.models import Sum
    total = OrderItem.objects.filter(tenant=tenant).aggregate(t=Sum("subtotal"))["t"] or 1
    return list(
        OrderItem.objects.filter(tenant=tenant)
        .values("seller__store_name")
        .annotate(revenue=Sum("subtotal"))
        .order_by("-revenue")[:10]
        .extra(select={"share": f"subtotal * 100.0 / {total}"})
    )
