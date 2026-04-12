"""seller_brand.py — Brand registration for sellers"""
from django.db import models
from api.marketplace.models import SellerProfile
from api.tenants.models import Tenant


class SellerBrand(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_seller_brands_tenant")
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="brands")
    brand_name = models.CharField(max_length=200)
    is_authorized = models.BooleanField(default=False)
    authorization_doc = models.FileField(upload_to="marketplace/brands/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_brand"

    def __str__(self):
        return f"{self.seller.store_name} — {self.brand_name}"
