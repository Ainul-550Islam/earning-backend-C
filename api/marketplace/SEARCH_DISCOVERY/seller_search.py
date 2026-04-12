"""
SEARCH_DISCOVERY/seller_search.py — Seller / Store Discovery
"""
from django.db.models import Q
from api.marketplace.models import SellerProfile


def search_sellers(tenant, query: str, filters: dict = None) -> list:
    qs = SellerProfile.objects.filter(tenant=tenant, status="active")
    if query:
        qs = qs.filter(
            Q(store_name__icontains=query)
            | Q(store_description__icontains=query)
            | Q(city__icontains=query)
        )
    if filters:
        if filters.get("city"):
            qs = qs.filter(city__icontains=filters["city"])
        if filters.get("min_rating"):
            qs = qs.filter(average_rating__gte=filters["min_rating"])
        if filters.get("is_featured"):
            qs = qs.filter(is_featured=True)
    return list(qs.order_by("-average_rating","-total_sales")[:50])


def get_featured_sellers(tenant, limit: int = 12) -> list:
    return list(SellerProfile.objects.filter(
        tenant=tenant, status="active", is_featured=True
    ).order_by("-total_sales")[:limit])


def get_top_sellers(tenant, limit: int = 10) -> list:
    return list(SellerProfile.objects.filter(
        tenant=tenant, status="active"
    ).order_by("-total_revenue")[:limit])
