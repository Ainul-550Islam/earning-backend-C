"""
DATABASE_MODELS/cart_table.py — Cart Table Reference & Queries
"""
from api.marketplace.models import Cart, CartItem
from django.db.models import Sum, Count


def active_carts_count(tenant) -> int:
    return Cart.objects.filter(tenant=tenant, is_active=True, items__isnull=False).distinct().count()


def cart_value_distribution(tenant) -> dict:
    from django.utils import timezone
    from datetime import timedelta
    since = timezone.now() - timedelta(days=7)
    carts = Cart.objects.filter(tenant=tenant, is_active=True, created_at__gte=since)
    totals = [c.total for c in carts if c.total > 0]
    if not totals:
        return {"avg": 0, "min": 0, "max": 0, "count": 0}
    return {
        "avg":   round(sum(totals) / len(totals), 2),
        "min":   float(min(totals)),
        "max":   float(max(totals)),
        "count": len(totals),
    }


__all__ = ["Cart","CartItem","active_carts_count","cart_value_distribution"]
