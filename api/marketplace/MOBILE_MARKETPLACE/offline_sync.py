"""
MOBILE_MARKETPLACE/offline_sync.py — Offline-First Data Sync Manifest
======================================================================
Generates sync manifests for mobile clients to cache offline.
App downloads: featured products, categories, user cart, order status.
"""
from django.utils import timezone


def generate_sync_manifest(tenant, user=None) -> dict:
    """Full sync package for app startup."""
    from api.marketplace.models import Category, Product
    from api.marketplace.enums import ProductStatus

    categories = list(
        Category.objects.filter(tenant=tenant, is_active=True, parent__isnull=True)
        .values("id","name","slug","image","sort_order")[:50]
    )
    featured = list(
        Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE, is_featured=True)
        .values("id","name","slug","base_price","sale_price","average_rating")[:20]
    )

    cart_data = {}
    if user:
        from api.marketplace.models import Cart
        cart = Cart.objects.filter(user=user, tenant=tenant, is_active=True).first()
        if cart:
            items = list(cart.items.values(
                "id","variant_id","quantity","unit_price",
                "variant__product__name","variant__name",
            ))
            cart_data = {"cart_id": cart.pk, "items": items, "total": str(cart.total)}

    return {
        "generated_at":  timezone.now().isoformat(),
        "ttl_seconds":   300,
        "categories":    categories,
        "featured":      featured,
        "cart":          cart_data,
        "config": {
            "currency":     "BDT",
            "free_shipping_threshold": 500,
        }
    }


def get_order_status_sync(user, tenant) -> list:
    """Recent orders status for offline display."""
    from api.marketplace.models import Order
    orders = Order.objects.filter(user=user, tenant=tenant).order_by("-created_at")[:10]
    return [
        {
            "order_number": o.order_number,
            "status":       o.status,
            "total":        str(o.total_price),
            "updated_at":   o.updated_at.isoformat(),
        }
        for o in orders
    ]


def get_wishlist_sync(user, tenant) -> list:
    """User wishlist for offline access."""
    from api.marketplace.PRODUCT_MANAGEMENT.product_wishlist import Wishlist
    items = Wishlist.objects.filter(user=user, tenant=tenant).select_related("product")
    return [
        {"product_id": w.product_id, "name": w.product.name, "price": str(w.product.effective_price)}
        for w in items
    ]
