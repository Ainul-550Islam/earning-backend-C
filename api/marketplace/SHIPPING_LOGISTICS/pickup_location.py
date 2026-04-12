"""
SHIPPING_LOGISTICS/pickup_location.py — Seller Pickup Locations & Warehouses
"""
from django.db import models


class PickupLocation(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="pickup_locations_tenant")
    seller      = models.ForeignKey("marketplace.SellerProfile", on_delete=models.CASCADE,
                                     related_name="pickup_locations")
    name        = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100)
    phone       = models.CharField(max_length=20)
    address     = models.TextField()
    city        = models.CharField(max_length=100)
    district    = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    latitude    = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    pickup_days = models.CharField(max_length=100, default="Sat-Thu",
                                    help_text="e.g. Sat-Thu 9AM-5PM")

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_pickup_location"

    def __str__(self):
        return f"{self.seller.store_name} — {self.name} ({self.city})"

    def save(self, *args, **kwargs):
        if self.is_default:
            PickupLocation.objects.filter(seller=self.seller).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


def get_seller_pickup_locations(seller) -> list:
    return list(
        PickupLocation.objects.filter(seller=seller, is_active=True)
        .values("id","name","address","city","phone","is_default","pickup_days")
    )
