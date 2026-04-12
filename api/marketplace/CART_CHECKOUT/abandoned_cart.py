"""
CART_CHECKOUT/abandoned_cart.py — Abandoned Cart Detection & Recovery
"""
from django.utils import timezone
from datetime import timedelta
from api.marketplace.models import Cart


ABANDONED_HOURS = 24


def get_abandoned_carts(tenant, hours: int = ABANDONED_HOURS) -> list:
    cutoff = timezone.now() - timedelta(hours=hours)
    return list(
        Cart.objects.filter(
            tenant=tenant,
            is_active=True,
            updated_at__lt=cutoff,
            user__isnull=False,
        ).prefetch_related("items__variant__product")
        .select_related("user")
        .filter(items__isnull=False)
        .distinct()
    )


def get_abandonment_stats(tenant, days: int = 30) -> dict:
    since   = timezone.now() - timedelta(days=days)
    total   = Cart.objects.filter(tenant=tenant, created_at__gte=since).count()
    active  = Cart.objects.filter(tenant=tenant, created_at__gte=since, is_active=True).count()
    abandoned = get_abandoned_carts(tenant)
    from api.marketplace.models import Order
    converted = Order.objects.filter(tenant=tenant, created_at__gte=since).count()
    return {
        "total_carts":     total,
        "abandoned_carts": len(abandoned),
        "converted":       converted,
        "abandonment_rate": round(len(abandoned) / total * 100, 1) if total else 0,
    }


def build_recovery_email_data(cart: Cart) -> dict:
    items = cart.items.select_related("variant__product").all()
    return {
        "user_name":  cart.user.get_full_name() or cart.user.username,
        "user_email": cart.user.email,
        "items": [
            {
                "product": item.variant.product.name,
                "qty":     item.quantity,
                "price":   str(item.unit_price),
                "subtotal":str(item.subtotal),
            }
            for item in items
        ],
        "cart_total": str(cart.total),
        "recovery_link": f"/cart/recover/{cart.pk}/",
    }
