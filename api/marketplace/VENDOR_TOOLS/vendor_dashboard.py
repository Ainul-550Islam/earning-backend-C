"""
VENDOR_TOOLS/vendor_dashboard.py — Seller Vendor Dashboard Aggregator
"""
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone


def get_full_dashboard(seller, tenant) -> dict:
    """Single call that powers the entire seller dashboard."""
    return {
        "summary":      _summary(seller, tenant),
        "today":        _today(seller, tenant),
        "this_month":   _period(seller, tenant, days=30),
        "top_products": _top_products(seller, tenant),
        "recent_orders":_recent_orders(seller, tenant),
        "inventory":    _inventory_alerts(seller, tenant),
        "ratings":      _rating_summary(seller, tenant),
        "escrow":       _escrow_summary(seller, tenant),
        "payout":       _payout_summary(seller, tenant),
    }


def _summary(seller, tenant) -> dict:
    from api.marketplace.models import Product
    from api.marketplace.enums import ProductStatus
    return {
        "store_name":     seller.store_name,
        "status":         seller.status,
        "tier":           getattr(seller, "subscription", None) and seller.subscription.plan or "basic",
        "total_products": Product.objects.filter(seller=seller, tenant=tenant).count(),
        "active_products":Product.objects.filter(seller=seller, tenant=tenant, status=ProductStatus.ACTIVE).count(),
        "total_sales":    seller.total_sales,
        "total_revenue":  str(seller.total_revenue),
        "avg_rating":     str(seller.average_rating),
        "response_rate":  str(seller.response_rate),
    }


def _today(seller, tenant) -> dict:
    from api.marketplace.models import OrderItem
    today = timezone.now().date()
    items = OrderItem.objects.filter(seller=seller, tenant=tenant, created_at__date=today)
    agg = items.aggregate(revenue=Sum("seller_net"), orders=Count("order", distinct=True))
    return {"revenue": str(agg["revenue"] or 0), "orders": agg["orders"] or 0}


def _period(seller, tenant, days: int = 30) -> dict:
    from api.marketplace.models import OrderItem
    since = timezone.now() - timezone.timedelta(days=days)
    items = OrderItem.objects.filter(seller=seller, tenant=tenant, created_at__gte=since)
    agg = items.aggregate(
        revenue=Sum("seller_net"),
        orders=Count("order", distinct=True),
        units=Sum("quantity"),
        commission_paid=Sum("commission_amount"),
    )
    return {
        "revenue":        str(agg["revenue"] or 0),
        "orders":         agg["orders"] or 0,
        "units_sold":     agg["units"] or 0,
        "commission_paid":str(agg["commission_paid"] or 0),
    }


def _top_products(seller, tenant, limit: int = 5) -> list:
    from api.marketplace.models import OrderItem
    from django.db.models.functions import Coalesce
    return list(
        OrderItem.objects.filter(seller=seller, tenant=tenant)
        .values("variant__product__name", "variant__product__id")
        .annotate(units=Sum("quantity"), revenue=Sum("seller_net"))
        .order_by("-revenue")[:limit]
    )


def _recent_orders(seller, tenant, limit: int = 10) -> list:
    from api.marketplace.models import OrderItem
    items = OrderItem.objects.filter(
        seller=seller, tenant=tenant
    ).select_related("order").order_by("-created_at")[:limit]
    return [
        {
            "order_number": i.order.order_number,
            "product":      i.product_name,
            "qty":          i.quantity,
            "net":          str(i.seller_net),
            "status":       i.item_status,
            "date":         i.created_at.strftime("%Y-%m-%d"),
        }
        for i in items
    ]


def _inventory_alerts(seller, tenant) -> dict:
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import get_low_stock_items, get_out_of_stock
    low   = get_low_stock_items(tenant, threshold=10).filter(variant__product__seller=seller).count()
    zero  = get_out_of_stock(tenant).filter(variant__product__seller=seller).count()
    return {"low_stock_count": low, "out_of_stock_count": zero}


def _rating_summary(seller, tenant) -> dict:
    from api.marketplace.models import ProductReview
    reviews = ProductReview.objects.filter(product__seller=seller, product__tenant=tenant, is_approved=True)
    agg = reviews.aggregate(avg=Avg("rating"), total=Count("id"))
    dist = {i: reviews.filter(rating=i).count() for i in range(1, 6)}
    return {
        "average":      str(round(agg["avg"] or 0, 2)),
        "total":        agg["total"] or 0,
        "distribution": dist,
        "unanswered":   reviews.filter(seller_reply="").count(),
    }


def _escrow_summary(seller, tenant) -> dict:
    from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager
    return EscrowManager.summary_for_seller(seller)


def _payout_summary(seller, tenant) -> dict:
    from api.marketplace.models import SellerPayout
    from api.marketplace.enums import PayoutStatus
    qs = SellerPayout.objects.filter(seller=seller)
    return {
        "pending":   str(qs.filter(status=PayoutStatus.PENDING).aggregate(t=Sum("amount"))["t"] or 0),
        "completed": str(qs.filter(status=PayoutStatus.COMPLETED).aggregate(t=Sum("amount"))["t"] or 0),
        "last_payout": qs.filter(status=PayoutStatus.COMPLETED).order_by("-created_at").values_list("amount", flat=True).first(),
    }
