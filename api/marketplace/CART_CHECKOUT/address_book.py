"""
CART_CHECKOUT/address_book.py — User Address Book
==================================================
Store, manage and validate delivery addresses for fast checkout.
"""
from django.db import models, transaction
from django.conf import settings
from api.marketplace.SHIPPING_LOGISTICS.shipping_city import get_city_info, search_cities
from api.marketplace.validators import validate_phone_bd


class SavedAddress(models.Model):
    LABEL_CHOICES = [
        ("home",   "Home"),
        ("office", "Office"),
        ("other",  "Other"),
    ]
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="saved_addresses_tenant")
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="saved_addresses")
    label       = models.CharField(max_length=10, choices=LABEL_CHOICES, default="home")
    full_name   = models.CharField(max_length=200)
    phone       = models.CharField(max_length=20)
    address_line= models.TextField(help_text="House/Road/Area details")
    city        = models.CharField(max_length=100)
    district    = models.CharField(max_length=100, blank=True)
    division    = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    country     = models.CharField(max_length=100, default="Bangladesh")
    latitude    = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_saved_address"
        ordering  = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.label}: {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Remove default from other addresses
            SavedAddress.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def to_shipping_data(self) -> dict:
        """Convert to Order shipping fields format."""
        return {
            "shipping_name":        self.full_name,
            "shipping_phone":       self.phone,
            "shipping_address":     self.address_line,
            "shipping_city":        self.city,
            "shipping_district":    self.district,
            "shipping_postal_code": self.postal_code,
            "shipping_country":     self.country,
        }


# ── Service functions ─────────────────────────────────────────────────────────

def get_user_addresses(user, tenant) -> list:
    """Get all active saved addresses for a user."""
    return list(
        SavedAddress.objects.filter(user=user, tenant=tenant, is_active=True)
        .values(
            "id","label","full_name","phone","address_line",
            "city","district","postal_code","country","is_default",
        )
    )


def get_default_address(user, tenant) -> dict:
    """Get user's default shipping address."""
    addr = SavedAddress.objects.filter(
        user=user, tenant=tenant, is_active=True, is_default=True
    ).first()
    if addr:
        return addr.to_shipping_data()
    # Fallback to most recently added
    addr = SavedAddress.objects.filter(user=user, tenant=tenant, is_active=True).first()
    return addr.to_shipping_data() if addr else {}


@transaction.atomic
def save_address(user, tenant, data: dict) -> SavedAddress:
    """Save a new delivery address."""
    # Enrich with city info
    city_info = get_city_info(data.get("city",""))
    if city_info and not data.get("district"):
        data["district"] = city_info.get("district","")
    if city_info and not data.get("division"):
        data["division"]  = city_info.get("division","")
    if city_info and not data.get("postal_code"):
        data["postal_code"]= city_info.get("postcode","")

    addr = SavedAddress.objects.create(
        user=user, tenant=tenant,
        label=data.get("label","other"),
        full_name=data["full_name"],
        phone=data["phone"],
        address_line=data["address_line"],
        city=data.get("city",""),
        district=data.get("district",""),
        division=data.get("division",""),
        postal_code=data.get("postal_code",""),
        country=data.get("country","Bangladesh"),
        is_default=data.get("is_default", False),
    )
    return addr


def update_address(address_id: int, user, data: dict) -> dict:
    try:
        addr = SavedAddress.objects.get(pk=address_id, user=user)
        for key, val in data.items():
            if hasattr(addr, key):
                setattr(addr, key, val)
        addr.save()
        return {"success": True, "id": addr.pk}
    except SavedAddress.DoesNotExist:
        return {"success": False, "error": "Address not found"}


def delete_address(address_id: int, user) -> bool:
    updated = SavedAddress.objects.filter(pk=address_id, user=user).update(is_active=False)
    return updated > 0


def set_default_address(address_id: int, user) -> bool:
    try:
        addr = SavedAddress.objects.get(pk=address_id, user=user, is_active=True)
        addr.is_default = True
        addr.save()
        return True
    except SavedAddress.DoesNotExist:
        return False


def validate_address(data: dict) -> dict:
    """Validate a shipping address dict before saving."""
    errors = []
    if not data.get("full_name","").strip():
        errors.append("Full name is required.")
    if not data.get("phone","").strip():
        errors.append("Phone number is required.")
    else:
        try:
            validate_phone_bd(data["phone"])
        except Exception as e:
            errors.append(str(e))
    if not data.get("address_line","").strip():
        errors.append("Address details are required.")
    if not data.get("city","").strip():
        errors.append("City is required.")
    return {"valid": len(errors) == 0, "errors": errors}


def search_address_suggestions(query: str) -> list:
    """Search city/area suggestions for address autocomplete."""
    return search_cities(query)
