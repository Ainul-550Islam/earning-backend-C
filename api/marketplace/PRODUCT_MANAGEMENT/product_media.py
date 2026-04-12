"""
PRODUCT_MANAGEMENT/product_media.py — Product Image & Media Management
"""
import os
import io
import logging
from django.db import models
from django.conf import settings
from api.marketplace.models import Product, ProductVariant

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGES_PER_PRODUCT = 8
MAX_SIZE_MB = 10


class ProductImage(models.Model):
    """Product gallery images."""
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="product_images_tenant")
    product     = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant     = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="images")
    image       = models.ImageField(upload_to="marketplace/products/gallery/")
    alt_text    = models.CharField(max_length=200, blank=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)
    is_primary  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_product_image"
        ordering  = ["sort_order","created_at"]

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


def validate_image_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def product_image_path(product_id: int, filename: str) -> str:
    return f"marketplace/products/{product_id}/{filename}"


def add_product_image(product: Product, image_file, alt_text: str = "",
                       variant=None, is_primary: bool = False) -> dict:
    if not validate_image_extension(image_file.name):
        return {"success": False, "error": f"Invalid format. Allowed: {ALLOWED_EXTENSIONS}"}
    if image_file.size > MAX_SIZE_MB * 1024 * 1024:
        return {"success": False, "error": f"Image too large (max {MAX_SIZE_MB}MB)"}
    count = ProductImage.objects.filter(product=product, is_active=True).count()
    if count >= MAX_IMAGES_PER_PRODUCT:
        return {"success": False, "error": f"Max {MAX_IMAGES_PER_PRODUCT} images per product"}

    img = ProductImage.objects.create(
        tenant=product.tenant, product=product, image=image_file,
        alt_text=alt_text or product.name, variant=variant,
        is_primary=is_primary or (count == 0),
    )
    return {"success": True, "image_id": img.pk, "url": img.image.url}


def get_product_images(product: Product) -> list:
    return [
        {"id": img.pk, "url": img.image.url, "alt": img.alt_text,
         "is_primary": img.is_primary, "sort_order": img.sort_order}
        for img in ProductImage.objects.filter(product=product, is_active=True)
    ]


def reorder_images(product: Product, image_ids_in_order: list):
    """Set sort order based on provided ID list."""
    for idx, img_id in enumerate(image_ids_in_order):
        ProductImage.objects.filter(pk=img_id, product=product).update(sort_order=idx)


def set_primary_image(product: Product, image_id: int) -> bool:
    try:
        img = ProductImage.objects.get(pk=image_id, product=product)
        img.is_primary = True
        img.save()
        return True
    except ProductImage.DoesNotExist:
        return False
