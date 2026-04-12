"""
SEARCH_DISCOVERY/facet_manager.py — Dynamic Faceted Filter Builder
"""
from api.marketplace.models import ProductAttribute, Category, Product
from django.db.models import Count, Min, Max


def build_facets(tenant, category_id=None) -> dict:
    qs = ProductAttribute.objects.filter(product__tenant=tenant, product__status="active")
    if category_id:
        qs = qs.filter(product__category_id=category_id)

    attribute_values = {}
    for attr in qs.values("name","value").annotate(cnt=Count("product", distinct=True)).order_by("name","value"):
        attribute_values.setdefault(attr["name"], []).append({
            "value": attr["value"], "count": attr["cnt"]
        })

    price_qs = Product.objects.filter(tenant=tenant, status="active")
    if category_id:
        price_qs = price_qs.filter(category_id=category_id)
    price_agg = price_qs.aggregate(min=Min("base_price"), max=Max("base_price"))

    cats = Category.objects.filter(
        tenant=tenant, is_active=True, products__status="active",
        **{"parent_id": category_id} if category_id else {"parent__isnull": True}
    ).annotate(count=Count("products")).values("id","name","slug","count").order_by("-count")[:20]

    return {
        "attributes":  attribute_values,
        "price_range": {"min": float(price_agg["min"] or 0), "max": float(price_agg["max"] or 0)},
        "categories":  list(cats),
        "ratings":     [{"value": i, "label": f"{i}★ & up"} for i in range(4,0,-1)],
    }


def apply_facet_filters(qs, facets: dict):
    for attr_name, attr_value in facets.items():
        if attr_name in ("min_price","max_price","category","rating"):
            continue
        qs = qs.filter(attributes__name=attr_name, attributes__value__icontains=attr_value)
    return qs
