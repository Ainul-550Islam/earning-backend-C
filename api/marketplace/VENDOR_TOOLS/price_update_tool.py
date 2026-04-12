"""
VENDOR_TOOLS/price_update_tool.py — Bulk Price Update Tool
"""
import csv, io, logging
from decimal import Decimal, InvalidOperation
from django.db import transaction

logger = logging.getLogger(__name__)


class PriceUpdateService:

    def __init__(self, seller, tenant):
        self.seller = seller
        self.tenant = tenant

    def update_from_csv(self, file_content: bytes) -> dict:
        """CSV columns: sku, base_price, sale_price (optional)"""
        result = {"updated": 0, "skipped": 0, "errors": []}
        reader = csv.DictReader(io.StringIO(file_content.decode("utf-8-sig", errors="replace")))
        for i, row in enumerate(reader, 2):
            sku = (row.get("sku") or "").strip()
            base_raw = (row.get("base_price") or "").strip()
            sale_raw = (row.get("sale_price") or "").strip()
            if not sku or not base_raw:
                result["skipped"] += 1
                continue
            try:
                base = Decimal(base_raw.replace(",",""))
                sale = Decimal(sale_raw.replace(",","")) if sale_raw else None
                self._update_price(sku, base, sale)
                result["updated"] += 1
            except Exception as e:
                result["errors"].append({"row": i, "sku": sku, "error": str(e)})
        return result

    def bulk_discount(self, product_ids: list, percent: Decimal) -> dict:
        """Apply X% discount to multiple products."""
        from api.marketplace.models import Product
        updated = 0
        for product in Product.objects.filter(pk__in=product_ids, seller=self.seller, tenant=self.tenant):
            discount = product.base_price * percent / 100
            product.sale_price = (product.base_price - discount).quantize(Decimal("0.01"))
            product.save(update_fields=["sale_price"])
            updated += 1
        return {"updated": updated, "discount_percent": str(percent)}

    def remove_all_discounts(self) -> int:
        from api.marketplace.models import Product
        count = Product.objects.filter(
            seller=self.seller, tenant=self.tenant, sale_price__isnull=False
        ).update(sale_price=None)
        return count

    def price_update_preview(self, product_ids: list, new_percent: Decimal) -> list:
        """Preview what prices will look like before applying."""
        from api.marketplace.models import Product
        result = []
        for p in Product.objects.filter(pk__in=product_ids, seller=self.seller):
            new_sale = (p.base_price * (1 - new_percent / 100)).quantize(Decimal("0.01"))
            result.append({
                "product_id":  p.pk,
                "name":        p.name,
                "current_price": str(p.effective_price),
                "new_price":   str(new_sale),
                "savings":     str(p.base_price - new_sale),
            })
        return result

    @transaction.atomic
    def _update_price(self, sku: str, base: Decimal, sale=None):
        from api.marketplace.models import ProductVariant
        v = ProductVariant.objects.select_related("product").get(
            sku=sku, product__seller=self.seller, tenant=self.tenant
        )
        v.product.base_price = base
        v.product.sale_price = sale
        v.product.save(update_fields=["base_price","sale_price"])
