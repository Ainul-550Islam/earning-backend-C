"""
VENDOR_TOOLS/product_import.py — Product Import from External Sources
"""
import csv
import json
import io
import logging
from decimal import Decimal
from api.marketplace.models import Product, ProductVariant, ProductInventory, Category
from api.marketplace.utils import unique_slugify, generate_sku

logger = logging.getLogger(__name__)


def import_from_json(seller, tenant, json_data: list) -> dict:
    """Import products from JSON list."""
    created, errors = 0, []
    for i, item in enumerate(json_data):
        try:
            _create_product_from_dict(seller, tenant, item)
            created += 1
        except Exception as e:
            errors.append({"index": i, "name": item.get("name","?"), "error": str(e)})
    return {"created": created, "errors": errors}


def _create_product_from_dict(seller, tenant, data: dict) -> Product:
    category = Category.objects.filter(tenant=tenant, slug=data.get("category_slug","")).first()
    slug     = unique_slugify(Product, data["name"])
    product  = Product.objects.create(
        tenant=tenant, seller=seller,
        name=data["name"], slug=slug,
        description=data.get("description", data["name"]),
        base_price=Decimal(str(data["base_price"])),
        sale_price=Decimal(str(data["sale_price"])) if data.get("sale_price") else None,
        category=category, status="draft",
        tags=data.get("tags", ""),
    )
    variant = ProductVariant.objects.create(
        tenant=tenant, product=product,
        name="Default", sku=data.get("sku") or generate_sku(product.name),
        color=data.get("color",""), size=data.get("size",""),
    )
    ProductInventory.objects.create(
        tenant=tenant, variant=variant, quantity=int(data.get("stock", 0))
    )
    return product
