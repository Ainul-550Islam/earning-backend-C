"""
CATEGORY_TAXONOMY/category_breadcrumb.py — Breadcrumb Navigation Builder
"""
from api.marketplace.models import Category


def get_breadcrumb(category: Category) -> list:
    """Build breadcrumb from root to given category."""
    crumbs = []
    node   = category
    while node:
        crumbs.insert(0, {
            "id":    node.pk,
            "name":  node.name,
            "slug":  node.slug,
            "level": node.level,
            "url":   f"/category/{node.slug}/",
        })
        node = node.parent
    return crumbs


def get_breadcrumb_string(category: Category, separator: str = " > ") -> str:
    """Return breadcrumb as a formatted string."""
    crumbs = get_breadcrumb(category)
    return separator.join(c["name"] for c in crumbs)


def get_schema_breadcrumb(category: Category) -> dict:
    """
    JSON-LD breadcrumb schema for SEO.
    https://schema.org/BreadcrumbList
    """
    crumbs = get_breadcrumb(category)
    return {
        "@context":  "https://schema.org",
        "@type":     "BreadcrumbList",
        "itemListElement": [
            {
                "@type":    "ListItem",
                "position": i + 1,
                "name":     c["name"],
                "item":     c["url"],
            }
            for i, c in enumerate(crumbs)
        ],
    }


def get_parent_chain(category: Category) -> list:
    """Return all ancestor categories as a list from root to parent."""
    chain = get_breadcrumb(category)
    return chain[:-1]  # Exclude the category itself


def get_sibling_breadcrumbs(category: Category) -> list:
    """Get breadcrumbs for all sibling categories."""
    siblings = Category.objects.filter(
        parent=category.parent, is_active=True
    ).exclude(pk=category.pk).order_by("sort_order","name")
    return [
        {"id": s.pk, "name": s.name, "slug": s.slug, "is_current": False}
        for s in siblings
    ]
