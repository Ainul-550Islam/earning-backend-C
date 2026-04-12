"""
CATEGORY_TAXONOMY/category_tree.py — Category Tree Builder
"""
from api.marketplace.models import Category


def build_tree(tenant, max_depth: int = 3) -> list:
    """Build full nested category tree as list of dicts."""
    roots = Category.objects.filter(
        tenant=tenant, parent__isnull=True, is_active=True
    ).order_by("sort_order","name")
    return [_build_node(cat, max_depth, 0) for cat in roots]


def _build_node(category: Category, max_depth: int, depth: int) -> dict:
    node = {
        "id":       category.pk,
        "name":     category.name,
        "slug":     category.slug,
        "icon":     category.icon,
        "level":    category.level,
        "children": [],
    }
    if depth < max_depth:
        children = category.children.filter(is_active=True).order_by("sort_order","name")
        node["children"] = [_build_node(c, max_depth, depth + 1) for c in children]
    return node


def get_category_path(category: Category) -> list:
    """Return list of ancestor categories from root to given category."""
    path = []
    node = category
    while node:
        path.insert(0, {"id": node.pk, "name": node.name, "slug": node.slug})
        node = node.parent
    return path


def flatten_tree(tenant) -> list:
    """Return all categories as flat list with path."""
    return [
        {
            "id":        cat.pk,
            "name":      cat.name,
            "slug":      cat.slug,
            "level":     cat.level,
            "full_path": cat.full_path,
            "parent_id": cat.parent_id,
        }
        for cat in Category.objects.filter(tenant=tenant, is_active=True).order_by("level","sort_order")
    ]


def get_sibling_categories(category: Category) -> list:
    return list(
        Category.objects.filter(
            tenant=category.tenant,
            parent=category.parent,
            is_active=True,
        ).exclude(pk=category.pk).order_by("sort_order")
    )
