"""
SEARCH_DISCOVERY/filter_manager.py — Dynamic Sidebar Filter Generation
"""
from api.marketplace.models import ProductAttribute, Product
from django.db.models import Min, Max, Count, Avg


def get_available_filters(tenant, category_id: int = None, queryset=None) -> dict:
    """
    Generate all available filter options for the search sidebar.
    Returns: price_range, ratings, attributes, categories, sellers
    """
    qs = queryset or Product.objects.filter(tenant=tenant, status="active")
    if category_id:
        qs = qs.filter(category_id=category_id)

    product_ids = qs.values_list("pk", flat=True)

    # Price range
    price_agg = qs.aggregate(min_p=Min("base_price"), max_p=Max("base_price"))

    # Attribute filters
    attributes = {}
    attr_qs = ProductAttribute.objects.filter(product_id__in=product_ids)
    for attr in attr_qs.values("name","value").distinct().order_by("name","value"):
        attributes.setdefault(attr["name"], [])
        if attr["value"] not in attributes[attr["name"]]:
            attributes[attr["name"]].append(attr["value"])

    # Rating buckets
    ratings = [
        {"value": r, "label": f"{r}★ & above",
         "count": qs.filter(average_rating__gte=r).count()}
        for r in [4, 3, 2, 1]
    ]

    # In-stock filter
    in_stock_count = qs.filter(variants__inventory__quantity__gt=0).distinct().count()

    # Categories
    from api.marketplace.models import Category
    categories = list(
        qs.values("category__id","category__name","category__slug")
        .annotate(count=Count("id"))
        .order_by("-count")[:15]
    )

    return {
        "price_range":  {"min": float(price_agg["min_p"] or 0), "max": float(price_agg["max_p"] or 0)},
        "ratings":      [r for r in ratings if r["count"] > 0],
        "attributes":   {k: sorted(v) for k,v in attributes.items()},
        "in_stock":     {"count": in_stock_count, "label": "In Stock Only"},
        "categories":   categories,
    }


def apply_filters(qs, filters: dict):
    """Apply a filter dict to a Product queryset."""
    if filters.get("category_id"):
        qs = qs.filter(category_id=filters["category_id"])
    if filters.get("min_price") is not None:
        qs = qs.filter(base_price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        qs = qs.filter(base_price__lte=filters["max_price"])
    if filters.get("min_rating"):
        qs = qs.filter(average_rating__gte=filters["min_rating"])
    if filters.get("in_stock"):
        qs = qs.filter(variants__inventory__quantity__gt=0).distinct()
    if filters.get("seller_id"):
        qs = qs.filter(seller_id=filters["seller_id"])
    if filters.get("condition"):
        qs = qs.filter(condition=filters["condition"])
    # Attribute filters: {"attributes": {"RAM": "8GB", "Color": "Black"}}
    for attr_name, attr_value in filters.get("attributes", {}).items():
        qs = qs.filter(attributes__name=attr_name, attributes__value__icontains=attr_value)
    return qs
