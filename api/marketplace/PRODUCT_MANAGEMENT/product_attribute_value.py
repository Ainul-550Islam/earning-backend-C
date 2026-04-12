"""
PRODUCT_MANAGEMENT/product_attribute_value.py
Pre-defined valid values per attribute, used for validation & dropdowns.
"""
from django.db import models
from api.tenants.models import Tenant


class AttributeValueDefinition(models.Model):
    """
    Admin-defined allowed values for each attribute name.
    Used to power filter checkboxes and validate product listings.
    """
    tenant          = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                         related_name="attr_value_defs_tenant")
    attribute_name  = models.CharField(max_length=100, db_index=True)
    value           = models.CharField(max_length=200)
    unit            = models.CharField(max_length=30, blank=True)
    sort_order      = models.PositiveSmallIntegerField(default=0)
    is_active       = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_attribute_value_definition"
        ordering  = ["sort_order","value"]
        unique_together = [("tenant","attribute_name","value")]

    def __str__(self):
        return f"{self.attribute_name}: {self.value}"


# ── Hardcoded common values (fallback if DB has no definitions) ───────────────
COMMON_ATTRIBUTE_VALUES = {
    "Color":    ["Red","Blue","Green","Black","White","Yellow","Pink","Grey","Orange","Purple","Brown","Beige"],
    "Size":     ["XS","S","M","L","XL","XXL","XXXL","4XL","5XL","Free Size"],
    "Material": ["Cotton","Polyester","Leather","Nylon","Wool","Silk","Denim","Linen","Rayon","Velvet"],
    "RAM":      ["2GB","3GB","4GB","6GB","8GB","12GB","16GB","32GB"],
    "Storage":  ["16GB","32GB","64GB","128GB","256GB","512GB","1TB"],
    "Display":  ["5.0 inch","5.5 inch","6.0 inch","6.1 inch","6.5 inch","6.7 inch","7.0 inch"],
    "Battery":  ["2000mAh","3000mAh","4000mAh","5000mAh","6000mAh"],
    "Processor":["Snapdragon","MediaTek","Apple A-series","Exynos","Dimensity"],
    "Weight":   ["100g","200g","300g","500g","1kg","2kg","5kg","10kg"],
    "Connectivity":["WiFi","Bluetooth 5.0","4G LTE","5G","USB-C","HDMI"],
}


def get_possible_values(attribute_name: str, tenant=None) -> list:
    """Get valid values for an attribute name."""
    if tenant:
        db_values = list(
            AttributeValueDefinition.objects.filter(
                tenant=tenant, attribute_name=attribute_name, is_active=True
            ).values_list("value", flat=True)
        )
        if db_values:
            return db_values
    return COMMON_ATTRIBUTE_VALUES.get(attribute_name, [])


def get_all_attributes_with_values(tenant=None) -> dict:
    """Get all attribute names and their possible values."""
    result = dict(COMMON_ATTRIBUTE_VALUES)  # Start with defaults
    if tenant:
        db_values = AttributeValueDefinition.objects.filter(tenant=tenant, is_active=True)
        for av in db_values:
            result.setdefault(av.attribute_name, [])
            if av.value not in result[av.attribute_name]:
                result[av.attribute_name].append(av.value)
    return result


def add_custom_value(tenant, attribute_name: str, value: str, unit: str = "") -> AttributeValueDefinition:
    obj, _ = AttributeValueDefinition.objects.get_or_create(
        tenant=tenant, attribute_name=attribute_name, value=value,
        defaults={"unit": unit, "is_active": True}
    )
    return obj


def is_valid_value(attribute_name: str, value: str, tenant=None) -> bool:
    """Check if a value is valid for the given attribute."""
    valid_values = get_possible_values(attribute_name, tenant)
    if not valid_values:
        return True  # No restriction if no values defined
    return value in valid_values
