"""
PRODUCT_MANAGEMENT/product_recommendation.py — Simple content-based recommendations
"""
from api.marketplace.models import Product


def similar_products(product: Product, limit: int = 8):
    return Product.objects.filter(
        tenant=product.tenant,
        category=product.category,
        status="active",
    ).exclude(pk=product.pk).order_by("-average_rating", "-total_sales")[:limit]


def trending_products(tenant, limit: int = 10):
    return Product.objects.filter(tenant=tenant, status="active").order_by("-total_sales")[:limit]


def top_rated_products(tenant, limit: int = 10):
    return Product.objects.filter(tenant=tenant, status="active", review_count__gte=5
                                  ).order_by("-average_rating")[:limit]
