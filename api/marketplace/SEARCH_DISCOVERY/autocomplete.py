"""
SEARCH_DISCOVERY/autocomplete.py — Search Autocomplete & Suggestions
"""
from django.core.cache import cache
from django.db.models import Q
from api.marketplace.models import Product, Category
from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent


def autocomplete_suggestions(tenant, query: str, limit: int = 8) -> list:
    """Fast autocomplete using cache + DB fallback."""
    if len(query) < 2:
        return []
    cache_key = f"autocomplete:{tenant.pk}:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Products
    products = list(
        Product.objects.filter(tenant=tenant, status="active", name__icontains=query)
        .values_list("name",flat=True)[:limit]
    )
    # Categories
    categories = list(
        Category.objects.filter(tenant=tenant, is_active=True, name__icontains=query)
        .values_list("name",flat=True)[:3]
    )
    suggestions = list(dict.fromkeys(products + categories))[:limit]
    cache.set(cache_key, suggestions, timeout=120)
    return suggestions


def trending_searches(tenant, days: int = 7, limit: int = 10) -> list:
    """Get trending search queries from analytics events."""
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    queries = (
        AppEvent.objects.filter(tenant=tenant, event_type="search", created_at__gte=since)
        .values("properties")
        .order_by()
    )
    query_counts = {}
    for e in queries:
        q = e["properties"].get("query","").strip().lower()
        if q and len(q) >= 2:
            query_counts[q] = query_counts.get(q, 0) + 1
    return sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:limit]


def zero_result_queries(tenant, days: int = 7) -> list:
    """Queries that returned no results — useful for content gaps."""
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    no_results = AppEvent.objects.filter(
        tenant=tenant, event_type="search",
        created_at__gte=since,
        properties__has_key="result_count",
    ).filter(properties__result_count=0)
    queries = {}
    for e in no_results:
        q = e.properties.get("query","").strip().lower()
        if q:
            queries[q] = queries.get(q, 0) + 1
    return sorted(queries.items(), key=lambda x: x[1], reverse=True)[:20]
