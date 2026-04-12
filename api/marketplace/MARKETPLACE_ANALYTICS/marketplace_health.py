"""
MARKETPLACE_ANALYTICS/marketplace_health.py — Marketplace Health Dashboard
"""
from django.utils import timezone
from django.db.models import Count, Sum, Avg


def full_health_report(tenant) -> dict:
    return {
        "products":  _product_health(tenant),
        "orders":    _order_health(tenant),
        "sellers":   _seller_health(tenant),
        "payments":  _payment_health(tenant),
        "reviews":   _review_health(tenant),
        "inventory": _inventory_health(tenant),
        "generated": timezone.now().isoformat(),
    }


def _product_health(tenant) -> dict:
    from api.marketplace.models import Product
    from api.marketplace.enums import ProductStatus
    total   = Product.objects.filter(tenant=tenant).count()
    active  = Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE).count()
    draft   = Product.objects.filter(tenant=tenant, status=ProductStatus.DRAFT).count()
    banned  = Product.objects.filter(tenant=tenant, status=ProductStatus.BANNED).count()
    return {"total": total, "active": active, "draft": draft, "banned": banned,
            "active_rate": round(active/total*100,1) if total else 0}


def _order_health(tenant) -> dict:
    from api.marketplace.models import Order
    from api.marketplace.enums import OrderStatus
    qs = Order.objects.filter(tenant=tenant)
    agg = qs.aggregate(
        total=Count("id"),
        pending=Count("id", filter=__import__("django.db.models",fromlist=["Q"]).Q(status=OrderStatus.PENDING)),
        delivered=Count("id", filter=__import__("django.db.models",fromlist=["Q"]).Q(status=OrderStatus.DELIVERED)),
        cancelled=Count("id", filter=__import__("django.db.models",fromlist=["Q"]).Q(status=OrderStatus.CANCELLED)),
        revenue=Sum("total_price"),
    )
    return {k: str(v) if k == "revenue" else v for k, v in agg.items()}


def _seller_health(tenant) -> dict:
    from api.marketplace.models import SellerProfile
    qs = SellerProfile.objects.filter(tenant=tenant)
    return {
        "total":     qs.count(),
        "active":    qs.filter(status="active").count(),
        "pending":   qs.filter(status="pending").count(),
        "suspended": qs.filter(status="suspended").count(),
        "avg_rating":str(qs.filter(status="active").aggregate(avg=Avg("average_rating"))["avg"] or 0),
    }


def _payment_health(tenant) -> dict:
    from api.marketplace.models import PaymentTransaction, EscrowHolding
    from api.marketplace.enums import PaymentStatus, EscrowStatus
    txns = PaymentTransaction.objects.filter(tenant=tenant)
    return {
        "total_transactions":  txns.count(),
        "success_rate":        round(txns.filter(status=PaymentStatus.SUCCESS).count() / max(1,txns.count()) * 100, 1),
        "escrow_holding":      str(EscrowHolding.objects.filter(tenant=tenant, status=EscrowStatus.HOLDING).aggregate(t=Sum("net_amount"))["t"] or 0),
        "disputed_escrows":    EscrowHolding.objects.filter(tenant=tenant, status=EscrowStatus.DISPUTED).count(),
    }


def _review_health(tenant) -> dict:
    from api.marketplace.models import ProductReview
    qs = ProductReview.objects.filter(product__tenant=tenant)
    return {
        "total":     qs.count(),
        "approved":  qs.filter(is_approved=True).count(),
        "pending":   qs.filter(is_approved=False).count(),
        "avg_rating":str(round(qs.filter(is_approved=True).aggregate(avg=Avg("rating"))["avg"] or 0, 2)),
    }


def _inventory_health(tenant) -> dict:
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import get_low_stock_items, get_out_of_stock
    return {
        "low_stock":    get_low_stock_items(tenant).count(),
        "out_of_stock": get_out_of_stock(tenant).count(),
    }
