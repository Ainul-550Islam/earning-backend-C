"""
PRODUCT_MANAGEMENT/product_category.py
Category management utilities.
"""
from api.marketplace.models import Category
from api.marketplace.utils import unique_slugify
from api.marketplace.cache import invalidate_category_tree


def create_category(tenant, name: str, parent=None, **kwargs) -> Category:
    slug = unique_slugify(Category, name)
    cat = Category.objects.create(tenant=tenant, name=name, slug=slug, parent=parent, **kwargs)
    invalidate_category_tree(tenant.id)
    return cat


def move_category(category: Category, new_parent) -> Category:
    category.parent = new_parent
    category.save(update_fields=["parent"])
    invalidate_category_tree(category.tenant_id)
    return category


def get_category_tree(tenant) -> list:
    """Return all root categories; each has .children attribute."""
    return list(Category.objects.filter(tenant=tenant, parent__isnull=True, is_active=True)
                .prefetch_related("children__children").order_by("sort_order"))
