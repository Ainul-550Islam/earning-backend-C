"""CATEGORY_TAXONOMY/category_meta.py — SEO meta management for categories"""
from api.marketplace.models import Category


def update_meta(category: Category, title: str, description: str) -> Category:
    category.meta_title = title[:255]
    category.meta_description = description
    category.save(update_fields=["meta_title","meta_description"])
    return category


def auto_generate_meta(category: Category) -> dict:
    title = f"Buy {category.name} Online — Best Prices in Bangladesh"
    desc  = f"Shop the latest {category.name} at the best prices. Fast delivery across Bangladesh."
    return {"meta_title": title, "meta_description": desc}


def get_category_schema(category: Category) -> dict:
    """Schema.org BreadcrumbList for SEO"""
    from api.marketplace.CATEGORY_TAXONOMY.category_tree import get_category_path
    path = get_category_path(category)
    items = [{"@type":"ListItem","position":i+1,"name":p["name"],"item":f"https://yoursite.com/c/{p['slug']}/"} for i,p in enumerate(path)]
    return {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":items}
