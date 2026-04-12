"""
PRODUCT_MANAGEMENT/product_tag.py — Product Tagging System
"""
from api.marketplace.models import Product


def get_tags(product: Product) -> list:
    """Return list of clean tags for a product."""
    if not product.tags:
        return []
    return [t.strip() for t in product.tags.split(",") if t.strip()]


def set_tags(product: Product, tags: list):
    """Set tags for a product (replaces existing)."""
    product.tags = ", ".join([t.strip() for t in tags if t.strip()])
    product.save(update_fields=["tags"])


def add_tag(product: Product, tag: str):
    """Add a single tag without removing existing ones."""
    existing = get_tags(product)
    tag = tag.strip().lower()
    if tag and tag not in [t.lower() for t in existing]:
        existing.append(tag)
        set_tags(product, existing)


def remove_tag(product: Product, tag: str):
    """Remove a specific tag from a product."""
    existing = get_tags(product)
    tag_lower = tag.strip().lower()
    updated = [t for t in existing if t.lower() != tag_lower]
    set_tags(product, updated)


def search_by_tag(tenant, tag: str, limit: int = None):
    qs = Product.objects.filter(
        tenant=tenant, tags__icontains=tag, status="active"
    ).order_by("-total_sales")
    return qs[:limit] if limit else qs


def get_popular_tags(tenant, limit: int = 20) -> list:
    """Get most commonly used tags across all products."""
    products = Product.objects.filter(tenant=tenant, status="active").exclude(tags="")
    tag_counts = {}
    for product in products.values_list("tags", flat=True):
        for tag in product.split(","):
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]


def suggest_tags(product_name: str, description: str = "", category_name: str = "") -> list:
    """Suggest relevant tags based on product name and description."""
    words = (f"{product_name} {description} {category_name}").lower().split()
    # Filter common words and short words
    stop_words = {"the","a","an","and","or","for","in","on","at","to","of","with","by","from"}
    suggested = [w for w in words if len(w) > 3 and w not in stop_words]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for w in suggested:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:10]
