"""
DATABASE_MODELS/product_table.py — Product Table Reference & Queries
=====================================================================
Central import point for all product-related models and common queries.
"""
from api.marketplace.models import Product, ProductVariant, ProductInventory, ProductAttribute
from api.marketplace.enums import ProductStatus, ProductCondition
from django.db.models import Q, Sum, Count, Avg


def get_products_by_ids(product_ids: list, tenant=None):
    qs = Product.objects.filter(pk__in=product_ids)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.prefetch_related("variants__inventory","attributes").select_related("category","seller")


def active_products_count(tenant) -> int:
    return Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE).count()


def products_needing_attention(tenant) -> dict:
    """Products that need seller action."""
    return {
        "no_image":    Product.objects.filter(tenant=tenant, variants__image__isnull=True).distinct().count(),
        "no_stock":    ProductInventory.objects.filter(variant__product__tenant=tenant, quantity=0).count(),
        "draft":       Product.objects.filter(tenant=tenant, status=ProductStatus.DRAFT).count(),
        "low_rating":  Product.objects.filter(tenant=tenant, average_rating__lt=3, review_count__gte=5).count(),
    }


def product_revenue_rank(tenant, limit: int = 50) -> list:
    from api.marketplace.models import OrderItem
    return list(
        OrderItem.objects.filter(tenant=tenant)
        .values("variant__product__id","variant__product__name")
        .annotate(revenue=Sum("subtotal"), units=Sum("quantity"))
        .order_by("-revenue")[:limit]
    )


__all__ = [
    "Product","ProductVariant","ProductInventory","ProductAttribute",
    "ProductStatus","ProductCondition",
    "get_products_by_ids","active_products_count",
    "products_needing_attention","product_revenue_rank",
]
