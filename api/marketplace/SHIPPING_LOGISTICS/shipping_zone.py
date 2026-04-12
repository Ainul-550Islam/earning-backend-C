"""
SHIPPING_LOGISTICS/shipping_zone.py — Shipping Zone Management
"""
from django.db import models


class ShippingZone(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="shipping_zones_tenant")
    name        = models.CharField(max_length=100)
    zone_type   = models.CharField(max_length=20, choices=[
        ("inside_dhaka","Inside Dhaka"),("outside_dhaka","Outside Dhaka"),
        ("divisional","Divisional City"),("remote","Remote Area"),
    ])
    rate        = models.DecimalField(max_digits=8, decimal_places=2, default=60)
    extra_rate  = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                      help_text="Extra per kg after first 0.5kg")
    is_active   = models.BooleanField(default=True)
    est_days    = models.PositiveSmallIntegerField(default=2)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_shipping_zone"

    def __str__(self):
        return f"{self.name} ({self.zone_type}) — {self.rate} BDT"


DHAKA_THANAS = [
    "Mirpur","Gulshan","Banani","Dhanmondi","Uttara","Mohammadpur",
    "Motijheel","Tejgaon","Jatrabari","Lalbagh","Rayer Bazar","Khilgaon",
    "Badda","Sabujbagh","Demra","Shyampur","Keraniganj","Pallabi",
]

def get_zone_for_city(city: str, district: str = "") -> str:
    city_lower = city.lower().strip()
    if any(thana.lower() in city_lower for thana in DHAKA_THANAS) or "dhaka" in city_lower:
        return "inside_dhaka"
    divisional_cities = ["chittagong","rajshahi","khulna","sylhet","barisal","rangpur","mymensingh","comilla"]
    if any(d in city_lower for d in divisional_cities):
        return "divisional"
    if district.lower() in ["cox's bazar","bandarban","rangamati","khagrachhari"]:
        return "remote"
    return "outside_dhaka"
