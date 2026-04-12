"""
PRODUCT_MANAGEMENT/product_attribute.py — Product Attribute Management
=======================================================================
Attributes are key-value specs: RAM=8GB, Color=Black, Material=Cotton, etc.
"""
from api.marketplace.models import ProductAttribute, Product


def set_attribute(product: Product, name: str, value: str, unit: str = "") -> ProductAttribute:
    """Create or update a single attribute."""
    attr, _ = ProductAttribute.objects.update_or_create(
        product=product, name=name,
        defaults={"value": value, "unit": unit, "tenant": product.tenant}
    )
    return attr


def set_attributes_bulk(product: Product, attributes: list) -> list:
    """
    Set multiple attributes at once.
    attributes = [{"name": str, "value": str, "unit": str (optional)}, ...]
    """
    result = []
    for attr_data in attributes:
        attr = set_attribute(
            product,
            name=attr_data["name"],
            value=attr_data["value"],
            unit=attr_data.get("unit",""),
        )
        result.append(attr)
    return result


def get_attributes(product: Product) -> list:
    return list(ProductAttribute.objects.filter(product=product).order_by("sort_order","name"))


def get_attribute_dict(product: Product) -> dict:
    """Return attributes as {name: value} dict for easy access."""
    return {
        a.name: f"{a.value} {a.unit}".strip()
        for a in get_attributes(product)
    }


def delete_attribute(product: Product, name: str) -> bool:
    deleted, _ = ProductAttribute.objects.filter(product=product, name=name).delete()
    return deleted > 0


def get_all_attribute_names(tenant) -> list:
    """Get all unique attribute names used across a tenant's products."""
    return list(
        ProductAttribute.objects.filter(product__tenant=tenant)
        .values_list("name", flat=True)
        .distinct()
        .order_by("name")
    )


def get_attribute_values_for_filter(tenant, attribute_name: str, category=None) -> list:
    """Get all unique values for a given attribute name, for use in filter sidebar."""
    qs = ProductAttribute.objects.filter(
        product__tenant=tenant, name=attribute_name, product__status="active"
    )
    if category:
        qs = qs.filter(product__category=category)
    values = qs.values_list("value","unit").distinct()
    return [f"{v[0]} {v[1]}".strip() for v in values]


def copy_attributes(source_product: Product, target_product: Product):
    """Copy all attributes from one product to another."""
    for attr in get_attributes(source_product):
        set_attribute(target_product, attr.name, attr.value, attr.unit)


def validate_required_attributes(product: Product, required_names: list) -> dict:
    """Check that all required attribute names are present."""
    existing = {a.name for a in get_attributes(product)}
    missing  = [n for n in required_names if n not in existing]
    return {"valid": len(missing) == 0, "missing_attributes": missing}
