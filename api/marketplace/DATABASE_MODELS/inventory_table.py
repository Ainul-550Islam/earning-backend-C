"""
DATABASE_MODELS/inventory_table.py — Inventory Table Reference & Queries
"""
from api.marketplace.models import ProductInventory, ProductVariant
from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import (
    InventoryManager, check_availability, get_low_stock_items, get_out_of_stock
)
from django.db.models import Sum


def inventory_overview(tenant) -> dict:
    qs = ProductInventory.objects.filter(variant__product__tenant=tenant)
    return {
        "total_skus":       qs.count(),
        "in_stock":         qs.filter(quantity__gt=0).count(),
        "out_of_stock":     qs.filter(quantity=0).count(),
        "low_stock":        qs.filter(quantity__lte=10, quantity__gt=0).count(),
        "total_units":      str(qs.aggregate(t=Sum("quantity"))["t"] or 0),
        "reserved_units":   str(qs.aggregate(t=Sum("reserved_quantity"))["t"] or 0),
    }


def get_inventory_by_sku(sku: str) -> dict:
    try:
        v = ProductVariant.objects.select_related("product","inventory").get(sku=sku)
        return {
            "sku":           v.sku,
            "product":       v.product.name,
            "quantity":      v.inventory.quantity,
            "reserved":      v.inventory.reserved_quantity,
            "available":     v.inventory.available_quantity,
            "warehouse":     v.inventory.warehouse_location,
            "is_low_stock":  v.inventory.is_low_stock,
        }
    except ProductVariant.DoesNotExist:
        return {}


__all__ = [
    "ProductInventory","ProductVariant","InventoryManager",
    "check_availability","get_low_stock_items","get_out_of_stock",
    "inventory_overview","get_inventory_by_sku",
]
