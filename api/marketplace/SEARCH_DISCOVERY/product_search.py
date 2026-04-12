"""SEARCH_DISCOVERY/product_search.py — Full-text product search"""
from django.db.models import Q
from api.marketplace.models import Product


def search_products(tenant, query: str, filters: dict = None, order_by: str = "-created_at"):
    qs = Product.objects.filter(tenant=tenant, status="active")
    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
        )
    if filters:
        category = filters.get("category")
        if category:
            qs = qs.filter(category_id=category)
        min_price = filters.get("min_price")
        if min_price:
            qs = qs.filter(base_price__gte=min_price)
        max_price = filters.get("max_price")
        if max_price:
            qs = qs.filter(base_price__lte=max_price)
        rating = filters.get("min_rating")
        if rating:
            qs = qs.filter(average_rating__gte=rating)
    return qs.order_by(order_by)
