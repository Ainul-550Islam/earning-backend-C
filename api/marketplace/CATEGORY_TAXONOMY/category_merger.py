"""
CATEGORY_TAXONOMY/category_merger.py — Category Merger & Reorganisation
"""
from django.db import transaction
from api.marketplace.models import Category, Product


@transaction.atomic
def merge_categories(source: Category, target: Category) -> dict:
    """
    Merge source category into target:
    - Move all products from source → target
    - Move all child categories from source → target
    - Delete source category
    """
    if source.pk == target.pk:
        raise ValueError("Cannot merge a category into itself")
    if source.tenant != target.tenant:
        raise ValueError("Cannot merge categories from different tenants")

    # Move products
    product_count = Product.objects.filter(category=source).update(category=target)

    # Move children
    child_count = Category.objects.filter(parent=source).update(parent=target)

    source_name = source.name
    source.delete()

    # Invalidate cache
    from api.marketplace.cache import invalidate_category_tree
    invalidate_category_tree(target.tenant_id)

    return {
        "source_deleted":        source_name,
        "target":                target.name,
        "products_moved":        product_count,
        "subcategories_moved":   child_count,
    }


@transaction.atomic
def split_category(parent: Category, new_name: str, product_ids: list, tenant) -> Category:
    """Create a new subcategory and move specified products into it."""
    from api.marketplace.utils import unique_slugify
    slug = unique_slugify(Category, new_name)
    new_cat = Category.objects.create(
        tenant=tenant, name=new_name, slug=slug, parent=parent, is_active=True
    )
    moved = Product.objects.filter(pk__in=product_ids, category=parent).update(category=new_cat)
    return new_cat


def reindex_category_levels(tenant):
    """Rebuild level field for all categories (after restructuring)."""
    for cat in Category.objects.filter(tenant=tenant, parent__isnull=True):
        _set_level(cat, 0)


def _set_level(category: Category, level: int):
    category.level = level
    category.save(update_fields=["level"])
    for child in category.children.all():
        _set_level(child, level + 1)
