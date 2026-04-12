"""CATEGORY_TAXONOMY/category_image.py — Category image management"""
from api.marketplace.models import Category
import os

ALLOWED_EXT = {".jpg",".jpeg",".png",".webp",".svg"}


def set_category_image(category: Category, image_file) -> Category:
    ext = os.path.splitext(image_file.name)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Invalid format. Allowed: {ALLOWED_EXT}")
    if image_file.size > 2*1024*1024:
        raise ValueError("Image must be under 2MB.")
    category.image = image_file
    category.save(update_fields=["image"])
    return category


def get_category_image_url(category: Category, default: str = "") -> str:
    try:
        return category.image.url if category.image else default
    except Exception:
        return default
