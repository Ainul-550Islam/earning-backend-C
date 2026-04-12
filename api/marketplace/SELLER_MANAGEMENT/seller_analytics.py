"""
SELLER_MANAGEMENT/seller_analytics.py — Seller Dashboard Analytics
"""
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from api.marketplace.models import OrderItem, SellerProfile, ProductReview


def revenue_by_period(seller: SellerProfile, group_by: str = "month") -> list:
    trunc = TruncMonth if group_by == "month" else TruncDay
    return list(
        OrderItem.objects.filter(seller=seller)
        .annotate(period=trunc("created_at"))
        .values("period")
        .annotate(revenue=Sum("seller_net"), orders=Count("order",distinct=True), units=Sum("quantity"))
        .order_by("period")
    )


def product_performance(seller: SellerProfile, limit: int = 10) -> list:
    return list(
        OrderItem.objects.filter(seller=seller)
        .values("variant__product__name","variant__product__id")
        .annotate(revenue=Sum("seller_net"), units=Sum("quantity"), orders=Count("order",distinct=True))
        .order_by("-revenue")[:limit]
    )


def customer_stats(seller: SellerProfile) -> dict:
    """Unique buyer analytics for a seller."""
    buyers = OrderItem.objects.filter(seller=seller).values("order__user").distinct().count()
    repeat = (
        OrderItem.objects.filter(seller=seller)
        .values("order__user")
        .annotate(orders=Count("order",distinct=True))
        .filter(orders__gte=2)
        .count()
    )
    return {
        "total_buyers":   buyers,
        "repeat_buyers":  repeat,
        "repeat_rate":    round(repeat / buyers * 100, 1) if buyers else 0,
    }


def rating_trend(seller: SellerProfile, months: int = 6) -> list:
    since = timezone.now() - timezone.timedelta(days=months * 30)
    return list(
        ProductReview.objects.filter(product__seller=seller, created_at__gte=since)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(avg_rating=Avg("rating"), count=Count("id"))
        .order_by("month")
    )


def daily_sales_last_week(seller: SellerProfile) -> list:
    since = timezone.now() - timezone.timedelta(days=7)
    return list(
        OrderItem.objects.filter(seller=seller, created_at__gte=since)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("seller_net"), orders=Count("order",distinct=True))
        .order_by("day")
    )


def seller_kpi_snapshot(seller: SellerProfile) -> dict:
    today_items = OrderItem.objects.filter(
        seller=seller, created_at__date=timezone.now().date()
    )
    month_items = OrderItem.objects.filter(
        seller=seller,
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    )
    return {
        "today_orders":   today_items.values("order").distinct().count(),
        "today_revenue":  str(today_items.aggregate(t=Sum("seller_net"))["t"] or 0),
        "month_revenue":  str(month_items.aggregate(t=Sum("seller_net"))["t"] or 0),
        "month_orders":   month_items.values("order").distinct().count(),
        "avg_rating":     str(seller.average_rating),
        "total_products": seller.products.filter(status="active").count(),
    }
