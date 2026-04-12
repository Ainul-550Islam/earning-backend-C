"""
PRODUCT_MANAGEMENT/product_sku.py — SKU Generation, Lookup & Management
========================================================================
"""
import random
import string
from django.db.models import Q
from api.marketplace.models import ProductVariant, Product
from api.marketplace.utils import generate_sku


def generate_unique_sku(product_name: str, color: str = "", size: str = "", tenant=None) -> str:
    """Generate a globally unique SKU."""
    suffix = f"{color}{size}".upper().replace(" ","")[:6]
    base   = generate_sku(product_name, suffix)
    # Ensure uniqueness
    counter = 0
    candidate = base
    while sku_exists(candidate):
        counter += 1
        rand = "".join(random.choices(string.digits, k=3))
        candidate = f"{base}-{rand}"
        if counter > 50:
            raise ValueError(f"Cannot generate unique SKU for '{product_name}'")
    return candidate


def sku_exists(sku: str) -> bool:
    return ProductVariant.objects.filter(sku=sku).exists()


def find_by_sku(sku: str, tenant=None) -> ProductVariant:
    qs = ProductVariant.objects.select_related("product","inventory")
    if tenant:
        qs = qs.filter(product__tenant=tenant)
    return qs.get(sku=sku)


def search_by_sku(query: str, tenant=None) -> list:
    qs = ProductVariant.objects.filter(sku__icontains=query).select_related("product")
    if tenant:
        qs = qs.filter(product__tenant=tenant)
    return list(qs[:20])


def bulk_sku_lookup(sku_list: list, tenant=None) -> dict:
    """Look up multiple SKUs at once. Returns {sku: variant_or_None}."""
    qs = ProductVariant.objects.filter(sku__in=sku_list).select_related("product","inventory")
    if tenant:
        qs = qs.filter(product__tenant=tenant)
    found = {v.sku: v for v in qs}
    return {sku: found.get(sku) for sku in sku_list}


def auto_generate_skus_for_product(product: Product) -> dict:
    """Generate and assign SKUs to all variants that lack one."""
    updated = 0
    for variant in product.variants.filter(sku=""):
        sku = generate_unique_sku(product.name, variant.color, variant.size)
        variant.sku = sku
        variant.save(update_fields=["sku"])
        updated += 1
    return {"product_id": product.pk, "skus_generated": updated}


def validate_sku_format(sku: str) -> dict:
    import re
    pattern = r"^[A-Za-z0-9\-_]{4,50}$"
    valid   = bool(re.match(pattern, sku))
    return {
        "valid":   valid,
        "sku":     sku,
        "error":   "SKU must be 4-50 chars, alphanumeric, hyphens and underscores only." if not valid else "",
    }


def export_sku_list(tenant) -> list:
    """Export all SKUs for a tenant for inventory management."""
    return list(
        ProductVariant.objects.filter(product__tenant=tenant)
        .select_related("product","inventory")
        .values(
            "sku","product__name","name","color","size",
            "inventory__quantity","inventory__reserved_quantity",
        )
    )
