"""
SHIPPING_LOGISTICS/delivery_partner.py — Last-Mile Delivery Partner Management
"""
from django.db import models


class DeliveryPartner(models.Model):
    PARTNER_TYPES = [
        ("courier","Courier Company"),("freelance","Freelance Rider"),
        ("internal","In-house Delivery"),("platform","Platform Logistics"),
    ]
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="delivery_partners_tenant")
    name         = models.CharField(max_length=200)
    partner_type = models.CharField(max_length=15, choices=PARTNER_TYPES)
    phone        = models.CharField(max_length=20, blank=True)
    email        = models.EmailField(blank=True)
    api_endpoint = models.URLField(blank=True)
    api_key      = models.CharField(max_length=200, blank=True)
    coverage_area= models.TextField(blank=True, help_text="JSON list of districts/cities covered")
    base_rate    = models.DecimalField(max_digits=8, decimal_places=2, default=60)
    per_km_rate  = models.DecimalField(max_digits=6, decimal_places=2, default=5)
    rating       = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_deliveries = models.PositiveIntegerField(default=0)
    is_active    = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_delivery_partner"

    def __str__(self):
        return f"{self.name} ({self.partner_type})"


class DeliveryAssignment(models.Model):
    STATUS = [("pending","Pending"),("assigned","Assigned"),("picked_up","Picked Up"),
              ("in_transit","In Transit"),("delivered","Delivered"),("failed","Failed")]
    tenant   = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                  related_name="delivery_assignments_tenant")
    order    = models.OneToOneField("marketplace.Order", on_delete=models.CASCADE,
                                     related_name="delivery_assignment")
    partner  = models.ForeignKey(DeliveryPartner, on_delete=models.SET_NULL, null=True)
    status   = models.CharField(max_length=15, choices=STATUS, default="pending")
    tracking_number = models.CharField(max_length=100, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    delivered_at= models.DateTimeField(null=True, blank=True)
    delivery_fee= models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes    = models.TextField(blank=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_delivery_assignment"
