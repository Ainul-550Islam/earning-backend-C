"""CATEGORY_TAXONOMY/subcategory_manager.py — Subcategory helpers"""
from api.marketplace.models import Category
from api.marketplace.utils import unique_slugify


def create_subcategory(tenant, parent: Category, name: str, **kwargs) -> Category:
    slug = unique_slugify(Category, name)
    return Category.objects.create(tenant=tenant, name=name, slug=slug, parent=parent, **kwargs)


def reorder_subcategories(category_ids: list):
    for i, cat_id in enumerate(category_ids):
        Category.objects.filter(pk=cat_id).update(sort_order=i)


def get_full_hierarchy(category: Category) -> dict:
    from api.marketplace.CATEGORY_TAXONOMY.category_tree import get_all_descendants_ids
    all_ids = [category.pk] + get_all_descendants_ids(category)
    return {
        "root": {"id": category.pk, "name": category.name},
        "total_products": __import__("api.marketplace.models",fromlist=["Product"]).Product.objects.filter(category_id__in=all_ids, status="active").count(),
        "depth": category.level,
    }
