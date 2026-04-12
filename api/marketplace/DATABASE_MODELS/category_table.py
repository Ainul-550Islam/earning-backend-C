"""
DATABASE_MODELS/category_table.py — Category Table Reference
"""
from api.marketplace.models import Category
from api.marketplace.CATEGORY_TAXONOMY.category_tree import build_tree, get_category_path
from api.marketplace.CATEGORY_TAXONOMY.category_model import get_all_descendants
from django.db.models import Count


def root_categories(tenant) -> list:
    return list(
        Category.objects.filter(tenant=tenant, parent__isnull=True, is_active=True)
        .order_by("sort_order","name")
    )


def categories_with_product_counts(tenant) -> list:
    return list(
        Category.objects.filter(tenant=tenant, is_active=True)
        .annotate(product_count=Count("products"))
        .order_by("level","sort_order")
        .values("id","name","slug","level","parent_id","product_count")
    )


def empty_categories(tenant) -> list:
    """Categories with no active products."""
    return list(
        Category.objects.filter(tenant=tenant, is_active=True)
        .annotate(product_count=Count("products"))
        .filter(product_count=0)
    )


__all__ = [
    "Category","build_tree","get_category_path","get_all_descendants",
    "root_categories","categories_with_product_counts","empty_categories",
]
