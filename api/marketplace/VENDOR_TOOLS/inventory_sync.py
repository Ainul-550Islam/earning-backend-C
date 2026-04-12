"""
VENDOR_TOOLS/inventory_sync.py — Real-time Inventory Sync with External Systems
================================================================================
Syncs inventory from: CSV upload, external ERP, warehouse APIs
Runs as Celery task every 15 minutes for connected sellers.
"""
from __future__ import annotations
import csv, io, logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class InventorySyncResult:
    def __init__(self):
        self.updated = 0
        self.skipped = 0
        self.errors  = []

    def to_dict(self):
        return {"updated": self.updated, "skipped": self.skipped, "errors": self.errors}


class InventorySyncService:

    def __init__(self, seller, tenant):
        self.seller = seller
        self.tenant = tenant

    def sync_from_csv(self, file_content: bytes) -> InventorySyncResult:
        """Update stock from a simple SKU,quantity CSV."""
        result = InventorySyncResult()
        reader = csv.DictReader(io.StringIO(file_content.decode("utf-8-sig", errors="replace")))

        for i, row in enumerate(reader, 2):
            sku = (row.get("sku") or row.get("SKU") or "").strip()
            qty_raw = (row.get("quantity") or row.get("stock") or "").strip()
            if not sku or not qty_raw:
                result.skipped += 1
                continue
            try:
                qty = int(qty_raw)
            except ValueError:
                result.errors.append({"row": i, "sku": sku, "error": "Invalid quantity"})
                continue
            try:
                self._update_stock(sku, qty)
                result.updated += 1
            except Exception as e:
                result.errors.append({"row": i, "sku": sku, "error": str(e)})

        logger.info("[InventorySync] CSV sync: %s", result.to_dict())
        return result

    def sync_from_dict(self, data: list) -> InventorySyncResult:
        """data = [{"sku": str, "quantity": int}, ...]"""
        result = InventorySyncResult()
        for item in data:
            try:
                self._update_stock(item["sku"], item["quantity"])
                result.updated += 1
            except Exception as e:
                result.errors.append({"sku": item.get("sku"), "error": str(e)})
        return result

    def get_low_stock_report(self, threshold: int = 10) -> list:
        from api.marketplace.models import ProductInventory
        items = ProductInventory.objects.filter(
            variant__product__seller=self.seller,
            variant__product__tenant=self.tenant,
            quantity__lte=threshold,
            track_quantity=True,
        ).select_related("variant__product")
        return [
            {
                "sku":       inv.variant.sku,
                "product":   inv.variant.product.name,
                "stock":     inv.quantity,
                "reserved":  inv.reserved_quantity,
                "available": inv.available_quantity,
                "alert":     "critical" if inv.quantity == 0 else "low",
            }
            for inv in items
        ]

    def get_full_inventory_export(self) -> list:
        from api.marketplace.models import ProductInventory
        items = ProductInventory.objects.filter(
            variant__product__seller=self.seller,
            variant__product__tenant=self.tenant,
        ).select_related("variant__product","variant")
        return [
            {
                "sku":           inv.variant.sku,
                "product":       inv.variant.product.name,
                "variant":       inv.variant.name,
                "quantity":      inv.quantity,
                "reserved":      inv.reserved_quantity,
                "available":     inv.available_quantity,
                "warehouse":     inv.warehouse_location,
                "last_restocked":inv.last_restocked_at.isoformat() if inv.last_restocked_at else "",
            }
            for inv in items
        ]

    @transaction.atomic
    def _update_stock(self, sku: str, quantity: int):
        from api.marketplace.models import ProductVariant
        variant = ProductVariant.objects.select_related("inventory").get(
            sku=sku, product__seller=self.seller, tenant=self.tenant
        )
        variant.inventory.quantity = max(0, quantity)
        variant.inventory.last_restocked_at = timezone.now()
        variant.inventory.save(update_fields=["quantity","last_restocked_at"])
