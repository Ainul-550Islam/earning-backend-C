"""
SEARCH_DISCOVERY/category_search.py — Category Search & Browse
"""
from api.marketplace.models import Category


def search_categories(tenant, query: str) -> list:
    return list(Category.objects.filter(
        tenant=tenant, is_active=True,
        name__icontains=query,
    ).order_by("level","sort_order")[:20])


def get_breadcrumb(category: Category) -> list:
    path = []
    node = category
    while node:
        path.insert(0, {"id": node.pk, "name": node.name, "slug": node.slug})
        node = node.parent
    return path


def get_children_with_counts(tenant, parent_id=None) -> list:
    from django.db.models import Count
    qs = Category.objects.filter(tenant=tenant, is_active=True, parent_id=parent_id)
    return list(qs.annotate(
        product_count=Count("products", filter=__import__("django.db.models",fromlist=["Q"]).Q(products__status="active"))
    ).values("id","name","slug","level","image","product_count").order_by("sort_order"))
