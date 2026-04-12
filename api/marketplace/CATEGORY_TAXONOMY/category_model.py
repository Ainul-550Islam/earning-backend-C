"""
CATEGORY_TAXONOMY/category_model.py — Category Model Helpers
"""
from django.db import transaction
from api.marketplace.models import Category, Product
from api.marketplace.utils import unique_slugify


def get_all_descendants(category: Category) -> list:
    """Recursively get all descendant category IDs."""
    ids = []
    for child in category.children.filter(is_active=True):
        ids.append(child.pk)
        ids.extend(get_all_descendants(child))
    return ids


def get_all_products_in_tree(category: Category):
    """Get all products in a category + all its subcategories."""
    all_ids = [category.pk] + get_all_descendants(category)
    return Product.objects.filter(category_id__in=all_ids, status="active")


def create_category(tenant, name: str, parent=None, icon: str = "",
                     description: str = "", sort_order: int = 0) -> Category:
    slug = unique_slugify(Category, name)
    return Category.objects.create(
        tenant=tenant, name=name, slug=slug, parent=parent,
        icon=icon, description=description, sort_order=sort_order,
        is_active=True,
    )


@transaction.atomic
def move_category(category: Category, new_parent) -> Category:
    """Move a category to a new parent in the tree."""
    old_parent_name = category.parent.name if category.parent else "Root"
    category.parent = new_parent
    category.save(update_fields=["parent"])
    # Invalidate cache
    from api.marketplace.cache import invalidate_category_tree
    invalidate_category_tree(category.tenant_id)
    return category


def deactivate_category_tree(category: Category) -> int:
    """Deactivate a category and all its descendants."""
    ids      = [category.pk] + get_all_descendants(category)
    count    = Category.objects.filter(pk__in=ids).update(is_active=False)
    # Deactivate all products in these categories
    Product.objects.filter(category_id__in=ids).update(status="inactive")
    return count


def get_leaf_categories(tenant) -> list:
    """Categories with no children (leaf nodes)."""
    return list(
        Category.objects.filter(tenant=tenant, is_active=True)
        .exclude(children__is_active=True)
        .order_by("level","sort_order","name")
    )


def category_depth(category: Category) -> int:
    """Get depth of a category in the tree."""
    return category.level


def reorder_categories(parent_id, ordered_ids: list) -> int:
    """Reorder child categories by setting sort_order."""
    updated = 0
    for idx, cat_id in enumerate(ordered_ids):
        updated += Category.objects.filter(pk=cat_id, parent_id=parent_id).update(sort_order=idx)
    return updated
