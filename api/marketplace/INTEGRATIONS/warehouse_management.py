"""INTEGRATIONS/warehouse_management.py — Warehouse Location & Bin Management"""
from django.db import models
from api.tenants.models import Tenant


class WarehouseLocation(models.Model):
    """Physical warehouse location for inventory."""
    tenant      = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                    related_name="marketplace_warehouse_locations_tenant")
    name        = models.CharField(max_length=100)
    zone        = models.CharField(max_length=50, blank=True)
    aisle       = models.CharField(max_length=10, blank=True)
    rack        = models.CharField(max_length=10, blank=True)
    bin         = models.CharField(max_length=10, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_warehouse_location"

    def __str__(self):
        return f"{self.name} | {self.zone}-{self.aisle}-{self.rack}-{self.bin}"

    @property
    def location_code(self) -> str:
        return f"{self.zone}{self.aisle}{self.rack}{self.bin}".upper()
