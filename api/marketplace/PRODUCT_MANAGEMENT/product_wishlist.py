"""
PRODUCT_MANAGEMENT/product_wishlist.py — Wishlist
"""
from django.db import models
from api.marketplace.models import Product
from django.conf import settings
from api.tenants.models import Tenant


class Wishlist(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_wishlists_tenant")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="marketplace_wishlists")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_wishlist"
        unique_together = [("user", "product")]

    def __str__(self):
        return f"{self.user.username} ♥ {self.product.name}"
