"""
SHIPPING_LOGISTICS/shipping_carrier.py — Shipping Carrier Registry
"""
from django.db import models


class ShippingCarrier(models.Model):
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="shipping_carriers_tenant")
    name         = models.CharField(max_length=100)
    code         = models.CharField(max_length=30, unique=True)
    logo         = models.ImageField(upload_to="marketplace/carriers/", null=True, blank=True)
    tracking_url = models.URLField(blank=True, help_text="Use {tracking_no} placeholder")
    api_endpoint = models.URLField(blank=True)
    api_key      = models.CharField(max_length=200, blank=True)
    supports_cod = models.BooleanField(default=True)
    max_weight_kg= models.DecimalField(max_digits=6, decimal_places=2, default=30)
    base_rate    = models.DecimalField(max_digits=8, decimal_places=2, default=60)
    per_kg_rate  = models.DecimalField(max_digits=8, decimal_places=2, default=20)
    cod_charge   = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_active    = models.BooleanField(default=True)
    est_days_min = models.PositiveSmallIntegerField(default=1)
    est_days_max = models.PositiveSmallIntegerField(default=3)
    service_area = models.CharField(max_length=20, default="nationwide",
                                     choices=[("nationwide","Nationwide"),("dhaka","Dhaka Only"),
                                              ("divisional","Divisional Capitals")])

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_shipping_carrier"
        ordering  = ["name"]

    def __str__(self):
        return self.name

    def get_tracking_url(self, tracking_no: str) -> str:
        if self.tracking_url and "{tracking_no}" in self.tracking_url:
            return self.tracking_url.replace("{tracking_no}", tracking_no)
        return self.tracking_url

    def calculate_rate(self, weight_kg: float, is_cod: bool = False) -> float:
        rate = float(self.base_rate) + (float(self.per_kg_rate) * max(0, weight_kg - 0.5))
        if is_cod and self.supports_cod:
            rate += float(self.cod_charge)
        return round(rate, 2)


BD_CARRIERS = [
    {"name": "Steadfast Courier",   "code": "steadfast",   "tracking_url": "https://steadfast.com.bd/t/{tracking_no}", "base_rate": 110, "supports_cod": True},
    {"name": "Pathao Courier",      "code": "pathao",      "tracking_url": "https://courier.pathao.com/track/{tracking_no}", "base_rate": 70,  "supports_cod": True},
    {"name": "Redx Courier",        "code": "redx",        "tracking_url": "https://redx.com.bd/track/{tracking_no}", "base_rate": 80,  "supports_cod": True},
    {"name": "eCourier",            "code": "ecourier",    "tracking_url": "https://www.ecourier.com.bd/track/{tracking_no}", "base_rate": 70,  "supports_cod": True},
    {"name": "Sundarban Courier",   "code": "sundarban",   "tracking_url": "", "base_rate": 60,  "supports_cod": True},
    {"name": "SA Paribahan",        "code": "sa_paribahan","tracking_url": "", "base_rate": 50,  "supports_cod": False},
]
