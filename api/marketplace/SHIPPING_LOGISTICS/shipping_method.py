"""shipping_method.py — Shipping method registry"""
from django.db import models
from api.tenants.models import Tenant


class ShippingMethod(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_shipping_methods_tenant")
    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=100)
    base_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    per_kg_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estimated_days_min = models.PositiveSmallIntegerField(default=1)
    estimated_days_max = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    supports_cod = models.BooleanField(default=True)
    is_express = models.BooleanField(default=False)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_shipping_method"

    def __str__(self):
        return f"{self.name} ({self.carrier})"

    def calculate_rate(self, weight_grams: int) -> float:
        weight_kg = weight_grams / 1000
        return float(self.base_rate) + (float(self.per_kg_rate) * weight_kg)
