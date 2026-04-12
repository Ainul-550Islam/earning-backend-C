"""
REVIEW_RATING/review_image.py — Review Image Management
"""
from django.db import models
from django.conf import settings
from api.marketplace.models import ProductReview
import os

MAX_IMAGES_PER_REVIEW = 5
ALLOWED_EXTS = {".jpg",".jpeg",".png",".webp"}
MAX_SIZE_MB   = 5


class ReviewImage(models.Model):
    tenant     = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                    related_name="review_images_tenant")
    review     = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="review_images")
    image      = models.ImageField(upload_to="marketplace/review_images/")
    caption    = models.CharField(max_length=200, blank=True)
    is_approved= models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_review_image"


def add_review_image(review: ProductReview, image_file, caption: str = "", tenant=None) -> dict:
    # Validate extension
    ext = os.path.splitext(image_file.name)[1].lower()
    if ext not in ALLOWED_EXTS:
        return {"success": False, "error": f"Invalid format. Allowed: {ALLOWED_EXTS}"}
    # Validate size
    if image_file.size > MAX_SIZE_MB * 1024 * 1024:
        return {"success": False, "error": f"Image too large. Max: {MAX_SIZE_MB}MB"}
    # Max images
    count = ReviewImage.objects.filter(review=review).count()
    if count >= MAX_IMAGES_PER_REVIEW:
        return {"success": False, "error": f"Max {MAX_IMAGES_PER_REVIEW} images per review"}

    img = ReviewImage.objects.create(review=review, image=image_file, caption=caption, tenant=tenant)
    return {"success": True, "image_id": img.pk, "url": img.image.url}


def get_review_images(review: ProductReview) -> list:
    return [{"id": img.pk, "url": img.image.url, "caption": img.caption}
            for img in ReviewImage.objects.filter(review=review, is_approved=True)]
